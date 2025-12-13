"""
Intelligent Traffic Management System - Fuzzy Logic Traffic Controller
4-WAY HYBRID JUNCTION: 1 Real Lane (YOLO) + 3 Simulated Lanes

Research Component for University Grading
==========================================
This module demonstrates fuzzy inference systems for traffic signal optimization.
Uses scikit-fuzzy for fuzzy set operations and rule-based inference.

Architecture:
- Lane North: REAL data from YOLO video detection
- Lane South/East/West: SIMULATED (random density, updates every 10 seconds)
- Round-robin cycle: N -> E -> S -> W with fuzzy-computed green durations
- Emergency mode: Triggered by ambulance detection (YOLO class_id=8)
"""

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
