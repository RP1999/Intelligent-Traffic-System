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
