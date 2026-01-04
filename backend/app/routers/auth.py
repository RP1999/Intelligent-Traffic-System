"""
Authentication Router - JWT-based Auth for Drivers and Admins
Provides login/register endpoints and token-based authentication.
"""

import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import aiosqlite

# Password hashing
try:
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
except ImportError:
    # Fallback to hashlib if passlib not available
    import hashlib
    pwd_context = None

# JWT tokens
try:
    from jose import JWTError, jwt
except ImportError:
    jwt = None
    JWTError = Exception

from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["Authentication"])

# Security
security = HTTPBearer(auto_error=False)

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "intelligent-traffic-management-secret-key-2025")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

# Database path
DB_PATH = settings.data_dir.parent / "backend" / "traffic.db"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class DriverRegister(BaseModel):
    phone: str
    password: str
    plate_number: str
    name: Optional[str] = None
    license_number: Optional[str] = None
    
    @classmethod
    def validate_phone(cls, v):
        if len(v) < 10:
            raise ValueError('Phone number must be at least 10 characters')
        return v
    
    @classmethod
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters')
        return v


class DriverLogin(BaseModel):
    phone: str
    password: str


class AdminLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_type: str
    expires_in: int = ACCESS_TOKEN_EXPIRE_HOURS * 3600


class UserInfo(BaseModel):
    user_id: int
    user_type: str  # 'driver' or 'admin'
    identifier: str  # phone for driver, username for admin


# =============================================================================
# PASSWORD UTILITIES
# =============================================================================

def hash_password(password: str) -> str:
    """Hash a password using bcrypt or fallback to sha256."""
    if pwd_context:
        return pwd_context.hash(password)
    else:
        import hashlib
        return hashlib.sha256(password.encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    if pwd_context:
        return pwd_context.verify(plain_password, hashed_password)
    else:
        import hashlib
        return hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password


# =============================================================================
# JWT UTILITIES
# =============================================================================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS))
    to_encode.update({"exp": expire.isoformat()})
    
    if jwt:
        # python-jose handles datetime, but we pass isoformat for consistency
        to_encode["exp"] = expire
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    else:
        # Fallback: simple base64 encoding (NOT SECURE - for demo only)
        import base64
        import json
        return base64.b64encode(json.dumps(to_encode).encode()).decode()


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token."""
    try:
        if jwt:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        else:
            # Fallback decoding
            import base64
            import json
            payload = json.loads(base64.b64decode(token.encode()).decode())
            if datetime.fromisoformat(payload.get("exp", "2000-01-01")) < datetime.utcnow():
                return None
            return payload
    except Exception:
        return None


# =============================================================================
# AUTHENTICATION DEPENDENCY
# =============================================================================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> UserInfo:
    """
    Dependency to get the current authenticated user from JWT token.
    Use this to protect routes.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    payload = decode_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return UserInfo(
        user_id=payload.get("user_id", 0),
        user_type=payload.get("user_type", "unknown"),
        identifier=payload.get("sub", ""),
    )


async def get_current_driver(user: UserInfo = Depends(get_current_user)) -> UserInfo:
    """Dependency to ensure current user is a driver."""
    if user.user_type != "driver":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Driver access required",
        )
    return user


async def get_current_admin(user: UserInfo = Depends(get_current_user)) -> UserInfo:
    """Dependency to ensure current user is an admin."""
    if user.user_type != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


# =============================================================================
# DATABASE HELPERS
# =============================================================================

async def get_db():
    """Get database connection."""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        yield db


async def ensure_tables_exist():
    """Ensure auth tables exist in database."""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        # Driver users table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS driver_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                plate_number TEXT,
                name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        """)
        
        # Admin users table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'admin',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        """)
        
        # Create default admin if not exists
        cursor = await db.execute("SELECT COUNT(*) FROM admin_users")
        count = (await cursor.fetchone())[0]
        if count == 0:
            default_password = hash_password("admin123")
            await db.execute(
                "INSERT INTO admin_users (username, password_hash, role) VALUES (?, ?, ?)",
                ("admin", default_password, "super_admin")
            )
            print("[AUTH] Created default admin user: admin / admin123")
        
        await db.commit()


# =============================================================================
# DRIVER AUTH ENDPOINTS
# =============================================================================

@router.post("/driver/register", response_model=Token, summary="Register a new driver")
async def register_driver(data: DriverRegister):
    """
    Register a new driver account.
    
    - Links to existing driver data if plate_number exists in drivers table
    - Returns JWT token on success
    """
    await ensure_tables_exist()
    
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        
        # Check if phone already registered
        cursor = await db.execute(
            "SELECT id FROM driver_users WHERE phone = ?",
            (data.phone,)
        )
        existing = await cursor.fetchone()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number already registered"
            )
        
        # Hash password and create user
        password_hash = hash_password(data.password)
        
        await db.execute(
            """INSERT INTO driver_users (phone, password_hash, plate_number, name, license_number)
               VALUES (?, ?, ?, ?, ?)""",
            (data.phone, password_hash, data.plate_number.upper(), data.name, data.license_number)
        )
        await db.commit()
        
        # Get the new user ID
        cursor = await db.execute(
            "SELECT id FROM driver_users WHERE phone = ?",
            (data.phone,)
        )
        user = await cursor.fetchone()
        user_id = user["id"]
        
        # Check if plate exists in drivers table and link
        cursor = await db.execute(
            "SELECT driver_id FROM drivers WHERE driver_id = ?",
            (data.plate_number.upper(),)
        )
        existing_driver = await cursor.fetchone()
        
        if not existing_driver:
            # Create entry in drivers table
            await db.execute(
                """INSERT OR IGNORE INTO drivers (driver_id, current_score, total_violations, total_fines)
                   VALUES (?, 100, 0, 0)""",
                (data.plate_number.upper(),)
            )
            await db.commit()
    
    # Create token
    token = create_access_token({
        "sub": data.phone,
        "user_id": user_id,
        "user_type": "driver",
        "plate_number": data.plate_number.upper(),
    })
    
    return Token(access_token=token, user_type="driver")


@router.post("/driver/login", response_model=Token, summary="Driver login")
async def login_driver(data: DriverLogin):
    """
    Login as a driver using phone and password.
    Returns JWT token on success.
    """
    await ensure_tables_exist()
    
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        
        cursor = await db.execute(
            "SELECT id, password_hash, plate_number FROM driver_users WHERE phone = ?",
            (data.phone,)
        )
        user = await cursor.fetchone()
        
        if not user or not verify_password(data.password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid phone or password"
            )
        
        # Update last login
        await db.execute(
            "UPDATE driver_users SET last_login = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), user["id"])
        )
        await db.commit()
    
    # Create token
    token = create_access_token({
        "sub": data.phone,
        "user_id": user["id"],
        "user_type": "driver",
        "plate_number": user["plate_number"],
    })
    
    return Token(access_token=token, user_type="driver")


# =============================================================================
# ADMIN AUTH ENDPOINTS
# =============================================================================

@router.post("/admin/login", response_model=Token, summary="Admin login")
async def login_admin(data: AdminLogin):
    """
    Login as an admin using username and password.
    Returns JWT token on success.
    """
    await ensure_tables_exist()
    
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        
        cursor = await db.execute(
            "SELECT id, password_hash, role FROM admin_users WHERE username = ?",
            (data.username,)
        )
        user = await cursor.fetchone()
        
        if not user or not verify_password(data.password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )
        
        # Update last login
        await db.execute(
            "UPDATE admin_users SET last_login = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), user["id"])
        )
        await db.commit()
    
    # Create token
    token = create_access_token({
        "sub": data.username,
        "user_id": user["id"],
        "user_type": "admin",
        "role": user["role"],
    })
    
    return Token(access_token=token, user_type="admin")


# =============================================================================
# TOKEN VALIDATION ENDPOINT
# =============================================================================

@router.get("/me", summary="Get current user info")
async def get_me(user: UserInfo = Depends(get_current_user)):
    """
    Get information about the currently authenticated user.
    Validates the token and returns user details.
    """
    return {
        "user_id": user.user_id,
        "user_type": user.user_type,
        "identifier": user.identifier,
        "authenticated": True,
    }
