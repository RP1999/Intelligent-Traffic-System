"""
Accident Risk Prediction Service (Member 4)
=============================================
Implements the finalized risk score formula:

    Risk_Score = (Speed_Factor × 0.6) + (Violation_History_Factor × 0.4)

Note: Weather factor REMOVED per supervisor decision.

Scale: 0-100 (higher = more dangerous)
Risk Levels:
- LOW: 0-29
- MEDIUM: 30-59
- HIGH: 60-79
- CRITICAL: 80-100
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List, Any
from dataclasses import dataclass

# Database path
DB_PATH = Path(__file__).parent.parent.parent / "traffic.db"


# =============================================================================
# CONFIGURATION
# =============================================================================

# Weight factors (must sum to 1.0)
SPEED_WEIGHT = 0.6
HISTORY_WEIGHT = 0.4

# Violation weights for history factor
VIOLATION_WEIGHTS = {
    'speeding': 15,
    'parking_violation': 5,
    'lane_weaving': 20,
    'wrong_way_driving': 40,
    'running_red_light': 35,
    'improper_stopping': 10,
    'default': 10,
}

# Risk level thresholds
RISK_LEVELS = {
    'LOW': (0, 30),
    'MEDIUM': (30, 60),
    'HIGH': (60, 80),
