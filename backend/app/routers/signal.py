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
# Endpoints - Single Signal (Legacy)
# =============================================================================

@router.get("/status", summary="Get signal status")
async def get_signal_status():
    """Get current traffic signal status (legacy single signal)."""
    signal = get_signal()
    status = signal.get_status()
    print(f"[API] /signal/status -> State={status['state']}, Remaining={status['remaining_time']}s, Vehicles={status['vehicle_count']}")
    return status


# =============================================================================
# Endpoints - 4-WAY JUNCTION (NEW)
# =============================================================================

@router.get("/4way/status", summary="Get 4-way junction status")
async def get_4way_status():
    """
    Get current status of all 4 lanes in the hybrid junction.
    
    - North: Real data from YOLO video detection
    - South/East/West: Simulated data (random, updates every 10s)
    """
    controller = get_four_way_controller()
    states = controller.get_status()
    
    # Log for debugging
    north = states['lanes']['north']
    print(f"[4WAY] Green={states['current_green'].upper()} | North: {north['vehicle_count']} vehicles | Remaining={states['green_remaining']}s | Emergency={states['emergency_mode']}")
    
    return states


@router.post("/4way/update", summary="Update North lane vehicle count")
async def update_4way_north(vehicle_count: int = Query(..., ge=0, le=100)):
    """
    Update the North lane vehicle count (from YOLO detection).
    
    This is called by the detection system to update the real traffic data.
    """
    controller = get_four_way_controller()
    controller.update_north_count(vehicle_count)
