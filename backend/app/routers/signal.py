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
    states = controller.get_status()
    
    print(f"[4WAY] North count updated: {vehicle_count} vehicles")
    
    return {
        "message": f"North lane updated with {vehicle_count} vehicles",
        "junction_status": states
    }


@router.post("/4way/emergency", summary="Trigger emergency mode")
async def trigger_4way_emergency(lane: str = Query("north", regex="^(north|south|east|west)$")):
    """
    Trigger emergency mode - forces specified lane GREEN.
    
    This simulates an ambulance detection. In production, this is 
    automatically triggered by YOLO when ambulance class is detected.
    """
    controller = get_four_way_controller()
    result = controller.activate_emergency_mode(lane)
    
    print(f"[4WAY] EMERGENCY MODE ACTIVATED - {lane.upper()} forced GREEN")
    
    return result


@router.post("/4way/emergency/stop", summary="Deactivate emergency mode")
async def stop_4way_emergency():
    """Deactivate emergency mode and resume normal cycle."""
    controller = get_four_way_controller()
    result = controller.deactivate_emergency_mode()
    
    print(f"[4WAY] Emergency mode deactivated - resuming normal cycle")
    
    return result


@router.post("/4way/tick", summary="Advance 4-way signal timer")
async def tick_4way(seconds: int = Query(1, ge=1, le=60)):
    """
    Manually advance the 4-way signal timer.
    Useful for demo/testing purposes.
    """
    controller = get_four_way_controller()
    states = controller.tick(seconds)
    
    print(f"[4WAY] Ticked {seconds}s | Green={states['current_green'].upper()} | Remaining={states['green_remaining']}s")
    
    return {
        "ticked_seconds": seconds,
        "junction_status": states
    }


@router.post("/update", summary="Update signal timing based on traffic")
async def update_signal(request: SignalUpdateRequest):
    """
    Update signal timing based on vehicle count using fuzzy logic.
    
    This endpoint:
    1. Takes the current vehicle count
    2. Runs fuzzy inference to determine optimal green duration
    3. Updates the signal timing parameters
    
    The fuzzy rules:
    - Low traffic (0-5 vehicles) → Short green (~10-20s)
    - Medium traffic (5-15 vehicles) → Medium green (~20-40s)
    - High traffic (15+ vehicles) → Long green (~40-60s)
    """
    signal = get_signal()
    recommendation = signal.update_timing(request.vehicle_count)
    
    return {
        "message": "Signal timing updated",
