"""
Authentication Router - JWT-based Auth for Drivers and Admins
Provides login/register endpoints and token-based authentication.
"""

import os
import re
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, field_validator

from app.db.firestore_client import get_db, Collections

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


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class DriverRegister(BaseModel):
    phone: str
    password: str
    plate_number: str
    name: Optional[str] = None
    license_number: Optional[str] = None

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('Phone number is required')
        if len(v) < 10:
            raise ValueError('Phone number must be at least 10 digits')
        if not re.match(r'^[\+]?[0-9\s\-]{10,15}$', v):
            raise ValueError('Invalid phone number format')
        return v

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters')
        if len(v) > 128:
            raise ValueError('Password must be at most 128 characters')
        if v.strip() != v:
            raise ValueError('Password must not start or end with spaces')
        return v

    @field_validator('plate_number')
    @classmethod
    def validate_plate_number(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError('Vehicle plate number is required')
        if len(v) < 3 or len(v) > 20:
            raise ValueError('Plate number must be 3-20 characters')
        return v

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if v and len(v) < 2:
                raise ValueError('Name must be at least 2 characters')
            if len(v) > 100:
                raise ValueError('Name must be at most 100 characters')
            return v if v else None
        return None

    @field_validator('license_number')
    @classmethod
    def validate_license_number(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip().upper()
            if v and len(v) < 3:
                raise ValueError('License number must be at least 3 characters')
            if len(v) > 20:
                raise ValueError('License number must be at most 20 characters')
            return v if v else None
        return None


class DriverLogin(BaseModel):
    phone: str
    password: str

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('Phone number is required')
        return v

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not v:
            raise ValueError('Password is required')
        return v


class AdminLogin(BaseModel):
    username: str
    password: str

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('Username is required')
        return v

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not v:
            raise ValueError('Password is required')
        return v


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_type: str
    expires_in: int = ACCESS_TOKEN_EXPIRE_HOURS * 3600


class UserInfo(BaseModel):
    user_id: str
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
    """Verify a password against its hash (supports bcrypt and sha256 fallback)."""
    # Detect hash format: bcrypt hashes start with '$2b$' or '$2a$'
    if hashed_password.startswith(('$2b$', '$2a$', '$2y$')):
        if pwd_context:
            return pwd_context.verify(plain_password, hashed_password)
        return False
    else:
        # SHA-256 fallback hash
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
# DATABASE HELPERS (Firestore)
# =============================================================================

async def ensure_tables_exist():
    """Seed default admin user if none exists in Firestore."""
    db = get_db()
    # Check if any admin exists
    admins = db.collection(Collections.ADMIN_USERS)
    first = None
    async for doc in admins.limit(1).stream():
        first = doc
    if first is None:
        default_password = hash_password("admin123")
        await admins.document("admin").set({
            "username": "admin",
            "password_hash": default_password,
            "role": "super_admin",
            "created_at": datetime.utcnow().isoformat(),
            "last_login": None,
        })
        print("[AUTH] Created default admin user: admin / admin123")


# =============================================================================
# DRIVER AUTH ENDPOINTS
# =============================================================================

@router.post("/driver/register", summary="Register a new driver")
async def register_driver(data: DriverRegister):
    """
    Register a new driver account.
    - Links to existing driver data if plate_number exists in drivers table
    - Returns JWT token on success
    """
    await ensure_tables_exist()
    db = get_db()

    # ---- Uniqueness checks: phone, plate_number, license_number ----
    from google.cloud.firestore_v1 import FieldFilter

    # 1. Check phone uniqueness
    phone_query = (
        db.collection(Collections.DRIVER_USERS)
        .where(filter=FieldFilter("phone", "==", data.phone))
        .limit(1)
    )
    async for doc in phone_query.stream():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number already registered"
        )

    # 2. Check plate_number uniqueness
    plate = data.plate_number.upper()
    
    # Also store a normalized version (no spaces/hyphens) for matching
    from app.utils.plate_utils import normalize_plate
    plate_normalized = normalize_plate(plate)
    
    plate_query = (
        db.collection(Collections.DRIVER_USERS)
        .where(filter=FieldFilter("plate_number", "==", plate))
        .limit(1)
    )
    async for doc in plate_query.stream():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vehicle plate number already registered"
        )
    
    # Also check by normalized plate to prevent duplicates like "WP ABC 1234" and "WPABC1234"
    norm_query = (
        db.collection(Collections.DRIVER_USERS)
        .where(filter=FieldFilter("plate_number_normalized", "==", plate_normalized))
        .limit(1)
    )
    async for doc in norm_query.stream():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vehicle plate number already registered (normalized match)"
        )

    # 3. Check license_number uniqueness (if provided)
    if data.license_number:
        lic = data.license_number.upper()
        lic_query = (
            db.collection(Collections.DRIVER_USERS)
            .where(filter=FieldFilter("license_number", "==", lic))
            .limit(1)
        )
        async for doc in lic_query.stream():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="License number already registered"
            )

    # Hash password and create user
    password_hash = hash_password(data.password)

    # Use phone as doc id (unique)
    user_doc_ref = db.collection(Collections.DRIVER_USERS).document()
    user_id = user_doc_ref.id  # auto-generated Firestore ID
    await user_doc_ref.set({
        "phone": data.phone,
        "password_hash": password_hash,
        "plate_number": plate,
        "plate_number_normalized": plate_normalized,
        "name": data.name,
        "license_number": data.license_number,
        "created_at": datetime.utcnow().isoformat(),
        "last_login": None,
    })

    # Ensure drivers collection entry exists
    driver_ref = db.collection(Collections.DRIVERS).document(plate_normalized)
    driver_doc = await driver_ref.get()
    if not driver_doc.exists:
        await driver_ref.set({
            "driver_id": plate_normalized,
            "plate_number_display": plate,
            "current_score": 100,
            "total_violations": 0,
            "total_fines": 0,
        })

    # Create token
    token = create_access_token({
        "sub": data.phone,
        "user_id": user_id,
        "user_type": "driver",
        "plate_number": plate,
    })

    return {
        "access_token": token,
        "token_type": "bearer",
        "user_type": "driver",
        "expires_in": ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        "name": data.name,
        "plate_number": plate,
        "license_number": data.license_number,
    }


@router.post("/driver/login", summary="Driver login")
async def login_driver(data: DriverLogin):
    """
    Login as a driver using phone and password.
    Returns JWT token on success.
    """
    await ensure_tables_exist()
    db = get_db()

    from google.cloud.firestore_v1 import FieldFilter
    query = (
        db.collection(Collections.DRIVER_USERS)
        .where(filter=FieldFilter("phone", "==", data.phone))
        .limit(1)
    )
    user_doc = None
    user_id = None
    async for doc in query.stream():
        user_doc = doc.to_dict()
        user_id = doc.id

    if not user_doc or not verify_password(data.password, user_doc["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid phone or password"
        )

    # Update last login
    await db.collection(Collections.DRIVER_USERS).document(user_id).update({
        "last_login": datetime.utcnow().isoformat(),
    })

    # Create token
    token = create_access_token({
        "sub": data.phone,
        "user_id": user_id,
        "user_type": "driver",
        "plate_number": user_doc.get("plate_number", ""),
    })

    return {
        "access_token": token,
        "token_type": "bearer",
        "user_type": "driver",
        "expires_in": ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        "name": user_doc.get("name"),
        "plate_number": user_doc.get("plate_number", ""),
        "license_number": user_doc.get("license_number"),
    }


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
    db = get_db()

    from google.cloud.firestore_v1 import FieldFilter
    query = (
        db.collection(Collections.ADMIN_USERS)
        .where(filter=FieldFilter("username", "==", data.username))
        .limit(1)
    )
    user_doc = None
    user_id = None
    async for doc in query.stream():
        user_doc = doc.to_dict()
        user_id = doc.id

    if not user_doc or not verify_password(data.password, user_doc["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    # Update last login
    await db.collection(Collections.ADMIN_USERS).document(user_id).update({
        "last_login": datetime.utcnow().isoformat(),
    })

    # Create token
    token = create_access_token({
        "sub": data.username,
        "user_id": user_id,
        "user_type": "admin",
        "role": user_doc.get("role", "admin"),
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
