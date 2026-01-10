"""
Intelligent Traffic Management System - OCR Service
Sprint H: License Plate Text Recognition

Uses EasyOCR with preprocessing optimized for Sri Lankan license plates.
Includes regex validation and filtering for realistic plate text.
"""

import re
from typing import Optional, Tuple, List
import cv2
import numpy as np

# Lazy load EasyOCR to avoid slow startup
_ocr_reader = None
