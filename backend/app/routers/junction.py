"""
Junction Safety Router - API Endpoints
Member 2: LiveSafeScore, Lane Weaving Detection, Community Alerts
"""

from fastapi import APIRouter, HTTPException
from typing import Optional

router = APIRouter(prefix="/junction", tags=["Junction Safety (Member 2)"])


# ============================================================================
# JUNCTION SAFETY ENDPOINTS
# ============================================================================

@router.get("/safety-score", summary="Get current LiveSafeScore")
async def get_safety_score():
    """
    Get the current junction safety score (0-100).
    Higher score = safer junction.
    """
    try:
        from app.services.lane_weaving_service import get_junction_safety
        safety = get_junction_safety()
        return safety.to_dict()
    except ImportError:
        raise HTTPException(status_code=503, detail="Lane weaving service not available")


@router.get("/safety-history", summary="Get safety score history")
async def get_safety_history(hours: int = 24):
    """
    Get junction safety score history over time.
    """
    # For now, return current state - full history requires DB integration
    try:
        from app.services.lane_weaving_service import get_junction_safety
        safety = get_junction_safety()
        return {
            "current": safety.to_dict(),
            "hours_requested": hours,
            "note": "Historical data requires database integration"
        }
    except ImportError:
        raise HTTPException(status_code=503, detail="Service not available")


@router.get("/lane-weaving-events", summary="Get recent lane weaving detections")
async def get_lane_weaving_events(limit: int = 20):
    """
    Get recent lane weaving detection events.
    """
    try:
        from app.services.lane_weaving_service import get_recent_weaving_events
        events = get_recent_weaving_events(limit)
        return {
            "events": events,
            "count": len(events),
        }
    except ImportError:
        raise HTTPException(status_code=503, detail="Service not available")


@router.post("/reset-safety", summary="Reset junction safety score")
async def reset_safety():
    """
    Reset the junction safety score to 100 (for testing/new session).
    """
    try:
        from app.services.lane_weaving_service import reset_junction_safety
        reset_junction_safety()
        return {"status": "reset", "new_score": 100}
    except ImportError:
        raise HTTPException(status_code=503, detail="Service not available")


# ============================================================================
# BEHAVIOR DETECTION ENDPOINTS (Member 4)
# ============================================================================

@router.get("/behavior-events", summary="Get abnormal driving behavior events")
async def get_behavior_events(limit: int = 20):
    """
    Get recent abnormal driving behavior detections:
    - Sudden stops
    - Harsh braking
    - Lane drifting
    """
    try:
        from app.services.behavior_service import get_recent_behavior_events
        events = get_recent_behavior_events(limit)
        return {
            "events": events,
            "count": len(events),
        }
    except ImportError:
        raise HTTPException(status_code=503, detail="Behavior service not available")


@router.get("/high-risk-vehicles", summary="Get vehicles with concerning behavior")
async def get_high_risk_vehicles():
    """
    Get list of vehicles showing multiple concerning behaviors.
    """
    try:
        from app.services.behavior_service import get_high_risk_vehicles
        vehicles = get_high_risk_vehicles()
        return {
            "high_risk_vehicles": vehicles,
            "count": len(vehicles),
        }
    except ImportError:
        raise HTTPException(status_code=503, detail="Behavior service not available")


@router.get("/vehicle/{track_id}/behavior", summary="Get behavior for a specific vehicle")
async def get_vehicle_behavior(track_id: int):
    """
    Get behavior summary for a specific tracked vehicle.
    """
    try:
        from app.services.behavior_service import get_vehicle_behavior
        behavior = get_vehicle_behavior(track_id)
        if behavior is None:
            raise HTTPException(status_code=404, detail=f"No behavior data for vehicle {track_id}")
        return behavior
    except ImportError:
        raise HTTPException(status_code=503, detail="Behavior service not available")


# ============================================================================
# RISK SCORE ENDPOINTS (Member 4)
# ============================================================================

@router.get("/risk/vehicle/{vehicle_id}", summary="Get risk score for a vehicle")
async def get_vehicle_risk(vehicle_id: int, current_speed: float = 50.0, speed_limit: float = 60.0):
    """
    Calculate risk score for a specific vehicle.
    
    Args:
        vehicle_id: The vehicle's tracking ID
        current_speed: Current speed in km/h
        speed_limit: Speed limit for the road
    """
    try:
        from app.services.risk_service import calculate_risk
        result = calculate_risk(vehicle_id, current_speed, speed_limit)
        return result.to_dict()
    except ImportError:
        raise HTTPException(status_code=503, detail="Risk service not available")


# ============================================================================
# FINE CALCULATION ENDPOINTS (Member 1)
# ============================================================================

@router.get("/fine/calculate", summary="Calculate dynamic fine for a violation")
async def calculate_fine(
    violation_type: str = "parking",
    duration_seconds: int = 60,
    vehicle_count_in_frame: int = 5
):
    """
    Calculate dynamic fine based on duration and traffic impact.
    
    Formula: Fine = Base + (Duration × 5) + (Traffic_Impact × 50)
    """
    try:
        from app.services.fine_service import calculate_dynamic_fine
        result = calculate_dynamic_fine(violation_type, duration_seconds, vehicle_count_in_frame)
        return result.to_dict()
    except ImportError:
        raise HTTPException(status_code=503, detail="Fine service not available")
