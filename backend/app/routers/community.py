"""
Community API Router - Public endpoints for community awareness
Some endpoints require admin authentication for creating/broadcasting alerts.
"""

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Query, Depends, HTTPException, Body
from pydantic import BaseModel
from google.cloud.firestore_v1 import FieldFilter

from app.config import get_settings
from app.db.firestore_client import get_db, Collections

settings = get_settings()
router = APIRouter(prefix="/community", tags=["Community"])


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class JunctionScore(BaseModel):
    junction_id: str
    junction_name: str
    current_score: float
    risk_level: str
    safety_color: str = 'GREEN'  # GREEN / YELLOW / RED (proposal)
    last_updated: str
    active_alerts: int
    traffic_level: str
    formula: str = 'LiveSafeScore = 100 - Σ(Penalty × Severity × ContextFactor) + TimeRecovery'


class CommunityAlert(BaseModel):
    alert_id: int
    alert_type: str  # 'high_risk', 'emergency', 'congestion', 'accident'
    severity: str  # 'low', 'medium', 'high', 'critical'
    message: str
    junction_id: str
    timestamp: str
    expires_at: Optional[str]
    anonymous: bool = True


class TrafficSummary(BaseModel):
    junction_id: str
    current_density: str
    estimated_wait_time: int  # seconds
    signal_phase: str
    last_updated: str


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_risk_level(score) -> str:
    """Get safety level from score — matches proposal's Green/Yellow/Red."""
    score_val = float(score) if score is not None else 0
    if score_val >= 70:
        return "safe"       # Green
    elif score_val >= 40:
        return "caution"    # Yellow
    else:
        return "danger"     # Red


def get_traffic_level(density: float) -> str:
    """Get traffic level from density."""
    if density < 0.3:
        return "low"
    elif density < 0.6:
        return "moderate"
    elif density < 0.8:
        return "high"
    else:
        return "congested"


# Maps violation types to community alert attributes
VIOLATION_ALERT_MAP = {
    "parking_no_parking": ("high_risk", "medium", "Parking violations detected in the area. Avoid no-parking zones."),
    "parking_no_stopping": ("high_risk", "medium", "No-stopping zone violations detected. Keep the traffic flowing."),
    "parking_overtime": ("congestion", "low", "Overtime parking detected. Please move your vehicle promptly."),
    "parking_handicap": ("high_risk", "high", "Handicap zone violations reported. Respect reserved parking."),
    "parking_loading": ("congestion", "low", "Loading zone misuse detected. Keep loading bays clear."),
    "speeding": ("high_risk", "high", "Speeding incidents reported. Please observe the speed limit."),
    "lane_weaving": ("high_risk", "medium", "Lane weaving behavior detected. Stay in your lane and drive carefully."),
    "running_red_light": ("high_risk", "critical", "Red light violations reported at the junction. Proceed with extreme caution."),
    "red_light": ("high_risk", "critical", "Red light violations reported at the junction. Proceed with extreme caution."),
    "wrong_way_driving": ("high_risk", "critical", "Wrong-way driving detected! Use extreme caution in the area."),
    "wrong_way": ("high_risk", "critical", "Wrong-way driving detected! Use extreme caution in the area."),
}


def create_community_alert_sync(
    violation_type: str,
    junction_id: str = "main",
    extra_info: str = "",
) -> Optional[str]:
    """
    Create a community alert from a violation and persist it to Firestore.
    Called synchronously from the scoring/detection pipeline.
    Uses a 10-minute deduplication window per violation type + junction.

    Returns the new document ID, or None if deduplicated / on error.
    """
    from app.db.firestore_client import get_sync_db

    mapping = VIOLATION_ALERT_MAP.get(violation_type)
    if not mapping:
        return None

    alert_type, severity, base_message = mapping
    now = datetime.now()
    dedup_cutoff = (now - timedelta(minutes=10)).isoformat()
    message = f"{base_message} {extra_info}".strip()

    try:
        db = get_sync_db()

        # ---- deduplication: skip if a similar alert was created recently ----
        # Use single-field query + in-memory filtering to avoid composite index requirement
        recent_alerts = (
            db.collection(Collections.COMMUNITY_ALERTS)
            .where(filter=FieldFilter("violation_type_src", "==", violation_type))
            .limit(10)
            .stream()
        )
        for adoc in recent_alerts:
            adata = adoc.to_dict()
            if (adata.get("junction_id") == junction_id
                    and adata.get("timestamp", "") >= dedup_cutoff):
                return None  # recent duplicate exists

        # ---- create and persist ----
        expires_at = (now + timedelta(hours=1)).isoformat()
        _, doc_ref = db.collection(Collections.COMMUNITY_ALERTS).add({
            "alert_type": alert_type,
            "severity": severity,
            "message": message,
            "junction_id": junction_id,
            "timestamp": now.isoformat(),
            "expires_at": expires_at,
            "created_by": "auto_system",
            "violation_type_src": violation_type,
        })
        print(f"[COMMUNITY] Alert created for {violation_type} at {junction_id}: {doc_ref.id}")
        return doc_ref.id
    except Exception as e:
        print(f"[COMMUNITY] Error creating alert for {violation_type}: {e}")
        return None


# =============================================================================
# JUNCTION SAFETY SCORE (PUBLIC)
# =============================================================================

@router.get("/junction-score", response_model=JunctionScore, summary="Get junction safety score")
async def get_junction_score(
    junction_id: str = Query(default="main", description="Junction identifier"),
):
    """
    Get the current LiveSafeScore for a junction.
    This is a public endpoint for community awareness.
    
    The score represents overall junction safety from 0-100:
    - 90-100: Excellent (very safe)
    - 70-89: Good (safe)
    - 50-69: Fair (caution advised)
    - 30-49: Poor (high risk)
    - 0-29: Critical (avoid if possible)
    """
    db = get_db()

    current_score = 85
    traffic_level = "moderate"
    updated_at = datetime.now().isoformat()

    # First try to get live junction safety from service
    safety_color = 'GREEN'
    try:
        from app.services.lane_weaving_service import get_junction_safety, get_traffic_density
        safety = get_junction_safety()
        if safety:
            current_score = safety.safety_score
            safety_color = safety.get_safety_color()
            traffic_level = get_traffic_density()  # use live traffic density
            updated_at = datetime.now().isoformat()
    except Exception as e:
        pass  # Fall back to DB

    # Get from DB if live service not available or for additional data
    safety_docs = []
    q = db.collection(Collections.JUNCTION_SAFETY).where(
        filter=FieldFilter("junction_id", "==", junction_id)
    )
    async for doc in q.stream():
        safety_docs.append(doc.to_dict())
    safety_docs.sort(key=lambda x: x.get("updated_at", ""), reverse=True)

    for result in safety_docs[:1]:
        # Use safety_score or current_score field
        db_score_val = result.get("safety_score")
        db_score = db_score_val if db_score_val is not None else result.get("current_score", 85)
        traffic_level = get_traffic_level(result.get("traffic_density", 0.5))
        # If live service didn't provide a score, use DB value
        if current_score == 85:
            current_score = db_score
            updated_at = result.get("updated_at", updated_at)

    # Count active alerts
    active_alerts = 0
    now_iso = datetime.now().isoformat()
    aq = db.collection(Collections.COMMUNITY_ALERTS).where(
        filter=FieldFilter("junction_id", "==", junction_id)
    )
    async for doc in aq.stream():
        a = doc.to_dict()
        exp = a.get("expires_at")
        if exp is None or exp > now_iso:
            active_alerts += 1

    return JunctionScore(
        junction_id=junction_id,
        junction_name=f"Junction {junction_id.upper()}",
        current_score=round(current_score, 1),
        risk_level=get_risk_level(current_score),
        safety_color=safety_color,
        last_updated=updated_at,
        active_alerts=active_alerts,
        traffic_level=traffic_level,
    )


@router.get("/junction-scores", summary="Get all junction scores")
async def get_all_junction_scores():
    """Get safety scores for all monitored junctions."""
    db = get_db()

    junctions = []
    async for doc in db.collection(Collections.JUNCTION_SAFETY).stream():
        row = doc.to_dict()
        score = row.get("safety_score", row.get("current_score", 85))
        junctions.append({
            "junction_id": row.get("junction_id", doc.id),
            "current_score": round(float(score), 1),
            "risk_level": get_risk_level(score),
            "safety_color": "GREEN" if float(score) >= 70 else ("YELLOW" if float(score) >= 40 else "RED"),
            "traffic_level": get_traffic_level(row.get("traffic_density", 0.5)),
            "last_updated": row.get("updated_at", datetime.now().isoformat()),
        })

    if not junctions:
        junctions.append({
            "junction_id": "main",
            "current_score": 85,
            "risk_level": "safe",
            "safety_color": "GREEN",
            "traffic_level": "moderate",
            "last_updated": datetime.now().isoformat(),
        })

    return {"junctions": junctions}


# =============================================================================
# COMMUNITY ALERTS (PUBLIC)
# =============================================================================

@router.get("/alerts", summary="Get community alerts")
async def get_community_alerts(
    junction_id: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None, description="Filter: low, medium, high, critical"),
    limit: int = Query(default=20, le=50),
):
    """
    Get anonymized community alerts for public awareness.
    No personal or vehicle-identifying information is included.
    
    Alert types:
    - high_risk: High-risk driving behavior detected
    - emergency: Emergency vehicle approaching
    - congestion: Traffic congestion warning
    - accident: Accident reported
    """
    db = get_db()
    now_iso = datetime.now().isoformat()

    alerts = []
    q = db.collection(Collections.COMMUNITY_ALERTS).order_by(
        "timestamp", direction="DESCENDING"
    ).limit(limit)

    async for doc in q.stream():
        a = doc.to_dict()
        exp = a.get("expires_at")
        # Skip expired alerts
        if exp and exp < now_iso:
            continue
        # Apply filters
        if junction_id and a.get("junction_id") != junction_id:
            continue
        if severity and a.get("severity") != severity:
            continue
        alerts.append({
            "alert_id": doc.id,
            "alert_type": a.get("alert_type", ""),
            "severity": a.get("severity", ""),
            "message": a.get("message", ""),
            "junction_id": a.get("junction_id", ""),
            "timestamp": a.get("timestamp", ""),
            "expires_at": exp,
        })

    # Generate dynamic alerts from recent violations/behaviors if none in DB,
    # then PERSIST them so they are returned on subsequent calls.
    if not alerts:
        now = datetime.now()
        one_hour_ago = (now - timedelta(hours=1)).isoformat()
        generated = []

        # Count recent violations by type
        try:
            vio_counts: dict = {}
            vq = db.collection(Collections.VIOLATIONS).order_by(
                "timestamp", direction="DESCENDING"
            ).limit(50)
            async for doc in vq.stream():
                v = doc.to_dict()
                ts = v.get("timestamp", "")
                if ts < one_hour_ago:
                    continue
                vtype = v.get("violation_type", "unknown")
                vio_counts[vtype] = vio_counts.get(vtype, 0) + 1

            for vtype, count in vio_counts.items():
                mapping = VIOLATION_ALERT_MAP.get(vtype)
                if count > 0 and mapping:
                    atype, sev, msg = mapping
                    target_junction = junction_id or "main"
                    full_msg = f"{msg} ({count} incident{'s' if count > 1 else ''} in the last hour)"
                    expires_at = (now + timedelta(hours=1)).isoformat()

                    # ---- persist to Firestore (with dedup) ----
                    dedup_cutoff = (now - timedelta(minutes=10)).isoformat()
                    dup_q = db.collection(Collections.COMMUNITY_ALERTS).where(
                        filter=FieldFilter("violation_type_src", "==", vtype)
                    ).limit(10)
                    already_exists = False
                    async for _d in dup_q.stream():
                        dd = _d.to_dict()
                        if (dd.get("junction_id") == target_junction
                                and dd.get("timestamp", "") >= dedup_cutoff):
                            already_exists = True
                            break

                    if not already_exists:
                        doc_ref = await db.collection(Collections.COMMUNITY_ALERTS).add({
                            "alert_type": atype,
                            "severity": sev,
                            "message": full_msg,
                            "junction_id": target_junction,
                            "timestamp": now.isoformat(),
                            "expires_at": expires_at,
                            "created_by": "auto_system",
                            "violation_type_src": vtype,
                        })
                        new_id = doc_ref[1].id if isinstance(doc_ref, tuple) else doc_ref.id
                    else:
                        new_id = f"dedup_{vtype}"

                    generated.append({
                        "alert_id": new_id,
                        "alert_type": atype,
                        "severity": sev,
                        "message": full_msg,
                        "junction_id": target_junction,
                        "timestamp": now.isoformat(),
                        "expires_at": expires_at,
                    })

            # Check recent abnormal behaviors
            bq = db.collection(Collections.ABNORMAL_BEHAVIOR).order_by(
                "timestamp", direction="DESCENDING"
            ).limit(20)
            behavior_count = 0
            async for doc in bq.stream():
                b = doc.to_dict()
                ts = b.get("timestamp", "")
                if ts >= one_hour_ago:
                    behavior_count += 1

            if behavior_count > 0:
                target_junction = junction_id or "main"
                beh_msg = (f"Abnormal driving behavior detected in the area. "
                           f"({behavior_count} event{'s' if behavior_count > 1 else ''} in the last hour)")
                beh_sev = "medium" if behavior_count < 5 else "high"
                expires_at = (now + timedelta(hours=1)).isoformat()

                dedup_cutoff = (now - timedelta(minutes=10)).isoformat()
                bdup_q = db.collection(Collections.COMMUNITY_ALERTS).where(
                    filter=FieldFilter("violation_type_src", "==", "abnormal_behavior")
                ).limit(10)
                beh_exists = False
                async for _d in bdup_q.stream():
                    dd = _d.to_dict()
                    if (dd.get("junction_id") == target_junction
                            and dd.get("timestamp", "") >= dedup_cutoff):
                        beh_exists = True
                        break

                if not beh_exists:
                    doc_ref = await db.collection(Collections.COMMUNITY_ALERTS).add({
                        "alert_type": "high_risk",
                        "severity": beh_sev,
                        "message": beh_msg,
                        "junction_id": target_junction,
                        "timestamp": now.isoformat(),
                        "expires_at": expires_at,
                        "created_by": "auto_system",
                        "violation_type_src": "abnormal_behavior",
                    })
                    new_id = doc_ref[1].id if isinstance(doc_ref, tuple) else doc_ref.id
                else:
                    new_id = "dedup_abnormal"

                generated.append({
                    "alert_id": new_id,
                    "alert_type": "high_risk",
                    "severity": beh_sev,
                    "message": beh_msg,
                    "junction_id": target_junction,
                    "timestamp": now.isoformat(),
                    "expires_at": expires_at,
                })

            alerts = generated
        except Exception as gen_err:
            import traceback
            print(f"[COMMUNITY] Error auto-generating alerts: {gen_err}")
            traceback.print_exc()

    return {
        "alerts": alerts,
        "total": len(alerts),
        "generated_at": now_iso,
    }


# =============================================================================
# TRAFFIC INFORMATION (PUBLIC)
# =============================================================================

@router.get("/traffic-summary", response_model=TrafficSummary, summary="Get traffic summary")
async def get_traffic_summary(
    junction_id: str = Query(default="main"),
):
    """
    Get current traffic summary for a junction.
    Includes density level and estimated wait times.
    """
    db = get_db()

    density = 0.4
    signal_phase = "normal"

    # Get latest junction data (sort in Python to avoid composite index)
    junction_docs = []
    q = db.collection(Collections.JUNCTION_SAFETY).where(
        filter=FieldFilter("junction_id", "==", junction_id)
    )
    async for doc in q.stream():
        junction_docs.append(doc.to_dict())
    junction_docs.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    for result in junction_docs[:1]:
        density = result.get("traffic_density", 0.4)

    # Check emergency status
    eq = db.collection(Collections.EMERGENCY_STATUS).where(
        filter=FieldFilter("junction_id", "==", junction_id)
    ).where(filter=FieldFilter("active", "==", True)).limit(1)
    async for _ in eq.stream():
        signal_phase = "emergency"

    wait_time = int(density * 120)

    return TrafficSummary(
        junction_id=junction_id,
        current_density=get_traffic_level(density),
        estimated_wait_time=wait_time,
        signal_phase=signal_phase,
        last_updated=datetime.now().isoformat(),
    )


@router.get("/violation-stats", summary="Get public violation statistics")
async def get_public_violation_stats(
    junction_id: Optional[str] = Query(default=None),
    days: int = Query(default=7, le=30),
):
    """
    Get anonymized violation statistics for community awareness.
    No driver or vehicle information is included.
    """
    db = get_db()
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    # Get violations since start_date
    q = db.collection(Collections.VIOLATIONS).where(
        filter=FieldFilter("timestamp", ">=", start_date)
    ).order_by("timestamp")

    by_type = {}
    daily = {}
    total = 0

    async for doc in q.stream():
        v = doc.to_dict()
        total += 1
        vtype = v.get("violation_type", "unknown")
        by_type[vtype] = by_type.get(vtype, 0) + 1
        ts = v.get("timestamp", "")
        date = ts[:10] if len(ts) >= 10 else ts
        daily[date] = daily.get(date, 0) + 1

    return {
        "period_days": days,
        "total_violations": total,
        "by_type": by_type,
        "daily_counts": [{"date": k, "count": v} for k, v in sorted(daily.items())],
        "message": "Drive safely! These statistics help improve road safety for everyone.",
    }


# =============================================================================
# SAFETY TIPS (PUBLIC)
# =============================================================================

@router.get("/safety-tips", summary="Get safety tips")
async def get_safety_tips():
    """Get contextual safety tips based on current conditions."""
    return {
        "tips": [
            {
                "id": 1,
                "category": "general",
                "tip": "Always maintain a safe following distance of at least 3 seconds.",
            },
            {
                "id": 2,
                "category": "lane_discipline",
                "tip": "Use turn signals at least 100 meters before changing lanes.",
            },
            {
                "id": 3,
                "category": "parking",
                "tip": "Never park in handicapped zones without proper authorization.",
            },
            {
                "id": 4,
                "category": "speed",
                "tip": "Reduce speed in areas with high pedestrian activity.",
            },
            {
                "id": 5,
                "category": "emergency",
                "tip": "Always yield to emergency vehicles and move to the side of the road.",
            },
        ],
        "featured_tip": "Your SafeScore affects insurance premiums. Drive responsibly!",
    }


# =============================================================================
# ALERT MANAGEMENT (Admin Protected)
# =============================================================================

class CreateAlertRequest(BaseModel):
    """Request model for creating a community alert."""
    alert_type: str  # 'high_risk', 'emergency', 'congestion', 'accident', 'construction'
    severity: str  # 'low', 'medium', 'high', 'critical'
    message: str
    junction_id: str = "main"
    expires_in_hours: Optional[int] = 24  # Auto-expire after N hours


class BroadcastAlertRequest(BaseModel):
    """Request model for broadcasting an alert to all junctions."""
    alert_type: str
    severity: str
    message: str
    expires_in_hours: Optional[int] = 12


@router.post("/alerts", summary="Create a community alert")
async def create_community_alert(
    request: CreateAlertRequest,
    admin_key: str = Query(..., description="Admin API key for authorization"),
):
    """
    Create a new community alert.
    Requires admin API key for authorization.
    
    Alert types:
    - high_risk: High-risk driving behavior detected in area
    - emergency: Emergency situation (accident, fire, etc.)
    - congestion: Traffic congestion warning
    - accident: Accident reported
    - construction: Road construction/maintenance
    """
    # Simple API key validation (in production, use proper auth)
    if admin_key != "itms-admin-2024":
        raise HTTPException(status_code=401, detail="Invalid admin API key")
    
    # Validate alert_type
    valid_types = ['high_risk', 'emergency', 'congestion', 'accident', 'construction', 'info']
    if request.alert_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid alert_type. Must be one of: {valid_types}")
    
    # Validate severity
    valid_severities = ['low', 'medium', 'high', 'critical']
    if request.severity not in valid_severities:
        raise HTTPException(status_code=400, detail=f"Invalid severity. Must be one of: {valid_severities}")
    
    now = datetime.now()
    expires_at = None
    if request.expires_in_hours:
        expires_at = (now + timedelta(hours=request.expires_in_hours)).isoformat()

    db = get_db()
    doc_ref = await db.collection(Collections.COMMUNITY_ALERTS).add({
        "alert_type": request.alert_type,
        "severity": request.severity,
        "message": request.message,
        "junction_id": request.junction_id,
        "timestamp": now.isoformat(),
        "expires_at": expires_at,
        "created_by": "admin",
    })
    # doc_ref is a tuple (update_time, doc_ref) for async add
    alert_id = doc_ref[1].id if isinstance(doc_ref, tuple) else doc_ref.id

    return {
        "status": "created",
        "alert_id": alert_id,
        "alert_type": request.alert_type,
        "severity": request.severity,
        "message": request.message,
        "junction_id": request.junction_id,
        "expires_at": expires_at,
        "timestamp": now.isoformat(),
    }


@router.post("/alerts/broadcast", summary="Broadcast alert to all junctions")
async def broadcast_alert(
    request: BroadcastAlertRequest,
    admin_key: str = Query(..., description="Admin API key for authorization"),
):
    """
    Broadcast an alert to all monitored junctions.
    Requires admin API key for authorization.
    
    This creates the same alert for all junctions simultaneously.
    """
    if admin_key != "itms-admin-2024":
        raise HTTPException(status_code=401, detail="Invalid admin API key")
    
    now = datetime.now()
    expires_at = None
    if request.expires_in_hours:
        expires_at = (now + timedelta(hours=request.expires_in_hours)).isoformat()

    db = get_db()

    # Get all junction IDs
    junction_ids = []
    async for doc in db.collection(Collections.JUNCTION_SAFETY).stream():
        jid = doc.to_dict().get("junction_id", doc.id)
        if jid not in junction_ids:
            junction_ids.append(jid)

    if not junction_ids:
        junction_ids = ["main"]

    # Insert alert for each junction
    created_ids = []
    for junction_id in junction_ids:
        doc_ref = await db.collection(Collections.COMMUNITY_ALERTS).add({
            "alert_type": request.alert_type,
            "severity": request.severity,
            "message": request.message,
            "junction_id": junction_id,
            "timestamp": now.isoformat(),
            "expires_at": expires_at,
            "created_by": "admin_broadcast",
        })
        aid = doc_ref[1].id if isinstance(doc_ref, tuple) else doc_ref.id
        created_ids.append(aid)

    return {
        "status": "broadcast",
        "alert_ids": created_ids,
        "junctions_affected": junction_ids,
        "alert_type": request.alert_type,
        "severity": request.severity,
        "message": request.message,
        "expires_at": expires_at,
        "timestamp": now.isoformat(),
    }


@router.delete("/alerts/{alert_id}", summary="Delete a community alert")
async def delete_community_alert(
    alert_id: str,
    admin_key: str = Query(..., description="Admin API key for authorization"),
):
    """Delete a specific community alert."""
    if admin_key != "itms-admin-2024":
        raise HTTPException(status_code=401, detail="Invalid admin API key")

    db = get_db()
    doc = await db.collection(Collections.COMMUNITY_ALERTS).document(alert_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Alert not found")

    await db.collection(Collections.COMMUNITY_ALERTS).document(alert_id).delete()
    return {"status": "deleted", "alert_id": alert_id}


@router.post("/alerts/clear-expired", summary="Clear all expired alerts")
async def clear_expired_alerts(
    admin_key: str = Query(..., description="Admin API key for authorization"),
):
    """Remove all expired community alerts from the database."""
    if admin_key != "itms-admin-2024":
        raise HTTPException(status_code=401, detail="Invalid admin API key")

    db = get_db()
    now = datetime.now().isoformat()
    deleted_count = 0

    async for doc in db.collection(Collections.COMMUNITY_ALERTS).stream():
        a = doc.to_dict()
        exp = a.get("expires_at")
        if exp and exp < now:
            await doc.reference.delete()
            deleted_count += 1

    return {
        "status": "cleared",
        "deleted_count": deleted_count,
        "timestamp": now,
    }


# =============================================================================
# DATABASE INITIALIZATION
# =============================================================================

async def init_community_tables():
    """Initialize community-related database collections (no-op for Firestore)."""
    # Firestore collections are created automatically on first write
    pass
