"""
Intelligent Traffic Management System - Driver Scoring Module
Tracks driver behavior, calculates risk scores, and applies violation penalties.
"""

import time
import sqlite3
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum

from app.config import get_settings

settings = get_settings()

# Database path for persistence
DB_PATH = Path(__file__).parent.parent.parent / "traffic.db"


class ViolationType(str, Enum):
    """Types of traffic violations."""
    PARKING_NO_PARKING = "parking_no_parking"
