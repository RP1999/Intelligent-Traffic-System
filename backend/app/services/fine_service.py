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
            'total_fine': self.total_fine,
            'formula': 'Base + (Duration × 5) + (Traffic_Impact × 50)'
        }


# =============================================================================
# CORE FUNCTIONS
# =============================================================================

def calculate_dynamic_fine(
    violation_type: str,
    duration_seconds: int,
    vehicle_count_in_frame: int,
    violation_id: Optional[int] = None
) -> FineBreakdown:
    """
    Calculate dynamic fine based on the finalized formula.
    
    Formula: Fine = Base + (Duration × 5) + (Traffic_Impact × 50)
    
    Args:
        violation_type: Type of parking zone ('no_parking', 'handicap_zone', etc.)
        duration_seconds: How long the vehicle was parked illegally
        vehicle_count_in_frame: Count of OTHER moving vehicles in frame
        violation_id: Optional ID if linked to existing violation record
        
    Returns:
        FineBreakdown object with detailed calculation.
    """
    # Get base penalty for zone type
    base_penalty = BASE_PENALTIES.get(violation_type.lower(), BASE_PENALTIES['default'])
    
    # Calculate duration penalty: Duration × Rate (5 LKR/second)
    duration_penalty = duration_seconds * DURATION_RATE
    
    # Calculate traffic impact penalty: Vehicle_Count × Multiplier (50 LKR/vehicle)
    impact_penalty = vehicle_count_in_frame * TRAFFIC_MULTIPLIER
    
    # Total fine
    total_fine = base_penalty + duration_penalty + impact_penalty
    
    return FineBreakdown(
        violation_id=violation_id or 0,
        zone_type=violation_type,
        duration_seconds=duration_seconds,
        traffic_impact=vehicle_count_in_frame,
        base_penalty=base_penalty,
        duration_penalty=duration_penalty,
        impact_penalty=impact_penalty,
        total_fine=total_fine
    )


def save_fine_to_database(fine: FineBreakdown) -> str:
    """
    Save the calculated fine to the dynamic_fines collection.
    
    Args:
        fine: FineBreakdown object with calculation details.
        
    Returns:
        ID of the inserted document.
    """
    db = get_sync_db()
    doc_ref = db.collection(Collections.DYNAMIC_FINES).add({
