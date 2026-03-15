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
        track_id: Vehicle tracking ID
        centroid: Current (x, y) position
        lane_center_x: Expected lane center x-coordinate
        plate_text: License plate if available
        _skip_add_position: Internal flag — True when called from
            analyze_vehicle_behavior() which already added the position.
    
    Returns:
        BehaviorEvent if lane drift detected
    """
    global _vehicle_behaviors
    
    if track_id not in _vehicle_behaviors:
        _vehicle_behaviors[track_id] = VehicleBehavior(track_id=track_id)
    
    behavior = _vehicle_behaviors[track_id]
    if not _skip_add_position:
        behavior.add_position(centroid[0], centroid[1])
    
    if len(behavior.positions) < DRIFT_WINDOW_FRAMES // 2:
        return None
    
    # Check per-type cooldown (drift uses longer cooldown)
    if not behavior.can_fire('lane_drift', BEHAVIOR_COOLDOWN * 2):
        return None
    
    # Calculate x-axis variance (drift indicator)
    x_variance = behavior.get_position_variance('x', DRIFT_WINDOW_FRAMES)
    behavior.drift_score = x_variance
    
    # Also check if consistently moving away from lane center
    positions = list(behavior.positions)[-DRIFT_WINDOW_FRAMES:]
    distances_from_center = [abs(p.x - lane_center_x) for p in positions]
    
    if len(distances_from_center) >= 4:
        first_half_avg = sum(distances_from_center[:len(distances_from_center)//2]) / (len(distances_from_center)//2)
        second_half_avg = sum(distances_from_center[len(distances_from_center)//2:]) / (len(distances_from_center)//2)
        
        # Drift detected: variance high AND moving away from center
        if x_variance > DRIFT_VARIANCE_THRESHOLD and second_half_avg > first_half_avg * 1.2:
            behavior.mark_fired('lane_drift')
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
            _queue_event_for_db_save(event)  # Save to database
            _send_behavior_warning(event)
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
    
    event = detect_lane_drift(track_id, centroid, plate_text=plate_text, _skip_add_position=True)
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


# Cache for Firestore-loaded behavior events (avoids re-querying on every API call)
_firestore_behavior_cache: List[dict] = []
_firestore_behavior_cache_time: float = 0.0
_FIRESTORE_CACHE_TTL = 60.0  # seconds


def get_recent_behavior_events(limit: int = 20) -> List[dict]:
    """Get recent behavior events. Falls back to Firestore if in-memory is empty."""
    if _behavior_events:
        return [e.to_dict() for e in _behavior_events[-limit:]]
    # Fallback: load from Firestore after server restart (cached)
    return _load_behavior_events_from_firestore(limit)


def _load_behavior_events_from_firestore(limit: int = 50) -> List[dict]:
    """Load recent behavior events from Firestore (used after server restart).
    Results are cached to avoid repeated Firestore queries."""
    global _firestore_behavior_cache, _firestore_behavior_cache_time
    
    # Return cache if fresh
    if _firestore_behavior_cache and (time.time() - _firestore_behavior_cache_time) < _FIRESTORE_CACHE_TTL:
        return _firestore_behavior_cache[:limit]
    
    try:
        from app.db.firestore_client import get_sync_db, Collections
        db = get_sync_db()
        # Try ordered query first; fall back to unordered if no index
        try:
            docs = (
                db.collection(Collections.ABNORMAL_BEHAVIOR)
                .order_by('timestamp', direction='DESCENDING')
                .limit(limit)
                .get()
            )
        except Exception:
            # Index might not exist — fetch without ordering
            docs = (
                db.collection(Collections.ABNORMAL_BEHAVIOR)
                .limit(limit)
                .get()
            )
        events = []
        for doc in docs:
            data = doc.to_dict()
            events.append({
                'vehicle_id': data.get('vehicle_id', 0),
                'behavior_type': data.get('behavior_type', 'unknown'),
                'severity': data.get('severity', 'medium'),
                'plate_number': data.get('plate_number'),
                'details': data.get('details', {}),
                'timestamp': data.get('timestamp', ''),
            })
        _firestore_behavior_cache = events
        _firestore_behavior_cache_time = time.time()
        print(f"[BEHAVIOR] Loaded {len(events)} events from Firestore")
        return events
    except Exception as e:
        print(f"[BEHAVIOR] Failed to load events from Firestore: {e}")
        return []


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

def _save_behavior_event_sync(event: BehaviorEvent):
    """Save a behavior event to Firestore using the sync client (thread-safe)."""
    try:
        from app.db.firestore_client import get_sync_db, Collections
        from app.utils.plate_utils import normalize_plate
        from datetime import timedelta as _td
        from google.cloud.firestore_v1 import FieldFilter

        # Use plate if available, otherwise fall back to UNKNOWN{id}
        # (same format the detection pipeline uses in yolo_detector.py)
        plate_norm = normalize_plate(event.plate_number) if event.plate_number else None
        identifier = plate_norm or f"UNKNOWN{event.vehicle_id}"

        db = get_sync_db()
        db.collection(Collections.ABNORMAL_BEHAVIOR).add({
            "vehicle_id": event.vehicle_id,
            "behavior_type": event.behavior_type.value,
            "severity": event.severity.value,
            "plate_number": event.plate_number,
            "plate_number_normalized": identifier,
            "details": event.details,
            "timestamp": datetime.now().isoformat(),
        })
        print(f"[DB] Saved behavior event: {event.behavior_type.value} for vehicle {event.vehicle_id}")

        # Always record as a driver event + ensure driver entity exists
        # (just like violations do for unknown plates)
        _record_behavior_as_driver_event(db, identifier, event)
        _ensure_driver_entity(db, identifier)

        # Create a driver notification so the warning always appears
        # in the notification list even if the FCM push thread fails.
        behavior_labels = {
            "sudden_stop": "Sudden Stop Detected",
            "harsh_brake": "Harsh Braking Detected",
            "lane_drift": "Lane Drifting Detected",
            "wrong_way": "Wrong-Way Driving Detected",
            "erratic_movement": "Erratic Movement Detected",
        }
        btype = event.behavior_type.value
        title = behavior_labels.get(btype, f"Warning: {btype.replace('_', ' ').title()}")
        body = f"Severity: {event.severity.value.upper()}"
        details_str = ", ".join(f"{k}: {v}" for k, v in (event.details or {}).items())
        if details_str:
            body += f" — {details_str}"

        # Quick dedup: skip if an identical notification was written
        # in the last 30 seconds (the FCM push thread may have created one)
        cutoff = (datetime.now() - _td(seconds=30)).isoformat()
        existing = list(
            db.collection(Collections.DRIVER_NOTIFICATIONS)
            .where(filter=FieldFilter("plate_number", "==", identifier))
            .limit(5)
            .stream()
        )
        already_exists = any(
            d.to_dict().get("title") == title
            and d.to_dict().get("timestamp", "") >= cutoff
            for d in existing
        )
        if not already_exists:
            db.collection(Collections.DRIVER_NOTIFICATIONS).add({
                "plate_number": identifier,
                "title": title,
                "message": body,
                "notification_type": "warning",
                "timestamp": datetime.now().isoformat(),
                "read": False,
            })
            print(f"[BEHAVIOR→NOTIF] Created notification for {identifier}: {title}")
    except Exception as e:
        print(f"[DB] Error saving behavior event: {e}")


def _ensure_driver_entity(db, plate_normalized: str):
    """
    Ensure a driver entity exists in the DRIVERS collection when a warning
    is issued, just like violations create/update driver records.
    Uses merge=True so it never overwrites existing violation-based data.
    """
    try:
        from app.db.firestore_client import Collections

        doc_ref = db.collection(Collections.DRIVERS).document(plate_normalized)
        doc = doc_ref.get()
        if doc.exists:
            # Driver already exists — just update the timestamp
            doc_ref.update({"updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        else:
            # Create a new driver entity with default score
            doc_ref.set({
                "driver_id": plate_normalized,
                "current_score": 100,
                "total_violations": 0,
                "total_fines": 0,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })
            print(f"[BEHAVIOR→DRIVER] Created driver entity for {plate_normalized}")
    except Exception as e:
        print(f"[BEHAVIOR→DRIVER] Error ensuring driver entity: {e}")


def _record_behavior_as_driver_event(db, plate_normalized: str, event: BehaviorEvent):
    """
    Record an abnormal behavior as a risk score entry on the driver's record.
    
    Behaviors are recorded in the RISK_SCORES collection for analytics 
    but do NOT directly mutate driver scores — that's handled exclusively
    by ScoringEngine.record_violation() to avoid conflicting score updates.
    
    Wrong-way driving is already handled as a formal WRONG_WAY violation
    by yolo_detector.check_wrong_way_violation(), so we do NOT issue
    a duplicate violation here. Behaviors are risk indicators, not violations.
    """
    try:
        from app.db.firestore_client import Collections
        
        # Map behavior severity to points (for risk analytics only)
        behavior_points = {
            'sudden_stop': 3,
            'harsh_brake': 4,
            'lane_drift': 5,
            'wrong_way': 15,
            'erratic_movement': 8,
        }
        
        btype = event.behavior_type.value
        points = behavior_points.get(btype, 2)
        
        # Calculate risk score using the real formula:
        # Risk_Score = (Speed_Factor × 0.6) + (History_Factor × 0.4)
        # For behavior events, speed_factor = 0 (no speed context)
        history_factor = min(100, points * 5)
        computed_risk_score = round((0 * 0.6) + (history_factor * 0.4), 1)
        
        # Determine risk level from computed score
        if computed_risk_score >= 80:
            risk_level = 'CRITICAL'
        elif computed_risk_score >= 60:
            risk_level = 'HIGH'
        elif computed_risk_score >= 30:
            risk_level = 'MEDIUM'
        else:
            risk_level = 'LOW'
        
        # Save to risk_scores collection for analytics/admin dashboards
        db.collection(Collections.RISK_SCORES).add({
            'vehicle_id': str(event.vehicle_id),
            'plate_number': event.plate_number,
            'plate_number_normalized': plate_normalized,
            'risk_score': computed_risk_score,
            'risk_level': risk_level,
            'speed_factor': 0,
            'violation_history_factor': history_factor,
            'behaviors_detected': [btype],
            'created_at': datetime.now().isoformat(),
        })
        
        print(f"[BEHAVIOR→RISK] Recorded {btype} risk entry for {plate_normalized}")
        
    except Exception as e:
        print(f"[BEHAVIOR→DRIVER] Error recording behavior to driver: {e}")


async def save_behavior_event_to_db(event: BehaviorEvent):
    """Save a behavior event to Firestore (async version — for direct async callers)."""
    try:
        from app.db.firestore_client import get_db, Collections

        db = get_db()
        await db.collection(Collections.ABNORMAL_BEHAVIOR).add({
            "vehicle_id": event.vehicle_id,
            "behavior_type": event.behavior_type.value,
            "severity": event.severity.value,
            "plate_number": event.plate_number,
            "details": event.details,
            "timestamp": datetime.now().isoformat(),
        })
        print(f"[DB] Saved behavior event: {event.behavior_type.value} for vehicle {event.vehicle_id}")
    except Exception as e:
        print(f"[DB] Error saving behavior event: {e}")


# ============================================================================
# SETTINGS INTEGRATION
# ============================================================================

def update_from_settings(settings: dict) -> None:
    """
    Update behavior detection thresholds from admin settings.
    Called when settings are saved via the Settings page.
    """
    global HARSH_BRAKE_PIXEL_THRESHOLD, DRIFT_VARIANCE_THRESHOLD, DRIFT_WINDOW_FRAMES
    global SUDDEN_STOP_SPEED_DROP, BEHAVIOR_COOLDOWN, PIXEL_TO_KMH_FACTOR
    
    detection = settings.get('detection', {})
    if detection:
        # Speed limit affects the pixel-to-kmh conversion factor indirectly
        speed_limit = detection.get('speed_limit', 60.0)
        PIXEL_TO_KMH_FACTOR = speed_limit / 120.0  # Scale factor relative to default
        
        # X-velocity threshold from detection settings maps to drift detection
        x_threshold = detection.get('x_velocity_threshold', 15.0)
        DRIFT_VARIANCE_THRESHOLD = max(3.0, x_threshold * 0.5)
        
        # Harsh brake threshold scales with speed limit (higher speed = larger pixel deltas)
        HARSH_BRAKE_PIXEL_THRESHOLD = max(5.0, speed_limit * 0.2)
        
        # Drift window scales with direction changes threshold (more changes = wider window)
        direction_changes = detection.get('direction_changes_threshold', 3)
        DRIFT_WINDOW_FRAMES = max(5, direction_changes * 3 + 1)
        
        # Sudden stop speed drop: fixed at 50% — not configurable via admin
        SUDDEN_STOP_SPEED_DROP = 0.5
        
        # Behavior cooldown derived from yellow light duration (debounce period)
        yellow_duration = detection.get('yellow_light_duration', 3.0)
        BEHAVIOR_COOLDOWN = max(1.0, yellow_duration * 0.67)
        
        print(f"[BEHAVIOR] Updated thresholds: drift_variance={DRIFT_VARIANCE_THRESHOLD:.1f}, "
              f"pixel_to_kmh={PIXEL_TO_KMH_FACTOR:.2f}, harsh_brake={HARSH_BRAKE_PIXEL_THRESHOLD:.1f}, "
              f"drift_window={DRIFT_WINDOW_FRAMES}, cooldown={BEHAVIOR_COOLDOWN:.1f}s")


# ============================================================================
# TEST
# ============================================================================
