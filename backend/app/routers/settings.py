"""
Admin Settings API Router
Manages configurable system settings for fines, penalties, and detection thresholds.
"""

from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.config import get_settings
from app.db.firestore_client import get_db, Collections
from app.routers.auth import get_current_admin, UserInfo
from app.parking.dynamic_fine import get_fine_calculator

settings = get_settings()
router = APIRouter(prefix="/settings", tags=["System Settings"])


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class ViolationPenaltySettings(BaseModel):
    """Settings for a single violation type."""
    points: int = Field(ge=0, le=100, description="Points deducted from driver score")
    fine: float = Field(ge=0, description="Fine amount in LKR")
    severity: str = Field(description="Severity level: low, medium, high, critical")


class FineSettings(BaseModel):
    """Fine configuration settings."""
    parking_no_parking: ViolationPenaltySettings = ViolationPenaltySettings(points=10, fine=2500.0, severity="medium")
    parking_no_stopping: ViolationPenaltySettings = ViolationPenaltySettings(points=10, fine=2500.0, severity="medium")
    parking_overtime: ViolationPenaltySettings = ViolationPenaltySettings(points=5, fine=1500.0, severity="low")
    parking_handicap: ViolationPenaltySettings = ViolationPenaltySettings(points=10, fine=5000.0, severity="high")
    parking_loading: ViolationPenaltySettings = ViolationPenaltySettings(points=10, fine=2000.0, severity="low")
    speeding: ViolationPenaltySettings = ViolationPenaltySettings(points=8, fine=5000.0, severity="medium")
    red_light: ViolationPenaltySettings = ViolationPenaltySettings(points=25, fine=10000.0, severity="high")
    wrong_way: ViolationPenaltySettings = ViolationPenaltySettings(points=20, fine=15000.0, severity="critical")
    lane_weaving: ViolationPenaltySettings = ViolationPenaltySettings(points=10, fine=3500.0, severity="medium")


class JunctionSafetySettings(BaseModel):
    """Junction safety scoring settings."""
    initial_score: int = Field(default=100, ge=0, le=100)
    min_score: int = Field(default=0, ge=0, le=100)
    max_score: int = Field(default=100, ge=0, le=100)
    score_decay_rate: float = Field(default=0.1, ge=0, le=1.0, description="Score recovery per second")
    lane_weaving_penalty: int = Field(default=5, ge=0, le=50)
    wrong_way_penalty: int = Field(default=20, ge=0, le=50)
    speeding_penalty: int = Field(default=8, ge=0, le=50)
    parking_violation_penalty: int = Field(default=10, ge=0, le=50)
    running_red_light_penalty: int = Field(default=25, ge=0, le=50)
    tailgating_penalty: int = Field(default=3, ge=0, le=50)


class DetectionSettings(BaseModel):
    """Detection thresholds and settings."""
    speed_limit: float = Field(default=60.0, ge=0, description="Speed limit in km/h")
    stop_line_y_position: int = Field(default=400, ge=0, description="Stop line Y position in pixels")
    yellow_light_duration: float = Field(default=3.0, ge=1.0, le=10.0, description="Yellow light duration in seconds")
    x_velocity_threshold: float = Field(default=15.0, ge=1.0, description="Lane weaving detection threshold")
    direction_changes_threshold: int = Field(default=3, ge=1, description="Min direction changes for weaving")
    wrong_way_angle_threshold: int = Field(default=120, ge=90, le=180, description="Wrong-way angle threshold in degrees")


class ParkingSettings(BaseModel):
    """Parking violation settings based on proposal formula: Base + (Duration × Rate) + (Traffic Impact × Cost)."""
    grace_period_seconds: int = Field(default=30, ge=0, description="Grace period before violation (seconds)")
    duration_rate_per_minute: float = Field(default=100.0, ge=0, description="Fine rate per minute over limit (LKR)")
    traffic_impact_cost: float = Field(default=500.0, ge=0, description="Cost multiplier for traffic impact")
    max_duration_penalty: float = Field(default=10000.0, ge=0, description="Maximum duration penalty (LKR)")


class SystemSettings(BaseModel):
    """Complete system settings."""
    fines: FineSettings = Field(default_factory=FineSettings)
    junction_safety: JunctionSafetySettings = Field(default_factory=JunctionSafetySettings)
    detection: DetectionSettings = Field(default_factory=DetectionSettings)
    parking: ParkingSettings = Field(default_factory=ParkingSettings)
    updated_at: Optional[str] = None
    updated_by: Optional[str] = None


# =============================================================================
# DEFAULT SETTINGS
# =============================================================================

DEFAULT_SETTINGS = SystemSettings()


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

async def get_system_settings() -> SystemSettings:
    """Get current system settings from Firestore or return defaults."""
    db = get_db()
    doc_ref = db.collection(Collections.SETTINGS).document("system")
    doc = await doc_ref.get()
    
    if doc.exists:
        data = doc.to_dict()
        return SystemSettings(**data)
    
    return DEFAULT_SETTINGS


async def save_system_settings(settings: SystemSettings, updated_by: str) -> SystemSettings:
    """Save system settings to Firestore and update all related services."""
    db = get_db()
    doc_ref = db.collection(Collections.SETTINGS).document("system")
    
    settings.updated_at = datetime.utcnow().isoformat()
    settings.updated_by = updated_by
    
    await doc_ref.set(settings.model_dump())
    
    # Update the dynamic fine calculator with new settings
    fine_calculator = get_fine_calculator()
    fine_calculator.update_from_settings(settings.model_dump())
    print(f"[Settings] Dynamic fine calculator updated by {updated_by}")
    
    # Update lane weaving service settings (junction safety penalties)
    try:
        from app.services.lane_weaving_service import update_from_settings as update_lane_weaving
        update_lane_weaving(settings.model_dump())
        print(f"[Settings] Lane weaving service updated by {updated_by}")
    except Exception as e:
        print(f"[Settings] Failed to update lane weaving service: {e}")
    
    # Update behavior detection service thresholds
    try:
        from app.services.behavior_service import update_from_settings as update_behavior
        update_behavior(settings.model_dump())
        print(f"[Settings] Behavior detection service updated by {updated_by}")
    except Exception as e:
        print(f"[Settings] Failed to update behavior detection service: {e}")
    
    # Update detection speed limits (speeding threshold and risk speed limit)
    try:
        from app.detection.yolo_detector import update_detection_settings
        update_detection_settings(settings.model_dump())
        print(f"[Settings] Detection thresholds updated by {updated_by}")
    except Exception as e:
        print(f"[Settings] Failed to update detection settings: {e}")
    
    # Update scoring engine violation penalties (fines and points)
    try:
        from app.scoring.scoring import update_penalties_from_settings
        update_penalties_from_settings(settings.model_dump())
        print(f"[Settings] Scoring penalties updated by {updated_by}")
    except Exception as e:
        print(f"[Settings] Failed to update scoring penalties: {e}")
    
    return settings


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.get("", response_model=SystemSettings, summary="Get all system settings")
async def get_settings_endpoint(user: UserInfo = Depends(get_current_admin)):
    """Get all configurable system settings."""
    return await get_system_settings()


@router.put("", response_model=SystemSettings, summary="Update all system settings")
async def update_settings_endpoint(
    new_settings: SystemSettings,
    user: UserInfo = Depends(get_current_admin)
):
    """Update all system settings (admin only)."""
    return await save_system_settings(new_settings, user.identifier)


@router.get("/fines", response_model=FineSettings, summary="Get fine settings")
async def get_fine_settings(user: UserInfo = Depends(get_current_admin)):
    """Get fine/penalty settings for all violation types."""
    settings = await get_system_settings()
    return settings.fines


@router.put("/fines", response_model=FineSettings, summary="Update fine settings")
async def update_fine_settings(
    fines: FineSettings,
    user: UserInfo = Depends(get_current_admin)
):
    """Update fine/penalty settings."""
    current = await get_system_settings()
    current.fines = fines
    await save_system_settings(current, user.identifier)
    return fines


@router.get("/junction-safety", response_model=JunctionSafetySettings, summary="Get junction safety settings")
async def get_junction_safety_settings(user: UserInfo = Depends(get_current_admin)):
    """Get junction safety scoring settings."""
    settings = await get_system_settings()
    return settings.junction_safety


@router.put("/junction-safety", response_model=JunctionSafetySettings, summary="Update junction safety settings")
async def update_junction_safety_settings(
    junction_safety: JunctionSafetySettings,
    user: UserInfo = Depends(get_current_admin)
):
    """Update junction safety scoring settings."""
    current = await get_system_settings()
    current.junction_safety = junction_safety
    await save_system_settings(current, user.identifier)
    return junction_safety


@router.get("/detection", response_model=DetectionSettings, summary="Get detection settings")
async def get_detection_settings(user: UserInfo = Depends(get_current_admin)):
    """Get detection thresholds and settings."""
    settings = await get_system_settings()
    return settings.detection


@router.put("/detection", response_model=DetectionSettings, summary="Update detection settings")
async def update_detection_settings(
    detection: DetectionSettings,
    user: UserInfo = Depends(get_current_admin)
):
    """Update detection thresholds."""
    current = await get_system_settings()
    current.detection = detection
    await save_system_settings(current, user.identifier)
    return detection


@router.get("/parking", response_model=ParkingSettings, summary="Get parking settings")
async def get_parking_settings(user: UserInfo = Depends(get_current_admin)):
    """Get parking violation settings."""
    settings = await get_system_settings()
    return settings.parking


@router.put("/parking", response_model=ParkingSettings, summary="Update parking settings")
async def update_parking_settings(
    parking: ParkingSettings,
    user: UserInfo = Depends(get_current_admin)
):
    """Update parking violation settings."""
    current = await get_system_settings()
    current.parking = parking
    await save_system_settings(current, user.identifier)
    return parking


@router.post("/reset", response_model=SystemSettings, summary="Reset to default settings")
async def reset_settings(user: UserInfo = Depends(get_current_admin)):
    """Reset all settings to default values."""
    default = SystemSettings()
    return await save_system_settings(default, user.identifier)


# =============================================================================
# INITIALIZATION (Called at startup)
# =============================================================================

async def initialize_fine_calculator():
    """
    Load settings from database and initialize all detection services.
    Called at server startup.
    """
    try:
        loaded_settings = await get_system_settings()
        
        # Initialize dynamic fine calculator
        fine_calculator = get_fine_calculator()
        fine_calculator.update_from_settings(loaded_settings.model_dump())
        print("[Settings] ✅ Dynamic fine calculator initialized from database")
        print(f"[Settings]    Grace period: {fine_calculator.params.grace_period_seconds}s")
        print(f"[Settings]    Duration rate: LKR {fine_calculator.params.duration_rate:.2f}/sec")
        print(f"[Settings]    Traffic multiplier: LKR {fine_calculator.params.traffic_multiplier:.0f}/vehicle")
        
        # Initialize lane weaving service (junction safety penalties)
        try:
            from app.services.lane_weaving_service import update_from_settings as update_lane_weaving
            update_lane_weaving(loaded_settings.model_dump())
            print("[Settings] ✅ Lane weaving service initialized from database")
        except Exception as e:
            print(f"[Settings] ⚠️ Failed to initialize lane weaving service: {e}")
        
        # Initialize behavior detection service thresholds
        try:
            from app.services.behavior_service import update_from_settings as update_behavior
            update_behavior(loaded_settings.model_dump())
            print("[Settings] ✅ Behavior detection service initialized from database")
        except Exception as e:
            print(f"[Settings] ⚠️ Failed to initialize behavior detection service: {e}")
        
        # Initialize detection thresholds (speed limit, speeding threshold)
        try:
            from app.detection.yolo_detector import update_detection_settings
            update_detection_settings(loaded_settings.model_dump())
            print("[Settings] ✅ Detection thresholds initialized from database")
        except Exception as e:
            print(f"[Settings] ⚠️ Failed to initialize detection settings: {e}")
        
        # Initialize scoring engine penalties (fines and points)
        try:
            from app.scoring.scoring import update_penalties_from_settings
            update_penalties_from_settings(loaded_settings.model_dump())
            print("[Settings] ✅ Scoring penalties initialized from database")
        except Exception as e:
            print(f"[Settings] ⚠️ Failed to initialize scoring penalties: {e}")
            
    except Exception as e:
        print(f"[Settings] ⚠️ Failed to load settings, using defaults: {e}")
