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
    
    Returns:
        Preprocessed binary image ready for OCR
    """
    # Convert to grayscale
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    # Apply Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Apply Otsu's thresholding for automatic binary conversion
    _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Optional: Invert if background is dark (white text on dark plate)
    # Check if the image is mostly dark
    mean_val = np.mean(binary)
    if mean_val < 127:
        binary = cv2.bitwise_not(binary)
    
    return binary


def clean_plate_text(text: str) -> str:
    """
    Clean and normalize recognized plate text.
    
    - Remove special characters except hyphen and space
    - Convert to uppercase
    - Normalize spacing
    
    Args:
        text: Raw OCR output
    
    Returns:
        Cleaned plate text
    """
    if not text:
        return ""
    
    # Convert to uppercase
    text = text.upper()
    
    # Keep only alphanumeric, hyphen, and space
    text = re.sub(r'[^A-Z0-9\-\s]', '', text)
    
    # Normalize multiple spaces to single space
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Common OCR corrections for Sri Lankan plates
    replacements = {
        'O': '0',  # Sometimes O is read as 0 (context-dependent)

        'I': '1',  # I can be 1
        'S': '5',  # S can be 5
        'B': '8',  # B can be 8
    }
    # Only apply these in the numeric portion (after letters)
    # This is a simplified approach
    
    return text


def validate_plate_text(text: str) -> bool:
    """
    Validate if text looks like a Sri Lankan license plate.
    
    Common Sri Lankan plate formats:
    - Province code + letters + numbers: WP ABC-1234, CP XY-5678
    - Old format: 123-4567
    - Bike format: WP AB-1234
    
    Args:
        text: Cleaned plate text
    
    Returns:
        True if text matches expected plate patterns
    """
    if not text:
        return False
    
    # Too short - probably noise
    if len(text) < 4:
        return False
    
    # Too long - probably multiple lines or garbage
    if len(text) > 15:
        return False
    
    # Must contain at least one letter and one digit
    has_letter = bool(re.search(r'[A-Z]', text))
    has_digit = bool(re.search(r'[0-9]', text))
    
    if not (has_letter or has_digit):
        return False
    
    # Sri Lankan plate patterns (flexible matching)
    patterns = [
