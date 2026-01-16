"""
Member 4: Abnormal Driving Behavior Detection Service
IT22337580 - Accident Risk Prediction

Detects:
- Sudden stops (>50% speed reduction in <2 seconds)
- Harsh braking (deceleration >8 m/s²)
- Lane drifting (consistent centroid drift toward edges)
- Wrong-way driving (opposite to expected flow)

All behaviors contribute to the risk score calculation.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from collections import deque
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

# Sudden stop detection
SUDDEN_STOP_SPEED_DROP = 0.5  # 50% speed reduction
SUDDEN_STOP_TIME_WINDOW = 2.0  # seconds

# Harsh braking detection
HARSH_BRAKE_DECELERATION = 8.0  # m/s² equivalent in pixels
HARSH_BRAKE_PIXEL_THRESHOLD = 12.0  # pixels per frame deceleration (lowered for 3 FPS analysis)

# Lane drifting detection
DRIFT_VARIANCE_THRESHOLD = 8.0  # pixels variance from center (lowered for 3 FPS)
DRIFT_WINDOW_FRAMES = 10  # frames (= ~3.3 seconds at 3 FPS)

# Speed estimation (pixels per second to approximate km/h)
PIXEL_TO_KMH_FACTOR = 0.5


# ============================================================================
# ENUMS
# ============================================================================

class BehaviorType(str, Enum):
    SUDDEN_STOP = 'sudden_stop'
    HARSH_BRAKE = 'harsh_brake'
    LANE_DRIFT = 'lane_drift'
    WRONG_WAY = 'wrong_way'
    ERRATIC_MOVEMENT = 'erratic_movement'


class SeverityLevel(str, Enum):
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class PositionRecord:
    """A single position and timestamp record."""
    x: int
    y: int
    timestamp: float
    speed_pixels: float = 0.0


@dataclass
class VehicleBehavior:
    """Tracks a vehicle's behavior history."""
    track_id: int
    positions: deque = field(default_factory=lambda: deque(maxlen=120))  # 4 seconds at 30fps
    speeds: deque = field(default_factory=lambda: deque(maxlen=60))
    behaviors_detected: List[str] = field(default_factory=list)
    last_behavior_time: float = 0.0
    # Per-behavior-type cooldown to prevent duplicate detections
    _last_type_time: Dict[str, float] = field(default_factory=dict)
    sudden_stop_count: int = 0
    harsh_brake_count: int = 0
    drift_score: float = 0.0

    def can_fire(self, behavior_type: str, cooldown: float = 30.0) -> bool:
        """Check if a behavior type can fire (per-type cooldown)."""
        last = self._last_type_time.get(behavior_type, 0.0)
        return (time.time() - last) >= cooldown

    def mark_fired(self, behavior_type: str):
        """Record that a behavior type just fired."""
        self._last_type_time[behavior_type] = time.time()
        self.last_behavior_time = time.time()
    
    def add_position(self, x: int, y: int, speed_pixels: float = 0.0):
        """Add a new position record."""
        self.positions.append(PositionRecord(x, y, time.time(), speed_pixels))
        if speed_pixels > 0:
            self.speeds.append(speed_pixels)
    
    def get_recent_speeds(self, window: int = 30) -> List[float]:
        """Get recent speed values."""
        return list(self.speeds)[-window:]
    
    def get_position_variance(self, axis: str = 'x', window: int = 30) -> float:
        """Calculate position variance for drift detection."""
        if len(self.positions) < window // 2:
            return 0.0
        
        positions = list(self.positions)[-window:]
        values = [p.x if axis == 'x' else p.y for p in positions]
        
        if not values:
            return 0.0
        
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        return variance ** 0.5  # Standard deviation


@dataclass
class BehaviorEvent:
    """A detected abnormal behavior event."""
    vehicle_id: int
    behavior_type: BehaviorType
    severity: SeverityLevel
    plate_number: Optional[str]
    details: Dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        return {
            'vehicle_id': self.vehicle_id,
            'behavior_type': self.behavior_type.value,
            'severity': self.severity.value,
            'plate_number': self.plate_number,
            'details': self.details,
            'timestamp': self.timestamp.isoformat(),
        }


# ============================================================================
# GLOBAL STATE
# ============================================================================

# Vehicle behavior tracking: track_id -> VehicleBehavior
_vehicle_behaviors: Dict[int, VehicleBehavior] = {}

# Recent behavior events
_behavior_events: List[BehaviorEvent] = []

