 """
Intelligent Traffic Management System - Parking Violation Detection
Detects vehicles parked illegally in no-parking zones using ROI polygons and dwell-time tracking.
"""

import time
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any
from datetime import datetime
from enum import Enum

import cv2
import numpy as np

from app.detection.yolo_detector import Detection


class ZoneType(str, Enum):
    """Type of parking zone."""
    NO_PARKING = "no_parking"        # Illegal to stop at all
    NO_STOPPING = "no_stopping"      # Illegal to even stop briefly
    LIMITED_PARKING = "limited"      # Time-limited parking (e.g., 15 min)
    HANDICAP = "handicap"            # Handicap-only parking
    LOADING = "loading"              # Loading zone (commercial vehicles)


@dataclass
class ParkingZone:
    """
    Defines a parking zone with a polygon boundary.
    
    Attributes:
        zone_id: Unique identifier for this zone
        name: Human-readable name (e.g., "Main St No Parking")
        polygon: List of (x, y) points defining the zone boundary
        zone_type: Type of parking restriction
        max_duration_sec: Maximum allowed parking duration (0 = no parking allowed)
