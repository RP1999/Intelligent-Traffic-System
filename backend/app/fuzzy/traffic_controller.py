import time
import asyncio
import random
import numpy as np
from typing import Dict, Optional, List

try:
    import skfuzzy as fuzz
    from skfuzzy import control as ctrl
    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False
    print("[WARNING] scikit-fuzzy not installed. Run: pip install scikit-fuzzy")


class FuzzyTrafficController:
    """
    Fuzzy logic controller for adaptive traffic signal timing.
    
    Input: Vehicle count at intersection
    Output: Green light duration in seconds
    
    Fuzzy Rules:
    - Low traffic (0-5 vehicles) → Short green (10-20s)
    - Medium traffic (5-15 vehicles) → Medium green (20-40s)
    - High traffic (15+ vehicles) → Long green (40-60s)
    """
    
    def __init__(self, min_green: int = 10, max_green: int = 60):
        """
        Initialize the fuzzy controller.
        
        Args:
            min_green: Minimum green light duration (seconds)
            max_green: Maximum green light duration (seconds)
        """
        self.min_green = min_green
        self.max_green = max_green
        self.simulation = None
        
        if FUZZY_AVAILABLE:
            self._setup_fuzzy_system()
        else:
            print("⚠️ Running in fallback mode (linear interpolation)")
    
    def _setup_fuzzy_system(self):
        """Set up the fuzzy inference system."""
        # Define fuzzy variables
        
        # Input: Vehicle count (0 to 30)
        self.vehicle_count = ctrl.Antecedent(np.arange(0, 31, 1), 'vehicle_count')
        
        # Output: Green light duration (10 to 60 seconds)
        self.green_duration = ctrl.Consequent(np.arange(self.min_green, self.max_green + 1, 1), 'green_duration')
        
        # Define membership functions for vehicle count (shifted lower for demo)
        # Low: mostly 0-4, Medium: 2-12, High: 8-30
        self.vehicle_count['low'] = fuzz.trimf(self.vehicle_count.universe, [0, 0, 4])
        self.vehicle_count['medium'] = fuzz.trimf(self.vehicle_count.universe, [2, 6, 12])
        self.vehicle_count['high'] = fuzz.trimf(self.vehicle_count.universe, [8, 15, 30])
        
        # Define membership functions for green duration
        self.green_duration['short'] = fuzz.trimf(self.green_duration.universe, 
                                                   [self.min_green, self.min_green, 25])
        self.green_duration['medium'] = fuzz.trimf(self.green_duration.universe, 
                                                    [20, 35, 50])
        self.green_duration['long'] = fuzz.trimf(self.green_duration.universe, 
                                                  [40, self.max_green, self.max_green])
        
        # Define fuzzy rules
        rule1 = ctrl.Rule(self.vehicle_count['low'], self.green_duration['short'])
        rule2 = ctrl.Rule(self.vehicle_count['medium'], self.green_duration['medium'])
        rule3 = ctrl.Rule(self.vehicle_count['high'], self.green_duration['long'])
        
        # Create control system
        self.traffic_ctrl = ctrl.ControlSystem([rule1, rule2, rule3])
        self.simulation = ctrl.ControlSystemSimulation(self.traffic_ctrl)
        
        print("✅ Fuzzy traffic controller initialized")
    
    def compute_green_duration(self, vehicle_count: int) -> int:
        """
        Compute optimal green light duration based on vehicle count.
        
        Args:
            vehicle_count: Number of vehicles waiting at intersection
            
        Returns:
            Green light duration in seconds
        """
        # Clamp vehicle count to valid range
        vehicle_count = max(0, min(30, vehicle_count))
        
        if self.simulation is not None:
            try:
                self.simulation.input['vehicle_count'] = vehicle_count
                self.simulation.compute()
                duration = int(self.simulation.output['green_duration'])
                return max(self.min_green, min(self.max_green, duration))
            except Exception as e:
                print(f"⚠️ Fuzzy computation error: {e}")
        
        # Fallback: Linear interpolation
        return self._linear_fallback(vehicle_count)
    
    def _linear_fallback(self, vehicle_count: int) -> int:
        """Fallback linear interpolation if fuzzy system unavailable."""
        # Map 0-30 vehicles to min_green-max_green seconds
        ratio = vehicle_count / 30.0
        duration = self.min_green + ratio * (self.max_green - self.min_green)
        return int(duration)
    
    def get_traffic_level(self, vehicle_count: int) -> str:
        """
        Get traffic level classification.
        
        Args:
            vehicle_count: Number of vehicles
            
        Returns:
            Traffic level: 'low', 'medium', or 'high'
        """
        # Make thresholds lower for demo so green appears with fewer vehicles
        if vehicle_count <= 2:
            return 'low'
        elif vehicle_count <= 8:
            return 'medium'
        else:
            return 'high'
    
    def get_signal_recommendation(self, vehicle_count: int) -> dict:
        """
        Get full signal recommendation with all details.
        
        Args:
            vehicle_count: Number of vehicles at intersection
            
        Returns:
            Dictionary with duration, traffic_level, and recommendation details
        """
        duration = self.compute_green_duration(vehicle_count)
        traffic_level = self.get_traffic_level(vehicle_count)
        
        return {
            "vehicle_count": vehicle_count,
            "traffic_level": traffic_level,
            "green_duration_sec": duration,
            "yellow_duration_sec": 3,  # Standard yellow light
            "red_duration_sec": max(10, 70 - duration),  # Remaining time for cross traffic
            "cycle_time_sec": duration + 3 + max(10, 70 - duration),
            "fuzzy_available": FUZZY_AVAILABLE,
        }


# =============================================================================
# Traffic Signal State Machine
# =============================================================================

class TrafficSignal:
    """
    Traffic signal state machine with timing control.
    Auto-advances based on elapsed time.
    """
    
    STATES = ['red', 'yellow', 'green']
    
    def __init__(self, signal_id: str = "main"):
        self.signal_id = signal_id
        self.state = 'red'
        self.remaining_time = 30  # Default red duration
        self.green_duration = 30
        self.yellow_duration = 3
        self.red_duration = 30
        self.controller = FuzzyTrafficController()
        self.last_update = time.time()
        self.last_tick_time = time.time()
        self.vehicle_count = 0
        self.auto_tick_enabled = True
    
    def update_timing(self, vehicle_count: int):
        """Update signal timing based on vehicle count."""
        self.vehicle_count = vehicle_count
        recommendation = self.controller.get_signal_recommendation(vehicle_count)
        
        self.green_duration = recommendation['green_duration_sec']
        self.red_duration = recommendation['red_duration_sec']
        
        return recommendation
    
    def set_state(self, state: str, duration: int = None):
        """Set signal state with optional duration override."""
        if state not in self.STATES:
            raise ValueError(f"Invalid state: {state}. Must be one of {self.STATES}")
        
        self.state = state
        
        if duration is not None:
            self.remaining_time = duration
        else:
            if state == 'green':
                self.remaining_time = self.green_duration
            elif state == 'yellow':
                self.remaining_time = self.yellow_duration
            else:
                self.remaining_time = self.red_duration
        
        import time
        self.last_update = time.time()
    
    def auto_tick(self) -> bool:
        """
        Automatically advance signal based on actual elapsed time.
        Call this periodically to keep signal synchronized with real time.
        
        Returns:
            True if state changed, False otherwise
        """
        if not self.auto_tick_enabled:
            return False
        
        current_time = time.time()
        elapsed = int(current_time - self.last_tick_time)
        
        if elapsed >= 1:
            self.last_tick_time = current_time
            return self.tick(elapsed)
        
        return False
    
    def tick(self, elapsed_seconds: int = 1) -> bool:
        """
        Advance the signal timer.
        
        Args:
            elapsed_seconds: Time elapsed since last tick
            
        Returns:
            True if state changed, False otherwise
        """
        self.remaining_time -= elapsed_seconds
        
        if self.remaining_time <= 0:
            # State transition
            if self.state == 'green':
                self.set_state('yellow')
            elif self.state == 'yellow':
                self.set_state('red')
            else:  # red
                self.set_state('green')
            return True
        
        return False
    
    def get_status(self) -> dict:
        """Get current signal status with auto-tick update."""
        # Auto-advance based on elapsed time
        state_changed = self.auto_tick()
        
        # Log status for debugging (only when state changes or every 5 polls)
        if state_changed:
            print(f"[SIGNAL] State changed to {self.state.upper()} | Remaining: {self.remaining_time}s | Vehicles: {self.vehicle_count}")
        
        return {
            "signal_id": self.signal_id,
            "state": self.state,
            "remaining_time": max(0, self.remaining_time),  # Never show negative
            "green_duration": self.green_duration,
            "yellow_duration": self.yellow_duration,
            "red_duration": self.red_duration,
            "vehicle_count": self.vehicle_count,
            "traffic_level": self.controller.get_traffic_level(self.vehicle_count),
        }


# Global signal instance
_signal: TrafficSignal = None


def get_signal() -> TrafficSignal:
    """Get or create the global traffic signal instance."""
    global _signal
    if _signal is None:
        _signal = TrafficSignal()
    return _signal


# =============================================================================
# 4-WAY HYBRID JUNCTION CONTROLLER
# =============================================================================

class FourWayTrafficController:
    """
    4-Way Junction Controller with Hybrid Data Sources.
    
    Architecture:
    - North Lane: REAL vehicle count from YOLO video detection
    - South/East/West Lanes: SIMULATED traffic density (random, updates every 10s)
    
    Cycle: Round-robin (N -> E -> S -> W) with fuzzy-computed green durations.
    Emergency: Ambulance detection forces one lane GREEN, others RED.
    """
    
    LANES = ['north', 'south', 'east', 'west']
    CYCLE_ORDER = ['north', 'east', 'south', 'west']  # Round-robin order
    COLORS = ['red', 'yellow', 'green']
    
    def __init__(self):
        """Initialize the 4-way controller."""
        # Vehicle counts per lane
        self.lane_counts: Dict[str, int] = {
            'north': 0, 'south': 0, 'east': 0, 'west': 0
        }
        
        # Light states per lane
        self.lane_states: Dict[str, str] = {
            'north': 'red', 'south': 'red', 'east': 'red', 'west': 'red'
        }
        
        # Current green lane and timing
        self.current_green_lane: str = 'north'
        self.green_remaining: int = 30
        self.yellow_remaining: int = 0
        self.is_yellow_phase: bool = False
        
        # Simulation timing
        self.last_sim_update: float = time.time()
        self.sim_update_interval: int = 10  # seconds between simulated data updates
        
        # Emergency mode
        self.emergency_mode: bool = False
        self.emergency_lane: Optional[str] = None
        self.emergency_start_time: Optional[float] = None
        self.emergency_duration: int = 30  # seconds
        
        # Fuzzy controller for computing green durations
        self.fuzzy_controller = FuzzyTrafficController()
        
        # Auto-tick timing
        self.last_tick_time: float = time.time()
        self.auto_tick_enabled: bool = True
        
        # Initialize with north green
        self.lane_states['north'] = 'green'
        self._update_simulated_lanes()
        
        print("[OK] 4-Way Hybrid Traffic Controller initialized")
    
    def _update_simulated_lanes(self):
        """Generate random traffic density for simulated lanes (S, E, W)."""
        current_time = time.time()
        
        if current_time - self.last_sim_update >= self.sim_update_interval:
            self.lane_counts['south'] = random.randint(0, 20)
            self.lane_counts['east'] = random.randint(0, 20)
            self.lane_counts['west'] = random.randint(0, 20)
            self.last_sim_update = current_time
    
    def get_simulated_density(self) -> Dict[str, int]:
        """
        Get current simulated traffic density for virtual lanes.
        
        Returns:
            Dict with vehicle counts for south, east, west lanes.
