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
                'deceleration': round(deceleration, 1),
                'speed_before': round(prev_speed, 1),
                'speed_after': round(current_speed, 1),
            }
        )
        
        _behavior_events.append(event)
        print(f"[BEHAVIOR] 🚨 Vehicle {track_id} HARSH BRAKE: decel={deceleration:.0f} px/frame")
        
        return event
    
    return None


def detect_lane_drift(
    track_id: int,
    centroid: Tuple[int, int],
    lane_center_x: int = 640,  # Approximate lane center
    plate_text: Optional[str] = None
) -> Optional[BehaviorEvent]:
    """
    Detect lane drifting: consistent movement toward lane edges.
    
    Args:
        track_id: Vehicle tracking ID
        centroid: Current (x, y) position
        lane_center_x: Expected lane center x-coordinate
        plate_text: License plate if available
    
    Returns:
        BehaviorEvent if lane drift detected
    """
    global _vehicle_behaviors
    
    if track_id not in _vehicle_behaviors:
        _vehicle_behaviors[track_id] = VehicleBehavior(track_id=track_id)
    
    behavior = _vehicle_behaviors[track_id]
    behavior.add_position(centroid[0], centroid[1])
    
    if len(behavior.positions) < DRIFT_WINDOW_FRAMES // 2:
        return None
    
    # Check cooldown
    if time.time() - behavior.last_behavior_time < BEHAVIOR_COOLDOWN * 2:
        return None
    
    # Calculate x-axis variance (drift indicator)
    x_variance = behavior.get_position_variance('x', DRIFT_WINDOW_FRAMES)
    behavior.drift_score = x_variance
    
    # Also check if consistently moving away from lane center
    positions = list(behavior.positions)[-DRIFT_WINDOW_FRAMES:]
    distances_from_center = [abs(p.x - lane_center_x) for p in positions]
    
    if len(distances_from_center) >= 10:
        first_half_avg = sum(distances_from_center[:len(distances_from_center)//2]) / (len(distances_from_center)//2)
        second_half_avg = sum(distances_from_center[len(distances_from_center)//2:]) / (len(distances_from_center)//2)
        
        # Drift detected: variance high AND moving away from center
        if x_variance > DRIFT_VARIANCE_THRESHOLD and second_half_avg > first_half_avg * 1.3:
            behavior.last_behavior_time = time.time()
            behavior.behaviors_detected.append('lane_drift')
            
            event = BehaviorEvent(
                vehicle_id=track_id,
                behavior_type=BehaviorType.LANE_DRIFT,
                severity=SeverityLevel.MEDIUM,
                plate_number=plate_text,
                details={
                    'x_variance': round(x_variance, 1),
                    'drift_from_center': round(second_half_avg - first_half_avg, 1),
                }
            )
            
            _behavior_events.append(event)
            print(f"[BEHAVIOR] ↔️ Vehicle {track_id} LANE DRIFT: variance={x_variance:.1f}")
            
            return event
    
    return None


def analyze_vehicle_behavior(
    track_id: int,
    centroid: Tuple[int, int],
    speed_pixels: float,
    plate_text: Optional[str] = None
) -> List[BehaviorEvent]:
    """
    Comprehensive behavior analysis for a vehicle.
    Runs all detection algorithms.
    
    Args:
        track_id: Vehicle tracking ID
        centroid: Current (x, y) position
        speed_pixels: Current speed in pixels/second
        plate_text: License plate if available
    
    Returns:
        List of detected behavior events
    """
    events = []
    
    # Update position and speed
    if track_id not in _vehicle_behaviors:
        _vehicle_behaviors[track_id] = VehicleBehavior(track_id=track_id)
    
    behavior = _vehicle_behaviors[track_id]
    behavior.add_position(centroid[0], centroid[1], speed_pixels)
    
    # Run detections
    event = detect_sudden_stop(track_id, speed_pixels, plate_text)
    if event:
        events.append(event)
    
    event = detect_harsh_brake(track_id, speed_pixels, plate_text)
    if event:
        events.append(event)
    
    event = detect_lane_drift(track_id, centroid, plate_text=plate_text)
    if event:
        events.append(event)
    
    return events


# ============================================================================
# API FUNCTIONS
# ============================================================================

def get_vehicle_behavior(track_id: int) -> Optional[Dict]:
    """Get behavior summary for a vehicle."""
    if track_id not in _vehicle_behaviors:
        return None
    
    behavior = _vehicle_behaviors[track_id]
    return {
        'track_id': track_id,
        'sudden_stop_count': behavior.sudden_stop_count,
        'harsh_brake_count': behavior.harsh_brake_count,
        'drift_score': round(behavior.drift_score, 1),
        'behaviors_detected': behavior.behaviors_detected[-10:],
    }


def get_recent_behavior_events(limit: int = 20) -> List[dict]:
    """Get recent behavior events."""
    return [e.to_dict() for e in _behavior_events[-limit:]]


def get_high_risk_vehicles() -> List[Dict]:
    """Get vehicles with concerning behavior patterns."""
    high_risk = []
    
    for track_id, behavior in _vehicle_behaviors.items():
        risk_count = behavior.sudden_stop_count + behavior.harsh_brake_count
        if risk_count >= 2 or behavior.drift_score > DRIFT_VARIANCE_THRESHOLD * 1.5:
            high_risk.append({
                'track_id': track_id,
                'risk_events': risk_count,
                'drift_score': round(behavior.drift_score, 1),
                'behaviors': behavior.behaviors_detected[-5:],
            })
    
    return sorted(high_risk, key=lambda x: x['risk_events'], reverse=True)


def cleanup_old_behaviors(max_age_seconds: float = 60.0):
    """Remove old behavior records."""
    global _vehicle_behaviors
    current_time = time.time()
    stale_ids = []
    
    for track_id, behavior in _vehicle_behaviors.items():
        if behavior.positions and (current_time - behavior.positions[-1].timestamp) > max_age_seconds:
            stale_ids.append(track_id)
    
    for track_id in stale_ids:
        del _vehicle_behaviors[track_id]


def reset_behaviors():
    """Reset all behavior tracking."""
    global _vehicle_behaviors, _behavior_events
    _vehicle_behaviors.clear()
    _behavior_events.clear()


# ============================================================================
# DATABASE INTEGRATION
# ============================================================================

async def save_behavior_event_to_db(event: BehaviorEvent):
    """Save a behavior event to the database."""
    try:
        import aiosqlite
        from app.config import get_settings
        
        settings = get_settings()
        db_path = settings.data_dir / "traffic.db"
        
        async with aiosqlite.connect(db_path) as db:
            await db.execute("""
                INSERT INTO abnormal_behavior_log 
                (vehicle_id, behavior_type, severity, plate_number, timestamp)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                event.vehicle_id,
                event.behavior_type.value,
                event.severity.value,
                event.plate_number,
            ))
            await db.commit()
            print(f"[DB] Saved behavior event: {event.behavior_type.value} for vehicle {event.vehicle_id}")
    except Exception as e:
        print(f"[DB] Error saving behavior event: {e}")


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Abnormal Behavior Detection Test")
    print("=" * 60)
    
    # Simulate sudden stop
    track_id = 1
    for speed in [100, 100, 100, 95, 90, 80, 60, 30, 10, 5]:
        detect_sudden_stop(track_id, speed, "TEST-001")
    
    # Simulate lane drift
    track_id = 2
    for i in range(40):
        x = 640 + i * 3  # Gradually drifting right
        y = 300 + i * 5
        detect_lane_drift(track_id, (x, y), lane_center_x=640, plate_text="TEST-002")
    
    print(f"\nRecent Events: {get_recent_behavior_events()}")
    print(f"High Risk Vehicles: {get_high_risk_vehicles()}")
