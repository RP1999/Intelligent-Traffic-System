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
DB_PATH = settings.db_path


class ViolationType(str, Enum):
    """Types of traffic violations."""
    PARKING_NO_PARKING = "parking_no_parking"
    PARKING_NO_STOPPING = "parking_no_stopping"
    PARKING_OVERTIME = "parking_overtime"
    PARKING_HANDICAP = "parking_handicap"
    PARKING_LOADING = "parking_loading"
    SPEEDING = "speeding"
    RED_LIGHT = "red_light"
    WRONG_WAY = "wrong_way"
    LANE_VIOLATION = "lane_violation"
    RECKLESS_DRIVING = "reckless_driving"


# Violation severity and penalty points (aligned with LiveSafeScore spec)
VIOLATION_PENALTIES = {
    ViolationType.PARKING_NO_PARKING: {"points": 10, "fine": 100.0, "severity": "medium"},
    ViolationType.PARKING_NO_STOPPING: {"points": 10, "fine": 100.0, "severity": "medium"},
    ViolationType.PARKING_OVERTIME: {"points": 5, "fine": 50.0, "severity": "low"},
    ViolationType.PARKING_HANDICAP: {"points": 10, "fine": 200.0, "severity": "high"},
    ViolationType.PARKING_LOADING: {"points": 10, "fine": 75.0, "severity": "low"},
    ViolationType.SPEEDING: {"points": 8, "fine": 150.0, "severity": "medium"},
    ViolationType.RED_LIGHT: {"points": 25, "fine": 300.0, "severity": "high"},
    ViolationType.WRONG_WAY: {"points": 20, "fine": 500.0, "severity": "critical"},
    ViolationType.LANE_VIOLATION: {"points": 5, "fine": 80.0, "severity": "low"},
    ViolationType.RECKLESS_DRIVING: {"points": 25, "fine": 1000.0, "severity": "critical"},
}


@dataclass
class ViolationRecord:
    """Record of a single violation event."""
    violation_id: str
    driver_id: str
    violation_type: ViolationType
    timestamp: float
    location: Optional[str] = None
    points_deducted: int = 0
    fine_amount: float = 0.0
    license_plate: Optional[str] = None
    snapshot_path: Optional[str] = None
    notes: str = ""
    
    def to_dict(self) -> dict:
        return {
            "violation_id": self.violation_id,
            "driver_id": self.driver_id,
            "violation_type": self.violation_type.value,
            "timestamp": datetime.fromtimestamp(self.timestamp).isoformat(),
            "location": self.location,
            "points_deducted": self.points_deducted,
            "fine_amount": self.fine_amount,
            "license_plate": self.license_plate,
            "snapshot_path": self.snapshot_path,
            "notes": self.notes,
        }


@dataclass
class DriverScore:
    """
    Driver score tracking with violation history.
    
    Score ranges:
    - 100-90: Excellent (Green)
    - 89-70: Good (Yellow-Green)
    - 69-50: Fair (Yellow)
    - 49-30: Poor (Orange)
    - 29-0: Critical (Red)
    """
    driver_id: str  # Can be license plate or device ID
    current_score: int = 100
    total_violations: int = 0
    total_fines: float = 0.0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    violation_history: List[ViolationRecord] = field(default_factory=list)
    
    @property
    def risk_level(self) -> str:
        """Get risk level based on current score."""
        if self.current_score >= 90:
            return "excellent"
        elif self.current_score >= 70:
            return "good"
        elif self.current_score >= 50:
            return "fair"
        elif self.current_score >= 30:
            return "poor"
        else:
            return "critical"
    
    @property
    def risk_color(self) -> Tuple[int, int, int]:
        """Get BGR color for visualization based on risk level."""
        colors = {
            "excellent": (0, 255, 0),      # Green
            "good": (0, 200, 100),         # Yellow-Green
            "fair": (0, 255, 255),         # Yellow
            "poor": (0, 165, 255),         # Orange
            "critical": (0, 0, 255),       # Red
        }
        return colors.get(self.risk_level, (128, 128, 128))
    
    def apply_violation(self, violation_type: ViolationType, violation_id: str = None,
                        location: str = None, license_plate: str = None,
                        snapshot_path: str = None, notes: str = "") -> ViolationRecord:
        """
        Apply a violation penalty to this driver's score.
        
        Args:
            violation_type: Type of violation
            violation_id: Unique ID for this violation
            location: Location description
            license_plate: License plate if detected
            snapshot_path: Path to violation snapshot image
            notes: Additional notes
            
        Returns:
            ViolationRecord for the applied violation
        """
        penalty = VIOLATION_PENALTIES.get(violation_type, {"points": 5, "fine": 50.0})
        points = penalty["points"]
        fine = penalty["fine"]
        
        # Apply penalty (score cannot go below 0)
        self.current_score = max(0, self.current_score - points)
        self.total_violations += 1
        self.total_fines += fine
        self.updated_at = time.time()
        
        # Create violation record
        record = ViolationRecord(
            violation_id=violation_id or f"VR-{int(time.time())}-{self.total_violations}",
            driver_id=self.driver_id,
            violation_type=violation_type,
            timestamp=time.time(),
            location=location,
            points_deducted=points,
            fine_amount=fine,
            license_plate=license_plate,
            snapshot_path=snapshot_path,
            notes=notes,
        )
        
        self.violation_history.append(record)
        
        # Keep only last 100 violations in memory
        if len(self.violation_history) > 100:
            self.violation_history = self.violation_history[-100:]
        
        return record
    
    def recover_points(self, days_clean: int = 30, points_per_period: int = 5) -> int:
        """
        Recover points based on clean driving period.
        
        Args:
            days_clean: Days without violations
            points_per_period: Points to recover per period
            
        Returns:
            Points recovered
        """
        if self.current_score >= 100:
            return 0
        
        # Check last violation time
        if self.violation_history:
            last_violation = max(v.timestamp for v in self.violation_history)
            days_since = (time.time() - last_violation) / 86400
        else:
            days_since = (time.time() - self.created_at) / 86400
        
        # Calculate recovery
        periods = int(days_since / days_clean)
        recovery = min(periods * points_per_period, 100 - self.current_score)
        
        if recovery > 0:
            self.current_score += recovery
            self.updated_at = time.time()
        
        return recovery
    
    def to_dict(self) -> dict:
        return {
            "driver_id": self.driver_id,
            "current_score": self.current_score,
            "risk_level": self.risk_level,
            "total_violations": self.total_violations,
            "total_fines": round(self.total_fines, 2),
            "created_at": datetime.fromtimestamp(self.created_at).isoformat(),
            "updated_at": datetime.fromtimestamp(self.updated_at).isoformat(),
            "recent_violations": [v.to_dict() for v in self.violation_history[-10:]],
        }


class ScoringEngine:
    """
    Central scoring engine for managing driver scores.
    """
    
    def __init__(self, initial_score: int = None):
        """
        Initialize scoring engine.
        
        Args:
            initial_score: Starting score for new drivers (default from settings)
        """
        self.initial_score = initial_score or settings.initial_driver_score
        self.drivers: Dict[str, DriverScore] = {}
        self._violation_counter = 0
    
    def get_or_create_driver(self, driver_id: str) -> DriverScore:
        """
        Get existing driver score or create new one.
        
        Args:
            driver_id: Unique driver identifier (license plate or device ID)
            
        Returns:
            DriverScore instance
        """
        if driver_id not in self.drivers:
            self.drivers[driver_id] = DriverScore(
                driver_id=driver_id,
                current_score=self.initial_score,
            )
        return self.drivers[driver_id]
    
    def record_violation(
        self,
        driver_id: str,
        violation_type: ViolationType,
        location: str = None,
        license_plate: str = None,
        snapshot_path: str = None,
        notes: str = "",
    ) -> Tuple[DriverScore, ViolationRecord]:
        """
        Record a violation for a driver.
        
        Args:
            driver_id: Driver identifier
            violation_type: Type of violation
            location: Location description
            license_plate: Detected license plate
            snapshot_path: Path to snapshot image
            notes: Additional notes
            
        Returns:
            Tuple of (updated DriverScore, ViolationRecord)
        """
        driver = self.get_or_create_driver(driver_id)
        
        self._violation_counter += 1
        violation_id = f"VIO-{int(time.time())}-{self._violation_counter:04d}"
        
        record = driver.apply_violation(
            violation_type=violation_type,
            violation_id=violation_id,
            location=location,
            license_plate=license_plate,
            snapshot_path=snapshot_path,
            notes=notes,
        )
        
        # Persist to database
        self._save_to_database(driver, record)
        
        return driver, record
    
    def _save_to_database(self, driver: DriverScore, violation: ViolationRecord):
        """
        Persist driver and violation data to SQLite database.
        """
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()
            
            # First insert the violation record (using driver_violations table)
            cursor.execute("""
                INSERT INTO driver_violations (violation_id, driver_id, violation_type, timestamp, location, points_deducted, fine_amount, license_plate, snapshot_path, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                violation.violation_id,
                violation.driver_id,
                violation.violation_type.value,
                violation.timestamp,
                violation.location or "Unknown",
                violation.points_deducted,
                violation.fine_amount,
                violation.license_plate,
                violation.snapshot_path,
                violation.notes,
            ))
            
            # Now calculate actual totals from database
            cursor.execute("""
                SELECT COUNT(*) as count, COALESCE(SUM(fine_amount), 0) as total_fines
                FROM driver_violations WHERE driver_id = ?
            """, (driver.driver_id,))
            row = cursor.fetchone()
            actual_violations = row[0] if row else 0
            actual_fines = row[1] if row else 0.0
            
            # Calculate score based on actual violations (10 points per violation, min 0)
            calculated_score = max(0, 100 - (actual_violations * 10))
            
            # Update or insert driver with correct counts
            cursor.execute("""
                INSERT INTO drivers (driver_id, current_score, total_violations, total_fines, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(driver_id) DO UPDATE SET
                    current_score = ?,
                    total_violations = ?,
                    total_fines = ?,
                    updated_at = ?
            """, (
                driver.driver_id,
                calculated_score,
                actual_violations,
                actual_fines,
                driver.created_at,  # Store timestamp as float (REAL)
                time.time(),        # Store timestamp as float (REAL)
                # For UPDATE clause
                calculated_score,
                actual_violations,
                actual_fines,
                time.time(),
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"[SCORING] DB Error: {e}")
    
    def get_driver_score(self, driver_id: str) -> Optional[DriverScore]:
        """Get driver score if exists."""
        return self.drivers.get(driver_id)
    
    def get_all_drivers(self) -> List[DriverScore]:
        """Get all driver scores."""
        return list(self.drivers.values())
    
    def get_leaderboard(self, limit: int = 10, ascending: bool = False) -> List[DriverScore]:
        """
        Get driver leaderboard sorted by score.
        
        Args:
            limit: Maximum number of drivers to return
            ascending: If True, show worst drivers first
            
        Returns:
            Sorted list of DriverScore
        """
        sorted_drivers = sorted(
            self.drivers.values(),
            key=lambda d: d.current_score,
            reverse=not ascending,
        )
        return sorted_drivers[:limit]
    
    def get_high_risk_drivers(self, threshold: int = 50) -> List[DriverScore]:
        """Get drivers with score below threshold."""
        return [d for d in self.drivers.values() if d.current_score < threshold]
    
    def get_statistics(self) -> dict:
        """Get overall scoring statistics."""
        if not self.drivers:
            return {
                "total_drivers": 0,
                "average_score": 0,
                "total_violations": 0,
                "total_fines": 0,
                "high_risk_count": 0,
            }
        
        scores = [d.current_score for d in self.drivers.values()]
        total_violations = sum(d.total_violations for d in self.drivers.values())
        total_fines = sum(d.total_fines for d in self.drivers.values())
        high_risk = len(self.get_high_risk_drivers())
        
        return {
            "total_drivers": len(self.drivers),
            "average_score": round(sum(scores) / len(scores), 1),
            "min_score": min(scores),
            "max_score": max(scores),
            "total_violations": total_violations,
            "total_fines": round(total_fines, 2),
            "high_risk_count": high_risk,
            "risk_distribution": {
                "excellent": sum(1 for d in self.drivers.values() if d.risk_level == "excellent"),
                "good": sum(1 for d in self.drivers.values() if d.risk_level == "good"),
                "fair": sum(1 for d in self.drivers.values() if d.risk_level == "fair"),
                "poor": sum(1 for d in self.drivers.values() if d.risk_level == "poor"),
                "critical": sum(1 for d in self.drivers.values() if d.risk_level == "critical"),
            },
        }
    
    def reset(self):
        """Reset all driver scores."""
        self.drivers.clear()
        self._violation_counter = 0


# Global scoring engine instance
_scoring_engine: Optional[ScoringEngine] = None


def get_scoring_engine() -> ScoringEngine:
    """Get or create the global scoring engine instance."""
    global _scoring_engine
    if _scoring_engine is None:
        _scoring_engine = ScoringEngine()
    return _scoring_engine


# =============================================================================
# Utility: Map parking zone type to violation type
# =============================================================================

def parking_zone_to_violation_type(zone_type: str) -> ViolationType:
    """Convert parking zone type to violation type."""
    mapping = {
        "no_parking": ViolationType.PARKING_NO_PARKING,
        "no_stopping": ViolationType.PARKING_NO_STOPPING,
        "limited": ViolationType.PARKING_OVERTIME,
        "handicap": ViolationType.PARKING_HANDICAP,
        "loading": ViolationType.PARKING_LOADING,
    }
    return mapping.get(zone_type, ViolationType.PARKING_NO_PARKING)


# =============================================================================
# CLI for testing
# =============================================================================

if __name__ == "__main__":
    # Demo the scoring system
    engine = ScoringEngine()
    
    # Create some test drivers
    print("🚗 Testing Scoring Engine\n")
    
    # Driver 1: Good driver with one violation
    driver1, vio1 = engine.record_violation(
        driver_id="ABC-1234",
        violation_type=ViolationType.PARKING_NO_PARKING,
        location="Main St No Parking Zone",
    )
    print(f"Driver {driver1.driver_id}: Score={driver1.current_score}, Risk={driver1.risk_level}")
    
    # Driver 2: Multiple violations
    driver2, _ = engine.record_violation("XYZ-5678", ViolationType.SPEEDING)
    driver2, _ = engine.record_violation("XYZ-5678", ViolationType.RED_LIGHT)
    driver2, _ = engine.record_violation("XYZ-5678", ViolationType.PARKING_NO_STOPPING)
    print(f"Driver {driver2.driver_id}: Score={driver2.current_score}, Risk={driver2.risk_level}")
    
    # Driver 3: Critical violations
    driver3, _ = engine.record_violation("BAD-0000", ViolationType.RECKLESS_DRIVING)
    driver3, _ = engine.record_violation("BAD-0000", ViolationType.WRONG_WAY)
    print(f"Driver {driver3.driver_id}: Score={driver3.current_score}, Risk={driver3.risk_level}")
    
    # Show statistics
    print("\n📊 Statistics:")
    stats = engine.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # Show leaderboard
    print("\n🏆 Leaderboard (Best Drivers):")
    for i, d in enumerate(engine.get_leaderboard(5), 1):
        print(f"  {i}. {d.driver_id}: {d.current_score} pts ({d.risk_level})")
    
    # Show high-risk drivers
    print("\n⚠️ High-Risk Drivers:")
    for d in engine.get_high_risk_drivers():
        print(f"  - {d.driver_id}: {d.current_score} pts, {d.total_violations} violations")
