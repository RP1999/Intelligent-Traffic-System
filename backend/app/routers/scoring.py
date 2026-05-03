"""
FastAPI router for driver scoring endpoints.
Provides API for driver lookup, score history, leaderboard, and statistics.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from datetime import datetime

from app.scoring import (
    get_scoring_engine,
    ViolationType,
    VIOLATION_PENALTIES,
    parking_zone_to_violation_type,
)
from app.db.database import (
    insert_driver,
    get_driver,
    list_drivers,
    update_driver_score,
    delete_driver,
    insert_driver_violation,
    list_driver_violations,
    get_driver_statistics,
)

router = APIRouter(prefix="/scoring", tags=["scoring"])


# ----------------------- Pydantic Models -----------------------
class ViolationInput(BaseModel):
    """Input for recording a violation."""
    violation_type: str  # ViolationType value
    location: Optional[str] = None
    license_plate: Optional[str] = None
    snapshot_path: Optional[str] = None
    notes: str = ""


class DriverResponse(BaseModel):
    """Response model for driver data."""
    driver_id: str
    current_score: int
    risk_level: str
    total_violations: int
    total_fines: float
    created_at: str
    updated_at: str


class ViolationResponse(BaseModel):
    """Response model for violation data."""
    violation_id: str
    driver_id: str
    violation_type: str
    timestamp: str
    location: Optional[str]
    points_deducted: int
    fine_amount: float
    license_plate: Optional[str]
    snapshot_path: Optional[str]
    notes: str


# ----------------------- Helper Functions -----------------------
def get_risk_level(score: int) -> str:
    """Get risk level from score."""
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


def format_driver(d: dict) -> dict:
    """Format driver dict for response."""
    return {
        "driver_id": d["driver_id"],
        "current_score": d["current_score"],
        "risk_level": get_risk_level(d["current_score"]),
        "total_violations": d["total_violations"],
        "total_fines": round(d["total_fines"], 2),
        "created_at": datetime.fromtimestamp(d["created_at"]).isoformat() if d.get("created_at") else None,
        "updated_at": datetime.fromtimestamp(d["updated_at"]).isoformat() if d.get("updated_at") else None,
    }


def format_violation(v: dict) -> dict:
    """Format violation dict for response."""
    return {
        "violation_id": v["violation_id"],
        "driver_id": v["driver_id"],
        "violation_type": v["violation_type"],
        "timestamp": datetime.fromtimestamp(v["timestamp"]).isoformat() if v.get("timestamp") else None,
        "location": v.get("location"),
        "points_deducted": v["points_deducted"],
        "fine_amount": round(v["fine_amount"], 2),
        "license_plate": v.get("license_plate"),
        "snapshot_path": v.get("snapshot_path"),
        "notes": v.get("notes", ""),
    }


# ----------------------- Endpoints -----------------------

@router.get("/drivers", summary="List all drivers")
async def get_all_drivers(
    limit: int = Query(100, ge=1, le=1000),
    order_by: str = Query("current_score", regex="^(current_score|total_violations|total_fines|created_at|updated_at|driver_id)$"),
    ascending: bool = Query(False),
):
    """
    List all drivers with optional sorting.
    
    - **limit**: Maximum number of drivers to return
    - **order_by**: Field to sort by (current_score, total_violations, total_fines, created_at, updated_at, driver_id)
    - **ascending**: Sort in ascending order if True
    """
    drivers = await list_drivers(limit=limit, order_by=order_by, ascending=ascending)
    return {
        "drivers": [format_driver(d) for d in drivers],
        "count": len(drivers),
    }


@router.get("/drivers/{driver_id}", summary="Get driver by ID")
async def get_driver_by_id(driver_id: str):
    """Get a specific driver's score and details."""
    driver = await get_driver(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail=f"Driver '{driver_id}' not found")
    
    # Get violation history
    violations = await list_driver_violations(driver_id, limit=20)
    
    return {
        "driver": format_driver(driver),
        "recent_violations": [format_violation(v) for v in violations],
    }


@router.get("/drivers/{driver_id}/violations", summary="Get driver violations")
async def get_driver_violation_history(
    driver_id: str,
    limit: int = Query(50, ge=1, le=500),
):
    """Get violation history for a specific driver."""
    driver = await get_driver(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail=f"Driver '{driver_id}' not found")
    
    violations = await list_driver_violations(driver_id, limit=limit)
    return {
        "driver_id": driver_id,
        "violations": [format_violation(v) for v in violations],
        "count": len(violations),
    }


@router.post("/drivers/{driver_id}/penalize", summary="Record a violation")
async def penalize_driver(driver_id: str, violation: ViolationInput):
    """
    Record a violation and penalize the driver.
    
    This will:
    1. Create the driver if they don't exist
    2. Apply the penalty (deduct points, add fine)
    3. Record the violation in history
    """
    import time
    
    # Validate violation type
    try:
        vio_type = ViolationType(violation.violation_type)
    except ValueError:
        valid_types = [v.value for v in ViolationType]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid violation_type. Valid types: {valid_types}"
        )
    
    # Get penalty info
    penalty = VIOLATION_PENALTIES.get(vio_type, {"points": 5, "fine": 50.0})
    points = penalty["points"]
    fine = penalty["fine"]
    
    # Get or create driver
    engine = get_scoring_engine()
    driver_score = engine.get_or_create_driver(driver_id)
    
    # Apply violation
    driver_score, record = engine.record_violation(
        driver_id=driver_id,
        violation_type=vio_type,
        location=violation.location,
        license_plate=violation.license_plate,
        snapshot_path=violation.snapshot_path,
        notes=violation.notes,
    )
    
    # Persist to database
    await insert_driver(
        driver_id=driver_id,
        current_score=driver_score.current_score,
        total_violations=driver_score.total_violations,
        total_fines=driver_score.total_fines,
        created_at=driver_score.created_at,
        updated_at=driver_score.updated_at,
    )
    
    await insert_driver_violation(
        violation_id=record.violation_id,
        driver_id=driver_id,
        violation_type=vio_type.value,
        timestamp=record.timestamp,
        location=record.location,
        points_deducted=record.points_deducted,
        fine_amount=record.fine_amount,
        license_plate=record.license_plate,
        snapshot_path=record.snapshot_path,
        notes=record.notes,
    )
    
    return {
        "message": f"Violation recorded for driver {driver_id}",
        "violation": record.to_dict(),
        "driver": driver_score.to_dict(),
    }


@router.delete("/drivers/{driver_id}", summary="Delete a driver")
async def remove_driver(driver_id: str):
    """Delete a driver and their violation history."""
    driver = await get_driver(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail=f"Driver '{driver_id}' not found")
    
    await delete_driver(driver_id)
    
    # Also remove from in-memory engine
    engine = get_scoring_engine()
    if driver_id in engine.drivers:
        del engine.drivers[driver_id]
    
    return {"message": f"Driver '{driver_id}' deleted", "driver_id": driver_id}


@router.get("/leaderboard", summary="Get driver leaderboard")
async def get_leaderboard(
    limit: int = Query(10, ge=1, le=100),
    worst: bool = Query(False, description="If True, show worst drivers instead of best"),
):
    """
    Get driver leaderboard sorted by score.
    
    - **limit**: Number of drivers to return
    - **worst**: If True, show lowest scores first (high-risk drivers)
    """
    drivers = await list_drivers(limit=limit, order_by="current_score", ascending=worst)
    
    return {
        "type": "worst" if worst else "best",
        "leaderboard": [
            {
                "rank": i + 1,
                **format_driver(d),
            }
            for i, d in enumerate(drivers)
        ],
        "count": len(drivers),
    }


@router.get("/high-risk", summary="Get high-risk drivers")
async def get_high_risk_drivers(
    threshold: int = Query(50, ge=0, le=100),
    limit: int = Query(50, ge=1, le=200),
):
    """
    Get drivers with scores below the threshold.
    
    - **threshold**: Score threshold (drivers with score < threshold are returned)
    - **limit**: Maximum number of drivers to return
    """
    # Get all drivers sorted by score ascending
    all_drivers = await list_drivers(limit=limit * 2, order_by="current_score", ascending=True)
    
    # Filter by threshold
    high_risk = [d for d in all_drivers if d["current_score"] < threshold][:limit]
    
    return {
        "threshold": threshold,
        "drivers": [format_driver(d) for d in high_risk],
        "count": len(high_risk),
    }


@router.get("/stats", summary="Get scoring statistics")
async def get_scoring_stats():
    """Get overall driver scoring statistics."""
    stats = await get_driver_statistics()
    return stats


@router.get("/violation-types", summary="Get violation types and penalties")
async def get_violation_types():
    """Get all violation types with their penalties."""
    return {
        "violation_types": [
            {
                "type": vio_type.value,
                "points": info["points"],
                "fine": info["fine"],
                "severity": info["severity"],
            }
            for vio_type, info in VIOLATION_PENALTIES.items()
        ]
    }


@router.post("/reset", summary="Reset all driver scores")
async def reset_all_scores():
    """
    Reset all driver scores (development/testing only).
    This clears all drivers and violations from memory and database.
    """
    # Clear in-memory engine
    engine = get_scoring_engine()
    engine.reset()
    
    # We won't delete from DB by default - just reset in-memory state
    # Add db_clear parameter if needed later
    
    return {"message": "Scoring engine reset (in-memory). Database records preserved."}


@router.post("/sync", summary="Sync in-memory scores to database")
async def sync_to_database():
    """
    Sync all in-memory driver scores to the database.
    Useful after batch operations or before shutdown.
    """
    engine = get_scoring_engine()
    synced = 0
    
    for driver_id, driver in engine.drivers.items():
        await insert_driver(
            driver_id=driver_id,
            current_score=driver.current_score,
            total_violations=driver.total_violations,
            total_fines=driver.total_fines,
            created_at=driver.created_at,
            updated_at=driver.updated_at,
        )
        synced += 1
    
    return {"message": f"Synced {synced} drivers to database", "synced_count": synced}


@router.post("/load", summary="Load scores from database to memory")
async def load_from_database():
    """
    Load driver scores from database into memory.
    Useful on startup or after manual database changes.
    """
    engine = get_scoring_engine()
    drivers = await list_drivers(limit=10000)
    
    loaded = 0
    for d in drivers:
        from app.scoring import DriverScore
        engine.drivers[d["driver_id"]] = DriverScore(
            driver_id=d["driver_id"],
            current_score=d["current_score"],
            total_violations=d["total_violations"],
            total_fines=d["total_fines"],
            created_at=d["created_at"] or 0,
            updated_at=d["updated_at"] or 0,
        )
        loaded += 1
    
    return {"message": f"Loaded {loaded} drivers from database", "loaded_count": loaded}
