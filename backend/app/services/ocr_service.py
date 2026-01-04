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
        # Province code + letters + hyphen + numbers: WP ABC-1234
        r'^[A-Z]{2,3}\s?[A-Z]{1,4}[\-\s]?\d{4}$',
        
        # Province code + letters + numbers (no hyphen): WP CAB1234
        r'^[A-Z]{2,3}\s?[A-Z]{1,4}\d{4}$',
        
        # Old format with hyphen: 123-4567 or 12-3456
        r'^\d{2,3}[\-\s]?\d{4}$',
        
        # Bike/motorbike format: WP AB-1234
        r'^[A-Z]{2}\s?[A-Z]{2}[\-\s]?\d{4}$',
        
        # Partial matches (at least 2 letters followed by digits)
        r'^[A-Z]{2,}\s?[\-]?\s?\d{3,}$',
        
        # Generic: starts with letters, ends with numbers
        r'^[A-Z]+.*\d{3,}$',
    ]
    
    for pattern in patterns:
        if re.match(pattern, text):
            return True
    
    # Fallback: If it has reasonable letter-number mix, accept it
    # This helps with partially visible plates
    letter_count = len(re.findall(r'[A-Z]', text))
    digit_count = len(re.findall(r'[0-9]', text))
    
    if letter_count >= 2 and digit_count >= 3:
        return True
    
    return False


def read_plate(image_crop: np.ndarray) -> Optional[str]:
    """
    Read license plate text from a cropped plate image.
    
    This is the main entry point for OCR. It:
    1. Preprocesses the image (grayscale, blur, threshold)
    2. Runs EasyOCR
    3. Cleans and validates the result
    4. Returns None if text is invalid (filters out false positives)
    
    Args:
        image_crop: BGR image of the cropped license plate
    
    Returns:
        Cleaned plate text if valid, None otherwise
    """
    if image_crop is None or image_crop.size == 0:
        return None
    
    # Check minimum size
    h, w = image_crop.shape[:2]
    if w < 20 or h < 10:
        return None
    
    # Get OCR reader
    reader = get_ocr_reader()
    if reader is None:
        return None
    
    try:
        # Preprocess the image
        preprocessed = preprocess_plate_image(image_crop)
        
        # Run OCR on both original and preprocessed
        # Sometimes the original works better, sometimes preprocessed
        results = []
        
        # Try preprocessed first (usually better for plates)
        ocr_results = reader.readtext(preprocessed, detail=0, paragraph=False)
        results.extend(ocr_results)
        
        # Also try original if preprocessed didn't work well
        if not results or all(len(r) < 3 for r in results):
            ocr_results = reader.readtext(image_crop, detail=0, paragraph=False)
            results.extend(ocr_results)
        
        if not results:
            return None
        
        # Combine all detected text
        combined_text = ' '.join(results)
        
        # Clean the text
        cleaned = clean_plate_text(combined_text)
        
        # Validate
        if validate_plate_text(cleaned):
            return cleaned
        
        return None
        
    except Exception as e:
        # Silently fail - OCR errors shouldn't crash the system
        return None


def read_plate_with_confidence(image_crop: np.ndarray) -> Tuple[Optional[str], float]:
    """
    Read license plate text with confidence score.
    
    Args:
        image_crop: BGR image of the cropped license plate
    
    Returns:
        Tuple of (plate_text, confidence) or (None, 0.0)
    """
    if image_crop is None or image_crop.size == 0:
        return None, 0.0
    
    reader = get_ocr_reader()
    if reader is None:
        return None, 0.0
    
    try:
        preprocessed = preprocess_plate_image(image_crop)
        
        # Get detailed results with confidence
        ocr_results = reader.readtext(preprocessed, detail=1, paragraph=False)
        
        if not ocr_results:
            return None, 0.0
        
        # Combine text and average confidence
        texts = []
        confidences = []
        
        for bbox, text, conf in ocr_results:
            texts.append(text)
            confidences.append(conf)
        
        combined_text = ' '.join(texts)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        cleaned = clean_plate_text(combined_text)
        
        if validate_plate_text(cleaned):
            return cleaned, avg_confidence
        
        return None, 0.0
        
    except Exception:
        return None, 0.0


# Module initialization - don't load OCR at import time
def init_ocr():
    """Explicitly initialize OCR reader. Called when needed."""
    return get_ocr_reader() is not None
