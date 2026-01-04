"""
Member 2: Junction Safety - Lane Weaving Detection Service
IT22900890 - LiveSafeScore System

Detects:
- Lane weaving (zig-zag movement)
- Wrong-way driving
- Junction safety scoring

Formula:
    Lane_Weaving = Detected if x_axis_velocity > threshold (zig-zag movement)
    LiveSafeScore = 100 - (Violation_Penalty × Decay_Factor)
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from collections import deque
from datetime import datetime


# ============================================================================
# CONFIGURATION
# ============================================================================

# Lane weaving detection thresholds
X_VELOCITY_THRESHOLD = 15.0  # pixels per frame for significant lateral movement
DIRECTION_CHANGES_THRESHOLD = 3  # minimum direction changes to detect weaving
WEAVING_WINDOW_FRAMES = 30  # frames to analyze for weaving pattern

# Wrong-way detection (requires known lane directions)
WRONG_WAY_ANGLE_THRESHOLD = 120  # degrees from expected direction

# Junction safety scoring
INITIAL_SAFETY_SCORE = 100
VIOLATION_PENALTIES = {
    'lane_weaving': 5,           # -5 points per incident
    'wrong_way_driving': 20,     # -20 points per incident
    'speeding': 8,               # -8 points per incident
    'parking_violation': 10,     # -10 points per incident
    'running_red_light': 25,     # -25 points per incident
    'tailgating': 3,             # -3 points per incident
}
SCORE_DECAY_RATE = 0.1  # Score recovery per second
MIN_SAFETY_SCORE = 0
MAX_SAFETY_SCORE = 100


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
    safety_score: float = 100.0
    last_violation_type: Optional[str] = None
    last_violation_time: Optional[float] = None
    violations_last_hour: int = 0
    weaving_events: List[WeavingEvent] = field(default_factory=list)
    
    def apply_penalty(self, violation_type: str):
        """Apply a penalty to the safety score."""
        penalty = VIOLATION_PENALTIES.get(violation_type, 10)
        self.safety_score = max(MIN_SAFETY_SCORE, self.safety_score - penalty)
        self.last_violation_type = violation_type
        self.last_violation_time = time.time()
        self.violations_last_hour += 1
        print(f"[JUNCTION] ⚠️ Safety penalty: -{penalty} for {violation_type} → Score: {self.safety_score:.1f}")
    
    def update_decay(self):
        """Apply score recovery over time."""
        if self.last_violation_time:
            elapsed = time.time() - self.last_violation_time
            recovery = min(elapsed * SCORE_DECAY_RATE, MAX_SAFETY_SCORE - self.safety_score)
            self.safety_score = min(MAX_SAFETY_SCORE, self.safety_score + recovery)
    
    def to_dict(self) -> dict:
        return {
            'junction_id': self.junction_id,
            'safety_score': round(self.safety_score, 1),
            'safety_level': self.get_safety_level(),
            'last_violation_type': self.last_violation_type,
            'violations_last_hour': self.violations_last_hour,
            'recent_weaving_events': len(self.weaving_events),
        }
    
    def get_safety_level(self) -> str:
        if self.safety_score >= 80:
            return 'SAFE'
        elif self.safety_score >= 60:
            return 'CAUTION'
        elif self.safety_score >= 40:
            return 'WARNING'
        else:
            return 'DANGER'


# ============================================================================
# GLOBAL STATE
# ============================================================================

# Vehicle tracks: track_id -> VehicleTrack
_vehicle_tracks: Dict[int, VehicleTrack] = {}

# Junction safety state
_junction_safety: JunctionSafety = JunctionSafety()


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
    global _vehicle_tracks, _junction_safety
    
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
        _junction_safety.apply_penalty('lane_weaving')
        _junction_safety.weaving_events.append(event)
        
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
    global _vehicle_tracks, _junction_safety
    
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
        _junction_safety.apply_penalty('wrong_way_driving')
        print(f"[WRONG-WAY] ⚠️ Vehicle {track_id} going {actual_direction} in {expected_direction} lane!")
        return True
    
    return False


# ============================================================================
# JUNCTION SAFETY API
# ============================================================================

def get_junction_safety() -> JunctionSafety:
    """Get current junction safety state."""
    global _junction_safety
    _junction_safety.update_decay()
    return _junction_safety


def get_safety_score() -> float:
    """Get current LiveSafeScore."""
    return get_junction_safety().safety_score


def reset_junction_safety():
    """Reset junction safety to initial state."""
    global _junction_safety, _vehicle_tracks
    _junction_safety = JunctionSafety()
    _vehicle_tracks.clear()
    print("[JUNCTION] Safety score reset to 100")


def get_recent_weaving_events(limit: int = 10) -> List[dict]:
    """Get recent lane weaving events."""
    return [e.to_dict() for e in _junction_safety.weaving_events[-limit:]]


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
    """Save a lane weaving event to the database."""
    try:
        import aiosqlite
        from app.config import get_settings
        
        settings = get_settings()
        db_path = settings.data_dir / "traffic.db"
        
        async with aiosqlite.connect(db_path) as db:
            await db.execute("""
                INSERT INTO lane_weaving_events 
                (vehicle_id, plate_number, avg_x_velocity, direction_changes, duration_frames)
                VALUES (?, ?, ?, ?, ?)
            """, (
                event.vehicle_id,
                event.plate_number,
                event.avg_x_velocity,
                event.direction_changes,
                event.duration_frames,
            ))
            await db.commit()
            print(f"[DB] Saved weaving event for vehicle {event.vehicle_id}")
    except Exception as e:
        print(f"[DB] Error saving weaving event: {e}")


async def update_junction_safety_in_db():
    """Update junction safety score in database."""
    try:
        import aiosqlite
        from app.config import get_settings
        
        settings = get_settings()
        db_path = settings.data_dir / "traffic.db"
        safety = get_junction_safety()
        
        async with aiosqlite.connect(db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO junction_safety 
                (id, junction_id, safety_score, last_violation_type, violations_last_hour, updated_at)
                VALUES (1, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                safety.junction_id,
                safety.safety_score,
                safety.last_violation_type,
                safety.violations_last_hour,
            ))
            await db.commit()
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
