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
        
        if mask_w <= 0 or mask_h <= 0:
            return 0.0
        
        # Translate polygon to bbox coordinate space
        translated_poly = [(p[0] - x1, p[1] - y1) for p in self.polygon]
        poly_np = np.array(translated_poly, dtype=np.int32)
        
        # Create masks
        zone_mask = np.zeros((mask_h, mask_w), dtype=np.uint8)
        cv2.fillPoly(zone_mask, [poly_np], 255)
        
        bbox_mask = np.ones((mask_h, mask_w), dtype=np.uint8) * 255
        
        # Calculate intersection
        intersection = cv2.bitwise_and(zone_mask, bbox_mask)
        intersection_area = np.count_nonzero(intersection)
        bbox_area = mask_w * mask_h
        
        return intersection_area / bbox_area if bbox_area > 0 else 0.0
    
    def to_dict(self) -> dict:
        return {
            "zone_id": self.zone_id,
            "name": self.name,
            "polygon": self.polygon,
            "zone_type": self.zone_type.value,
            "max_duration_sec": self.max_duration_sec,
            "active": self.active,
        }


@dataclass
class TrackedVehicle:
    """
    Tracks a vehicle's presence in a parking zone over time.
    """
    track_id: int
    zone_id: str
    first_seen: float  # timestamp
    last_seen: float   # timestamp
    class_name: str = "vehicle"
    license_plate: Optional[str] = None
    centroid_history: List[Tuple[int, int]] = field(default_factory=list)
    
    @property
    def dwell_time(self) -> float:
        """Time spent in zone (seconds)."""
        return self.last_seen - self.first_seen
    
    @property
    def is_stationary(self) -> bool:
        """Check if vehicle has been mostly stationary (not just passing through)."""
        if len(self.centroid_history) < 3:
            return True  # Not enough data, assume stationary
        
        # Calculate total movement
        total_movement = 0.0
        for i in range(1, len(self.centroid_history)):
            prev = self.centroid_history[i - 1]
            curr = self.centroid_history[i]
            dist = np.sqrt((curr[0] - prev[0])**2 + (curr[1] - prev[1])**2)
            total_movement += dist
        
        # If average movement per update is small, consider stationary
        avg_movement = total_movement / (len(self.centroid_history) - 1)
        return avg_movement < 20  # pixels - tune based on video resolution


@dataclass
class ParkingViolation:
    """
    Represents a parking violation event.
    """
