"""
Driver API Router - Protected endpoints for driver mobile app
Requires JWT authentication with driver role.
"""

from datetime import datetime
from typing import List, Optional
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from google.cloud.firestore_v1 import FieldFilter

from app.config import get_settings
from app.db.firestore_client import get_db, Collections
from app.routers.auth import get_current_driver, UserInfo, decode_token

settings = get_settings()
router = APIRouter(prefix="/driver", tags=["Driver App"])


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class DriverProfile(BaseModel):
    user_id: str
    phone: str
    name: Optional[str]
    plate_number: str
    license_number: Optional[str] = None
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


class FcmTokenRequest(BaseModel):
    fcm_token: str
    platform: str = "android"  # 'android' or 'ios'


class ProfileUpdate(BaseModel):
    """Request model for updating driver profile."""
    name: Optional[str] = None
    phone: Optional[str] = None

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

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if v and not re.match(r'^[\+]?[0-9\s\-]{10,15}$', v):
                raise ValueError('Invalid phone number format')
            return v if v else None
        return None


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
    db = get_db()
    doc = await db.collection(Collections.DRIVER_USERS).document(str(user.user_id)).get()
    if doc.exists:
        return doc.to_dict().get("plate_number", "")
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
    db = get_db()

    # Get driver user details
    doc = await db.collection(Collections.DRIVER_USERS).document(str(user.user_id)).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Driver profile not found")

    driver_user = doc.to_dict()
    plate_number = driver_user.get("plate_number", "")
    
    # Get normalized plate for matching violations
    from app.utils.plate_utils import normalize_plate
    plate_norm = normalize_plate(plate_number) if plate_number else ""

    # Calculate score directly from violations for accuracy
    total_violations = 0
    pending_fines = 0.0  # Only unpaid fines
    total_points_deducted = 0
    
    seen_ids = set()
    # Search by original plate, normalized plate, and license_plate field
    search_values = set(filter(None, [plate_number, plate_norm]))
    for plate_val in search_values:
        for field_name in ("driver_id", "license_plate"):
            q = db.collection(Collections.VIOLATIONS).where(
                filter=FieldFilter(field_name, "==", plate_val)
            )
            async for doc in q.stream():
                if doc.id not in seen_ids:
                    seen_ids.add(doc.id)
                    v = doc.to_dict()
                    total_violations += 1
                    total_points_deducted += v.get("points_deducted", 0) or 0
                    # Only count unpaid fines for pending amount
                    status = (v.get("status") or "").lower()
                    if status in ("pending", "unpaid", ""):
                        pending_fines += v.get("fine_amount", 0) or 0
    
    current_score = max(0, 100 - total_points_deducted)

    return DriverProfile(
        user_id=doc.id,
        phone=driver_user.get("phone", ""),
        name=driver_user.get("name"),
        plate_number=plate_number,
        license_number=driver_user.get("license_number"),
        current_score=current_score,
        risk_level=get_risk_level(current_score),
        total_violations=total_violations,
        total_fines=pending_fines,  # Return pending fines as total_fines for UI
        member_since=driver_user.get("created_at") or datetime.now().isoformat(),
    )


@router.put("/me", response_model=DriverProfile, summary="Update driver profile")
async def update_driver_profile(
    data: ProfileUpdate,
    user: UserInfo = Depends(get_current_driver),
):
    """
    Update the current driver's profile.
    Currently supports updating: name, phone.
    """
    db = get_db()

    doc = await db.collection(Collections.DRIVER_USERS).document(str(user.user_id)).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Driver profile not found")

    update_fields = {}

    if data.name is not None:
        update_fields["name"] = data.name

    if data.phone is not None and data.phone != doc.to_dict().get("phone"):
        # Check phone uniqueness
        phone_query = (
            db.collection(Collections.DRIVER_USERS)
            .where(filter=FieldFilter("phone", "==", data.phone))
            .limit(1)
        )
        async for existing in phone_query.stream():
            if existing.id != str(user.user_id):
                raise HTTPException(
                    status_code=400,
                    detail="Phone number already in use by another account"
                )
        update_fields["phone"] = data.phone

    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    update_fields["updated_at"] = datetime.utcnow().isoformat()
    await db.collection(Collections.DRIVER_USERS).document(str(user.user_id)).update(update_fields)

    # Return updated profile
    return await get_driver_profile(user)


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
    db = get_db()

    # Query violations where driver_id or license_plate matches
    # Note: Sorting in Python to avoid composite index requirements
    all_violations = []
    seen_ids = set()
    
    # Query by driver_id
    q1 = db.collection(Collections.VIOLATIONS).where(
        filter=FieldFilter("driver_id", "==", plate_number)
    )
    async for doc in q1.stream():
        d = doc.to_dict()
        d["_id"] = doc.id
        all_violations.append(d)
        seen_ids.add(doc.id)

    # Query by license_plate (avoid duplicates)
    q2 = db.collection(Collections.VIOLATIONS).where(
        filter=FieldFilter("license_plate", "==", plate_number)
    )
    async for doc in q2.stream():
        if doc.id not in seen_ids:
            d = doc.to_dict()
            d["_id"] = doc.id
            all_violations.append(d)

    # Sort combined results by timestamp desc
    all_violations.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    total = len(all_violations)
    page = all_violations[offset: offset + limit]

    return {
        "violations": [
            {
                "violation_id": v.get("violation_id", v["_id"]),
                "violation_type": v.get("violation_type", ""),
                "timestamp": v.get("timestamp", ""),
                "location": v.get("location"),
                "fine_amount": v.get("fine_amount", 0),
                "points_deducted": v.get("points_deducted", 0),
                "evidence_path": v.get("evidence_path") or v.get("snapshot_path"),
                "notes": v.get("notes"),
                "status": "recorded",
            }
            for v in page
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
    db = get_db()

    fines = []

    # Query from dynamic_fines collection (sort in Python to avoid composite index)
    fine_docs = []
    q = db.collection(Collections.DYNAMIC_FINES).where(
        filter=FieldFilter("plate_number", "==", plate_number)
    )
    async for doc in q.stream():
        fine_docs.append((doc.id, doc.to_dict()))
    fine_docs.sort(key=lambda x: x[1].get("created_at", ""), reverse=True)

    for doc_id, f in fine_docs:
        fine_status = f.get("status", "unpaid")
        fines.append({
            "fine_id": doc_id,
            "violation_type": f.get("zone_type", ""),
            "amount": f.get("total_fine", 0),
            "issued_date": f.get("created_at", ""),
            "due_date": None,
            "status": fine_status,
            "breakdown": {
                "base": f.get("base_penalty", 0),
                "duration": f.get("duration_penalty", 0),
                "impact": f.get("impact_penalty", 0),
            },
        })

    # Also get fines from violations collection (sort in Python)
    vio_fines = []
    seen_vio_ids = set()
    for field_name in ("driver_id", "license_plate"):
        q2 = db.collection(Collections.VIOLATIONS).where(
            filter=FieldFilter(field_name, "==", plate_number)
        )
        async for doc in q2.stream():
            if doc.id not in seen_vio_ids:
                vio_fines.append((doc.id, doc.to_dict()))
                seen_vio_ids.add(doc.id)
    vio_fines.sort(key=lambda x: x[1].get("timestamp", ""), reverse=True)

    for doc_id, v in vio_fines:
        if v.get("fine_amount", 0) > 0:
            # Use actual document ID for payment to work
            fine_status = v.get("status", "pending")
            # Map violation status to fine status
            if fine_status == "paid":
                mapped_status = "paid"
            else:
                mapped_status = "unpaid"
            
            # Build breakdown from stored fine_breakdown if available
            fb = v.get("fine_breakdown")
            breakdown = None
            if fb:
                breakdown = {
                    "base": fb.get("base_penalty", 0),
                    "duration": fb.get("duration_penalty", 0),
                    "impact": fb.get("traffic_impact_penalty", 0),
                }
            
            fines.append({
                "fine_id": doc_id,  # Use real doc ID, not hash
                "violation_type": v.get("violation_type", ""),
                "amount": v.get("fine_amount", 0),
                "issued_date": v.get("timestamp", ""),
                "due_date": None,
                "status": mapped_status,
                "breakdown": breakdown,
            })

    # Apply status filter
    if status_filter and status_filter != "all":
        fines = [f for f in fines if f["status"] == status_filter]

    total_unpaid = sum(f["amount"] for f in fines if f["status"] == "unpaid")

    return {
        "fines": fines,
        "total_count": len(fines),
        "total_unpaid_amount": total_unpaid,
        "currency": "LKR",
    }


@router.post("/fines/{fine_id}/pay", summary="Pay a fine")
async def pay_fine(
    fine_id: str,
    user: UserInfo = Depends(get_current_driver),
):
    """
    Mark a fine/violation as paid.
    In production, this would integrate with a payment gateway.
    """
    plate_number = await get_plate_from_token(user)
    db = get_db()
    
    # Check if this is a violation ID or dynamic fine ID
    # Try violations collection first
    doc = await db.collection(Collections.VIOLATIONS).document(fine_id).get()
    if doc.exists:
        v = doc.to_dict()
        # Verify this violation belongs to the driver
        if v.get("driver_id") != plate_number and v.get("license_plate") != plate_number:
            raise HTTPException(status_code=403, detail="This fine does not belong to you")
        
        # Update status to paid
        await db.collection(Collections.VIOLATIONS).document(fine_id).update({
            "status": "paid",
            "paid_at": datetime.now().isoformat(),
        })
        
        return {
            "status": "success",
            "message": "Fine paid successfully",
            "fine_id": fine_id,
            "amount": v.get("fine_amount", 0),
        }
    
    # Try dynamic_fines collection
    doc = await db.collection(Collections.DYNAMIC_FINES).document(fine_id).get()
    if doc.exists:
        f = doc.to_dict()
        if f.get("plate_number") != plate_number:
            raise HTTPException(status_code=403, detail="This fine does not belong to you")
        
        await db.collection(Collections.DYNAMIC_FINES).document(fine_id).update({
            "status": "paid",
            "paid_at": datetime.now().isoformat(),
        })
        
        return {
            "status": "success",
            "message": "Fine paid successfully",
            "fine_id": fine_id,
            "amount": f.get("amount", 0),
        }
    
    raise HTTPException(status_code=404, detail="Fine not found")


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
    db = get_db()

    # Normalize plate to match how notifications are stored
    from app.utils.plate_utils import normalize_plate
    plate_norm = normalize_plate(plate_number) if plate_number else ""

    notifications = []

    # Query from driver_notifications collection (sort in Python to avoid composite index)
    # Search both normalized and raw plate to catch all notifications
    seen_ids = set()
    notif_docs = []
    for pv in dict.fromkeys([plate_norm, plate_number]):
        if not pv:
            continue
        q = db.collection(Collections.DRIVER_NOTIFICATIONS).where(
            filter=FieldFilter("plate_number", "==", pv)
        )
        if unread_only:
            q = q.where(filter=FieldFilter("read", "==", False))
        async for doc in q.stream():
            if doc.id not in seen_ids:
                seen_ids.add(doc.id)
                notif_docs.append((doc.id, doc.to_dict()))
    # Sort by timestamp descending and limit
    notif_docs.sort(key=lambda x: x[1].get("timestamp", ""), reverse=True)
    notif_docs = notif_docs[:limit]

    for doc_id, n in notif_docs:
        notifications.append({
            "notification_id": doc_id,
            "title": n.get("title", ""),
            "message": n.get("message", ""),
            "notification_type": n.get("notification_type", "info"),
            "timestamp": n.get("timestamp", ""),
            "read": bool(n.get("read", False)),
        })

    # Sort by timestamp desc and limit
    notifications.sort(key=lambda x: x["timestamp"], reverse=True)
    notifications = notifications[:limit]

    return {
        "notifications": notifications,
        "unread_count": sum(1 for n in notifications if not n["read"]),
        "total_count": len(notifications),
    }


@router.post("/notifications/{notification_id}/read", summary="Mark notification as read")
async def mark_notification_read(
    notification_id: str,
    user: UserInfo = Depends(get_current_driver),
):
    """Mark a specific notification as read."""
    db = get_db()
    
    # Check if notification exists first
    doc_ref = db.collection(Collections.DRIVER_NOTIFICATIONS).document(notification_id)
    doc = await doc_ref.get()
    
    if not doc.exists:
        # Check if this is an auto-generated violation notification (numeric hash ID)
        # These are ephemeral and don't have Firestore documents, so we succeed silently
        if notification_id.isdigit():
            return {"status": "marked_read", "notification_id": notification_id, "note": "ephemeral"}
        raise HTTPException(status_code=404, detail="Notification not found")
    
    # Verify the notification belongs to this user
    notif_data = doc.to_dict()
    plate_number = await get_plate_from_token(user)
    from app.utils.plate_utils import normalize_plate
    plate_norm = normalize_plate(plate_number) if plate_number else ""
    notif_driver = notif_data.get("driver_id") or notif_data.get("plate_number") or ""
    notif_driver_norm = normalize_plate(notif_driver) if notif_driver else ""
    if notif_driver_norm != plate_norm and notif_driver != plate_number:
        raise HTTPException(status_code=403, detail="Not authorized to access this notification")
    
    await doc_ref.update({"read": True})
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
    db = get_db()

    # Get violations with points to calculate historical scores
    violations = []
    for field_name in ("driver_id", "license_plate"):
        q = db.collection(Collections.VIOLATIONS).where(
            filter=FieldFilter(field_name, "==", plate_number)
        )
        async for doc in q.stream():
            d = doc.to_dict()
            d["_id"] = doc.id
            violations.append(d)

    # Deduplicate and sort by timestamp ascending
    seen = set()
    unique = []
    for v in violations:
        if v["_id"] not in seen:
            seen.add(v["_id"])
            unique.append(v)
    unique.sort(key=lambda x: x.get("timestamp", ""))

    # Build score history
    score_history = []
    current_score = 100
    for v in unique:
        pts = v.get("points_deducted", 0)
        current_score = max(0, current_score - pts)
        score_history.append({
            "timestamp": v.get("timestamp", ""),
            "score": current_score,
            "change": -pts,
            "reason": v.get("violation_type", ""),
        })

    # Get current score from drivers collection
    driver_doc = await db.collection(Collections.DRIVERS).document(plate_number).get()
    final_score = driver_doc.to_dict().get("current_score", current_score) if driver_doc.exists else current_score

    return {
        "current_score": final_score,
        "history": score_history[-50:],
        "trend": "stable" if len(score_history) < 2 else (
            "improving" if score_history[-1]["score"] > score_history[0]["score"] else "declining"
        ),
    }


# =============================================================================
# FCM TOKEN REGISTRATION
# =============================================================================

@router.post("/fcm-token", summary="Register FCM push token")
async def register_fcm_token(
    body: FcmTokenRequest,
    user: UserInfo = Depends(get_current_driver),
):
    """
    Register or update the driver's FCM push notification token.
    Called by the mobile app on startup and token refresh.
    """
    plate_number = await get_plate_from_token(user)
    if not plate_number:
        raise HTTPException(status_code=404, detail="Driver not found")

    from app.utils.plate_utils import normalize_plate
    plate_norm = normalize_plate(plate_number) or plate_number

    db = get_db()
    # Use NORMALIZED plate as document ID so token lookups from
    # scoring engine and behaviour service (which normalize first) always match.
    # Also store under the raw plate for backward compatibility.
    token_doc = {
        "plate_number": plate_number,
        "plate_number_normalized": plate_norm,
        "fcm_token": body.fcm_token,
        "platform": body.platform,
        "updated_at": datetime.now().isoformat(),
    }
    await db.collection(Collections.DRIVER_FCM_TOKENS).document(plate_norm).set(token_doc)
    # If raw plate differs, also write under the raw key so legacy lookups work
    if plate_norm != plate_number:
        await db.collection(Collections.DRIVER_FCM_TOKENS).document(plate_number).set(token_doc)

    return {"status": "ok", "message": "FCM token registered"}


@router.delete("/fcm-token", summary="Remove FCM push token")
async def remove_fcm_token(
    user: UserInfo = Depends(get_current_driver),
):
    """Remove driver's FCM token (e.g. on logout)."""
    plate_number = await get_plate_from_token(user)

    from app.utils.plate_utils import normalize_plate
    plate_norm = normalize_plate(plate_number) or plate_number

    db = get_db()
    # Delete both normalized and raw doc IDs
    await db.collection(Collections.DRIVER_FCM_TOKENS).document(plate_norm).delete()
    if plate_norm != plate_number:
        await db.collection(Collections.DRIVER_FCM_TOKENS).document(plate_number).delete()

    return {"status": "ok", "message": "FCM token removed"}
