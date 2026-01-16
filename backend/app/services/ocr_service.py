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


def get_ocr_reader():
    """Get or initialize the EasyOCR reader (lazy loading)."""
    global _ocr_reader
    if _ocr_reader is None:
        try:
            import easyocr
            print("🔤 Initializing EasyOCR reader (English)...")
            _ocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
            print("✅ EasyOCR initialized successfully")
        except ImportError:
            print("⚠️ EasyOCR not installed. Run: pip install easyocr")
            return None
        except Exception as e:
            print(f"⚠️ EasyOCR initialization failed: {e}")
            return None
    return _ocr_reader


def preprocess_plate_image(image: np.ndarray) -> np.ndarray:
    """
    Preprocess license plate image for better OCR accuracy.
    
    Pipeline:
    1. Convert to grayscale
    2. Apply Gaussian blur to reduce noise
    3. Apply Otsu's thresholding to make text pop
    
    Args:
        image: BGR image of the license plate crop
    
