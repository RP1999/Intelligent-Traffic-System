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
