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
        
