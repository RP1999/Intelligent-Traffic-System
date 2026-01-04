"""
Driver API Router - Protected endpoints for driver mobile app
Requires JWT authentication with driver role.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
import aiosqlite

from app.config import get_settings
from app.routers.auth import get_current_driver, UserInfo, decode_token

settings = get_settings()
router = APIRouter(prefix="/driver", tags=["Driver App"])

# Database path
DB_PATH = settings.data_dir.parent / "backend" / "traffic.db"


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class DriverProfile(BaseModel):
    user_id: int
    phone: str
    name: Optional[str]
    plate_number: str
    current_score: int
    risk_level: str
    total_violations: int
    total_fines: float
    member_since: str


class ViolationRecord(BaseModel):
    violation_id: str
    violation_type: str
    timestamp: str
    location: Optional[str]
    fine_amount: float
    points_deducted: int
    status: str
    evidence_path: Optional[str]


class FineRecord(BaseModel):
    fine_id: int
    violation_type: str
    amount: float
    issued_date: str
    due_date: Optional[str]
    status: str  # 'unpaid', 'paid', 'overdue'
    breakdown: Optional[dict]


class NotificationRecord(BaseModel):
    notification_id: int
    title: str
    message: str
    notification_type: str  # 'warning', 'violation', 'info'
    timestamp: str
    read: bool


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_risk_level(score: int) -> str:
    """Get risk level string from score."""
    if score >= 90:
        return "excellent"
    elif score >= 70:
        return "good"
    elif score >= 50:
        return "fair"
    elif score >= 30:
        return "poor"
    else:
        return "critical"


async def get_plate_from_token(user: UserInfo) -> str:
    """Extract plate number from user token data."""
    # The plate number should be stored in a driver_users table lookup
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT plate_number FROM driver_users WHERE id = ?",
            (user.user_id,)
        )
        result = await cursor.fetchone()
        if result:
            return result["plate_number"]
    return ""


# =============================================================================
# DRIVER PROFILE ENDPOINTS
# =============================================================================

@router.get("/me", response_model=DriverProfile, summary="Get driver profile")
async def get_driver_profile(user: UserInfo = Depends(get_current_driver)):
    """
    Get the current driver's profile including:
    - Personal details
    - Current safety score
    - Total violations and fines
    """
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        
        # Get driver user details
        cursor = await db.execute(
            """SELECT id, phone, name, plate_number, created_at 
               FROM driver_users WHERE id = ?""",
            (user.user_id,)
        )
        driver_user = await cursor.fetchone()
        
        if not driver_user:
            raise HTTPException(status_code=404, detail="Driver profile not found")
        
        plate_number = driver_user["plate_number"]
        
        # Get score from drivers table
        cursor = await db.execute(
            """SELECT current_score, total_violations, total_fines 
               FROM drivers WHERE driver_id = ?""",
            (plate_number,)
        )
        driver_score = await cursor.fetchone()
        
        current_score = driver_score["current_score"] if driver_score else 100
        total_violations = driver_score["total_violations"] if driver_score else 0
        total_fines = driver_score["total_fines"] if driver_score else 0.0
        
        return DriverProfile(
            user_id=driver_user["id"],
            phone=driver_user["phone"],
            name=driver_user["name"],
            plate_number=plate_number,
            current_score=current_score,
            risk_level=get_risk_level(current_score),
            total_violations=total_violations,
            total_fines=total_fines,
            member_since=driver_user["created_at"] or datetime.now().isoformat(),
        )


@router.get("/my-violations", summary="Get driver's violation history")
async def get_my_violations(
    user: UserInfo = Depends(get_current_driver),
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
):
    """
    Get list of violations for the logged-in driver.
    Filtered by the driver's plate number.
    """
    plate_number = await get_plate_from_token(user)
    
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        
        # Query violations for this plate
        cursor = await db.execute(
            """SELECT violation_id, violation_type, timestamp, location,
                      fine_amount, points_deducted, snapshot_path, notes
               FROM violations 
               WHERE driver_id = ? OR license_plate = ?
               ORDER BY timestamp DESC
               LIMIT ? OFFSET ?""",
            (plate_number, plate_number, limit, offset)
        )
        violations = await cursor.fetchall()
        
        # Get total count
        cursor = await db.execute(
            """SELECT COUNT(*) as count FROM violations 
               WHERE driver_id = ? OR license_plate = ?""",
            (plate_number, plate_number)
        )
        total = (await cursor.fetchone())["count"]
        
        return {
            "violations": [
                {
                    "violation_id": v["violation_id"],
                    "violation_type": v["violation_type"],
                    "timestamp": v["timestamp"],
                    "location": v["location"],
                    "fine_amount": v["fine_amount"],
                    "points_deducted": v["points_deducted"],
                    "evidence_path": v["snapshot_path"],
                    "notes": v["notes"],
                    "status": "recorded",
                }
                for v in violations
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }


@router.get("/my-fines", summary="Get driver's unpaid fines")
async def get_my_fines(
    user: UserInfo = Depends(get_current_driver),
    status_filter: Optional[str] = Query(default=None, description="Filter by: unpaid, paid, all"),
):
    """
    Get list of fines for the logged-in driver.
    Default shows unpaid fines only.
    """
    plate_number = await get_plate_from_token(user)
    
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        
        # Check if dynamic_fines table exists
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='dynamic_fines'"
        )
        table_exists = await cursor.fetchone()
        
        fines = []
        
        if table_exists:
            # Query from dynamic_fines table
            query = """SELECT id, zone_type, total_fine, base_penalty, 
                              duration_penalty, impact_penalty, created_at
                       FROM dynamic_fines 
                       WHERE plate_number = ?
                       ORDER BY created_at DESC"""
            cursor = await db.execute(query, (plate_number,))
            fine_records = await cursor.fetchall()
            
            for f in fine_records:
                fines.append({
                    "fine_id": f["id"],
                    "violation_type": f["zone_type"],
                    "amount": f["total_fine"],
                    "issued_date": f["created_at"],
                    "due_date": None,
                    "status": "unpaid",  # TODO: Add payment tracking
                    "breakdown": {
                        "base": f["base_penalty"],
                        "duration": f["duration_penalty"],
                        "impact": f["impact_penalty"],
                    }
                })
        
        # Also get fines from violations table
        cursor = await db.execute(
            """SELECT violation_id, violation_type, fine_amount, timestamp
               FROM violations 
               WHERE (driver_id = ? OR license_plate = ?) AND fine_amount > 0
               ORDER BY timestamp DESC""",
            (plate_number, plate_number)
        )
        violation_fines = await cursor.fetchall()
        
        for v in violation_fines:
            fines.append({
                "fine_id": hash(v["violation_id"]) % 10000,
                "violation_type": v["violation_type"],
                "amount": v["fine_amount"],
                "issued_date": v["timestamp"],
                "due_date": None,
                "status": "unpaid",
                "breakdown": None,
            })
        
        # Calculate totals
        total_unpaid = sum(f["amount"] for f in fines if f["status"] == "unpaid")
        
        return {
            "fines": fines,
            "total_count": len(fines),
            "total_unpaid_amount": total_unpaid,
            "currency": "LKR",
        }


@router.get("/notifications", summary="Get driver notifications")
async def get_notifications(
    user: UserInfo = Depends(get_current_driver),
    unread_only: bool = Query(default=False),
    limit: int = Query(default=20, le=50),
):
    """
    Get personal notifications/alerts for the driver.
    Includes warnings, violation notices, and system messages.
    """
    plate_number = await get_plate_from_token(user)
    
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        
        # Check if notifications table exists
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='driver_notifications'"
        )
        table_exists = await cursor.fetchone()
        
        notifications = []
        
        if table_exists:
            query = """SELECT id, title, message, notification_type, timestamp, read
                       FROM driver_notifications
                       WHERE plate_number = ?"""
            if unread_only:
                query += " AND read = 0"
            query += " ORDER BY timestamp DESC LIMIT ?"
            
            cursor = await db.execute(query, (plate_number, limit))
            notif_records = await cursor.fetchall()
            
            for n in notif_records:
                notifications.append({
                    "notification_id": n["id"],
                    "title": n["title"],
                    "message": n["message"],
                    "notification_type": n["notification_type"],
                    "timestamp": n["timestamp"],
                    "read": bool(n["read"]),
                })
        
        # Generate notifications from recent violations
        cursor = await db.execute(
            """SELECT violation_type, timestamp, fine_amount
               FROM violations 
               WHERE (driver_id = ? OR license_plate = ?)
               ORDER BY timestamp DESC LIMIT 10""",
            (plate_number, plate_number)
        )
        recent_violations = await cursor.fetchall()
        
        for v in recent_violations:
            notifications.append({
                "notification_id": hash(f"{v['timestamp']}{v['violation_type']}") % 100000,
                "title": f"{v['violation_type'].replace('_', ' ').title()} Recorded",
                "message": f"A {v['violation_type']} violation was recorded. Fine: LKR {v['fine_amount']:.2f}",
                "notification_type": "violation",
                "timestamp": v["timestamp"],
                "read": False,
            })
        
        # Sort by timestamp and limit
        notifications.sort(key=lambda x: x["timestamp"], reverse=True)
        notifications = notifications[:limit]
        
        return {
            "notifications": notifications,
            "unread_count": sum(1 for n in notifications if not n["read"]),
            "total_count": len(notifications),
        }


@router.post("/notifications/{notification_id}/read", summary="Mark notification as read")
async def mark_notification_read(
    notification_id: int,
    user: UserInfo = Depends(get_current_driver),
):
    """Mark a specific notification as read."""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute(
            "UPDATE driver_notifications SET read = 1 WHERE id = ?",
            (notification_id,)
        )
        await db.commit()
    
    return {"status": "marked_read", "notification_id": notification_id}


@router.get("/score-history", summary="Get driver's score history")
async def get_score_history(
    user: UserInfo = Depends(get_current_driver),
    days: int = Query(default=30, le=90),
):
    """
    Get driver's safety score history over time.
    Shows how score has changed with each violation.
    """
    plate_number = await get_plate_from_token(user)
    
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        
        # Get violations with points to calculate historical scores
        cursor = await db.execute(
            """SELECT timestamp, points_deducted, violation_type
               FROM violations 
               WHERE (driver_id = ? OR license_plate = ?)
               ORDER BY timestamp ASC""",
            (plate_number, plate_number)
        )
        violations = await cursor.fetchall()
        
        # Build score history
        score_history = []
        current_score = 100
        
        for v in violations:
            current_score = max(0, current_score - v["points_deducted"])
            score_history.append({
                "timestamp": v["timestamp"],
                "score": current_score,
                "change": -v["points_deducted"],
                "reason": v["violation_type"],
            })
        
        # Get current score
        cursor = await db.execute(
            "SELECT current_score FROM drivers WHERE driver_id = ?",
            (plate_number,)
        )
        driver = await cursor.fetchone()
        final_score = driver["current_score"] if driver else current_score
        
        return {
            "current_score": final_score,
            "history": score_history[-50:],  # Last 50 entries
            "trend": "stable" if len(score_history) < 2 else (
                "improving" if score_history[-1]["score"] > score_history[0]["score"] else "declining"
            ),
        }
