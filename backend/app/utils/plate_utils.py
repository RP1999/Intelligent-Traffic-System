"""
Plate Number Normalization Utility

Provides canonical plate normalization so that "WP ABC-1234", "WP ABC 1234",
and "WPABC1234" all resolve to the same string: "WPABC1234".

Used at:
- Driver registration (store normalized version alongside original)
- OCR recognition (normalize before matching)
- All Firestore queries that compare plate numbers
"""

import re


def normalize_plate(plate: str) -> str:
    """
    Normalize a license plate string to a canonical form.
    
    Strips all spaces, hyphens, and special characters, then uppercases.
    Examples:
        "WP ABC-1234"  -> "WPABC1234"
        "wp abc 1234"  -> "WPABC1234"
        "WP-CAB-1234"  -> "WPCAB1234"
        "123-4567"     -> "1234567"
    
    Args:
        plate: Raw plate number string
    
    Returns:
        Normalized uppercase plate string with no spaces/hyphens
    """
    if not plate:
        return ""
    # Remove spaces, hyphens, and any non-alphanumeric characters
    normalized = re.sub(r'[^A-Za-z0-9]', '', plate)
    return normalized.upper()
