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

import time
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from collections import deque
from datetime import datetime
from enum import Enum


# ============================================================================
# CONFIGURATION
# ============================================================================

# Sudden stop detection
SUDDEN_STOP_SPEED_DROP = 0.5  # 50% speed reduction
SUDDEN_STOP_TIME_WINDOW = 2.0  # seconds

# Harsh braking detection
HARSH_BRAKE_DECELERATION = 8.0  # m/s² equivalent in pixels
HARSH_BRAKE_PIXEL_THRESHOLD = 40.0  # pixels per frame deceleration

# Lane drifting detection
DRIFT_VARIANCE_THRESHOLD = 15.0  # pixels variance from center
DRIFT_WINDOW_FRAMES = 30

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
    sudden_stop_count: int = 0
    harsh_brake_count: int = 0
    drift_score: float = 0.0
    
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

# Behavior cooldown to prevent spam
BEHAVIOR_COOLDOWN = 5.0  # seconds


# ============================================================================
# DETECTION FUNCTIONS
# ============================================================================

def detect_sudden_stop(
    track_id: int,
    current_speed: float,
    plate_text: Optional[str] = None
) -> Optional[BehaviorEvent]:
    """
    Detect sudden stop: >50% speed reduction in <2 seconds.
    
    Args:
        track_id: Vehicle tracking ID
        current_speed: Current speed in pixels/second
        plate_text: License plate if available
    
    Returns:
        BehaviorEvent if sudden stop detected
    """
    global _vehicle_behaviors
    
    if track_id not in _vehicle_behaviors:
        _vehicle_behaviors[track_id] = VehicleBehavior(track_id=track_id)
    
    behavior = _vehicle_behaviors[track_id]
    behavior.speeds.append(current_speed)
    
    # Need speed history
    if len(behavior.speeds) < 10:
        return None
    
    # Check cooldown
    if time.time() - behavior.last_behavior_time < BEHAVIOR_COOLDOWN:
        return None
    
    speeds = list(behavior.speeds)
    recent_speeds = speeds[-10:]  # Last ~0.33 seconds
    older_speeds = speeds[-30:-20] if len(speeds) >= 30 else speeds[:10]
    
    if not older_speeds or not recent_speeds:
        return None
    
    avg_old_speed = sum(older_speeds) / len(older_speeds)
    avg_new_speed = sum(recent_speeds) / len(recent_speeds)
    
    # Sudden stop: speed dropped by more than 50%
    if avg_old_speed > 20 and avg_new_speed < avg_old_speed * (1 - SUDDEN_STOP_SPEED_DROP):
        behavior.sudden_stop_count += 1
        behavior.last_behavior_time = time.time()
        behavior.behaviors_detected.append('sudden_stop')
        
        severity = SeverityLevel.HIGH if avg_old_speed > 100 else SeverityLevel.MEDIUM
        
        event = BehaviorEvent(
            vehicle_id=track_id,
            behavior_type=BehaviorType.SUDDEN_STOP,
            severity=severity,
            plate_number=plate_text,
            details={
                'speed_before': round(avg_old_speed, 1),
                'speed_after': round(avg_new_speed, 1),
                'speed_drop_percent': round((1 - avg_new_speed / avg_old_speed) * 100, 1),
            }
        )
        
        _behavior_events.append(event)
        print(f"[BEHAVIOR] 🛑 Vehicle {track_id} SUDDEN STOP: {avg_old_speed:.0f} → {avg_new_speed:.0f} px/s")
        
        return event
    
    return None


def detect_harsh_brake(
    track_id: int,
    current_speed: float,
    plate_text: Optional[str] = None
) -> Optional[BehaviorEvent]:
    """
    Detect harsh braking: high deceleration rate.
    
    Args:
        track_id: Vehicle tracking ID
        current_speed: Current speed in pixels/second
        plate_text: License plate if available
    
    Returns:
        BehaviorEvent if harsh brake detected
    """
    global _vehicle_behaviors
    
    if track_id not in _vehicle_behaviors:
        _vehicle_behaviors[track_id] = VehicleBehavior(track_id=track_id)
    
    behavior = _vehicle_behaviors[track_id]
    
    if len(behavior.speeds) < 2:
        return None
    
    # Check cooldown
    if time.time() - behavior.last_behavior_time < BEHAVIOR_COOLDOWN:
        return None
    
    prev_speed = behavior.speeds[-2] if len(behavior.speeds) >= 2 else current_speed
    deceleration = prev_speed - current_speed
    
    if deceleration > HARSH_BRAKE_PIXEL_THRESHOLD:
        behavior.harsh_brake_count += 1
        behavior.last_behavior_time = time.time()
        behavior.behaviors_detected.append('harsh_brake')
        
        severity = SeverityLevel.HIGH if deceleration > HARSH_BRAKE_PIXEL_THRESHOLD * 1.5 else SeverityLevel.MEDIUM
        
        event = BehaviorEvent(
            vehicle_id=track_id,
            behavior_type=BehaviorType.HARSH_BRAKE,
            severity=severity,
            plate_number=plate_text,
            details={
