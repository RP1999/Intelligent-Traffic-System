"""
Admin API Router - Protected endpoints for admin dashboard
Requires JWT authentication with admin role.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import Response
from pydantic import BaseModel
from google.cloud.firestore_v1 import FieldFilter

from app.config import get_settings
from app.db.firestore_client import get_db, Collections
from app.routers.auth import get_current_admin, UserInfo
from app.fuzzy.traffic_controller import get_four_way_controller

settings = get_settings()
router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])


# =============================================================================
# VIDEO SNAPSHOT FOR ZONE EDITOR
# =============================================================================

@router.get("/video/snapshot", summary="Get video snapshot for zone editor")
async def get_admin_video_snapshot(user: UserInfo = Depends(get_current_admin)):
    """
    Get a CLEAN snapshot from the video feed for the Zone Editor.
    This returns a frame WITHOUT detection boxes or zone overlays.
    Lazy-starts the video worker if not already running.
    """
    # Import here to avoid circular imports
    from app.routers.video import _video_state, start_video_worker
    
    # Lazy start: Start worker if not running
    if not _video_state.running:
        start_video_worker()
        # Wait up to 15 seconds for first frame (YOLO models take time to load)
        for _ in range(150):  # Max 15 seconds (model loading can take 5-10s)
            await asyncio.sleep(0.1)
            if _video_state.get_snapshot() is not None:
                break
    
    snapshot = _video_state.get_snapshot()
    
    if snapshot is None:
        raise HTTPException(status_code=503, detail="No snapshot available yet. Video stream starting...")
    
    return Response(
        content=snapshot,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
        }
    )


@router.post("/video/snapshot/refresh", summary="Refresh zone editor snapshot")
async def refresh_admin_video_snapshot(user: UserInfo = Depends(get_current_admin)):
    """
    Request a fresh clean snapshot for Zone Editor.
    Captures the next video frame as a clean image without any overlays.
    """
    from app.routers.video import _video_state
    
    _video_state.request_new_snapshot()
    
    # Wait for new snapshot (max 2 seconds)
    for _ in range(20):
        await asyncio.sleep(0.1)
        if _video_state.raw_frame_captured:
            break
    
    return {"status": "refreshed", "message": "New clean snapshot captured"}


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class DashboardStats(BaseModel):
    violations_today: int
    violations_this_week: int
    average_risk_score: float
    current_traffic_level: str
    active_junctions: int
    total_vehicles_today: int
    pending_fines: float
    emergency_mode: bool
    total_drivers: int = 0


class ViolationDetail(BaseModel):
    violation_id: str
    driver_id: str
    license_plate: Optional[str]
    violation_type: str
    timestamp: str
    location: Optional[str]
    fine_amount: float
    points_deducted: int
    evidence_path: Optional[str]
    notes: Optional[str]


class DriverSummary(BaseModel):
    driver_id: str
    current_score: int
    total_violations: int
    total_fines: float
    last_violation: Optional[str]


class EmergencyResponse(BaseModel):
    status: str
    message: str
    affected_junctions: List[str]
    timestamp: str


# =============================================================================
# DASHBOARD STATISTICS
# =============================================================================

@router.get("/dashboard/stats", response_model=DashboardStats, summary="Get dashboard statistics")
async def get_dashboard_stats(user: UserInfo = Depends(get_current_admin)):
    """
    Get comprehensive dashboard statistics including:
    - Violations count (today and week)
    - Average risk score across all drivers
    - Traffic level estimation
    - Active junction count
    """
    db = get_db()

    today = datetime.now().strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    # Violations today
    violations_today = 0
    q = db.collection(Collections.VIOLATIONS).where(
        filter=FieldFilter("timestamp", ">=", today)
    )
    async for _ in q.stream():
        violations_today += 1

    # Violations this week
    violations_week = 0
    q = db.collection(Collections.VIOLATIONS).where(
        filter=FieldFilter("timestamp", ">=", week_ago)
    )
    async for _ in q.stream():
        violations_week += 1

    # Average risk score from drivers
    scores = []
    total_drivers = 0
    async for doc in db.collection(Collections.DRIVERS).stream():
        d = doc.to_dict()
        scores.append(d.get("current_score", 100))
        total_drivers += 1
    avg_score = sum(scores) / len(scores) if scores else 100.0

    # Compute average risk score from actual RISK_SCORES collection
    # (uses the real formula: Speed_Factor × 0.6 + History_Factor × 0.4)
    real_risk_scores = []
    try:
        seen_vehicles = set()
        rq = db.collection(Collections.RISK_SCORES).order_by(
            "created_at", direction="DESCENDING"
        ).limit(200)
        async for rdoc in rq.stream():
            rd = rdoc.to_dict()
            vid = rd.get("vehicle_id") or rd.get("plate_number") or ""
            if vid in seen_vehicles:
                continue  # Keep only latest per vehicle
            seen_vehicles.add(vid)
            rs = rd.get("risk_score")
            if rs is not None:
                real_risk_scores.append(float(rs))
    except Exception as e:
        print(f"[ADMIN] Failed to fetch risk scores: {e}")

    if real_risk_scores:
        avg_risk = round(sum(real_risk_scores) / len(real_risk_scores), 2)
    else:
        # Fallback: derive from driver safety scores only if no real risk data
        avg_risk = round(100 - avg_score, 2)

    # Get junction safety score
    # Get junction safety score and derive traffic level
    traffic_level = "normal"
    q = db.collection(Collections.JUNCTION_SAFETY).order_by(
        "updated_at", direction="DESCENDING"
    ).limit(1)
    async for doc in q.stream():
        js = doc.to_dict()
        safety_score = js.get("safety_score", 50)
        # Use safety score directly (not inverted) with proposal thresholds
        if safety_score < 40:
            traffic_level = "high"       # RED zone = high risk
        elif safety_score < 70:
            traffic_level = "moderate"   # YELLOW zone
        else:
            traffic_level = "low"        # GREEN zone

    # Pending fines (only sum unpaid violations)
    pending_fines = 0.0
    try:
        q = db.collection(Collections.VIOLATIONS).where(
            filter=FieldFilter("status", "in", ["pending", "unpaid", None])
        )
        async for doc in q.stream():
            v = doc.to_dict()
            fa = v.get("fine_amount", 0)
            if fa and fa > 0:
                pending_fines += fa
    except Exception:
        # Fallback: sum all violations if status field doesn't exist
        async for doc in db.collection(Collections.VIOLATIONS).stream():
            v = doc.to_dict()
            status = v.get("status", "pending")
            if status in ["pending", "unpaid", None]:
                fa = v.get("fine_amount", 0)
                if fa and fa > 0:
                    pending_fines += fa

    # Check emergency mode
    emergency_mode = False
    eq = db.collection(Collections.EMERGENCY_STATUS).order_by(
        "triggered_at", direction="DESCENDING"
    ).limit(1)
    async for doc in eq.stream():
        emergency_mode = bool(doc.to_dict().get("active", False))

    return DashboardStats(
        violations_today=violations_today,
        violations_this_week=violations_week,
        average_risk_score=avg_risk,
        current_traffic_level=traffic_level,
        active_junctions=1,
        total_vehicles_today=violations_today * 10,
        pending_fines=pending_fines,
        emergency_mode=emergency_mode,
        total_drivers=total_drivers,
    )


# =============================================================================
# VIOLATION MANAGEMENT
# =============================================================================

# Type categories that match multiple violation types
VIOLATION_TYPE_CATEGORIES = {
    "parking": ["parking_no_parking", "parking_no_stopping", "parking_overtime", 
                "parking_handicap", "parking_loading"],
    "lane_weaving": ["lane_weaving"],
}


@router.get("/violations", summary="Get all violations")
async def get_all_violations(
    user: UserInfo = Depends(get_current_admin),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    violation_type: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None, description="Filter by status: pending, verified, paid, dismissed"),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
):
    """
    Get paginated list of all violations with optional filters.
    Admin only endpoint.
    
    violation_type can be:
    - An exact type like 'red_light', 'speeding'
    - A category like 'parking' (matches all parking_* types)
    - A category like 'lane_weaving' (matches lane_weaving)
    
    status can be: pending, verified, paid, dismissed
    """
    db = get_db()

    # Build query - avoid composite index by fetching all and filtering in Python
    q = db.collection(Collections.VIOLATIONS)
    
    # Check if violation_type is a category or exact match
    category_types = None
    filter_type = None
    if violation_type:
        if violation_type in VIOLATION_TYPE_CATEGORIES:
            # It's a category, we'll filter in-memory
            category_types = VIOLATION_TYPE_CATEGORIES[violation_type]
        else:
            # Exact match - filter in-memory (avoids composite index)
            filter_type = violation_type
    
    # Only apply date filters if no violation_type filter (to avoid composite index)
    # For simplicity, fetch all and filter in Python
    
    # Collect all docs (filter and sort in Python to avoid composite index)
    all_docs = []
    async for doc in q.stream():
        doc_dict = doc.to_dict()
        
        # Filter by violation_type in Python
        if filter_type:
            if doc_dict.get("violation_type") != filter_type:
                continue
        if category_types:
            if doc_dict.get("violation_type") not in category_types:
                continue
        
        # Filter by date in Python
        ts = doc_dict.get("timestamp", "")
        if date_from and ts < date_from:
            continue
        if date_to and ts > date_to + " 23:59:59":
            continue
        
        # Filter by status in Python
        if status:
            doc_status = doc_dict.get("status") or "pending"
            if doc_status.lower() != status.lower():
                continue
        
        all_docs.append((doc.id, doc_dict))
    
    # Sort by timestamp descending in Python
    all_docs.sort(key=lambda x: x[1].get("timestamp", ""), reverse=True)

    total = len(all_docs)
    page = all_docs[offset: offset + limit]

    return {
        "violations": [
            {
                "violation_id": doc_id,
                "driver_id": v.get("driver_id", ""),
                "license_plate": v.get("license_plate", v.get("driver_id", "")),
                "violation_type": v.get("violation_type", ""),
                "timestamp": v.get("timestamp", ""),
                "location": v.get("location") or "Unknown",
                "fine_amount": v.get("fine_amount", 0) or 0,
                "points_deducted": v.get("points_deducted", 0),
                "evidence_path": v.get("evidence_path") or v.get("snapshot_path"),
                "notes": f"Severity: {v['severity']}" if v.get("severity") else None,
                "status": v.get("status") or "pending",
                "fine_breakdown": v.get("fine_breakdown"),
            }
            for doc_id, v in page
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
        "filters_applied": {
            "violation_type": violation_type,
            "status": status,
            "date_from": date_from,
            "date_to": date_to,
        }
    }


@router.get("/violations/{violation_id}", summary="Get violation details")
async def get_violation_details(
    violation_id: str,
    user: UserInfo = Depends(get_current_admin),
):  
    """Get detailed information about a specific violation."""
    db = get_db()
    doc = await db.collection(Collections.VIOLATIONS).document(violation_id).get()

    if not doc.exists:
        raise HTTPException(status_code=404, detail="Violation not found")

    v = doc.to_dict()
    return {
        "violation_id": doc.id,
        "driver_id": v.get("driver_id", ""),
        "license_plate": v.get("license_plate", v.get("driver_id", "")),
        "violation_type": v.get("violation_type", ""),
        "timestamp": v.get("timestamp", ""),
        "location": v.get("location") or "Unknown",
        "fine_amount": v.get("fine_amount", 0) or 0,
        "points_deducted": v.get("points_deducted", 0) or 0,
        "severity": v.get("severity"),
        "status": v.get("status") or "pending",
        "evidence_path": v.get("evidence_path") or v.get("snapshot_path"),
        "fine_breakdown": v.get("fine_breakdown"),
    }


@router.delete("/violations/{violation_id}", summary="Delete a violation")
async def delete_violation(
    violation_id: str,
    user: UserInfo = Depends(get_current_admin),
):
    """Delete a violation record (admin only)."""
    db = get_db()
    doc = await db.collection(Collections.VIOLATIONS).document(violation_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Violation not found")

    await db.collection(Collections.VIOLATIONS).document(violation_id).delete()
    return {"status": "deleted", "violation_id": violation_id}


@router.patch("/violations/{violation_id}/status", summary="Update violation status")
async def update_violation_status(
    violation_id: str,
    new_status: str = Query(..., description="New status: pending, verified, dismissed, paid"),
    user: UserInfo = Depends(get_current_admin),
):
    """Update the status of a violation (admin only)."""
    db = get_db()
    
    # Validate status
    valid_statuses = ["pending", "verified", "dismissed", "paid"]
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
    
    doc = await db.collection(Collections.VIOLATIONS).document(violation_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Violation not found")
    
    # Update status
    await db.collection(Collections.VIOLATIONS).document(violation_id).update({
        "status": new_status,
        "status_updated_at": datetime.now().isoformat(),
        "status_updated_by": user.identifier,
    })
    
    print(f"[ADMIN] Violation {violation_id} status updated to '{new_status}' by {user.identifier}")
    
    return {"status": "updated", "violation_id": violation_id, "new_status": new_status}


# =============================================================================
# DRIVER MANAGEMENT
# =============================================================================

@router.get("/drivers", summary="Get all drivers")
async def get_all_drivers(
    user: UserInfo = Depends(get_current_admin),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="current_score", description="Sort by: current_score, total_violations, total_fines"),
    order: str = Query(default="asc", description="Order: asc, desc"),
    search: Optional[str] = Query(default=None, description="Search by plate, name, phone"),
    risk_level: Optional[str] = Query(default=None, description="Filter by: excellent, good, fair, poor, critical"),
    registered_only: bool = Query(default=False, description="Only include drivers linked to registered driver users"),
):
    """Get paginated list of drivers with profile-enriched metadata."""
    db = get_db()
    from app.utils.plate_utils import normalize_plate

    valid_sorts = ["current_score", "total_violations", "total_fines", "driver_id"]
    if sort_by not in valid_sorts:
        sort_by = "current_score"

    direction = "DESCENDING" if order.lower() == "desc" else "ASCENDING"

    # Get all drivers sorted
    all_drivers = []
    q = db.collection(Collections.DRIVERS).order_by(sort_by, direction=direction)
    async for doc in q.stream():
        d = doc.to_dict()
        d["_driver_id"] = doc.id
        all_drivers.append(d)

    # Build a plate-indexed lookup map for registered users once.
    users_by_plate = {}
    users_by_plate_norm = {}
    async for udoc in db.collection(Collections.DRIVER_USERS).stream():
        u = udoc.to_dict()
        plate = str(u.get("plate_number") or "").strip().upper()
        plate_norm = str(u.get("plate_number_normalized") or "").strip().upper()
        if not plate_norm and plate:
            plate_norm = normalize_plate(plate)
        if plate:
            users_by_plate[plate] = u
        if plate_norm:
            users_by_plate_norm[plate_norm] = u

    requested_risk = (risk_level or "").strip().lower()
    if requested_risk == "all":
        requested_risk = ""
    valid_risks = {"excellent", "good", "fair", "poor", "critical"}
    if requested_risk and requested_risk not in valid_risks:
        requested_risk = ""

    search_query = (search or "").strip().lower()

    merged = []
    for d in all_drivers:
        driver_id = str(d.get("driver_id") or d.get("_driver_id") or "").strip()
        if not driver_id:
            continue

        normalized_driver_id = normalize_plate(driver_id)
        user_doc = (
            users_by_plate.get(driver_id.upper())
            or (users_by_plate_norm.get(normalized_driver_id) if normalized_driver_id else None)
        )

        if registered_only and not user_doc:
            continue

        score = d.get("current_score", 100)
        score_risk = get_risk_level(score)
        if requested_risk and score_risk != requested_risk:
            continue

        plate_number = (
            (user_doc or {}).get("plate_number")
            or d.get("plate_number_display")
            or driver_id
        )
        name = (user_doc or {}).get("name") or "Unknown Driver"
        phone = (user_doc or {}).get("phone")

        if search_query:
            haystacks = [
                driver_id,
                normalized_driver_id,
                plate_number,
                name,
                phone or "",
            ]
            if not any(search_query in str(v).lower() for v in haystacks if v):
                continue

        merged.append({
            "driver_id": driver_id,
            "plate_number": plate_number,
            "name": name,
            "phone": phone,
            "is_registered": user_doc is not None,
            "current_score": score,
            "total_violations": d.get("total_violations", 0),
            "total_fines": d.get("total_fines", 0.0),
            "last_violation": d.get("updated_at"),
            "risk_level": score_risk,
        })

    total = len(merged)
    page = merged[offset: offset + limit]

    return {
        "drivers": page,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/drivers/{driver_id}", summary="Get driver details")
async def get_driver_details(
    driver_id: str,
    user: UserInfo = Depends(get_current_admin),
):
    """Get detailed information about a specific driver."""
    db = get_db()

    doc = await db.collection(Collections.DRIVERS).document(driver_id).get()
    
    # Initialize driver data - either from document or defaults
    if doc.exists:
        driver = doc.to_dict()
    else:
        driver = {
            "driver_id": driver_id,
            "current_score": 100,
            "total_violations": 0,
            "total_fines": 0.0,
        }

    # Get user details
    name = "Unknown Driver"
    phone = None
    plate_number = driver.get("plate_number_display") or driver_id
    
    from app.utils.plate_utils import normalize_plate
    norm_driver_id = normalize_plate(driver_id)
    
    uq = db.collection(Collections.DRIVER_USERS).where(
        filter=FieldFilter("plate_number", "==", driver_id)
    ).limit(1)
    found_user = False
    async for udoc in uq.stream():
        u = udoc.to_dict()
        name = u.get("name") or "Unknown Driver"
        phone = u.get("phone")
        plate_number = u.get("plate_number") or plate_number
        found_user = True
    
    # Fallback: try normalized plate match
    if not found_user and norm_driver_id:
        uq2 = db.collection(Collections.DRIVER_USERS).where(
            filter=FieldFilter("plate_number_normalized", "==", norm_driver_id)
        ).limit(1)
        async for udoc in uq2.stream():
            u = udoc.to_dict()
            name = u.get("name") or "Unknown Driver"
            phone = u.get("phone")
            plate_number = u.get("plate_number") or plate_number

    # Get all violations for this driver and calculate stats
    # Search by both original and normalized plate to catch all matches
    seen_vio_ids = set()
    violations_raw = []
    for search_id in set(filter(None, [driver_id, norm_driver_id])):
        for field_name in ("driver_id", "license_plate"):
            vq = db.collection(Collections.VIOLATIONS).where(
                filter=FieldFilter(field_name, "==", search_id)
            )
            async for vdoc in vq.stream():
                if vdoc.id not in seen_vio_ids:
                    seen_vio_ids.add(vdoc.id)
                    violations_raw.append((vdoc.id, vdoc.to_dict()))
    
    # Sort by timestamp descending in Python
    violations_raw.sort(key=lambda x: x[1].get("timestamp", ""), reverse=True)
    
    violations = []
    total_fines = 0.0
    total_points_deducted = 0
    last_violation_time = None
    for vdoc_id, v in violations_raw:
        fine_amount = v.get("fine_amount", 0) or 0
        points = v.get("points_deducted", 0) or 0
        total_fines += fine_amount
        total_points_deducted += points
        if not last_violation_time:
            last_violation_time = v.get("timestamp")
        violations.append({
            "violation_id": vdoc_id,
            "violation_type": v.get("violation_type", ""),
            "timestamp": v.get("timestamp", ""),
            "fine_amount": fine_amount,
            "location": v.get("location"),
        })

    # Calculate score: sum of actual points_deducted from violations
    total_violations = len(violations)
    calculated_score = max(0, 100 - total_points_deducted)

    # Fetch latest risk score for this driver
    # RISK_SCORES stores vehicle_id as tracking int (e.g. "5") and plate_number
    # as the detected plate. We search by plate_number and plate_number_normalized
    # since driver_id is a plate string, not a tracking ID.
    risk_score = None
    risk_level_pred = None

    # Try by plate_number (exact match)
    try:
        rq = db.collection(Collections.RISK_SCORES).where(
            filter=FieldFilter("plate_number", "==", driver_id)
        ).limit(5)
        best_doc = None
        async for rdoc in rq.stream():
            rd = rdoc.to_dict()
            # Pick the most recent by created_at
            if best_doc is None or (rd.get("created_at", "") > best_doc.get("created_at", "")):
                best_doc = rd
        if best_doc:
            risk_score = best_doc.get("risk_score")
            risk_level_pred = best_doc.get("risk_level")
    except Exception as e:
        print(f"[ADMIN] Risk score query by plate_number failed: {e}")

    # Fallback: try by normalized plate
    if risk_score is None and norm_driver_id:
        try:
            rq2 = db.collection(Collections.RISK_SCORES).where(
                filter=FieldFilter("plate_number_normalized", "==", norm_driver_id)
            ).limit(5)
            best_doc = None
            async for rdoc in rq2.stream():
                rd = rdoc.to_dict()
                if best_doc is None or (rd.get("created_at", "") > best_doc.get("created_at", "")):
                    best_doc = rd
            if best_doc:
                risk_score = best_doc.get("risk_score")
                risk_level_pred = best_doc.get("risk_level")
        except Exception as e:
            print(f"[ADMIN] Risk score query by normalized plate failed: {e}")

    # Fallback: calculate from driver's violation history factor
    # (uses History_Factor × 0.4 since we have no live speed data)
    if risk_score is None:
        # Count recent violations for this driver
        fallback_violation_count = total_violations  # already counted above
        # History factor: each violation adds points (weighted or 10 per violation)
        history_factor = min(100, fallback_violation_count * 10)
        # Without live speed, assume moderate speed factor of 20 (just under limit)
        speed_factor_fallback = 20.0
        risk_score = round((speed_factor_fallback * 0.6) + (history_factor * 0.4), 1)
        if risk_score >= 80:
            risk_level_pred = "CRITICAL"
        elif risk_score >= 60:
            risk_level_pred = "HIGH"
        elif risk_score >= 30:
            risk_level_pred = "MEDIUM"
        else:
            risk_level_pred = "LOW"

    return {
        "driver_id": driver_id,
        "plate_number": plate_number,
        "name": name,
        "phone": phone,
        "current_score": driver.get("current_score", calculated_score),
        "risk_score": risk_score,
        "risk_level_prediction": risk_level_pred,
        "total_violations": total_violations,
        "total_fines": total_fines,
        "last_violation": last_violation_time or driver.get("updated_at"),
        "recent_violations": violations[:20],  # Limit to 20 most recent
    }


# =============================================================================
# EMERGENCY CONTROL
# =============================================================================

@router.post("/emergency/trigger", response_model=EmergencyResponse, summary="Trigger emergency mode")
async def trigger_emergency(
    junction_id: str = Query(default="main", description="Junction to trigger emergency for"),
    emergency_type: str = Query(default="ambulance", description="Type: ambulance, fire, police"),
    lane: str = Query(default="north", description="Lane to force GREEN"),
):
    """
    Trigger emergency mode for a junction.
    This simulates an ambulance/emergency vehicle approach.
    All signals will be set to allow emergency vehicle passage.
    """
    controller = get_four_way_controller()
    if controller:
        controller.activate_emergency_mode(lane=lane)
        print(f"[ADMIN] 🚑 Emergency mode activated - Lane: {lane}")
    else:
        print(f"[ADMIN] ⚠️ Traffic controller not available for emergency mode")

    db = get_db()
    now = datetime.now().isoformat()
    await db.collection(Collections.EMERGENCY_STATUS).add({
        "junction_id": junction_id,
        "emergency_type": emergency_type,
        "active": True,
        "triggered_by": "admin",
        "triggered_at": now,
        "resolved_at": None,
    })

    return EmergencyResponse(
        status="triggered",
        message=f"Emergency mode activated for {emergency_type} at junction {junction_id}",
        affected_junctions=[junction_id],
        timestamp=now,
    )


@router.post("/emergency/clear", summary="Clear emergency mode")
async def clear_emergency(
    user: UserInfo = Depends(get_current_admin),
    junction_id: str = Query(default="main"),
):
    """Clear emergency mode and return to normal operation."""
    controller = get_four_way_controller()
    if controller:
        controller.deactivate_emergency_mode()
        print(f"[ADMIN] ✅ Emergency mode deactivated by {user.identifier}")

    db = get_db()
    now = datetime.now().isoformat()
    # Find active emergencies for this junction and deactivate
    q = db.collection(Collections.EMERGENCY_STATUS).where(
        filter=FieldFilter("junction_id", "==", junction_id)
    ).where(filter=FieldFilter("active", "==", True))
    async for doc in q.stream():
        await doc.reference.update({"active": False, "resolved_at": now})

    return {
        "status": "cleared",
        "message": f"Emergency mode cleared for junction {junction_id}",
        "timestamp": now,
    }


# =============================================================================
# ANALYTICS
# =============================================================================

@router.get("/analytics/violation-trends", summary="Get violation trends")
async def get_violation_trends(
    user: UserInfo = Depends(get_current_admin),
    days: int = Query(default=7, le=30),
):
    """Get violation trends over the specified number of days."""
    db = get_db()
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    # Get violations since start_date
    q = db.collection(Collections.VIOLATIONS).where(
        filter=FieldFilter("timestamp", ">=", start_date)
    ).order_by("timestamp")

    # Normalise raw violation_type → display category for the pie chart
    def _normalise_vtype(raw: str) -> str:
        raw_l = raw.lower()
        if raw_l.startswith("parking"):
            return "parking_no_parking"   # group all parking sub-types
        if raw_l in ("lane_violation", "lane_weaving", "lane_drift"):
            return "lane_weaving"
        if raw_l == "reckless_driving":
            return "speeding"              # fold legacy reckless into speeding
        return raw_l

    trends = {}
    async for doc in q.stream():
        v = doc.to_dict()
        ts = v.get("timestamp", "")
        date = ts[:10] if len(ts) >= 10 else ts  # Extract YYYY-MM-DD
        vtype = _normalise_vtype(v.get("violation_type", "unknown"))
        if date not in trends:
            trends[date] = {"date": date, "total": 0, "by_type": {}}
        trends[date]["by_type"][vtype] = trends[date]["by_type"].get(vtype, 0) + 1
        trends[date]["total"] += 1

    return {
        "period_days": days,
        "start_date": start_date,
        "trends": list(trends.values()),
    }


@router.get("/analytics/hotspots", summary="Get violation hotspots")
async def get_violation_hotspots(
    user: UserInfo = Depends(get_current_admin),
):
    """Get locations with highest violation counts."""
    db = get_db()

    location_stats = {}
    async for doc in db.collection(Collections.VIOLATIONS).stream():
        v = doc.to_dict()
        loc = v.get("location")
        if loc:
            if loc not in location_stats:
                location_stats[loc] = {"violation_count": 0, "total_fines": 0.0}
            location_stats[loc]["violation_count"] += 1
            location_stats[loc]["total_fines"] += v.get("fine_amount", 0) or 0

    # Sort by violation count desc, take top 10
    hotspots = sorted(
        [{"location": k, **v} for k, v in location_stats.items()],
        key=lambda x: x["violation_count"],
        reverse=True,
    )[:10]

    return {"hotspots": hotspots}


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
