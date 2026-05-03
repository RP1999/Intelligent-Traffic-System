"""
Accident Risk Prediction Router

Risk Score Formula (Finalized - No Weather):
    Risk_Score = (Speed_Factor × 0.6) + (Violation_History_Factor × 0.4)

Scale: 0-100 (higher = more dangerous)
- LOW: 0-30
- MEDIUM: 30-60
- HIGH: 60-80
- CRITICAL: 80-100
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

import threading

from app.config import get_settings
from app.db.firestore_client import get_db, get_sync_db, Collections
from app.routers.auth import get_current_admin, UserInfo
from app.services.behavior_service import (
    get_recent_behavior_events,
    get_high_risk_vehicles as get_high_risk_vehicles_behavior,
    get_vehicle_behavior,
    _vehicle_behaviors,
    PIXEL_TO_KMH_FACTOR,
)

settings = get_settings()
router = APIRouter(prefix="/risk", tags=["Risk Prediction"])


# =============================================================================
# RISK SCORE CONFIGURATION
# =============================================================================

# Speed factor weights
SPEED_WEIGHT = 0.6
VIOLATION_HISTORY_WEIGHT = 0.4

# Violation weights for history scoring
VIOLATION_WEIGHTS = {
    'speeding': 15,
    'parking': 5,
    'parking_no_parking': 5,
    'parking_no_stopping': 5,
    'lane_weaving': 20,
    'lane_drift': 10,
    'wrong_way': 40,
    'wrong_way_driving': 40,
    'running_red_light': 35,
    'red_light': 35,
    'improper_stopping': 10,
}

# Behavior weights (abnormal behavior contributes to history factor)
BEHAVIOR_WEIGHTS = {
    'sudden_stop': 10,
    'harsh_brake': 12,
    'lane_drift': 15,
    'erratic_movement': 20,
}


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class RiskScoreResponse(BaseModel):
    """Risk score for a single vehicle."""
    vehicle_id: str
    risk_score: float
    risk_level: str
    speed_factor: float
    violation_history_factor: float
    current_speed: Optional[float] = None
    plate_number: Optional[str] = None
    behaviors_detected: List[str] = []
    timestamp: str


class RiskScoresSummary(BaseModel):
    """Summary of all risk scores."""
    total_vehicles: int
    high_risk_count: int
    average_risk_score: float
    risk_distribution: Dict[str, int]
    scores: List[RiskScoreResponse]


class BehaviorLogEntry(BaseModel):
    """Single behavior log entry."""
    vehicle_id: int
    behavior_type: str
    severity: str
    plate_number: Optional[str]
    details: Dict[str, Any]
    timestamp: str


# =============================================================================
# RISK CALCULATION FUNCTIONS
# =============================================================================

def calculate_speed_factor(current_speed: float, speed_limit: float = 60.0) -> float:
    """
    Calculate speed factor (0-100).
    
    Args:
        current_speed: Current speed in km/h (or estimated)
        speed_limit: Speed limit in km/h
    
    Returns:
        Speed factor score (0-100)
    """
    if speed_limit <= 0:
        speed_limit = 60.0
    
    speed_ratio = current_speed / speed_limit
    
    if speed_ratio <= 0.8:
        return 0  # Safe speed
    elif speed_ratio <= 1.0:
        return (speed_ratio - 0.8) * 100  # 0-20
    elif speed_ratio <= 1.2:
        return 20 + (speed_ratio - 1.0) * 150  # 20-50
    elif speed_ratio <= 1.5:
        return 50 + (speed_ratio - 1.2) * 166.67  # 50-100
    else:
        return 100  # Maximum risk


async def calculate_violation_history_factor(
    driver_id: str,
    days: int = 30
) -> float:
    """
    Calculate violation history factor based on past violations.
    
    Args:
        driver_id: Driver ID or plate number
        days: Number of days to look back
    
    Returns:
        Violation history factor (0-100)
    """
    try:
        db = get_db()
        
        # Calculate date threshold
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        # Query violations for this driver
        violations_ref = db.collection(Collections.VIOLATIONS)
        query = violations_ref.where("driver_id", "==", driver_id)
        
        violations = []
        async for doc in query.stream():
            v = doc.to_dict()
            if v.get("timestamp", "") >= cutoff_date:
                violations.append(v)
        
        # Calculate weighted score
        history_score = 0
        for v in violations:
            violation_type = v.get("violation_type", "")
            weight = VIOLATION_WEIGHTS.get(violation_type, 10)
            history_score += weight
        
        # Cap at 100
        return min(100, history_score)
    except Exception as e:
        print(f"[RISK] Error calculating history factor: {e}")
        return 0


def calculate_behavior_factor(track_id: int) -> float:
    """
    Calculate behavior factor from recent abnormal behaviors.
    
    Args:
        track_id: Vehicle tracking ID
    
    Returns:
        Behavior factor score (0-50)
    """
    behavior = get_vehicle_behavior(track_id)
    if not behavior:
        return 0
    
    score = 0
    score += behavior.get('sudden_stop_count', 0) * BEHAVIOR_WEIGHTS['sudden_stop']
    score += behavior.get('harsh_brake_count', 0) * BEHAVIOR_WEIGHTS['harsh_brake']
    
    # Drift score contribution
    drift = behavior.get('drift_score', 0)
    if drift > 15:
        score += BEHAVIOR_WEIGHTS['lane_drift']
    
    return min(50, score)  # Cap at 50


def get_risk_level(score: float) -> str:
    """Get risk level label from score."""
    if score < 30:
        return 'LOW'
    elif score < 60:
        return 'MEDIUM'
    elif score < 80:
        return 'HIGH'
    else:
        return 'CRITICAL'


async def calculate_risk_score(
    vehicle_id: str,
    track_id: int,
    current_speed: float = 0,
    plate_number: Optional[str] = None,
    speed_limit: float = 60.0
) -> RiskScoreResponse:
    """
    Calculate complete risk score for a vehicle.
    
    Formula: Risk_Score = (Speed_Factor × 0.6) + (Violation_History_Factor × 0.4)
    """
    # Calculate speed factor
    speed_factor = calculate_speed_factor(current_speed, speed_limit)
    
    # Calculate violation history factor
    driver_id = plate_number or vehicle_id
    history_factor = await calculate_violation_history_factor(driver_id)
    
    # Add behavior factor to history
    behavior_factor = calculate_behavior_factor(track_id)
    combined_history = min(100, history_factor + behavior_factor)
    
    # Final risk score
    risk_score = (speed_factor * SPEED_WEIGHT) + (combined_history * VIOLATION_HISTORY_WEIGHT)
    risk_score = round(risk_score, 1)
    
    # Get detected behaviors
    behavior = get_vehicle_behavior(track_id)
    behaviors = behavior.get('behaviors_detected', []) if behavior else []
    
    return RiskScoreResponse(
        vehicle_id=vehicle_id,
        risk_score=risk_score,
        risk_level=get_risk_level(risk_score),
        speed_factor=round(speed_factor, 1),
        violation_history_factor=round(combined_history, 1),
        current_speed=round(current_speed, 1) if current_speed else None,
        plate_number=plate_number,
        behaviors_detected=behaviors[-5:],
        timestamp=datetime.now().isoformat(),
    )


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.get("/current-scores", response_model=RiskScoresSummary, summary="Get all vehicle risk scores")
async def get_current_risk_scores(
    limit: int = Query(50, ge=1, le=200),
    user: UserInfo = Depends(get_current_admin)
):
    """
    Get current risk scores for all tracked vehicles.
    Combines speed factor and violation history.
    """
    scores = []
    
    # Calculate risk for all currently tracked vehicles
    # Copy items to avoid RuntimeError if dict changes during iteration
    vehicle_snapshot = list(_vehicle_behaviors.items())
    for track_id, behavior in vehicle_snapshot:
        # Estimate current speed from recent speeds
        recent_speeds = list(behavior.speeds)[-5:]
        current_speed = sum(recent_speeds) / len(recent_speeds) if recent_speeds else 0
        
        # Convert pixels/sec to km/h using configurable factor
        speed_kmh = current_speed * PIXEL_TO_KMH_FACTOR
        
        score = await calculate_risk_score(
            vehicle_id=str(track_id),
            track_id=track_id,
            current_speed=speed_kmh,
        )
        scores.append(score)
    
    # If we computed live scores, persist them in background
    if scores:
        _persist_scores_background(scores)
    else:
        # No vehicles currently tracked — load from Firestore history
        scores = await _load_scores_from_firestore(limit)

    # Sort by risk score descending
    scores.sort(key=lambda x: x.risk_score, reverse=True)
    scores = scores[:limit]
    
    # Calculate statistics
    risk_distribution = {'LOW': 0, 'MEDIUM': 0, 'HIGH': 0, 'CRITICAL': 0}
    total_score = 0
    
    for s in scores:
        risk_distribution[s.risk_level] += 1
        total_score += s.risk_score
    
    return RiskScoresSummary(
        total_vehicles=len(scores),
        high_risk_count=risk_distribution['HIGH'] + risk_distribution['CRITICAL'],
        average_risk_score=round(total_score / len(scores), 1) if scores else 0,
        risk_distribution=risk_distribution,
        scores=scores,
    )


def _persist_scores_background(scores: List[RiskScoreResponse]):
    """Save computed risk scores to Firestore in a background thread so API stays fast."""
    def _save():
        try:
            from app.utils.plate_utils import normalize_plate
            db = get_sync_db()
            batch = db.batch()
            now = datetime.now().isoformat()
            for s in scores:
                doc_ref = db.collection(Collections.RISK_SCORES).document()
                plate_norm = normalize_plate(s.plate_number) if s.plate_number else None
                batch.set(doc_ref, {
                    'vehicle_id': s.vehicle_id,
                    'risk_score': s.risk_score,
                    'risk_level': s.risk_level,
                    'speed_factor': s.speed_factor,
                    'violation_history_factor': s.violation_history_factor,
                    'current_speed': s.current_speed,
                    'plate_number': s.plate_number,
                    'plate_number_normalized': plate_norm,
                    'behaviors_detected': s.behaviors_detected,
                    'created_at': now,
                })
            batch.commit()
        except Exception as e:
            print(f"[RISK] Failed to persist scores: {e}")
    threading.Thread(target=_save, daemon=True).start()


async def _load_scores_from_firestore(limit: int = 50) -> List[RiskScoreResponse]:
    """Load most recent risk scores from Firestore (used after server restart)."""
    scores = []
    try:
        db = get_db()
        # Try ordered query; fall back to unordered if index missing
        try:
            query = db.collection(Collections.RISK_SCORES).order_by(
                'created_at', direction='DESCENDING'
            ).limit(limit * 3)  # fetch extra to deduplicate per vehicle
        except Exception:
            query = db.collection(Collections.RISK_SCORES).limit(limit * 3)
        
        seen_vehicles = set()
        async for doc in query.stream():
            data = doc.to_dict()
            vid = str(data.get('vehicle_id', ''))
            # Keep only the latest score per vehicle
            if vid in seen_vehicles:
                continue
            seen_vehicles.add(vid)
            scores.append(RiskScoreResponse(
                vehicle_id=vid,
                risk_score=data.get('risk_score', 0),
                risk_level=data.get('risk_level', 'LOW'),
                speed_factor=data.get('speed_factor', 0),
                violation_history_factor=data.get('violation_history_factor', 0),
                current_speed=data.get('current_speed'),
                plate_number=data.get('plate_number'),
                behaviors_detected=data.get('behaviors_detected', []),
                timestamp=data.get('created_at', ''),
            ))
        print(f"[RISK] Loaded {len(scores)} risk scores from Firestore")
    except Exception as e:
        print(f"[RISK] Failed to load scores from Firestore: {e}")
    return scores


@router.get("/vehicle/{vehicle_id}", response_model=RiskScoreResponse, summary="Get specific vehicle risk")
async def get_vehicle_risk_score(
    vehicle_id: str,
    user: UserInfo = Depends(get_current_admin)
):
    """
    Get detailed risk score for a specific vehicle.
    Vehicle ID can be track_id or plate number.
    """
    # Try to find by track_id
    try:
        track_id = int(vehicle_id)
        if track_id in _vehicle_behaviors:
            behavior = _vehicle_behaviors[track_id]
            recent_speeds = list(behavior.speeds)[-5:]
            current_speed = (sum(recent_speeds) / len(recent_speeds) * 0.5) if recent_speeds else 0
            
            return await calculate_risk_score(
                vehicle_id=vehicle_id,
                track_id=track_id,
                current_speed=current_speed,
            )
    except ValueError:
        pass
    
    # Try to find by plate number
    for track_id, behavior in _vehicle_behaviors.items():
        # Check if plate matches (would need to store plate in behavior)
        pass
    
    # Calculate based on history only (vehicle not currently tracked)
    return await calculate_risk_score(
        vehicle_id=vehicle_id,
        track_id=0,
        current_speed=0,
        plate_number=vehicle_id,
    )


@router.get("/high-risk-vehicles", summary="Get vehicles above risk threshold")
async def get_high_risk_vehicles_endpoint(
    threshold: float = Query(60.0, ge=0, le=100),
    user: UserInfo = Depends(get_current_admin)
):
    """
    Get all vehicles with risk score above the specified threshold.
    Default threshold is 60 (HIGH risk level).
    """
    all_scores = await get_current_risk_scores(limit=200, user=user)
    
    high_risk = [
        s for s in all_scores.scores
        if s.risk_score >= threshold
    ]
    
    # Also include behavior-based high risk
    behavior_high_risk = get_high_risk_vehicles_behavior()
    
    return {
        "threshold": threshold,
        "count": len(high_risk),
        "vehicles": high_risk,
        "behavior_alerts": behavior_high_risk,
    }


@router.get("/behavior-log", summary="Get abnormal behavior history")
async def get_behavior_log_endpoint(
    limit: int = Query(50, ge=1, le=200),
    behavior_type: Optional[str] = Query(None, description="Filter by type: sudden_stop, harsh_brake, lane_drift"),
    user: UserInfo = Depends(get_current_admin)
):
    """
    Get recent abnormal behavior events.
    These events contribute to the violation history factor in risk scoring.
    
    Behavior types:
    - sudden_stop: >50% speed reduction in <2 seconds
    - harsh_brake: Deceleration >8 m/s²
    - lane_drift: Consistent movement toward lane edges
    - wrong_way: Movement opposite to expected flow
    """
    # Try in-memory events first
    events = get_recent_behavior_events(limit=limit)
    
    # If in-memory is empty, fall back to Firestore
    if not events:
        try:
            db = get_db()
            query = db.collection(Collections.ABNORMAL_BEHAVIOR).order_by(
                "timestamp", direction="DESCENDING"
            ).limit(limit)
            
            async for doc in query.stream():
                data = doc.to_dict()
                events.append({
                    'vehicle_id': data.get('vehicle_id', 0),
                    'behavior_type': data.get('behavior_type', 'unknown'),
                    'severity': data.get('severity', 'medium'),
                    'plate_number': data.get('plate_number'),
                    'details': data.get('details', {}),
                    'timestamp': data.get('timestamp', ''),
                })
        except Exception as e:
            print(f"[RISK] Failed to fetch behavior log from Firestore: {e}")
    
    if behavior_type:
        events = [e for e in events if e.get('behavior_type') == behavior_type]
    
    # Group by severity
    severity_counts = {'low': 0, 'medium': 0, 'high': 0, 'critical': 0}
    for e in events:
        sev = e.get('severity', 'medium')
        if sev in severity_counts:
            severity_counts[sev] += 1
    
    return {
        "total_events": len(events),
        "severity_breakdown": severity_counts,
        "events": events,
    }


@router.get("/stats", summary="Get risk analytics statistics")
async def get_risk_stats(
    user: UserInfo = Depends(get_current_admin)
):
    """
    Get aggregated risk statistics for dashboard analytics.
    """
    all_scores = await get_current_risk_scores(limit=200, user=user)
    events = get_recent_behavior_events(limit=100)
    
    # If in-memory + sync fallback returned nothing, try async Firestore
    if not events:
        try:
            db = get_db()
            query = db.collection(Collections.ABNORMAL_BEHAVIOR).order_by(
                "timestamp", direction="DESCENDING"
            ).limit(100)
            async for doc in query.stream():
                data = doc.to_dict()
                events.append({
                    'vehicle_id': data.get('vehicle_id', 0),
                    'behavior_type': data.get('behavior_type', 'unknown'),
                    'severity': data.get('severity', 'medium'),
                    'plate_number': data.get('plate_number'),
                    'details': data.get('details', {}),
                    'timestamp': data.get('timestamp', ''),
                })
        except Exception as e:
            print(f"[RISK] Stats: Failed async behavior load: {e}")
    
    # Behavior type breakdown
    behavior_types = {}
    for e in events:
        bt = e.get('behavior_type', 'unknown')
        behavior_types[bt] = behavior_types.get(bt, 0) + 1
    
    return {
        "summary": {
            "total_vehicles_tracked": all_scores.total_vehicles,
            "high_risk_count": all_scores.high_risk_count,
            "average_risk_score": all_scores.average_risk_score,
        },
        "risk_distribution": all_scores.risk_distribution,
        "behavior_events_count": len(events),
        "behavior_types": behavior_types,
        "formula": "Risk_Score = (Speed_Factor × 0.6) + (Violation_History_Factor × 0.4)",
    }
