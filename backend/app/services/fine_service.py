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

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass

# Database path
DB_PATH = Path(__file__).parent.parent.parent / "traffic.db"


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


def save_fine_to_database(fine: FineBreakdown) -> int:
    """
    Save the calculated fine to the dynamic_fines table.
    
    Args:
        fine: FineBreakdown object with calculation details.
        
    Returns:
        ID of the inserted record.
    """
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO dynamic_fines (
                violation_id, zone_type, base_penalty, duration_seconds,
                duration_penalty, traffic_impact, impact_penalty, total_fine
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            fine.violation_id,
            fine.zone_type,
            fine.base_penalty,
            fine.duration_seconds,
            fine.duration_penalty,
            fine.traffic_impact,
            fine.impact_penalty,
            fine.total_fine
        ))
        
        conn.commit()
        fine_id = cursor.lastrowid
        print(f"[FINE] Saved fine #{fine_id}: {fine.total_fine} LKR (Zone: {fine.zone_type})")
        return fine_id
        
    finally:
        conn.close()


def get_fine_by_violation(violation_id: int) -> Optional[Dict]:
    """
    Get fine breakdown for a specific violation.
    
    Args:
        violation_id: ID of the violation record.
        
    Returns:
        Dict with fine breakdown or None if not found.
    """
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT * FROM dynamic_fines WHERE violation_id = ?
        """, (violation_id,))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))
        
    finally:
        conn.close()


def update_payment_status(fine_id: int, status: str) -> bool:
    """
    Update the payment status of a fine.
    
    Args:
        fine_id: ID of the fine record.
        status: New status ('unpaid', 'paid', 'disputed')
        
    Returns:
        True if updated, False if not found.
    """
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE dynamic_fines SET payment_status = ? WHERE id = ?
        """, (status, fine_id))
        
        conn.commit()
        return cursor.rowcount > 0
        
    finally:
        conn.close()


def get_unpaid_fines(limit: int = 50) -> list:
    """
    Get list of all unpaid fines.
    
    Args:
        limit: Maximum number of records to return.
        
    Returns:
        List of fine records as dicts.
    """
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT * FROM dynamic_fines 
            WHERE payment_status = 'unpaid' 
            ORDER BY created_at DESC 
            LIMIT ?
        """, (limit,))
        
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
        
    finally:
        conn.close()


def calculate_and_save_fine(
    violation_id: int,
    violation_type: str,
    duration_seconds: int,
    vehicle_count_in_frame: int
) -> Dict:
    """
    Calculate fine and save to database in one step.
    
    Args:
        violation_id: ID of the violation record
        violation_type: Type of parking zone
        duration_seconds: Duration of violation
        vehicle_count_in_frame: Number of other vehicles affected
        
    Returns:
        Dict with fine ID and breakdown.
    """
    # Calculate
    fine = calculate_dynamic_fine(
        violation_type=violation_type,
        duration_seconds=duration_seconds,
        vehicle_count_in_frame=vehicle_count_in_frame,
        violation_id=violation_id
    )
    
    # Save
    fine_id = save_fine_to_database(fine)
    
    result = fine.to_dict()
    result['fine_id'] = fine_id
    
    return result


# =============================================================================
# CLI TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("DYNAMIC FINE CALCULATION SERVICE TEST")
    print("=" * 60)
    print()
    print("Formula: Fine = Base + (Duration × 5) + (Traffic_Impact × 50)")
    print()
    
    # Test cases
    test_cases = [
        {"zone": "no_parking", "duration": 60, "vehicles": 5},
        {"zone": "handicap_zone", "duration": 120, "vehicles": 3},
        {"zone": "fire_lane", "duration": 30, "vehicles": 10},
        {"zone": "bus_stop", "duration": 180, "vehicles": 8},
    ]
    
    print("-" * 60)
    print(f"{'Zone':<15} {'Duration':<10} {'Vehicles':<10} {'Total Fine':<12}")
    print("-" * 60)
    
    for case in test_cases:
        fine = calculate_dynamic_fine(
            violation_type=case["zone"],
            duration_seconds=case["duration"],
            vehicle_count_in_frame=case["vehicles"]
        )
        
        print(f"{case['zone']:<15} {case['duration']:>6}s    {case['vehicles']:>5}       {fine.total_fine:>8.0f} LKR")
    
    print("-" * 60)
    print()
    
    # Detailed breakdown for first case
    fine = calculate_dynamic_fine("no_parking", 60, 5, violation_id=1)
    print("Detailed Breakdown (no_parking, 60s, 5 vehicles):")
    print(f"  Base Penalty:     {fine.base_penalty:>8.0f} LKR")
    print(f"  Duration Penalty: {fine.duration_penalty:>8.0f} LKR (60 × 5)")
    print(f"  Impact Penalty:   {fine.impact_penalty:>8.0f} LKR (5 × 50)")
    print(f"  ─────────────────────────────")
    print(f"  TOTAL FINE:       {fine.total_fine:>8.0f} LKR")
    print()
    print("[OK] Fine calculation service test complete!")
