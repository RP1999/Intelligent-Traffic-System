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
    'CRITICAL': (80, 101),
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class RiskScore:
    """Container for risk score calculation result."""
    vehicle_id: int
    plate_number: Optional[str]
    risk_score: float
    speed_factor: float
    violation_history_factor: float
    risk_level: str
    current_speed: float
    speed_limit: float
    violation_count: int
    
    def to_dict(self) -> dict:
        return {
            'vehicle_id': self.vehicle_id,
            'plate_number': self.plate_number,
            'risk_score': round(self.risk_score, 1),
            'speed_factor': round(self.speed_factor, 1),
            'violation_history_factor': round(self.violation_history_factor, 1),
            'risk_level': self.risk_level,
            'current_speed': round(self.current_speed, 1),
            'speed_limit': self.speed_limit,
            'violation_count': self.violation_count,
            'formula': '(Speed_Factor × 0.6) + (History_Factor × 0.4)',
            'weights': {
                'speed': SPEED_WEIGHT,
                'history': HISTORY_WEIGHT
            }
        }


# =============================================================================
# CORE FUNCTIONS
# =============================================================================

def calculate_speed_factor(current_speed: float, speed_limit: float) -> float:
    """
    Calculate the speed factor component of risk score.
    
    Scale: 0-100 based on how fast relative to limit.
    
    Args:
        current_speed: Current vehicle speed (km/h or pixel equivalent)
        speed_limit: Speed limit for the zone
        
    Returns:
        Speed factor (0-100)
    """
    if speed_limit <= 0:
        speed_limit = 60.0  # Default
    
    speed_ratio = current_speed / speed_limit
    
    # Calculate speed factor based on ratio brackets
    if speed_ratio <= 0.8:
        # Safe speed (under 80% of limit)
        speed_factor = 0
    elif speed_ratio <= 1.0:
        # Approaching limit (80-100%)
        # Linear scale: 0-20
        speed_factor = (speed_ratio - 0.8) * 100  # 0 at 0.8, 20 at 1.0
    elif speed_ratio <= 1.2:
        # Slightly over (100-120%)
        # Linear scale: 20-50
        speed_factor = 20 + (speed_ratio - 1.0) * 150  # 20 at 1.0, 50 at 1.2
    elif speed_ratio <= 1.5:
        # Significantly over (120-150%)
        # Linear scale: 50-100
        speed_factor = 50 + (speed_ratio - 1.2) * 166.67  # 50 at 1.2, 100 at 1.5
    else:
        # Extremely over (>150%)
        speed_factor = 100
    
    return min(100, max(0, speed_factor))


def calculate_history_factor(violation_history_count: int = None, violations: List[Dict] = None) -> float:
    """
    Calculate the violation history factor component of risk score.
    
    Scale: 0-100 based on past violations.
    
    Args:
        violation_history_count: Simple count of violations (if no details available)
        violations: List of violation dicts with 'type' key (for weighted calculation)
        
    Returns:
        History factor (0-100)
    """
    history_score = 0
    
    if violations:
        # Weighted calculation based on violation types
        for v in violations:
            violation_type = v.get('type', v.get('violation_type', 'default'))
            weight = VIOLATION_WEIGHTS.get(violation_type.lower(), VIOLATION_WEIGHTS['default'])
            history_score += weight
    elif violation_history_count is not None:
        # Simple calculation: 10 points per violation
        history_score = violation_history_count * 10
    
    # Cap at 100
    return min(100, history_score)


def get_risk_level(score: float) -> str:
    """
    Get risk level classification from score.
    
    Args:
        score: Risk score (0-100)
        
    Returns:
        Risk level string: 'LOW', 'MEDIUM', 'HIGH', or 'CRITICAL'
    """
    for level, (low, high) in RISK_LEVELS.items():
        if low <= score < high:
            return level
    return 'CRITICAL'


def calculate_risk(
    speed: float,
    speed_limit: float,
    violation_history_count: int,
    vehicle_id: int = 0,
    plate_number: str = None
) -> RiskScore:
    """
    Calculate accident risk score for a vehicle.
    
    Formula: Risk_Score = (Speed_Factor × 0.6) + (History_Factor × 0.4)
    
    Args:
        speed: Current vehicle speed
        speed_limit: Speed limit for the zone
        violation_history_count: Number of past violations (last 30 days)
        vehicle_id: Optional vehicle/track ID
        plate_number: Optional license plate
        
    Returns:
        RiskScore object with detailed calculation.
    """
    # Calculate components
    speed_factor = calculate_speed_factor(speed, speed_limit)
    history_factor = calculate_history_factor(violation_history_count=violation_history_count)
    
    # Final risk score
    risk_score = (speed_factor * SPEED_WEIGHT) + (history_factor * HISTORY_WEIGHT)
    
    # Get risk level
    risk_level = get_risk_level(risk_score)
    
    return RiskScore(
        vehicle_id=vehicle_id,
        plate_number=plate_number,
        risk_score=risk_score,
        speed_factor=speed_factor,
        violation_history_factor=history_factor,
        risk_level=risk_level,
        current_speed=speed,
        speed_limit=speed_limit,
        violation_count=violation_history_count
    )


def save_risk_score_to_database(risk: RiskScore) -> int:
    """
    Save the calculated risk score to the risk_scores table.
    
    Args:
        risk: RiskScore object with calculation details.
        
    Returns:
        ID of the inserted record.
    """
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO risk_scores (
                vehicle_id, plate_number, risk_score, speed_factor,
                violation_history_factor, risk_level, current_speed, speed_limit
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            risk.vehicle_id,
            risk.plate_number,
            risk.risk_score,
            risk.speed_factor,
            risk.violation_history_factor,
            risk.risk_level,
            risk.current_speed,
            risk.speed_limit
        ))
        
        conn.commit()
        risk_id = cursor.lastrowid
        print(f"[RISK] Saved score #{risk_id}: {risk.risk_score:.1f} ({risk.risk_level}) for vehicle {risk.vehicle_id}")
        return risk_id
        
    finally:
        conn.close()


def get_recent_violations(vehicle_id: int = None, plate_number: str = None, days: int = 30) -> List[Dict]:
    """
    Get recent violations for a vehicle from the database.
    
    Args:
        vehicle_id: Track ID of the vehicle
        plate_number: License plate number
        days: Number of days to look back
        
    Returns:
        List of violation dicts.
    """
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    try:
        # Calculate date threshold
        threshold = (datetime.now() - timedelta(days=days)).isoformat()
        
