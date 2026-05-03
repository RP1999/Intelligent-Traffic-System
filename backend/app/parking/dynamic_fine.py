"""
Dynamic Fine Calculation Module
Based on Proposal IT22925572 (Gunarathna R.P)

Formula: Fine = Base_Penalty + (Duration_Seconds × Rate_Per_Second) + (Traffic_Impact × Multiplier)

Where:
- Base_Penalty: Zone-specific base fine amount (LKR)
- Duration_Seconds: Time parked in violation zone
- Rate_Per_Second: Fine rate per second over grace period (LKR/sec)
- Traffic_Impact: Count of OTHER moving vehicles in frame during violation
- Multiplier: Cost per affected vehicle (LKR/vehicle)
"""

from dataclasses import dataclass
from typing import Dict, Optional, Any
from enum import Enum


class ZoneType(str, Enum):
    """Type of parking zone."""
    NO_PARKING = "no_parking"
    NO_STOPPING = "no_stopping"
    LIMITED_PARKING = "limited"
    HANDICAP = "handicap"
    LOADING = "loading"
    FIRE_LANE = "fire_lane"
    BUS_STOP = "bus_stop"
    SCHOOL_ZONE = "school_zone"


@dataclass
class DynamicFineParams:
    """Parameters for dynamic fine calculation."""
    # Base penalties by zone type (LKR)
    base_penalties: Dict[str, float] = None
    # Duration rate (LKR per second) — admin default: 100 LKR/min = 1.67/sec
    duration_rate: float = 1.67
    # Traffic impact multiplier (LKR per affected vehicle) — matches admin default
    traffic_multiplier: float = 500.0
    # Grace period before fine starts accumulating (seconds)
    grace_period_seconds: int = 30
    # Maximum duration penalty cap (LKR)
    max_duration_penalty: float = 10000.0
    
    def __post_init__(self):
        if self.base_penalties is None:
            self.base_penalties = {
                ZoneType.NO_PARKING.value: 1000.0,
                ZoneType.NO_STOPPING.value: 1500.0,
                ZoneType.LIMITED_PARKING.value: 500.0,
                ZoneType.HANDICAP.value: 2500.0,
                ZoneType.LOADING.value: 750.0,
                ZoneType.FIRE_LANE.value: 3000.0,
                ZoneType.BUS_STOP.value: 1500.0,
                ZoneType.SCHOOL_ZONE.value: 2000.0,
            }


@dataclass
class FineBreakdown:
    """Detailed breakdown of calculated fine."""
    base_penalty: float
    duration_seconds: float
    duration_penalty: float
    traffic_impact_count: int
    traffic_impact_penalty: float
    total_fine: float
    zone_type: str
    grace_period_applied: bool = False
    
    def to_dict(self) -> dict:
        return {
            "base_penalty": round(self.base_penalty, 2),
            "duration_seconds": round(self.duration_seconds, 1),
            "duration_penalty": round(self.duration_penalty, 2),
            "traffic_impact_count": self.traffic_impact_count,
            "traffic_impact_penalty": round(self.traffic_impact_penalty, 2),
            "total_fine": round(self.total_fine, 2),
            "zone_type": self.zone_type,
            "grace_period_applied": self.grace_period_applied,
        }


class DynamicFineCalculator:
    """
    Calculates dynamic fines based on IT22925572 proposal formula.
    
    Formula: Fine = Base + (Duration × Rate) + (Traffic_Impact × Multiplier)
    """
    
    def __init__(self, params: DynamicFineParams = None):
        """Initialize with parameters (or use defaults)."""
        self.params = params or DynamicFineParams()
    
    def update_params(self, params: DynamicFineParams) -> None:
        """Update calculation parameters."""
        self.params = params
    
    def update_from_settings(self, settings: dict) -> None:
        """Update parameters from settings dict (from API/DB)."""
        parking_settings = settings.get("parking", {})
        
        self.params.grace_period_seconds = parking_settings.get("grace_period_seconds", 30)
        self.params.duration_rate = parking_settings.get("duration_rate_per_minute", 100.0) / 60.0  # Convert to per second
        self.params.traffic_multiplier = parking_settings.get("traffic_impact_cost", 500.0)
        self.params.max_duration_penalty = parking_settings.get("max_duration_penalty", 10000.0)
        
        # Update base penalties from fine settings
        fines_settings = settings.get("fines", {})
        if fines_settings:
            # Map fine settings to zone types
            zone_fine_mapping = {
                "parking_no_parking": ZoneType.NO_PARKING.value,
                "parking_no_stopping": ZoneType.NO_STOPPING.value,
                "parking_overtime": ZoneType.LIMITED_PARKING.value,
                "parking_handicap": ZoneType.HANDICAP.value,
                "parking_loading": ZoneType.LOADING.value,
            }
            for fine_key, zone_type in zone_fine_mapping.items():
                if fine_key in fines_settings:
                    fine_data = fines_settings[fine_key]
                    if isinstance(fine_data, dict):
                        self.params.base_penalties[zone_type] = fine_data.get("fine", 1000.0)
    
    def calculate(
        self,
        zone_type: str,
        duration_seconds: float,
        traffic_impact_count: int = 0,
    ) -> FineBreakdown:
        """
        Calculate dynamic fine with full breakdown.
        
        Args:
            zone_type: Type of parking zone (no_parking, handicap, etc.)
            duration_seconds: Total time parked in violation zone
            traffic_impact_count: Number of other moving vehicles affected
            
        Returns:
            FineBreakdown with all penalty components
        """
        # 1. Base penalty from zone type
        base_penalty = self.params.base_penalties.get(zone_type, 1000.0)
        
        # 2. Duration penalty (only after grace period)
        effective_duration = max(0, duration_seconds - self.params.grace_period_seconds)
        grace_period_applied = effective_duration < duration_seconds
        
        duration_penalty = effective_duration * self.params.duration_rate
        # Cap duration penalty
        duration_penalty = min(duration_penalty, self.params.max_duration_penalty)
        
        # 3. Traffic impact penalty
        traffic_impact_penalty = traffic_impact_count * self.params.traffic_multiplier
        
        # 4. Total fine
        total_fine = base_penalty + duration_penalty + traffic_impact_penalty
        
        return FineBreakdown(
            base_penalty=base_penalty,
            duration_seconds=duration_seconds,
            duration_penalty=duration_penalty,
            traffic_impact_count=traffic_impact_count,
            traffic_impact_penalty=traffic_impact_penalty,
            total_fine=total_fine,
            zone_type=zone_type,
            grace_period_applied=grace_period_applied,
        )
    
    def calculate_simple(
        self,
        zone_type: str,
        duration_seconds: float = 0,
        traffic_impact_count: int = 0,
    ) -> float:
        """Calculate fine and return just the total amount."""
        breakdown = self.calculate(zone_type, duration_seconds, traffic_impact_count)
        return breakdown.total_fine
    
    def get_preview(
        self,
        zone_type: str,
        estimated_duration_seconds: float = 60,
        estimated_traffic_impact: int = 5,
    ) -> dict:
        """
        Get a preview of what the fine would be (for warning displays).
        Used during grace period to show driver potential fine.
        """
        breakdown = self.calculate(zone_type, estimated_duration_seconds, estimated_traffic_impact)
        return {
            "estimated_fine": round(breakdown.total_fine, 2),
            "breakdown": breakdown.to_dict(),
            "warning": f"Potential fine: LKR {breakdown.total_fine:,.0f}",
            "grace_period_remaining": max(0, self.params.grace_period_seconds),
        }


# Global calculator instance with default params
_calculator = DynamicFineCalculator()


def get_fine_calculator() -> DynamicFineCalculator:
    """Get the global fine calculator instance."""
    return _calculator


def calculate_dynamic_fine(
    zone_type: str,
    duration_seconds: float = 0,
    traffic_impact_count: int = 0,
) -> FineBreakdown:
    """
    Convenience function to calculate dynamic fine.
    
    Args:
        zone_type: Type of parking zone
        duration_seconds: Time parked in violation zone
        traffic_impact_count: Number of other vehicles affected
        
    Returns:
        FineBreakdown with complete penalty details
    """
    return _calculator.calculate(zone_type, duration_seconds, traffic_impact_count)


def get_fine_amount(
    zone_type: str,
    duration_seconds: float = 0,
    traffic_impact_count: int = 0,
) -> float:
    """Get just the fine amount (for backwards compatibility)."""
    return _calculator.calculate_simple(zone_type, duration_seconds, traffic_impact_count)
