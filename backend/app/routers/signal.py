from typing import Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.fuzzy.traffic_controller import (
    FuzzyTrafficController,
    TrafficSignal,
    get_signal,
    get_four_way_controller,
    FUZZY_AVAILABLE,
)

router = APIRouter(prefix="/signal", tags=["Signal Control"])


# =============================================================================
# Pydantic Models
# =============================================================================

class SignalUpdateRequest(BaseModel):
    """Request model for updating signal timing."""
    vehicle_count: int
    signal_id: Optional[str] = "main"


class SignalStateRequest(BaseModel):
    """Request model for setting signal state."""
    state: str  # 'red', 'yellow', 'green'
    duration: Optional[int] = None


class SignalResponse(BaseModel):
    """Response model for signal status."""
    signal_id: str
    state: str
    remaining_time: int
    green_duration: int
    yellow_duration: int
    red_duration: int
    vehicle_count: int
    traffic_level: str


# =============================================================================
