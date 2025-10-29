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
        color: Display color for visualization (BGR)
        active: Whether this zone is currently being monitored
    """
    zone_id: str
    name: str
    polygon: List[Tuple[int, int]]
    zone_type: ZoneType = ZoneType.NO_PARKING
    max_duration_sec: float = 0.0  # 0 = no parking allowed
    color: Tuple[int, int, int] = (0, 0, 255)  # Red by default
    active: bool = True
    
    def contains_point(self, point: Tuple[int, int]) -> bool:
        """Check if a point is inside the polygon."""
        polygon_np = np.array(self.polygon, dtype=np.int32)
        result = cv2.pointPolygonTest(polygon_np, point, False)
        return result >= 0  # >= 0 means inside or on edge
    
    def contains_centroid(self, detection: Detection) -> bool:
        """Check if detection centroid is inside this zone."""
        return self.contains_point(detection.centroid)
    
    def get_overlap_ratio(self, bbox: Tuple[int, int, int, int]) -> float:
        """
        Calculate what fraction of the bounding box overlaps with this zone.
        
        Args:
            bbox: (x1, y1, x2, y2) bounding box
            
        Returns:
            Overlap ratio (0.0 to 1.0)
        """
        x1, y1, x2, y2 = bbox
        
        # Create a mask for the zone polygon
        # Use bounding box dimensions for the mask
        mask_w = x2 - x1
        mask_h = y2 - y1
