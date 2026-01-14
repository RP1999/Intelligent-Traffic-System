"""
Dynamic Fine Calculation Service (Member 1)
=============================================
Implements the finalized dynamic fine formula:

    Fine = Base + (Duration × Rate) + (Traffic_Impact × Multiplier)

Where:
- Base = Fixed penalty based on zone type
- Duration = How long the vehicle was parked illegally (seconds)
- Rate = 5 LKR per second
- Traffic_Impact = Count of OTHER moving vehicles in frame
- Multiplier = 50 LKR per affected vehicle
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass

from app.db.firestore_client import get_sync_db, Collections


# =============================================================================
# CONFIGURATION
# =============================================================================

# Base penalties by zone type (in LKR)
BASE_PENALTIES = {
    'no_parking': 1000,
    'handicap_zone': 2500,
    'fire_lane': 3000,
    'bus_stop': 1500,
    'school_zone': 2000,
    'default': 1000,
}

# Duration rate: LKR per second
DURATION_RATE = 5

# Traffic impact multiplier: LKR per affected vehicle
TRAFFIC_MULTIPLIER = 50


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class FineBreakdown:
    """Container for dynamic fine calculation result."""
    violation_id: int
    zone_type: str
    duration_seconds: int
    traffic_impact: int
    base_penalty: float
    duration_penalty: float
    impact_penalty: float
    total_fine: float
    
    def to_dict(self) -> dict:
        return {
            'violation_id': self.violation_id,
            'zone_type': self.zone_type,
            'duration_seconds': self.duration_seconds,
            'traffic_impact': self.traffic_impact,
            'base_penalty': self.base_penalty,
            'duration_penalty': self.duration_penalty,
            'impact_penalty': self.impact_penalty,
