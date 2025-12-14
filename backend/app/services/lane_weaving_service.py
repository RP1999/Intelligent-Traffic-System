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
