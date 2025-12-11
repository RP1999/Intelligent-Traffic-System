"""
Intelligent Traffic Management System - Driver Scoring Module
Tracks driver behavior, calculates risk scores, and applies violation penalties.
"""

import time
import sqlite3
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum

from app.config import get_settings

settings = get_settings()

# Database path for persistence
DB_PATH = Path(__file__).parent.parent.parent / "traffic.db"


class ViolationType(str, Enum):
    """Types of traffic violations."""
    PARKING_NO_PARKING = "parking_no_parking"
    PARKING_NO_STOPPING = "parking_no_stopping"
    PARKING_OVERTIME = "parking_overtime"
    PARKING_HANDICAP = "parking_handicap"
    PARKING_LOADING = "parking_loading"
    SPEEDING = "speeding"
    RED_LIGHT = "red_light"
    WRONG_WAY = "wrong_way"
    LANE_VIOLATION = "lane_violation"
    RECKLESS_DRIVING = "reckless_driving"


# Violation severity and penalty points (aligned with LiveSafeScore spec)
VIOLATION_PENALTIES = {
    ViolationType.PARKING_NO_PARKING: {"points": 10, "fine": 100.0, "severity": "medium"},
    ViolationType.PARKING_NO_STOPPING: {"points": 10, "fine": 100.0, "severity": "medium"},
    ViolationType.PARKING_OVERTIME: {"points": 5, "fine": 50.0, "severity": "low"},
    ViolationType.PARKING_HANDICAP: {"points": 10, "fine": 200.0, "severity": "high"},
    ViolationType.PARKING_LOADING: {"points": 10, "fine": 75.0, "severity": "low"},
    ViolationType.SPEEDING: {"points": 8, "fine": 150.0, "severity": "medium"},
    ViolationType.RED_LIGHT: {"points": 25, "fine": 300.0, "severity": "high"},
    ViolationType.WRONG_WAY: {"points": 20, "fine": 500.0, "severity": "critical"},
    ViolationType.LANE_VIOLATION: {"points": 5, "fine": 80.0, "severity": "low"},
    ViolationType.RECKLESS_DRIVING: {"points": 25, "fine": 1000.0, "severity": "critical"},
}


@dataclass
class ViolationRecord:
    """Record of a single violation event."""
    violation_id: str
    driver_id: str
    violation_type: ViolationType
    timestamp: float
    location: Optional[str] = None
    points_deducted: int = 0
    fine_amount: float = 0.0
    license_plate: Optional[str] = None
    snapshot_path: Optional[str] = None
    notes: str = ""
    
    def to_dict(self) -> dict:
        return {
            "violation_id": self.violation_id,
            "driver_id": self.driver_id,
            "violation_type": self.violation_type.value,
            "timestamp": datetime.fromtimestamp(self.timestamp).isoformat(),
            "location": self.location,
            "points_deducted": self.points_deducted,
