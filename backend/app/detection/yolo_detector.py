"""
Intelligent Traffic Management System - YOLOv8 Advanced Detection Module
FINAL VERSION: Full Integration with TTS, Scoring, Traffic Control

Features:
=========
1. Two-Stage Detection: Vehicle Tracking → Plate Detection (Zoom)
2. OCR Caching: Only run OCR every 2+ seconds per vehicle
3. Frame Skipping: Run YOLO every 2nd frame, reuse boxes on skipped frames
4. Speed Estimation: Calculate vehicle speed from centroid movement
5. Parking Zones: Configurable red zones with warning/violation phases
6. TTS Warnings: Voice alerts for parking violations
7. Database Integration: Save violations to SQLite via ScoringEngine
8. Signal Automation: Fuzzy logic traffic light control
9. Visual Effects: Flashing purple boxes for penalized vehicles
"""

import sys
import time
from pathlib import Path
from typing import Generator, Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime

import cv2
import numpy as np

# Add parent to path for imports when running as script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.config import get_settings

settings = get_settings()


# ============================================================================
# CONFIGURATION CONSTANTS
# ============================================================================

