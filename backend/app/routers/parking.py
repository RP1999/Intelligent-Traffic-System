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
