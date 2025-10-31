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
