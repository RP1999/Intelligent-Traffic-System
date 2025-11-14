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

