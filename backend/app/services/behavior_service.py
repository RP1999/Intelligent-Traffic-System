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

# Behavior cooldown to prevent spam (per-type minimum gap)
BEHAVIOR_COOLDOWN = 30.0  # seconds between same-type detections for same vehicle

# Queue for DB saving
_db_save_queue: List[BehaviorEvent] = []


def _queue_event_for_db_save(event: BehaviorEvent):
    """Queue an event for sync DB saving in a background thread."""
    _db_save_queue.append(event)
    
    # Save to DB in background thread using sync Firestore client
    import threading
    
    def _save_in_thread():
        try:
            _save_behavior_event_sync(event)
        except Exception as e:
            print(f"[BEHAVIOR] ⚠️ Failed to save event to DB: {e}")
    
    # Fire and forget - save to DB in background thread
    thread = threading.Thread(target=_save_in_thread, daemon=True)
    thread.start()


def _send_behavior_warning(event: BehaviorEvent):
    """Fire-and-forget: send a warning push notification for a behavior event.
    Uses vehicle tracking ID as fallback when plate is not available,
    mirroring how violations always create entries for unknown drivers."""
    # Use plate if available, otherwise fall back to UNKNOWN{id}
    # (same format the detection pipeline uses in yolo_detector.py)
    identifier = event.plate_number or f"UNKNOWN{event.vehicle_id}"
    try:
        import threading
        from app.services.push_notification_service import send_warning_notification
        details_str = ", ".join(f"{k}: {v}" for k, v in (event.details or {}).items())

        def _do_send():
            try:
                send_warning_notification(
                    plate_number=identifier,
                    behavior_type=event.behavior_type.value,
                    severity=event.severity.value,
                    details=details_str,
                )
            except Exception as e:
                logger.error("Behavior warning push error: %s", e)

        threading.Thread(target=_do_send, daemon=True).start()
    except Exception as e:
        logger.error("Failed to queue behavior warning: %s", e)


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
    # NOTE: Don't append to speeds here — analyze_vehicle_behavior() already
    # called add_position() which records the speed. Double-recording dilutes
    # the speed change ratio and makes sudden stops harder to detect.
    
    # Need speed history
    if len(behavior.speeds) < 6:
        return None
    
    # Check per-type cooldown
    if not behavior.can_fire('sudden_stop', BEHAVIOR_COOLDOWN):
        return None
    
    speeds = list(behavior.speeds)
    recent_speeds = speeds[-5:]  # Last ~1.7 seconds at 3 FPS
    older_speeds = speeds[-12:-7] if len(speeds) >= 12 else speeds[:5]
    
    if not older_speeds or not recent_speeds:
        return None
    
    avg_old_speed = sum(older_speeds) / len(older_speeds)
    avg_new_speed = sum(recent_speeds) / len(recent_speeds)
    
    # Sudden stop: speed dropped by more than 50% (guard lowered for realistic pixel speeds)
    if avg_old_speed > 5 and avg_new_speed < avg_old_speed * (1 - SUDDEN_STOP_SPEED_DROP):
        behavior.sudden_stop_count += 1
        behavior.mark_fired('sudden_stop')
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
        _queue_event_for_db_save(event)  # Save to database
        _send_behavior_warning(event)
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
    
    # Check per-type cooldown
    if not behavior.can_fire('harsh_brake', BEHAVIOR_COOLDOWN):
        return None
    
    prev_speed = behavior.speeds[-2] if len(behavior.speeds) >= 2 else current_speed
    deceleration = prev_speed - current_speed
    
    if deceleration > HARSH_BRAKE_PIXEL_THRESHOLD:
        behavior.harsh_brake_count += 1
        behavior.mark_fired('harsh_brake')
        behavior.behaviors_detected.append('harsh_brake')
        
        severity = SeverityLevel.HIGH if deceleration > HARSH_BRAKE_PIXEL_THRESHOLD * 1.5 else SeverityLevel.MEDIUM
        
        event = BehaviorEvent(
            vehicle_id=track_id,
            behavior_type=BehaviorType.HARSH_BRAKE,
            severity=severity,
            plate_number=plate_text,
            details={
                'deceleration': round(deceleration, 1),
                'speed_before': round(prev_speed, 1),
                'speed_after': round(current_speed, 1),
            }
        )
        
        _behavior_events.append(event)
        _queue_event_for_db_save(event)  # Save to database
        _send_behavior_warning(event)
        print(f"[BEHAVIOR] 🚨 Vehicle {track_id} HARSH BRAKE: decel={deceleration:.0f} px/frame")
        
        return event
    
    return None


def detect_lane_drift(
    track_id: int,
    centroid: Tuple[int, int],
    lane_center_x: int = 640,  # Approximate lane center
    plate_text: Optional[str] = None,
    _skip_add_position: bool = False,
) -> Optional[BehaviorEvent]:
    """
    Detect lane drifting: consistent movement toward lane edges.
    
    Args:
