"""
Intelligent Traffic Management System - Parking API Router
Endpoints for managing parking zones and violations.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.config import get_settings
from app.parking.parking_detector import (
    ParkingZone,
    ParkingViolation,
    ParkingDetector,
    ZoneType,
    create_sample_zones,
)
from app.db.database import (
    insert_violation,
    insert_zone,
    delete_zone as db_delete_zone,
    list_zones as db_list_zones,
    list_violations as db_list_violations,
    get_violation as db_get_violation,
    insert_driver,
    insert_driver_violation,
    schedule_coroutine,
)
from app.scoring import (
    get_scoring_engine,
    parking_zone_to_violation_type,
)

settings = get_settings()
router = APIRouter(prefix="/parking", tags=["Parking"])

# Global parking detector instance (shared across requests)
_detector: Optional[ParkingDetector] = None


async def get_detector() -> ParkingDetector:
    """Get or create the global parking detector instance."""
    global _detector
    if _detector is None:
        # Attempt to load zones from DB
        zones = await db_list_zones()
        if not zones:
            # Initialize with sample zones for demo and persist them
            zones = create_sample_zones(1280, 720)
            for z in zones:
                schedule_coroutine(insert_zone(z))

        # Violation callback: persist to DB and apply driver scoring
        def _violation_callback(v: ParkingViolation):
            try:
                # 1. Persist parking violation to DB
                schedule_coroutine(insert_violation(v))
                
                # 2. Apply driver scoring
                # Use license plate if available, otherwise use track_id as driver_id
                driver_id = v.license_plate if v.license_plate else f"TRACK-{v.track_id}"
                
                # Map zone type to violation type
                vio_type = parking_zone_to_violation_type(v.zone_type.value if v.zone_type else "no_parking")
                
                # Get scoring engine and record violation
                engine = get_scoring_engine()
                driver_score, vio_record = engine.record_violation(
                    driver_id=driver_id,
                    violation_type=vio_type,
                    location=v.zone_name,
                    license_plate=v.license_plate,
                    snapshot_path=v.snapshot_path,
                    notes=f"Parking violation in {v.zone_name} for {v.duration_sec:.1f}s",
                )
                
                # 3. Persist driver score update to DB
                async def _persist_driver():
                    await insert_driver(
                        driver_id=driver_id,
                        current_score=driver_score.current_score,
                        total_violations=driver_score.total_violations,
                        total_fines=driver_score.total_fines,
                        created_at=driver_score.created_at,
                        updated_at=driver_score.updated_at,
                    )
                    await insert_driver_violation(
                        violation_id=vio_record.violation_id,
                        driver_id=driver_id,
                        violation_type=vio_type.value,
                        timestamp=vio_record.timestamp,
                        location=vio_record.location,
                        points_deducted=vio_record.points_deducted,
                        fine_amount=vio_record.fine_amount,
                        license_plate=vio_record.license_plate,
                        snapshot_path=vio_record.snapshot_path,
                        notes=vio_record.notes,
                    )
                
                schedule_coroutine(_persist_driver())
                
                print(f"⚠️ Violation scored: {driver_id} → Score: {driver_score.current_score} ({driver_score.risk_level})")
                
            except Exception as e:
                print(f"Error in violation callback: {e}")

        _detector = ParkingDetector(
            zones=zones,
            min_overlap=settings.parking_min_overlap,
            violation_callback=_violation_callback,
        )
    return _detector


# =============================================================================
# Pydantic models for request/response
# =============================================================================

class ZoneCreate(BaseModel):
    """Request model for creating a parking zone."""
    zone_id: str
    name: str
    polygon: List[List[int]]  # List of [x, y] points
    zone_type: str = "no_parking"
    max_duration_sec: float = 0.0
    color: List[int] = [0, 0, 255]  # BGR
    active: bool = True


class ZoneResponse(BaseModel):
    """Response model for a parking zone."""
    zone_id: str
    name: str
    polygon: List[List[int]]
    zone_type: str
    max_duration_sec: float
    active: bool


class ViolationResponse(BaseModel):
    """Response model for a parking violation."""
    violation_id: str
    track_id: int
    zone_id: str
    zone_name: str
    zone_type: str
    start_time: str
    end_time: Optional[str]
    duration_sec: float
    license_plate: Optional[str]
    snapshot_path: Optional[str]
    fine_amount: float
    status: str


class ZoneStatsResponse(BaseModel):
    """Response model for zone statistics."""
    zone_id: str
    name: str
    type: str
    vehicles_currently: int
    total_violations: int
    active: bool


# =============================================================================
# Zone Management Endpoints
# =============================================================================

@router.get("/zones", response_model=List[ZoneResponse])
async def list_zones():
    """List all parking zones."""
    detector = await get_detector()
    # Prefer DB-backed zones if available
    try:
        db_zones = await db_list_zones()
        if db_zones:
            zones = db_zones
        else:
            zones = detector.get_zones()
    except Exception:
        zones = detector.get_zones()
    return [
        ZoneResponse(
            zone_id=z.zone_id,
            name=z.name,
            polygon=[list(p) for p in z.polygon],
            zone_type=z.zone_type.value,
            max_duration_sec=z.max_duration_sec,
            active=z.active,
        )
        for z in zones
    ]


@router.get("/zones/{zone_id}", response_model=ZoneResponse)
async def get_zone(zone_id: str):
    """Get a specific parking zone."""
    detector = await get_detector()
    if zone_id not in detector.zones:
        raise HTTPException(status_code=404, detail=f"Zone not found: {zone_id}")
    
    z = detector.zones[zone_id]
    return ZoneResponse(
        zone_id=z.zone_id,
        name=z.name,
        polygon=[list(p) for p in z.polygon],
        zone_type=z.zone_type.value,
        max_duration_sec=z.max_duration_sec,
        active=z.active,
    )


@router.post("/zones", response_model=ZoneResponse)
async def create_zone(zone: ZoneCreate):
    """Create a new parking zone."""
    detector = await get_detector()
    
    if zone.zone_id in detector.zones:
        raise HTTPException(status_code=400, detail=f"Zone already exists: {zone.zone_id}")
    
    try:
        zone_type = ZoneType(zone.zone_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid zone_type. Must be one of: {[t.value for t in ZoneType]}"
        )
    
    new_zone = ParkingZone(
        zone_id=zone.zone_id,
        name=zone.name,
        polygon=[tuple(p) for p in zone.polygon],
        zone_type=zone_type,
        max_duration_sec=zone.max_duration_sec,
        color=tuple(zone.color),
        active=zone.active,
    )
    
    detector.add_zone(new_zone)
    # Persist to DB
    try:
        await insert_zone(new_zone)
    except Exception:
        pass
    
    return ZoneResponse(
        zone_id=new_zone.zone_id,
        name=new_zone.name,
        polygon=[list(p) for p in new_zone.polygon],
        zone_type=new_zone.zone_type.value,
        max_duration_sec=new_zone.max_duration_sec,
        active=new_zone.active,
    )


@router.delete("/zones/{zone_id}")
async def delete_zone(zone_id: str):
    """Delete a parking zone."""
    detector = await get_detector()
    
    if not detector.remove_zone(zone_id):
        raise HTTPException(status_code=404, detail=f"Zone not found: {zone_id}")
    # remove from DB
    try:
        await db_delete_zone(zone_id)
    except Exception:
        pass
    return {"status": "deleted", "zone_id": zone_id}


@router.patch("/zones/{zone_id}/toggle")
async def toggle_zone(zone_id: str):
    """Toggle a parking zone's active state."""
    detector = await get_detector()
    
    if zone_id not in detector.zones:
        raise HTTPException(status_code=404, detail=f"Zone not found: {zone_id}")
    
    zone = detector.zones[zone_id]
    zone.active = not zone.active
    
    return {"zone_id": zone_id, "active": zone.active}


# =============================================================================
# Violation Endpoints
# =============================================================================

@router.get("/violations", response_model=List[ViolationResponse])
async def list_violations(
    status: Optional[str] = Query(None, description="Filter by status: active, resolved, disputed"),
    zone_id: Optional[str] = Query(None, description="Filter by zone ID"),
    limit: int = Query(100, ge=1, le=1000),
):
    """List parking violations with optional filters."""
    # Prefer persisted violations from DB when possible
    try:
        violations = await db_list_violations(limit=limit)
    except Exception:
        detector = await get_detector()
        violations = detector.get_all_violations()
    
    # Apply filters
    if status:
        violations = [v for v in violations if v.status == status]
    if zone_id:
        violations = [v for v in violations if v.zone_id == zone_id]
    
    # Limit results
    violations = violations[:limit]
    
    return [
        ViolationResponse(**v.to_dict())
        for v in violations
    ]


@router.get("/violations/active", response_model=List[ViolationResponse])
async def list_active_violations():
    """List only active (unresolved) parking violations."""
    try:
        violations = await db_list_violations(limit=1000)
        violations = [v for v in violations if v.status == "active"]
    except Exception:
        detector = await get_detector()
        violations = detector.get_active_violations()
    return [ViolationResponse(**v.to_dict()) for v in violations]


@router.get("/violations/{violation_id}", response_model=ViolationResponse)
async def get_violation(violation_id: str):
    """Get a specific violation by ID."""
    try:
        v = await db_get_violation(violation_id)
        if v:
            return ViolationResponse(**v.to_dict())
    except Exception:
        pass
    detector = await get_detector()
    for v in detector.get_all_violations():
        if v.violation_id == violation_id:
            return ViolationResponse(**v.to_dict())
    
    raise HTTPException(status_code=404, detail=f"Violation not found: {violation_id}")


# =============================================================================
# Statistics Endpoints
# =============================================================================

@router.get("/stats")
async def get_stats():
    """Get overall parking statistics."""
    detector = await get_detector()
    zone_stats = detector.get_zone_stats()
    try:
        violations = await db_list_violations(limit=1000)
    except Exception:
        violations = detector.get_all_violations()
    
    total_fines = sum(v.fine_amount for v in violations)
    
    return {
        "total_zones": len(detector.zones),
        "active_zones": sum(1 for z in detector.zones.values() if z.active),
        "vehicles_tracked": len(detector.tracked_vehicles),
        "total_violations": len(violations),
        "active_violations": len(detector.get_active_violations()),
        "total_fines": round(total_fines, 2),
        "zones": zone_stats,
    }


@router.post("/reset")
async def reset_detector():
    """Reset the parking detector (clear all tracking and violations)."""
    detector = await get_detector()
    detector.reset()
    return {"status": "reset", "message": "Parking detector reset successfully"}
