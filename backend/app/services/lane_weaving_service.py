"""
Member 2: Junction Safety - Lane Weaving Detection Service
IT22900890 - LiveSafeScore System

Detects:
- Lane weaving (zig-zag movement)
- Wrong-way driving
- Junction safety scoring

Formula:
    Lane_Weaving = Detected if x_axis_velocity > threshold (zig-zag movement)
    LiveSafeScore = 100 - Σ(Violation_Penalty_i × Severity_Weight_i × Context_Factor)
    + Time_Recovery (SCORE_DECAY_RATE points/sec up to MAX)

    Context_Factor scales penalties based on traffic density:
      - Low traffic:   ×0.8
      - Moderate:      ×1.0
      - High traffic:  ×1.3
      - Congested:     ×1.5

Safety Levels (proposal: Green/Yellow/Red):
    GREEN  (SAFE):    score >= 70  — Safe conditions
    YELLOW (CAUTION): score >= 40  — Caution advised
    RED    (DANGER):  score <  40  — Dangerous conditions
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from collections import deque
from datetime import datetime


# ============================================================================
# CONFIGURATION
# ============================================================================

# Lane weaving detection thresholds (can be updated from settings)
X_VELOCITY_THRESHOLD = 15.0  # pixels per frame for significant lateral movement
DIRECTION_CHANGES_THRESHOLD = 3  # minimum direction changes to detect weaving
WEAVING_WINDOW_FRAMES = 30  # frames to analyze for weaving pattern

# Wrong-way detection (requires known lane directions)
WRONG_WAY_ANGLE_THRESHOLD = 120  # degrees from expected direction

# Junction safety scoring (can be updated from settings)
INITIAL_SAFETY_SCORE = 100
VIOLATION_PENALTIES = {
    'lane_weaving': 5,           # -5 points per incident
    'wrong_way_driving': 20,     # -20 points per incident
    'speeding': 8,               # -8 points per incident
    'parking_violation': 10,     # -10 points per incident
    'running_red_light': 25,     # -25 points per incident
    'tailgating': 3,             # -3 points per incident
}
SCORE_DECAY_RATE = 0.05  # Points recovered per second (~20 sec per penalty point)
MIN_SAFETY_SCORE = 0
MAX_SAFETY_SCORE = 100

# Context-aware penalty multiplier based on traffic density
# (proposal: violations in dense traffic are more dangerous)
TRAFFIC_DENSITY_MULTIPLIER = {
    'low': 0.8,
    'moderate': 1.0,
    'high': 1.3,
    'congested': 1.5,
}

# Current traffic density (updated by detection pipeline)
_current_traffic_density: str = 'moderate'


def update_from_settings(settings: dict) -> None:
    """Update lane weaving and junction safety settings from API settings."""
    global X_VELOCITY_THRESHOLD, DIRECTION_CHANGES_THRESHOLD, WRONG_WAY_ANGLE_THRESHOLD
    global VIOLATION_PENALTIES, SCORE_DECAY_RATE
    global INITIAL_SAFETY_SCORE, MIN_SAFETY_SCORE, MAX_SAFETY_SCORE
    
    # Update detection settings
    detection = settings.get('detection', {})
    if detection:
        X_VELOCITY_THRESHOLD = detection.get('x_velocity_threshold', 15.0)
        DIRECTION_CHANGES_THRESHOLD = detection.get('direction_changes_threshold', 3)
        WRONG_WAY_ANGLE_THRESHOLD = detection.get('wrong_way_angle_threshold', 120)
    
    # Update junction safety settings
    junction = settings.get('junction_safety', {})
    if junction:
        INITIAL_SAFETY_SCORE = junction.get('initial_score', 100)
        MIN_SAFETY_SCORE = junction.get('min_score', 0)
        MAX_SAFETY_SCORE = junction.get('max_score', 100)
        VIOLATION_PENALTIES['lane_weaving'] = junction.get('lane_weaving_penalty', 5)
        VIOLATION_PENALTIES['wrong_way_driving'] = junction.get('wrong_way_penalty', 20)
        VIOLATION_PENALTIES['speeding'] = junction.get('speeding_penalty', 8)
        VIOLATION_PENALTIES['parking_violation'] = junction.get('parking_violation_penalty', 10)
        VIOLATION_PENALTIES['running_red_light'] = junction.get('running_red_light_penalty', 25)
        VIOLATION_PENALTIES['tailgating'] = junction.get('tailgating_penalty', 3)
        SCORE_DECAY_RATE = junction.get('score_decay_rate', 0.1)
    
    print(f"[JUNCTION] Settings updated: initial={INITIAL_SAFETY_SCORE}, "
          f"min={MIN_SAFETY_SCORE}, max={MAX_SAFETY_SCORE}, "
          f"penalties={VIOLATION_PENALTIES}, decay={SCORE_DECAY_RATE}")


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class VehicleTrack:
    """Tracks a vehicle's position history for behavior analysis."""
    track_id: int
    positions: deque = field(default_factory=lambda: deque(maxlen=60))
    timestamps: deque = field(default_factory=lambda: deque(maxlen=60))
    is_weaving: bool = False
    is_wrong_way: bool = False
    weaving_score: float = 0.0
    last_direction: Optional[str] = None  # 'left', 'right', None
    direction_changes: int = 0
    
    def add_position(self, x: int, y: int, timestamp: float = None):
        """Add a new position to the track."""
        if timestamp is None:
            timestamp = time.time()
        self.positions.append((x, y))
        self.timestamps.append(timestamp)
    
    def get_x_velocities(self, window: int = None) -> List[float]:
        """Calculate x-axis velocities over recent positions."""
        if len(self.positions) < 2:
            return []
        
        window = window or WEAVING_WINDOW_FRAMES
        positions = list(self.positions)[-window:]
        
        velocities = []
        for i in range(1, len(positions)):
            x_vel = positions[i][0] - positions[i-1][0]
            velocities.append(x_vel)
        
        return velocities


@dataclass
class WeavingEvent:
    """A detected lane weaving event."""
    vehicle_id: int
    plate_number: Optional[str]
    avg_x_velocity: float
    direction_changes: int
    duration_frames: int
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        return {
            'vehicle_id': self.vehicle_id,
            'plate_number': self.plate_number,
            'avg_x_velocity': round(self.avg_x_velocity, 2),
            'direction_changes': self.direction_changes,
            'duration_frames': self.duration_frames,
            'timestamp': self.timestamp.isoformat(),
        }


@dataclass
class JunctionSafety:
    """Junction-level safety score tracking."""
    junction_id: str = 'main'
    safety_score: float = -1.0  # Sentinel; __post_init__ sets from INITIAL_SAFETY_SCORE
    last_violation_type: Optional[str] = None
    last_violation_time: Optional[float] = None
    violations_last_hour: int = 0
    weaving_events: List[WeavingEvent] = field(default_factory=list)
    
    def __post_init__(self):
        if self.safety_score < 0:
            self.safety_score = float(INITIAL_SAFETY_SCORE)
    
    def apply_penalty(self, violation_type: str, traffic_density: str = None):
        """Apply a context-aware penalty to the safety score and persist to Firestore.
        
        Formula: effective_penalty = base_penalty × context_factor
        Where context_factor scales with traffic density (denser = more dangerous).
        """
        base_penalty = VIOLATION_PENALTIES.get(violation_type, 10)
        density = traffic_density or _current_traffic_density
        context_factor = TRAFFIC_DENSITY_MULTIPLIER.get(density, 1.0)
        effective_penalty = base_penalty * context_factor
        
        self.safety_score = max(MIN_SAFETY_SCORE, self.safety_score - effective_penalty)
        self.last_violation_type = violation_type
        self.last_violation_time = time.time()
        self.violations_last_hour += 1
        self.last_penalty_detail = {
            'violation_type': violation_type,
            'base_penalty': base_penalty,
            'context_factor': context_factor,
            'traffic_density': density,
            'effective_penalty': round(effective_penalty, 1),
        }
        print(f"[JUNCTION] ⚠️ Safety penalty: -{effective_penalty:.1f} "
              f"({base_penalty}×{context_factor}) for {violation_type} → Score: {self.safety_score:.1f}")
        # Persist updated score to Firestore in background
        _persist_junction_safety_background(self)
    
    def update_decay(self):
        """Apply score recovery over time (delta-based).
        Capped at 300s elapsed to prevent full recovery after long downtime."""
        if self.last_violation_time:
            now = time.time()
            last_recovery = getattr(self, '_last_recovery_time', self.last_violation_time)
            elapsed = min(now - last_recovery, 300.0)  # Cap at 5 minutes
            recovery = min(elapsed * SCORE_DECAY_RATE, MAX_SAFETY_SCORE - self.safety_score)
            self.safety_score = min(MAX_SAFETY_SCORE, self.safety_score + recovery)
            self._last_recovery_time = now
    
    def to_dict(self) -> dict:
        return {
            'junction_id': self.junction_id,
            'safety_score': round(self.safety_score, 1),
            'safety_level': self.get_safety_level(),
            'safety_color': self.get_safety_color(),
            'last_violation_type': self.last_violation_type,
            'violations_last_hour': self.violations_last_hour,
            'recent_weaving_events': len(self.weaving_events),
            'last_penalty_detail': getattr(self, 'last_penalty_detail', None),
            'formula': 'LiveSafeScore = 100 - Σ(Penalty × Severity × ContextFactor) + TimeRecovery',
            'traffic_density': _current_traffic_density,
        }
    
    def get_safety_level(self) -> str:
        """Get safety level matching proposal's Green/Yellow/Red scheme."""
        if self.safety_score >= 70:
            return 'SAFE'       # Green
        elif self.safety_score >= 40:
            return 'CAUTION'    # Yellow
        else:
            return 'DANGER'     # Red
    
    def get_safety_color(self) -> str:
        """Get the proposal's Green/Yellow/Red color for displays."""
        if self.safety_score >= 70:
            return 'GREEN'
        elif self.safety_score >= 40:
            return 'YELLOW'
        else:
            return 'RED'


# ============================================================================
# GLOBAL STATE
# ============================================================================

# Vehicle tracks: track_id -> VehicleTrack
_vehicle_tracks: Dict[int, VehicleTrack] = {}

# Junction safety state — loaded from Firestore on first access
_junction_safety: JunctionSafety = None  # Lazy-initialized
_junction_safety_loaded: bool = False


def _load_junction_safety_from_firestore() -> JunctionSafety:
    """Load the last known junction safety score from Firestore."""
    try:
        from app.db.firestore_client import get_sync_db, Collections
        db = get_sync_db()
        doc = db.collection(Collections.JUNCTION_SAFETY).document('main').get()
        if doc.exists:
            data = doc.to_dict()
            safety = JunctionSafety(
                junction_id=data.get('junction_id', 'main'),
                safety_score=float(data.get('safety_score', INITIAL_SAFETY_SCORE)),
            )
            safety.last_violation_type = data.get('last_violation_type')
            safety.violations_last_hour = data.get('violations_last_hour', 0)
            ts = data.get('updated_at')
            if ts:
                try:
                    dt = datetime.fromisoformat(ts)
                    safety.last_violation_time = dt.timestamp()
                    safety._last_recovery_time = dt.timestamp()
                except Exception:
                    pass
            print(f"[JUNCTION] Loaded safety score from Firestore: {safety.safety_score:.1f}")
            return safety
    except Exception as e:
        print(f"[JUNCTION] Failed to load safety from Firestore: {e}")
    return JunctionSafety()


def _persist_junction_safety_background(safety: 'JunctionSafety'):
    """Save junction safety score to Firestore in a background thread."""
    import threading
    def _save():
        try:
            from app.db.firestore_client import get_sync_db, Collections
            db = get_sync_db()
            db.collection(Collections.JUNCTION_SAFETY).document(
                safety.junction_id or 'main'
            ).set({
                'junction_id': safety.junction_id,
                'safety_score': safety.safety_score,
                'last_violation_type': safety.last_violation_type,
                'violations_last_hour': safety.violations_last_hour,
                'updated_at': datetime.now().isoformat(),
            }, merge=True)
        except Exception as e:
            print(f"[JUNCTION] Failed to persist safety to Firestore: {e}")
    threading.Thread(target=_save, daemon=True).start()


# ============================================================================
# LANE WEAVING DETECTION
# ============================================================================

def detect_lane_weaving(
    track_id: int,
    centroid: Tuple[int, int],
    plate_text: Optional[str] = None
) -> Optional[WeavingEvent]:
    """
    Detect zig-zag/weaving movement by analyzing x-axis velocity changes.
    
    Args:
        track_id: Vehicle tracking ID
        centroid: Current (x, y) position
        plate_text: License plate if available
    
    Returns:
        WeavingEvent if weaving detected, None otherwise
    """
    global _vehicle_tracks
    
    # Get or create track
    if track_id not in _vehicle_tracks:
        _vehicle_tracks[track_id] = VehicleTrack(track_id=track_id)
    
    track = _vehicle_tracks[track_id]
    track.add_position(centroid[0], centroid[1])
    
    # Need enough history to analyze
    if len(track.positions) < WEAVING_WINDOW_FRAMES // 2:
        return None
    
    # Calculate x-axis velocities
    x_velocities = track.get_x_velocities(WEAVING_WINDOW_FRAMES)
    if not x_velocities:
        return None
    
    # Count direction changes
    direction_changes = 0
    prev_direction = None
    
    for x_vel in x_velocities:
        if abs(x_vel) < 2:  # Ignore small movements
            continue
        
        current_direction = 'left' if x_vel < 0 else 'right'
        if prev_direction and current_direction != prev_direction:
            direction_changes += 1
        prev_direction = current_direction
    
    # Calculate average absolute x-velocity
    avg_x_velocity = sum(abs(v) for v in x_velocities) / len(x_velocities)
    
    # Detect weaving: high lateral velocity + multiple direction changes
    is_weaving = (
        avg_x_velocity > X_VELOCITY_THRESHOLD and
        direction_changes >= DIRECTION_CHANGES_THRESHOLD
    )
    
    track.is_weaving = is_weaving
    track.direction_changes = direction_changes
    track.weaving_score = avg_x_velocity
    
    if is_weaving and not track.last_direction:  # First detection for this vehicle
        track.last_direction = prev_direction
        
        # Create weaving event
        event = WeavingEvent(
            vehicle_id=track_id,
            plate_number=plate_text,
            avg_x_velocity=avg_x_velocity,
            direction_changes=direction_changes,
            duration_frames=len(x_velocities),
        )
        
        # Apply penalty to junction safety
        junction = get_junction_safety()
        junction.apply_penalty('lane_weaving')
        junction.weaving_events.append(event)
        
        print(f"[WEAVING] 🚗 Vehicle {track_id} detected weaving! "
              f"X-vel: {avg_x_velocity:.1f}, Changes: {direction_changes}")
        
        return event
    
    return None


def detect_wrong_way(
    track_id: int,
    centroid: Tuple[int, int],
    expected_direction: str = 'down',  # 'up', 'down', 'left', 'right'
    plate_text: Optional[str] = None
) -> bool:
    """
    Detect if a vehicle is traveling in the wrong direction.
    
    Args:
        track_id: Vehicle tracking ID
        centroid: Current (x, y) position
        expected_direction: Expected traffic flow direction
        plate_text: License plate if available
    
    Returns:
        True if wrong-way driving detected
    """
    global _vehicle_tracks
    
    if track_id not in _vehicle_tracks:
        _vehicle_tracks[track_id] = VehicleTrack(track_id=track_id)
    
    track = _vehicle_tracks[track_id]
    
    if len(track.positions) < 5:
        return False
    
    # Calculate movement direction
    positions = list(track.positions)
    start = positions[-10] if len(positions) >= 10 else positions[0]
    end = positions[-1]
    
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    
    # Determine actual direction
    if abs(dy) > abs(dx):
        actual_direction = 'down' if dy > 0 else 'up'
    else:
        actual_direction = 'right' if dx > 0 else 'left'
    
    # Check if wrong way
    opposite_directions = {
        'up': 'down',
        'down': 'up',
        'left': 'right',
        'right': 'left',
    }
    
    is_wrong_way = (actual_direction == opposite_directions.get(expected_direction))
    
    if is_wrong_way and not track.is_wrong_way:
        track.is_wrong_way = True
        get_junction_safety().apply_penalty('wrong_way_driving')
        print(f"[WRONG-WAY] ⚠️ Vehicle {track_id} going {actual_direction} in {expected_direction} lane!")
        return True
    
    return False


# ============================================================================
# JUNCTION SAFETY API
# ============================================================================

def get_junction_safety() -> JunctionSafety:
    """Get current junction safety state. Lazy-loads from Firestore on first access."""
    global _junction_safety, _junction_safety_loaded
    if _junction_safety is None:
        if not _junction_safety_loaded:
            _junction_safety = _load_junction_safety_from_firestore()
            _junction_safety_loaded = True
        else:
            _junction_safety = JunctionSafety()
    _junction_safety.update_decay()
    return _junction_safety


def get_safety_score() -> float:
    """Get current LiveSafeScore."""
    return get_junction_safety().safety_score


def set_traffic_density(density: str):
    """Update the current traffic density for context-aware penalty scaling.
    
    Called by the detection pipeline when vehicle counts change.
    Valid values: 'low', 'moderate', 'high', 'congested'
    """
    global _current_traffic_density
    if density in TRAFFIC_DENSITY_MULTIPLIER:
        _current_traffic_density = density


def get_traffic_density() -> str:
    """Get the current traffic density setting."""
    return _current_traffic_density


def reset_junction_safety():
    """Reset junction safety to initial state."""
    global _junction_safety, _vehicle_tracks
    _junction_safety = JunctionSafety()
    _vehicle_tracks.clear()
    # Persist reset to Firestore
    _persist_junction_safety_background(_junction_safety)
    print("[JUNCTION] Safety score reset to 100")


def get_recent_weaving_events(limit: int = 10) -> List[dict]:
    """Get recent lane weaving events."""
    return [e.to_dict() for e in get_junction_safety().weaving_events[-limit:]]


def cleanup_old_tracks(max_age_seconds: float = 30.0):
    """Remove old vehicle tracks that haven't been updated recently."""
    global _vehicle_tracks
    current_time = time.time()
    stale_ids = []
    
    for track_id, track in _vehicle_tracks.items():
        if track.timestamps and (current_time - track.timestamps[-1]) > max_age_seconds:
            stale_ids.append(track_id)
    
    for track_id in stale_ids:
        del _vehicle_tracks[track_id]


# ============================================================================
# DATABASE INTEGRATION
# ============================================================================

async def save_weaving_event_to_db(event: WeavingEvent):
    """Save a lane weaving event to Firestore."""
    try:
        from app.db.firestore_client import get_db, Collections

        db = get_db()
        await db.collection(Collections.LANE_WEAVING_EVENTS).add({
            "vehicle_id": event.vehicle_id,
            "plate_number": event.plate_number,
            "avg_x_velocity": event.avg_x_velocity,
            "direction_changes": event.direction_changes,
            "duration_frames": event.duration_frames,
            "timestamp": event.timestamp.isoformat(),
        })
        print(f"[DB] Saved weaving event for vehicle {event.vehicle_id}")
    except Exception as e:
        print(f"[DB] Error saving weaving event: {e}")


async def update_junction_safety_in_db():
    """Update junction safety score in Firestore."""
    try:
        from app.db.firestore_client import get_db, Collections

        db = get_db()
        safety = get_junction_safety()
        doc_id = safety.junction_id or "main"
        await db.collection(Collections.JUNCTION_SAFETY).document(doc_id).set({
            "junction_id": safety.junction_id,
            "safety_score": safety.safety_score,
            "last_violation_type": safety.last_violation_type,
            "violations_last_hour": safety.violations_last_hour,
            "updated_at": datetime.now().isoformat(),
        }, merge=True)
    except Exception as e:
        print(f"[DB] Error updating junction safety: {e}")


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Lane Weaving Detection Test")
    print("=" * 60)
    
    # Simulate a weaving vehicle
    import random
    
    track_id = 1
    for i in range(40):
        # Zig-zag pattern
        x = 400 + (20 * (i % 2) * (-1 if i % 4 < 2 else 1))
        y = 200 + i * 10
        
        result = detect_lane_weaving(track_id, (x, y), plate_text="TEST-1234")
        if result:
            print(f"Weaving detected: {result.to_dict()}")
    
    print(f"\nJunction Safety: {get_junction_safety().to_dict()}")
