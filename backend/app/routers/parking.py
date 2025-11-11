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
                
