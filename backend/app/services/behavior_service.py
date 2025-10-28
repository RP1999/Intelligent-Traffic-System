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
