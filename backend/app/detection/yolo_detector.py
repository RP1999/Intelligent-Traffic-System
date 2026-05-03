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

# Frame skipping - only run YOLO every N frames
YOLO_DETECTION_INTERVAL: int = 1  # Run every analysis frame (analysis already throttled to 1 FPS)

# Plate detection interval
PLATE_DETECTION_INTERVAL: int = 1  # Detect plates every analysis frame (already at 1 FPS)

# OCR cooldown per vehicle (seconds)
OCR_COOLDOWN_SECONDS: float = 2.0

# Speed estimation (pixels/sec to km/h)
# This factor depends on camera geometry (distance, angle, FOV).
# Tuned for SriLankan_Traffic_Video.mp4 (1920x1080, overhead-angle).
SPEED_SCALE_FACTOR: float = 1.5

# Speed display cap — prevents unrealistic values from tracker jitter
SPEED_MAX_KMH: float = 200.0

# Speeding threshold (in km/h after scale conversion)
SPEEDING_THRESHOLD_KMH: float = 60.0  # vehicles above this are flagged (matches admin default)

# Consecutive-frame speeding check: vehicle must exceed threshold for
# this many consecutive analysis frames before being flagged as speeding.
# At ANALYSIS_FPS=3, 2 consecutive frames = ~0.67s of sustained speeding.
# This eliminates false positives from tracking jitter / ID swaps.
SPEEDING_CONSECUTIVE_FRAMES: int = 2

# Parking violation timing (shorter for demo sensitivity)
PARKING_WARNING_SECONDS: float = 3.0  # seconds before a warning
PARKING_VIOLATION_SECONDS: float = 8.0  # seconds before a violation

# Signal automation interval
SIGNAL_UPDATE_INTERVAL: int = 30  # frames (~1 second at 30fps)

# History cleanup
PLATE_HISTORY_MAX_AGE: int = 30
TRACKING_HISTORY_MAX_AGE: int = 60

# TTS cooldown (don't spam warnings)
TTS_COOLDOWN_SECONDS: float = 10.0


# ============================================================================
# SETTINGS INTEGRATION
# ============================================================================

# Yellow light duration (seconds) — used for red light violation grace period
YELLOW_LIGHT_DURATION: float = 3.0  # matches admin default


def update_detection_settings(settings: dict) -> None:
    """
    Update detection thresholds from admin settings.
    Called when settings are saved via the Settings page.
    """
    global SPEEDING_THRESHOLD_KMH, SPEED_SCALE_FACTOR, YELLOW_LIGHT_DURATION
    global _stop_line_config, STOP_LINE_RATIO
    
    detection = settings.get('detection', {})
    if detection:
        speed_limit = detection.get('speed_limit', 60.0)
        # Update speeding threshold to match the configured speed limit
        SPEEDING_THRESHOLD_KMH = speed_limit
        
        # Update stop line Y position from admin settings
        stop_line_y = detection.get('stop_line_y_position', 400)
        # Convert pixel position to ratio (assuming 1080p frame height)
        # This serves as a default; Firestore config document overrides if present
        _stop_line_config['y_position'] = stop_line_y / 1080.0
        STOP_LINE_RATIO = _stop_line_config['y_position']
        
        # Update yellow light duration
        YELLOW_LIGHT_DURATION = detection.get('yellow_light_duration', 3.0)
        
        # Propagate yellow light duration to traffic signal controller
        try:
            from app.fuzzy.traffic_controller import get_signal
            signal = get_signal()
            signal.yellow_duration = int(YELLOW_LIGHT_DURATION)
            print(f"[DETECTION] Traffic signal yellow duration updated to {signal.yellow_duration}s")
        except Exception as e:
            print(f"[DETECTION] Could not update traffic signal yellow duration: {e}")
        
        print(f"[DETECTION] Updated: speed_limit={SPEEDING_THRESHOLD_KMH} km/h, "
              f"stop_line_ratio={STOP_LINE_RATIO:.3f}, yellow_light={YELLOW_LIGHT_DURATION}s")
    
    parking = settings.get('parking', {})
    if parking:
        global PARKING_WARNING_SECONDS, PARKING_VIOLATION_SECONDS
        grace = parking.get('grace_period_seconds', 30)
        # Warning fires at 50 % of the grace period; violation fires once the
        # full grace period has elapsed.
        PARKING_WARNING_SECONDS = max(3.0, grace * 0.5)
        PARKING_VIOLATION_SECONDS = max(PARKING_WARNING_SECONDS + 2, float(grace))
        print(f"[DETECTION] Updated parking: warning={PARKING_WARNING_SECONDS}s, violation={PARKING_VIOLATION_SECONDS}s")


# ============================================================================
# PARKING ZONES CONFIGURATION
# ============================================================================

# Define parking zones as polygons (x, y) in frame coordinates
# These are "no parking" zones - red boxes will be drawn
# Adjust these coordinates based on your video feed
DEFAULT_PARKING_ZONES = [
    {
        "id": "zone_1",
        "name": "No Parking Zone 1",
        "polygon": [(50, 400), (300, 400), (300, 550), (50, 550)],
        "color": (0, 0, 255),  # Red
    },
    {
        "id": "zone_2", 
        "name": "No Parking Zone 2",
        "polygon": [(500, 400), (750, 400), (750, 550), (500, 550)],
        "color": (0, 0, 255),  # Red
    },
]


# ============================================================================
# GLOBAL STATE & CACHING
# ============================================================================

# Model cache
_model_cache: Dict[str, Any] = {}

# Plate history: track_id -> {"bbox", "text", "timestamp", "frame_count"}
plate_history: Dict[int, Dict[str, Any]] = {}

# OCR cooldown: track_id -> last_ocr_time
ocr_cooldown: Dict[int, float] = {}

# Speed tracking: track_id -> {"prev_centroid", "prev_time", "speed", "is_speeding", "speed_pixels"}
speed_history: Dict[int, Dict[str, Any]] = {}

# Parking tracking: track_id -> {"entry_time", "zone_id", "warned", "penalized", "plate", "tts_time"}
parking_tracker: Dict[int, Dict[str, Any]] = {}

# Penalized vehicles (for flashing effect)
penalized_vehicles: Dict[int, float] = {}  # track_id -> penalize_time

# Current analysis frame for evidence snapshot capture
_current_analysis_frame: Optional[np.ndarray] = None

# Previous frame detections (for frame skipping)
_prev_detections: List[Any] = []
_prev_plate_boxes: List[Tuple[int, int, int, int]] = []

# Frame counter
_frame_counter: int = 0

# Parking zones (can be updated at runtime)
parking_zones: List[Dict] = DEFAULT_PARKING_ZONES.copy()


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class Detection:
    """Container for a single detection result."""
    track_id: int
    class_id: int
    class_name: str
    confidence: float
    bbox: Tuple[int, int, int, int]
    centroid: Tuple[int, int]
    area: int
    timestamp: float = field(default_factory=time.time)
    has_plate: bool = False
    plate_bbox: Optional[Tuple[int, int, int, int]] = None
    plate_text: Optional[str] = None
    speed_kmh: float = 0.0
    speed_pixels: float = 0.0
    is_speeding: bool = False
    parking_time: float = 0.0
    parking_status: str = ""  # "", "warning", "violation"
    parking_zone: Optional[str] = None
    is_penalized: bool = False
    
    def to_dict(self) -> dict:
        return {
            "track_id": self.track_id,
            "class_id": self.class_id,
            "class_name": self.class_name,
            "confidence": round(self.confidence, 3),
            "bbox": self.bbox,
            "centroid": self.centroid,
            "area": self.area,
            "timestamp": self.timestamp,
            "has_plate": self.has_plate,
            "plate_bbox": self.plate_bbox,
            "plate_text": self.plate_text,
            "speed_kmh": round(self.speed_kmh, 1),
            "speed_pixels": round(self.speed_pixels, 1),
            "is_speeding": self.is_speeding,
            "parking_time": round(self.parking_time, 1),
            "parking_status": self.parking_status,
            "parking_zone": self.parking_zone,
            "is_penalized": self.is_penalized,
        }


@dataclass 
class FrameResult:
    """Container for detection results from a single frame."""
    frame_id: int
    timestamp: float
    detections: List[Detection]
    inference_time_ms: float
    plate_boxes: List[Tuple[int, int, int, int]] = field(default_factory=list)
    image: Optional[np.ndarray] = None
    vehicle_count: int = 0
    speeding_count: int = 0
    parking_warnings: int = 0
    parking_violations: int = 0
    signal_state: Optional[str] = None
    signal_duration: Optional[int] = None
    
    def to_dict(self) -> dict:
        return {
            "frame_id": self.frame_id,
            "timestamp": self.timestamp,
            "detection_count": len(self.detections),
            "plate_count": len(self.plate_boxes),
            "inference_time_ms": round(self.inference_time_ms, 2),
            "vehicle_count": self.vehicle_count,
            "speeding_count": self.speeding_count,
            "parking_warnings": self.parking_warnings,
            "parking_violations": self.parking_violations,
            "signal_state": self.signal_state,
            "signal_duration": self.signal_duration,
            "detections": [d.to_dict() for d in self.detections],
        }


# ============================================================================
# CLASS DEFINITIONS
# ============================================================================

VEHICLE_CLASSES = {
    2: "car",
    3: "motorcycle", 
    5: "bus",
    7: "truck",
}

# Emergency vehicle classes (for YOLO retraining)
EMERGENCY_CLASSES = {
    8: "ambulance",
    # Future additions:
    # 9: "fire_truck",
    # 10: "police_car",
}

TRAFFIC_CLASSES = {
    **VEHICLE_CLASSES,
    **EMERGENCY_CLASSES,
    0: "person",
    1: "bicycle",
}

VEHICLE_CLASS_IDS = [2, 3, 5, 7]
EMERGENCY_CLASS_IDS = [8]  # Ambulance - triggers emergency mode
ALL_VEHICLE_CLASS_IDS = VEHICLE_CLASS_IDS + EMERGENCY_CLASS_IDS


# ============================================================================
# LAZY SERVICE IMPORTS
# ============================================================================

_ocr_service = None
_scoring_engine = None
_traffic_controller = None
_tts_service = None
_lane_weaving_service = None
_behavior_service = None


def get_ocr_service():
    """Lazy load OCR service."""
    global _ocr_service
    if _ocr_service is None:
        try:
            from app.services.ocr_service import read_plate
            _ocr_service = read_plate
            print("✅ OCR service loaded")
        except ImportError as e:
            print(f"⚠️ OCR service not available: {e}")
            _ocr_service = lambda x: None
    return _ocr_service


def get_lane_weaving_service():
    """Lazy load lane weaving detection service (Member 2)."""
    global _lane_weaving_service
    if _lane_weaving_service is None:
        try:
            from app.services import lane_weaving_service
            _lane_weaving_service = lane_weaving_service
            print("✅ Lane weaving service loaded (Member 2)")
        except ImportError as e:
            print(f"⚠️ Lane weaving service not available: {e}")
            _lane_weaving_service = None
    return _lane_weaving_service


def get_behavior_service():
    """Lazy load abnormal behavior detection service (Member 4)."""
    global _behavior_service
    if _behavior_service is None:
        try:
            from app.services import behavior_service
            _behavior_service = behavior_service
            print("✅ Behavior detection service loaded (Member 4)")
        except ImportError as e:
            print(f"⚠️ Behavior service not available: {e}")
            _behavior_service = None
    return _behavior_service


def get_scoring_engine():
    """Lazy load scoring engine for database violations."""
    global _scoring_engine
    if _scoring_engine is None:
        try:
            from app.scoring import get_scoring_engine as _get_engine, ViolationType
            _scoring_engine = {"engine": _get_engine(), "ViolationType": ViolationType}
            print("✅ Scoring engine loaded")
        except ImportError as e:
            print(f"⚠️ Scoring engine not available: {e}")
            _scoring_engine = {"engine": None, "ViolationType": None}
    return _scoring_engine


def get_traffic_controller():
    """Lazy load 4-way traffic signal controller."""
    global _traffic_controller
    if _traffic_controller is None:
        try:
            from app.fuzzy.traffic_controller import get_four_way_controller
            _traffic_controller = get_four_way_controller()
            print("[OK] 4-Way Traffic controller loaded")
        except ImportError as e:
            print(f"[WARNING] Traffic controller not available: {e}")
            _traffic_controller = None
    return _traffic_controller


# Emergency detection state
_last_emergency_detection_time: float = 0
EMERGENCY_COOLDOWN_SECONDS: float = 30.0  # Don't re-trigger for 30 seconds


def check_for_emergency_vehicle(detections: list) -> tuple:
    """
    Check if any detection is an emergency vehicle (ambulance).
    
    Args:
        detections: List of Detection objects from current frame.
        
    Returns:
        Tuple of (is_emergency, vehicle_type, track_id)
    """
    for det in detections:
        if det.class_id in EMERGENCY_CLASS_IDS:
            vehicle_type = EMERGENCY_CLASSES.get(det.class_id, 'emergency')
            return (True, vehicle_type, det.track_id)
    return (False, None, None)


def trigger_emergency_if_detected(detections: list) -> dict:
    """
    If an ambulance is detected, trigger emergency mode on the 4-way controller.
    Includes cooldown to prevent spam.
    
    Args:
        detections: List of Detection objects from current frame.
        
    Returns:
        Dict with emergency status or None if no emergency.
    """
    global _last_emergency_detection_time
    
    is_emergency, vehicle_type, track_id = check_for_emergency_vehicle(detections)
    
    if not is_emergency:
        return None
    
    current_time = time.time()
    
    # Check cooldown
    if (current_time - _last_emergency_detection_time) < EMERGENCY_COOLDOWN_SECONDS:
        return {'status': 'cooldown', 'message': 'Emergency mode already active'}
    
    _last_emergency_detection_time = current_time
    
    # Trigger emergency on traffic controller
    controller = get_traffic_controller()
    if controller:
        result = controller.activate_emergency_mode('north')  # Video = North lane
        
        # Play TTS alert
        speak_warning(
            f"Emergency! {vehicle_type.title()} detected. Clearing North lane.",
            track_id=track_id,
            warning_type="emergency"
        )
        
        print(f"[EMERGENCY] {vehicle_type.upper()} detected (Track ID: {track_id}) - North lane forced GREEN!")
        return result
    
    return {'status': 'error', 'message': 'Traffic controller not available'}


def get_tts_service():
    """Lazy load TTS service for voice warnings."""
    global _tts_service
    if _tts_service is None:
        try:
            from app.tts import get_tts_service as _get_tts
            _tts_service = _get_tts()
            print("✅ TTS service loaded")
        except ImportError as e:
            print(f"⚠️ TTS service not available: {e}")
            _tts_service = None
    return _tts_service


# ============================================================================
# TTS WARNING FUNCTION
# ============================================================================

def speak_warning(message: str, track_id: int = None, warning_type: str = None):
    """
    Generate and play a voice warning dynamically.
    
    Args:
        message: The actual warning message to speak
        track_id: Vehicle track ID (for cooldown tracking)
        warning_type: Type of warning (for logging only)
    
    Includes cooldown to prevent spam.
    """
    global parking_tracker
    
    current_time = time.time()
    
    # Check TTS cooldown for this vehicle
    if track_id is not None and track_id in parking_tracker:
        last_tts = parking_tracker[track_id].get("tts_time", 0)
        if (current_time - last_tts) < TTS_COOLDOWN_SECONDS:
            return  # Skip, too soon
        parking_tracker[track_id]["tts_time"] = current_time
    
    # Log to console
    print(f"[AUDIO] 🔊 {message}")
    
    # Try to use TTS service - ALWAYS generate dynamic messages
    tts = get_tts_service()
    if tts:
        try:
            # Generate and play the ACTUAL message (not cached files)
            tts.generate_warning(message, play_immediately=True)
        except Exception as e:
            print(f"[TTS] Error: {e}")


# ============================================================================
# MODEL LOADING
# ============================================================================

def load_model(model_path: str, device: str = "cpu") -> Any:
    """Load a YOLOv8 model with caching."""
    global _model_cache
    
    cache_key = f"{model_path}_{device}"
    
    if cache_key not in _model_cache:
        from ultralytics import YOLO
        
        print(f"🔄 Loading model: {model_path} on {device}...")
        start = time.time()
        
        model = YOLO(model_path)
        model.to(device)
        
        print(f"✅ Model loaded in {time.time() - start:.2f}s")
        _model_cache[cache_key] = model
    
    return _model_cache[cache_key]


def load_vehicle_model(device: str = "cpu") -> Any:
    """Load the YOLOv8 vehicle detection model."""
    return load_model("yolov8n.pt", device)


def load_plate_model(device: str = "cpu") -> Any:
    """Load the custom license plate detection model."""
    possible_paths = [
        Path("models") / "best_plate.pt",
        Path(__file__).parent.parent.parent.parent / "models" / "best_plate.pt",
        Path(settings.plate_model) if settings.plate_model else None,
    ]
    
    for path in possible_paths:
        if path and path.exists():
            print(f"📋 Found plate model at: {path}")
            return load_model(str(path), device)
    
    print(f"⚠️ Plate model not found")
    return None


def get_models(device: str = "cpu") -> Tuple[Any, Any]:
    """Initialize and return both models."""
    return load_vehicle_model(device), load_plate_model(device)


# ============================================================================
# ZONE HELPER FUNCTIONS
# ============================================================================

def point_in_polygon(point: Tuple[int, int], polygon: List[Tuple[int, int]]) -> bool:
    """Check if a point is inside a polygon using cv2.pointPolygonTest."""
    polygon_np = np.array(polygon, dtype=np.int32)
    result = cv2.pointPolygonTest(polygon_np, point, False)
    return result >= 0


def get_zone_for_point(point: Tuple[int, int]) -> Optional[Dict]:
    """Find which parking zone contains a point, if any."""
    for zone in parking_zones:
        if point_in_polygon(point, zone["polygon"]):
            return zone
    return None


# ============================================================================
# SPEED ESTIMATION
# ============================================================================

def calculate_speed(track_id: int, centroid: Tuple[int, int], current_time: float) -> Tuple[float, float, bool]:
    """
    Calculate vehicle speed from centroid movement with consecutive-frame validation.
    
    Speed must exceed threshold for SPEEDING_CONSECUTIVE_FRAMES in a row
    to be flagged — this eliminates false positives from tracker jitter.
    
    Improvements:
    - First real measurement uses raw speed (no EMA ramp-up from 0)
    - Higher EMA alpha (0.5) for faster convergence
    - Uses km/h threshold directly (not pixel threshold)
    - Speed capped at SPEED_MAX_KMH
    
    Returns:
        Tuple of (speed_kmh, speed_pixels_per_sec, is_speeding)
    """
    global speed_history
    
    if track_id not in speed_history:
        speed_history[track_id] = {
            "prev_centroid": centroid,
            "prev_time": current_time,
            "speed": 0.0,
            "speed_pixels": 0.0,
            "is_speeding": False,
            "frame_count": 0,
            "consecutive_speeding": 0,
        }
        return 0.0, 0.0, False
    
    history = speed_history[track_id]
    history["frame_count"] += 1
    
    time_delta = current_time - history["prev_time"]
    
    if time_delta < 0.01:
        return history["speed"], history["speed_pixels"], history["is_speeding"]
    
    prev_x, prev_y = history["prev_centroid"]
    curr_x, curr_y = centroid
    
    distance_pixels = np.sqrt((curr_x - prev_x) ** 2 + (curr_y - prev_y) ** 2)
    speed_pixels_per_sec = distance_pixels / time_delta
    speed_kmh = speed_pixels_per_sec * SPEED_SCALE_FACTOR
    
    # Cap unrealistic speeds (tracker jitter can cause huge jumps)
    speed_kmh = min(speed_kmh, SPEED_MAX_KMH)
    
    # First real measurement: use raw speed directly (don't EMA from 0)
    if history["frame_count"] == 1:
        smoothed_speed = speed_kmh
        smoothed_pixels = speed_pixels_per_sec
    else:
        # EMA smoothing (alpha=0.5 for responsive convergence)
        alpha = 0.5
        smoothed_speed = alpha * speed_kmh + (1 - alpha) * history["speed"]
        smoothed_pixels = alpha * speed_pixels_per_sec + (1 - alpha) * history["speed_pixels"]
    
    # Consecutive-frame speeding check using km/h threshold
    raw_over_threshold = smoothed_speed > SPEEDING_THRESHOLD_KMH
    if raw_over_threshold:
        history["consecutive_speeding"] = history.get("consecutive_speeding", 0) + 1
    else:
        history["consecutive_speeding"] = 0
    
    is_speeding = history["consecutive_speeding"] >= SPEEDING_CONSECUTIVE_FRAMES
    
    history["prev_centroid"] = centroid
    history["prev_time"] = current_time
    history["speed"] = smoothed_speed
    history["speed_pixels"] = smoothed_pixels
    history["is_speeding"] = is_speeding
    
    return smoothed_speed, smoothed_pixels, is_speeding


def cleanup_speed_history(active_track_ids: set):
    """Remove speed history for vehicles no longer tracked."""
    global speed_history
    to_remove = [tid for tid in speed_history if tid not in active_track_ids]
    for tid in to_remove:
        if speed_history[tid]["frame_count"] > TRACKING_HISTORY_MAX_AGE:
            del speed_history[tid]


# ============================================================================
# EVIDENCE SNAPSHOT CAPTURE
# ============================================================================

def _capture_evidence_snapshot(
    track_id: int,
    violation_type: str,
    bbox: Tuple[int, int, int, int] = None,
    extra_text: str = "",
) -> Optional[str]:
    """
    Capture the current analysis frame as evidence for a violation.
    Draws a red box around the violating vehicle + violation text + timestamp.
    
    Returns:
        URL path to the evidence image (e.g., /evidence/evidence_parking_...) or None
    """
    global _current_analysis_frame
    if _current_analysis_frame is None:
        return None

    try:
        snapshots_dir = Path(settings.data_dir) / "snapshots"
        snapshots_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"evidence_{violation_type}_{ts}_{track_id}.jpg"
        filepath = snapshots_dir / filename

        evidence = _current_analysis_frame.copy()
        font = cv2.FONT_HERSHEY_SIMPLEX

        # Highlight the violating vehicle with a thick red box
        if bbox:
            x1, y1, x2, y2 = bbox
            cv2.rectangle(evidence, (x1, y1), (x2, y2), (0, 0, 255), 4)
            label = f"VIOLATION: {violation_type.upper().replace('_', ' ')}"
            # Background for text
            (tw, th), _ = cv2.getTextSize(label, font, 0.9, 2)
            cv2.rectangle(evidence, (x1, y1 - th - 10), (x1 + tw + 4, y1), (0, 0, 255), -1)
            cv2.putText(evidence, label, (x1 + 2, y1 - 6), font, 0.9, (255, 255, 255), 2)

        # Extra text (e.g., speed info)
        if extra_text:
            cv2.putText(evidence, extra_text, (10, 40), font, 0.9, (0, 0, 255), 2)

        # Timestamp overlay at bottom
        ts_display = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        h = evidence.shape[0]
        cv2.putText(evidence, f"Evidence: {ts_display}", (10, h - 20), font, 0.8, (0, 255, 255), 2)

        cv2.imwrite(str(filepath), evidence, [cv2.IMWRITE_JPEG_QUALITY, 85])
        print(f"[EVIDENCE] 📸 Captured: {filename}")
        # Return just the filename - the /evidence/ prefix is added by the frontend
        return filename

    except Exception as e:
        print(f"[EVIDENCE] ❌ Error capturing evidence: {e}")
        return None


# ============================================================================
# PARKING VIOLATION DETECTION
# ============================================================================

def check_parking_violation(
    det: Detection,
    current_time: float,
) -> Tuple[float, str, Optional[str], bool]:
    """
    Check if a vehicle is in a parking violation zone.
    
    Returns:
        Tuple of (time_in_zone, status, zone_id, is_penalized)
    """
    global parking_tracker, penalized_vehicles
    
    track_id = det.track_id
    
    # Check if vehicle centroid is in any parking zone
    zone = get_zone_for_point(det.centroid)
    
    if zone is None:
        # Vehicle is not in any zone
        if track_id in parking_tracker:
            del parking_tracker[track_id]
        return 0.0, "", None, track_id in penalized_vehicles
    
    zone_id = zone["id"]
    
    # Vehicle is stationary in a zone (speed < 5 km/h)
    is_stationary = det.speed_kmh < 5.0
    
    if track_id in parking_tracker:
        entry = parking_tracker[track_id]
        time_in_zone = current_time - entry["entry_time"]
        
        if time_in_zone >= PARKING_VIOLATION_SECONDS:
            status = "violation"
            
            if not entry.get("penalized", False):
                # Get plate display - use detection plate, or stored plate, or fallback to vehicle ID
                plate_display = det.plate_text or entry.get("plate") or f"Vehicle {track_id}"
                
                # APPLY PENALTY TO DATABASE
                _apply_parking_penalty(
                    track_id=track_id,
                    plate_text=det.plate_text or entry.get("plate"),
                    zone_id=zone_id,
                    bbox=det.bbox,
                )
                entry["penalized"] = True
                penalized_vehicles[track_id] = current_time
                
                # TTS Violation announcement
                speak_warning(
                    f"Violation recorded for {plate_display}. Fine has been issued.",
                    track_id
                )
                
        elif time_in_zone >= PARKING_WARNING_SECONDS:
            status = "warning"
            
            if not entry.get("warned", False):
                # TTS Warning - use plate text from detection or stored entry
                plate_display = det.plate_text or entry.get("plate") or f"Vehicle {track_id}"
                speak_warning(
                    f"{plate_display}, please move immediately. You are in a no parking zone.",
                    track_id
                )
                entry["warned"] = True

                # Save warning notification to DB + send FCM push
                raw_plate = det.plate_text or entry.get("plate")
                if raw_plate:
                    import threading
                    def _save_parking_warning(plate_raw=raw_plate, zone=zone_id):
                        try:
                            from app.services.push_notification_service import send_warning_notification
                            send_warning_notification(
                                plate_number=plate_raw,
                                behavior_type="parking_warning",
                                severity="medium",
                                details=f"You are parked in a no-parking zone ({zone}). Move immediately to avoid a fine.",
                            )
                        except Exception as e:
                            print(f"[PARKING] Warning notification error: {e}")
                    threading.Thread(target=_save_parking_warning, daemon=True).start()
        else:
            status = ""
        
        # Update plate if available
        if det.plate_text and not entry.get("plate"):
            entry["plate"] = det.plate_text
        
        is_penalized = entry.get("penalized", False) or track_id in penalized_vehicles
        return time_in_zone, status, zone_id, is_penalized
    
    else:
        # Start tracking if vehicle is stationary in zone
        if is_stationary:
            parking_tracker[track_id] = {
                "entry_time": current_time,
                "zone_id": zone_id,
                "warned": False,
                "penalized": False,
                "plate": det.plate_text,
                "tts_time": 0,
            }
        return 0.0, "", zone_id, track_id in penalized_vehicles


def _apply_parking_penalty(track_id: int, plate_text: str, zone_id: str, bbox: Tuple[int, int, int, int] = None):
    """Apply parking violation penalty to database with dynamic fine calculation."""
    scoring = get_scoring_engine()
    
    # Normalize plate for consistent DB matching
    from app.utils.plate_utils import normalize_plate
    normalized = normalize_plate(plate_text) if plate_text else None
    driver_id = normalized or f"UNKNOWN{track_id}"
    
    if scoring["engine"] is None:
        print(f"[PENALTY] ⚠️ Scoring engine not available. Would penalize: {driver_id}")
        return
    
    ViolationType = scoring["ViolationType"]
    
    # Determine violation type from zone type
    zone_type = _get_zone_type(zone_id)
    violation_type = _parking_zone_to_violation_type(zone_type, ViolationType)
    
    # Calculate dynamic fine using the DynamicFineCalculator
    dynamic_fine_amount = None
    dynamic_fine_breakdown = None
    try:
        from app.parking.dynamic_fine import get_fine_calculator
        fine_calc = get_fine_calculator()
        # Get parking duration from tracker
        entry = parking_tracker.get(track_id, {})
        duration = time.time() - entry.get('entry_time', time.time()) if entry else 0
        # Get current vehicle count for traffic impact
        vehicle_count = len(speed_history)
        fine_result = fine_calc.calculate(
            zone_type=zone_type,
            duration_seconds=duration,
            traffic_impact_count=vehicle_count
        )
        dynamic_fine_amount = fine_result.total_fine
        dynamic_fine_breakdown = fine_result.to_dict()
        dynamic_fine_breakdown["formula"] = "Base + (Duration × Rate) + (Traffic Impact × Cost)"
        print(f"[PARKING] Dynamic fine: LKR {dynamic_fine_amount:.0f} "
              f"(base={fine_result.base_penalty:.0f} + duration={fine_result.duration_penalty:.0f} "
              f"+ traffic={fine_result.traffic_impact_penalty:.0f})")
    except Exception as e:
        print(f"[PARKING] Dynamic fine calc failed, using default: {e}")
    
    # Capture evidence snapshot
    evidence_path = _capture_evidence_snapshot(
        track_id, "parking", bbox=bbox,
        extra_text=f"Illegal Parking - Zone: {zone_id}"
    )
    
    try:
        zone_display_name = _get_zone_name(zone_id)
        driver, violation = scoring["engine"].record_violation(
            driver_id=driver_id,
            violation_type=violation_type,
            location=zone_display_name,
            license_plate=plate_text,
            snapshot_path=evidence_path,
            notes=f"Automated detection - illegal parking in {zone_type} zone",
            fine_override=dynamic_fine_amount,
            fine_breakdown=dynamic_fine_breakdown,
        )
        
        print(f"[PENALTY] 🚨 DB SAVED: {driver_id} | Score: {driver.current_score} | Fine: LKR {violation.fine_amount:.0f}")
        
        # Update junction safety score for parking violations
        try:
            from app.services.lane_weaving_service import get_junction_safety
            junction = get_junction_safety()
            junction.apply_penalty('parking_violation')
        except Exception as je:
            print(f"[PENALTY] Junction safety update error: {je}")
        
    except Exception as e:
        print(f"[PENALTY] Error saving to DB: {e}")


def _get_zone_type(zone_id: str) -> str:
    """Get zone type from zone_id. Returns 'no_parking' as default."""
    for zone in parking_zones:
        if zone.get('id') == zone_id:
            return zone.get('zone_type', 'no_parking')
    return 'no_parking'


def _get_zone_name(zone_id: str) -> str:
    """Get the admin-configured display name for a parking zone."""
    for zone in parking_zones:
        if zone.get('id') == zone_id:
            return zone.get('name') or zone_id
    return zone_id


def _parking_zone_to_violation_type(zone_type: str, ViolationType):
    """Map parking zone type to ViolationType enum."""
    mapping = {
        'no_parking': ViolationType.PARKING_NO_PARKING,
        'no_stopping': ViolationType.PARKING_NO_STOPPING,
        'limited': ViolationType.PARKING_OVERTIME,
        'handicap': ViolationType.PARKING_HANDICAP,
        'loading': ViolationType.PARKING_LOADING,
    }
    return mapping.get(zone_type, ViolationType.PARKING_NO_PARKING)


def _apply_speeding_penalty(track_id: int, plate_text: str, speed: float, bbox: Tuple[int, int, int, int] = None):
    """Apply speeding violation penalty to database with evidence capture."""
    scoring = get_scoring_engine()
    
    # Normalize plate for consistent DB matching
    from app.utils.plate_utils import normalize_plate
    normalized = normalize_plate(plate_text) if plate_text else None
    driver_id = normalized or f"UNKNOWN{track_id}"
    
    # TTS warning for speeding
    tts_name = plate_text if (plate_text and not plate_text.startswith("UNKNOWN")) else f"Vehicle {track_id}"
    speak_warning(
        f"Speeding violation! {tts_name} detected at {speed:.0f} kilometers per hour. Speed limit is {SPEEDING_THRESHOLD_KMH:.0f}.",
        track_id=track_id,
        warning_type="speeding"
    )
    
    if scoring["engine"] is None:
        print(f"[PENALTY] ⚠️ Scoring engine not available. Would penalize speeder: {driver_id}")
        return
    
    ViolationType = scoring["ViolationType"]
    
    # Capture evidence snapshot
    evidence_path = _capture_evidence_snapshot(
        track_id, "speeding", bbox=bbox,
        extra_text=f"Speeding: {speed:.0f} km/h (Limit: {SPEEDING_THRESHOLD_KMH:.0f} km/h)"
    )
    
    try:
        driver, violation = scoring["engine"].record_violation(
            driver_id=driver_id,
            violation_type=ViolationType.SPEEDING,
            location="Traffic Camera",
            license_plate=plate_text,
            snapshot_path=evidence_path,
            notes=f"Speeding: {speed:.0f} km/h detected (limit: {SPEEDING_THRESHOLD_KMH:.0f} km/h)",
        )
        print(f"[PENALTY] 🚨 SPEEDING DB SAVED: {driver_id} | Speed: {speed:.0f} km/h | Fine: LKR {violation.fine_amount}")
        
        # Update junction safety score
        try:
            from app.services.lane_weaving_service import get_junction_safety
            junction = get_junction_safety()
            junction.apply_penalty('speeding')
        except Exception as je:
            print(f"[PENALTY] Junction safety update error: {je}")
        
        penalized_vehicles[track_id] = time.time()
        
    except Exception as e:
        print(f"[PENALTY] Error saving speeding to DB: {e}")


def cleanup_parking_tracker(active_track_ids: set):
    """Remove parking entries for vehicles no longer tracked."""
    global parking_tracker
    to_remove = [tid for tid in parking_tracker if tid not in active_track_ids]
    for tid in to_remove:
        del parking_tracker[tid]


# Lane weaving penalty cooldown: track_id -> last_penalty_time
_lane_weaving_cooldown: Dict[int, float] = {}

def _apply_lane_weaving_penalty(track_id: int, plate_text: str, weaving_event, bbox: Tuple[int, int, int, int] = None):
    """Apply lane weaving violation penalty to database with evidence capture."""
    global _lane_weaving_cooldown
    
    # 30s cooldown per vehicle to avoid spamming
    now = time.time()
    if track_id in _lane_weaving_cooldown and (now - _lane_weaving_cooldown[track_id]) < 30.0:
        return
    
    scoring = get_scoring_engine()
    
    from app.utils.plate_utils import normalize_plate
    normalized = normalize_plate(plate_text) if plate_text else None
    driver_id = normalized or f"UNKNOWN{track_id}"
    
    # TTS warning
    tts_name = plate_text if (plate_text and not plate_text.startswith("UNKNOWN")) else f"Vehicle {track_id}"
    speak_warning(
        f"Lane weaving detected! {tts_name} is driving erratically.",
        track_id=track_id,
        warning_type="lane_weaving"
    )
    
    if scoring["engine"] is None:
        print(f"[LANE_WEAVING] ⚠️ Scoring engine not available. Would penalize: {driver_id}")
        return
    
    ViolationType = scoring["ViolationType"]
    
    evidence_path = _capture_evidence_snapshot(
        track_id, "lane_weaving", bbox=bbox,
        extra_text=f"Lane Weaving - {weaving_event.direction_changes} direction changes"
    )
    
    try:
        driver, violation = scoring["engine"].record_violation(
            driver_id=driver_id,
            violation_type=ViolationType.LANE_WEAVING,
            location="Traffic Camera",
            license_plate=plate_text,
            snapshot_path=evidence_path,
            notes=f"Lane weaving: {weaving_event.direction_changes} direction changes, "
                  f"avg lateral velocity: {weaving_event.avg_x_velocity:.1f} px/frame",
        )
        print(f"[LANE_WEAVING] 🚨 DB SAVED: {driver_id} | Fine: LKR {violation.fine_amount}")
        _lane_weaving_cooldown[track_id] = now
        
    except Exception as e:
        print(f"[LANE_WEAVING] Error saving to DB: {e}")


# ============================================================================
# SIGNAL AUTOMATION (4-WAY JUNCTION)
# ============================================================================

def update_traffic_signal(vehicle_count: int, frame_id: int, detections: list = None) -> Tuple[Optional[str], Optional[int]]:
    """
    Update 4-way traffic signal based on vehicle count.
    Also checks for emergency vehicles (ambulance) to trigger emergency mode.
    
    Args:
        vehicle_count: Number of vehicles detected (for North lane)
        frame_id: Current frame number
        detections: List of Detection objects (for emergency vehicle check)
    
    Returns:
        Tuple of (current_state, green_remaining)
    """
    controller = get_traffic_controller()
    
    if controller is None:
        return None, None
    
    try:
        # Check for emergency vehicles (ambulance) if detections provided
        if detections:
            emergency_result = trigger_emergency_if_detected(detections)
            if emergency_result and emergency_result.get('status') == 'emergency_activated':
                return 'green', controller.emergency_duration
        
        # Update North lane count (real YOLO data)
        controller.update_north_count(vehicle_count)
        
        # Auto-tick advances the signal based on elapsed time
        if frame_id % SIGNAL_UPDATE_INTERVAL == 0:
            states = controller.auto_tick()
            current_green = states['current_green']
            state = states['lanes'][current_green]['state']
            remaining = states['green_remaining']
            
            print(f"[SIGNAL] 4-WAY | Green: {current_green.upper()} | State={state} | Remaining={remaining}s | Emergency={states['emergency_mode']}")
            
            return state, remaining
        
        return None, None
        
    except Exception as e:
        print(f"[SIGNAL] Error: {e}")
        return None, None


# ============================================================================
# STAGE 1: VEHICLE TRACKING
# ============================================================================

def track_vehicles(
    model: Any,
    frame: np.ndarray,
    confidence: float = 0.5,
    frame_id: int = 0,
) -> Tuple[List[Detection], bool]:
    """
    Stage 1: Vehicle detection with tracking and frame skipping.
    """
    global _prev_detections
    
    run_detection = (frame_id % YOLO_DETECTION_INTERVAL == 0)
    
    if not run_detection and _prev_detections:
        return _prev_detections, False
    
    results = model.track(
        source=frame,
        conf=confidence,
        classes=VEHICLE_CLASS_IDS,
        persist=True,
        verbose=False,
    )
    
    detections = []
    current_time = time.time()
    
    if results and len(results) > 0:
        result = results[0]
        
        if result.boxes is not None:
            boxes = result.boxes
            
            for i in range(len(boxes)):
                xyxy = boxes.xyxy[i].cpu().numpy()
                x1, y1, x2, y2 = map(int, xyxy)
                
                conf = float(boxes.conf[i].cpu().numpy())
                cls_id = int(boxes.cls[i].cpu().numpy())
                
                track_id = int(boxes.id[i].cpu().numpy()) if boxes.id is not None else -1
                
                centroid = ((x1 + x2) // 2, (y1 + y2) // 2)
                area = (x2 - x1) * (y2 - y1)
                class_name = VEHICLE_CLASSES.get(cls_id, f"class_{cls_id}")
                
                speed_kmh, speed_pixels, is_speeding = calculate_speed(track_id, centroid, current_time)
                
                detection = Detection(
                    track_id=track_id,
                    class_id=cls_id,
                    class_name=class_name,
                    confidence=conf,
                    bbox=(x1, y1, x2, y2),
                    centroid=centroid,
                    area=area,
                    timestamp=current_time,
                    speed_kmh=speed_kmh,
                    speed_pixels=speed_pixels,
                    is_speeding=is_speeding,
                )
                
                # Check speeding penalty (only once per vehicle)
                if is_speeding and track_id not in penalized_vehicles:
                    # We'll apply penalty if plate is detected later
                    pass
                
                detections.append(detection)
    
    _prev_detections = detections
    
    active_ids = {d.track_id for d in detections}
    cleanup_speed_history(active_ids)
    cleanup_parking_tracker(active_ids)
    
    return detections, True


# ============================================================================
# STAGE 2: PLATE DETECTION WITH OCR
# ============================================================================

def detect_plates_in_crops(
    plate_model: Any,
    frame: np.ndarray,
    vehicle_detections: List[Detection],
    confidence: float = 0.2,
) -> Tuple[List[Tuple[int, int, int, int]], Dict[int, Dict[str, Any]]]:
    """Stage 2: Plate detection with OCR caching."""
    global plate_history, ocr_cooldown
    
    if plate_model is None:
        return [], {}
    
    all_plates = []
    vehicle_plate_map = {}
    
    read_plate = get_ocr_service()
    current_time = time.time()
    
    for det in vehicle_detections:
        vx1, vy1, vx2, vy2 = det.bbox
        
        h, w = frame.shape[:2]
        vx1, vy1 = max(0, vx1), max(0, vy1)
        vx2, vy2 = min(w, vx2), min(h, vy2)
        
        crop_w, crop_h = vx2 - vx1, vy2 - vy1
        if crop_w < 50 or crop_h < 50:
            continue
        
        vehicle_crop = frame[vy1:vy2, vx1:vx2]
        
        results = plate_model.predict(source=vehicle_crop, conf=confidence, verbose=False)
        
        if results and len(results) > 0 and results[0].boxes is not None:
            boxes = results[0].boxes
            
            for i in range(len(boxes)):
                xyxy = boxes.xyxy[i].cpu().numpy()
                px1, py1, px2, py2 = map(int, xyxy)
                
                # Geometric filter: ignore top 30%
                if (py1 + py2) // 2 < (crop_h * 0.3):
                    continue
                
                # Convert to real coordinates
                real_px1, real_py1 = vx1 + px1, vy1 + py1
                real_px2, real_py2 = vx1 + px2, vy1 + py2
                plate_bbox = (real_px1, real_py1, real_px2, real_py2)
                
                # OCR with caching
                plate_text = None
                should_run_ocr = True
                track_id = det.track_id
                
                if track_id in plate_history and plate_history[track_id].get("text"):
                    plate_text = plate_history[track_id]["text"]
                    last_ocr_time = ocr_cooldown.get(track_id, 0)
                    if (current_time - last_ocr_time) < OCR_COOLDOWN_SECONDS:
                        should_run_ocr = False
                
                if should_run_ocr:
                    plate_crop = vehicle_crop[py1:py2, px1:px2]
                    if plate_crop.size > 0:
                        new_text = read_plate(plate_crop)
                        if new_text:
                            plate_text = new_text
                            ocr_cooldown[track_id] = current_time
                            
                            # If this vehicle was speeding and now we have plate, penalize
                            if det.is_speeding and track_id not in penalized_vehicles:
                                _apply_speeding_penalty(track_id, plate_text, det.speed_kmh, bbox=det.bbox)
                
                all_plates.append(plate_bbox)
                vehicle_plate_map[track_id] = {"bbox": plate_bbox, "text": plate_text}
                
                plate_history[track_id] = {
                    "bbox": plate_bbox,
                    "text": plate_text,
                    "timestamp": current_time,
                    "frame_count": 0,
                }
                break
    
    return all_plates, vehicle_plate_map


def update_plate_history(vehicle_detections: List[Detection]) -> Dict[int, Dict[str, Any]]:
    """Update plate history and return remembered plates."""
    global plate_history
    
    current_track_ids = {det.track_id for det in vehicle_detections}
    remembered_plates = {}
    
    to_remove = []
    for track_id, info in plate_history.items():
        info["frame_count"] += 1
        
        if track_id in current_track_ids and info["frame_count"] < PLATE_HISTORY_MAX_AGE:
            remembered_plates[track_id] = {"bbox": info["bbox"], "text": info.get("text")}
        
        if info["frame_count"] >= PLATE_HISTORY_MAX_AGE:
            to_remove.append(track_id)
    
    for track_id in to_remove:
        del plate_history[track_id]
        if track_id in ocr_cooldown:
            del ocr_cooldown[track_id]
    
    return remembered_plates


# ============================================================================
# MAIN DETECTION PIPELINE
# ============================================================================

def detect_and_track(
    vehicle_model: Any,
    frame: np.ndarray,
    frame_id: int = 0,
    confidence: float = 0.5,
    plate_model: Any = None,
    run_plate_detection: bool = True,
) -> FrameResult:
    """
    Complete detection pipeline with all integrations.
    """
    global _frame_counter, _prev_plate_boxes, _current_analysis_frame
    
    # Store current frame for evidence snapshot capture
    _current_analysis_frame = frame.copy()
    
    timestamp = time.time()
    start_time = time.time()
    
    # Stage 1: Vehicle tracking
    detections, _ = track_vehicles(vehicle_model, frame, confidence, _frame_counter)
    
    # Stage 2: Plate detection
    all_plates = []
    vehicle_plate_map = {}
    
    if run_plate_detection and plate_model is not None:
        if _frame_counter % PLATE_DETECTION_INTERVAL == 0:
            all_plates, vehicle_plate_map = detect_plates_in_crops(plate_model, frame, detections)
            _prev_plate_boxes = all_plates
        else:
            all_plates = _prev_plate_boxes
        
        remembered_plates = update_plate_history(detections)
        for track_id, plate_info in remembered_plates.items():
            if track_id not in vehicle_plate_map:
                vehicle_plate_map[track_id] = plate_info
                if plate_info["bbox"] not in all_plates:
                    all_plates.append(plate_info["bbox"])
    
    # Enrich detections
    speeding_count = 0
    parking_warnings = 0
    parking_violations = 0
    red_light_violations = 0
    
    # Get frame dimensions for red light and zone checks
    frame_height = frame.shape[0]
    frame_width = frame.shape[1]
    
    # Get member services
    lane_service = get_lane_weaving_service()
    behavior_svc = get_behavior_service()
    
    for det in detections:
        # Add plate info
        if det.track_id in vehicle_plate_map:
            plate_info = vehicle_plate_map[det.track_id]
            det.has_plate = True
            det.plate_bbox = plate_info["bbox"]
            det.plate_text = plate_info.get("text")
        
        if det.is_speeding:
            speeding_count += 1
            # Fallback: penalize speeding vehicles even without plate detection
            if det.track_id not in penalized_vehicles:
                plate = det.plate_text or f"UNKNOWN{det.track_id}"
                _apply_speeding_penalty(det.track_id, plate, det.speed_kmh, bbox=det.bbox)
        
        # Check parking violations
        parking_time, parking_status, zone_id, is_penalized = check_parking_violation(det, timestamp)
        det.parking_time = parking_time
        det.parking_status = parking_status
        det.parking_zone = zone_id
        det.is_penalized = is_penalized
        
        if parking_status == "warning":
            parking_warnings += 1
        elif parking_status == "violation":
            parking_violations += 1
        
        # ===== MEMBER 2: Red Light Violation Detection =====
        is_red_light_violator = check_red_light_violation(det, frame_height, timestamp, frame_width)
        if is_red_light_violator:
            det.is_penalized = True
            red_light_violations += 1
        
        # ===== Wrong-Way Violation Detection =====
        is_wrong_way = check_wrong_way_violation(det, timestamp)
        if is_wrong_way:
            det.is_penalized = True
        
        # ===== MEMBER 2: Lane Weaving Detection =====
        if lane_service:
            try:
                weaving_event = lane_service.detect_lane_weaving(
                    det.track_id, det.centroid, det.plate_text
                )
                if weaving_event:
                    print(f"[MEMBER2] Lane weaving: Vehicle {det.track_id}")
                    # Issue formal lane weaving violation via ScoringEngine
                    _apply_lane_weaving_penalty(
                        det.track_id,
                        det.plate_text or f"UNKNOWN{det.track_id}",
                        weaving_event,
                        bbox=det.bbox
                    )
            except Exception as e:
                pass  # Non-critical feature
        
        # ===== MEMBER 4: Abnormal Behavior Detection =====
        if behavior_svc:
            try:
                behavior_svc.analyze_vehicle_behavior(
                    det.track_id,
                    det.centroid,
                    det.speed_pixels,
                    det.plate_text
                )
            except Exception as e:
                pass  # Non-critical feature
    
    # Signal automation (4-way junction with emergency detection)
    vehicle_count = len(detections)
    signal_state, signal_duration = update_traffic_signal(vehicle_count, _frame_counter, detections)
    
    _frame_counter += 1
    inference_time = (time.time() - start_time) * 1000
    
    return FrameResult(
        frame_id=frame_id,
        timestamp=timestamp,
        detections=detections,
        inference_time_ms=inference_time,
        plate_boxes=all_plates,
        image=frame,
        vehicle_count=vehicle_count,
        speeding_count=speeding_count,
        parking_warnings=parking_warnings,
        parking_violations=parking_violations,
        signal_state=signal_state,
        signal_duration=signal_duration,
    )


# ============================================================================
# RED LIGHT VIOLATION DETECTION (Member 2 Feature)
# ============================================================================

# Stop line configuration (loaded from Firestore)
_stop_line_config = {
    "y_position": 0.6,   # 60% down from top (default)
    "x_start": 0.0,      # Left boundary (0 = left edge)
    "x_end": 1.0,        # Right boundary (1.0 = full width, all lanes)
    "active": True,
}

# Legacy constant for backward compatibility
STOP_LINE_RATIO = 0.6  # Will be overridden by config

# Red light violation tracking
_red_light_violators: Dict[int, float] = {}  # track_id -> violation_time
_red_light_plate_cooldown: Dict[str, float] = {}  # plate_text -> last_violation_time

# Wrong-way tracking: track_id -> {"consecutive_wrong": int, "penalized": bool}
_wrong_way_tracker: Dict[int, Dict[str, Any]] = {}

# Wrong-way detection constants
# Expected traffic flow direction: downward in frame (positive dy)
WRONG_WAY_CONSECUTIVE_FRAMES: int = 3   # Must move wrong-way for 3 consecutive analysis frames
WRONG_WAY_MIN_SPEED_PIXELS: float = 30.0  # Minimum speed to consider direction meaningful
WRONG_WAY_COOLDOWN_SECONDS: float = 10.0  # Don't re-penalize same vehicle within 10s


def load_stop_line_config():
    """Load stop line configuration from Firestore."""
    global _stop_line_config, STOP_LINE_RATIO
    try:
        from app.db.firestore_client import get_sync_db, Collections
        db = get_sync_db()
        doc = db.collection(Collections.CONFIG).document("main_stop_line").get()
        if doc.exists:
            data = doc.to_dict()
            _stop_line_config = {
                "y_position": data.get("y_position", 0.6),
                "x_start": data.get("x_start", 0.0),
                "x_end": data.get("x_end", 1.0),
                "active": data.get("active", True),
            }
            STOP_LINE_RATIO = _stop_line_config["y_position"]
            print(f"[STOP_LINE] Loaded config: Y={_stop_line_config['y_position']:.2f}, "
                  f"X={_stop_line_config['x_start']:.2f}-{_stop_line_config['x_end']:.2f}")
    except Exception as e:
        print(f"[STOP_LINE] Warning: Could not load config: {e}")


def get_stop_line_config() -> dict:
    """Get current stop line configuration."""
    return _stop_line_config.copy()

def check_red_light_violation(
    det: Detection,
    frame_height: int,
    current_time: float,
    frame_width: int = 1920,
) -> bool:
    """
    Check if a vehicle is violating a red light.
    
    Enhanced Logic (v3):
    - Get current signal state for North lane (video feed)
    - Define stop line at configured y_position ratio of frame height
    - Check if vehicle is within the monitored lane (x_start to x_end)
    - If signal is RED and vehicle crossed stop line:
      - Verify vehicle is MOVING TOWARD the stop line (downward in frame)
      - Require minimum speed to avoid flagging slow-rolling stops
      - Apply 5-second cooldown per vehicle to prevent duplicate penalties
    
    Args:
        det: Detection object with vehicle info
        frame_height: Height of the video frame
        current_time: Current timestamp
        frame_width: Width of the video frame (for x filtering)
    
    Returns:
        True if violation detected, False otherwise
    """
    global _red_light_violators, _stop_line_config
    
    # Check if red light detection is active
    if not _stop_line_config.get("active", True):
        return False
    
    # Get traffic controller
    controller = get_traffic_controller()
    if controller is None:
        return False
    
    try:
        # Get North lane state (the video feed lane)
        status = controller.get_all_states()
        north_state = status.get('lanes', {}).get('north', {}).get('state', 'green')
        
        # Only check when light is RED
        if north_state != 'red':
            return False
        
        # Get stop line configuration
        y_ratio = _stop_line_config.get("y_position", 0.6)
        x_start_ratio = _stop_line_config.get("x_start", 0.0)
        x_end_ratio = _stop_line_config.get("x_end", 1.0)  # Full width by default
        
        # DEBUG: Log config once per second
        import time as _time
        _now = int(_time.time())
        if not hasattr(check_red_light_violation, '_last_debug') or check_red_light_violation._last_debug != _now:
            check_red_light_violation._last_debug = _now
            print(f"[RED_LIGHT DEBUG] Config: y={y_ratio:.2f}, x_start={x_start_ratio:.2f}, x_end={x_end_ratio:.2f}")
        
        # Calculate stop line position
        stop_line_y = int(frame_height * y_ratio)
        
        # Calculate x boundaries for the monitored lane
        x_start = int(frame_width * x_start_ratio)
        x_end = int(frame_width * x_end_ratio)
        
        # Get vehicle bounding box
        x1, y1, x2, vehicle_y = det.bbox
        vehicle_center_x = (x1 + x2) // 2
        
        # CHECK: Is vehicle within the monitored lane (x range)?
        # This prevents false positives from opposite lane vehicles
        if vehicle_center_x < x_start or vehicle_center_x > x_end:
            return False  # Vehicle is outside monitored lane
        
        # Check if vehicle crossed the stop line (bottom of bbox past stop line)
        crossed_line = vehicle_y > stop_line_y
        
        # Check how far past the stop line the vehicle is
        pixels_past_line = vehicle_y - stop_line_y if crossed_line else 0
        
        # Must be at least 20px past the line
        is_past_line = pixels_past_line > 20
        
        track_id = det.track_id
        
        # Direction-of-travel check: only needed for vehicles just past the line
        # Vehicles far past the line (50+ px) are obviously violations
        # Vehicles close to line need direction check to avoid false positives
        moving_forward = True  # Default to true for vehicles far past line
        if pixels_past_line < 50 and track_id in speed_history:
            prev_centroid = speed_history[track_id].get("prev_centroid")
            if prev_centroid:
                # Positive dy = moving down = moving toward/past stop line
                dy = det.centroid[1] - prev_centroid[1]
                moving_forward = dy >= 0  # Not backing up (allow stationary/forward)
        
        # Violation: Red light + crossed line by 20+px + not backing up
        if crossed_line and is_past_line and moving_forward:
            # Get plate if available
            plate_text = det.plate_text or f"UNKNOWN{track_id}"
            
            # Use 2-minute (120 second) cooldown per plate to prevent duplicate violations
            # This prevents the same vehicle from being penalized multiple times
            if plate_text in _red_light_plate_cooldown:
                last_time = _red_light_plate_cooldown[plate_text]
                if (current_time - last_time) < 120.0:  # 2 minutes
                    return True  # Still in violation state but don't re-penalize
            
            # Also check track_id for UNKNOWN plates (5 second cooldown to avoid spam)
            if plate_text.startswith("UNKNOWN") and track_id in _red_light_violators:
                last_violation_time = _red_light_violators[track_id]
                if (current_time - last_violation_time) < 5.0:
                    return True  # Still in violation state but don't re-penalize
            
            # Record violation by both plate and track_id
            _red_light_plate_cooldown[plate_text] = current_time
            _red_light_violators[track_id] = current_time
            
            # Apply penalty
            _apply_red_light_penalty(track_id, plate_text, det.speed_kmh, bbox=det.bbox)
            
            return True
        
        return False
        
    except Exception as e:
        print(f"[RED_LIGHT] Error checking violation: {e}")
        return False


def _apply_red_light_penalty(track_id: int, plate_text: str, speed: float, bbox: Tuple[int, int, int, int] = None):
    """Apply red light violation penalty to database with evidence capture."""
    global penalized_vehicles
    
    scoring = get_scoring_engine()
    
    # Normalize plate for consistent DB matching
    from app.utils.plate_utils import normalize_plate
    normalized = normalize_plate(plate_text) if plate_text else None
    driver_id = normalized or plate_text
    
    # TTS warning
    tts_name = plate_text if (plate_text and not plate_text.startswith("UNKNOWN")) else f"Vehicle {track_id}"
    speak_warning(
        f"Red light violation detected! {tts_name} ran a red light at {speed:.0f} kilometers per hour.",
        track_id=track_id,
        warning_type="red_light"
    )
    
    if scoring["engine"] is None:
        print(f"[RED_LIGHT] ⚠️ Scoring engine not available. Would penalize: {driver_id}")
        return
    
    ViolationType = scoring["ViolationType"]
    
    # Capture evidence snapshot
    evidence_path = _capture_evidence_snapshot(
        track_id, "red_light", bbox=bbox,
        extra_text=f"Red Light Violation at {speed:.0f} km/h"
    )
    
    try:
        # Use RED_LIGHT violation type
        violation_type = ViolationType.RED_LIGHT
        
        driver, violation = scoring["engine"].record_violation(
            driver_id=driver_id,
            violation_type=violation_type,
            location="Traffic Camera",
            license_plate=plate_text,
            snapshot_path=evidence_path,
            notes=f"Red Light Violation: Crossed stop line at {speed:.0f} km/h",
        )
        print(f"[RED_LIGHT] 🚨 VIOLATION DB SAVED: {driver_id} | Speed: {speed:.0f} km/h | Fine: LKR {violation.fine_amount}")
        
        # Update junction safety score
        try:
            from app.services.lane_weaving_service import get_junction_safety
            junction = get_junction_safety()
            junction.apply_penalty('running_red_light')
        except Exception as je:
            print(f"[RED_LIGHT] Junction safety update error: {je}")
        
        penalized_vehicles[track_id] = time.time()
        
    except Exception as e:
        print(f"[RED_LIGHT] Error saving to DB: {e}")


# ============================================================================
# WRONG-WAY VIOLATION DETECTION
# ============================================================================

def check_wrong_way_violation(
    det: Detection,
    current_time: float,
) -> bool:
    """
    Detect vehicles traveling against the dominant traffic flow.
    
    In the video feed, normal traffic flows DOWNWARD (increasing Y).
    A vehicle consistently moving UPWARD (decreasing Y) at speed is wrong-way.
    
    Uses consecutive-frame validation: direction must be wrong for
    WRONG_WAY_CONSECUTIVE_FRAMES in a row before flagging (avoids false alarms).
    
    Args:
        det: Detection object with vehicle info
        current_time: Current timestamp
    
    Returns:
        True if wrong-way violation detected, False otherwise
    """
    global _wrong_way_tracker, penalized_vehicles
    
    track_id = det.track_id
    
    # Need speed history to check direction
    if track_id not in speed_history:
        return False
    
    # Need minimum speed to determine direction meaningfully
    if det.speed_pixels < WRONG_WAY_MIN_SPEED_PIXELS:
        # Moving too slowly to determine direction — reset counter
        if track_id in _wrong_way_tracker:
            _wrong_way_tracker[track_id]["consecutive_wrong"] = 0
        return False
    
    # Compute direction of travel (dy over recent movement)
    hist = speed_history[track_id]
    prev_centroid = hist.get("prev_centroid")
    if prev_centroid is None:
        return False
    
    dy = det.centroid[1] - prev_centroid[1]
    
    # Normal flow = downward (dy > 0), Wrong-way = upward (dy < -3)
    going_wrong_way = dy < -3
    
    if track_id not in _wrong_way_tracker:
        _wrong_way_tracker[track_id] = {
            "consecutive_wrong": 0,
            "penalized": False,
            "last_penalty_time": 0,
        }
    
    entry = _wrong_way_tracker[track_id]
    
    if going_wrong_way:
        entry["consecutive_wrong"] += 1
    else:
        entry["consecutive_wrong"] = 0
        return False
    
    # Only flag after sustained wrong-way movement
    if entry["consecutive_wrong"] < WRONG_WAY_CONSECUTIVE_FRAMES:
        return False
    
    # Cooldown check
    if (current_time - entry.get("last_penalty_time", 0)) < WRONG_WAY_COOLDOWN_SECONDS:
        return True  # Still in violation state but don't re-penalize
    
    # Already penalized this vehicle?
    if entry["penalized"]:
        return True
    
    # Apply wrong-way penalty
    entry["penalized"] = True
    entry["last_penalty_time"] = current_time
    
    plate_text = det.plate_text or f"UNKNOWN{track_id}"
    _apply_wrong_way_penalty(track_id, plate_text, det.speed_kmh, bbox=det.bbox)
    
    return True


def _apply_wrong_way_penalty(track_id: int, plate_text: str, speed: float, bbox: Tuple[int, int, int, int] = None):
    """Apply wrong-way violation penalty to database with evidence capture."""
    global penalized_vehicles
    
    scoring = get_scoring_engine()
    
    # Normalize plate for consistent DB matching
    from app.utils.plate_utils import normalize_plate
    normalized = normalize_plate(plate_text) if plate_text else None
    driver_id = normalized or plate_text
    
    # TTS warning
    tts_name = plate_text if (plate_text and not plate_text.startswith("UNKNOWN")) else f"Vehicle {track_id}"
    speak_warning(
        f"Wrong way violation! {tts_name} is driving against traffic at {speed:.0f} kilometers per hour.",
        track_id=track_id,
        warning_type="wrong_way"
    )
    
    if scoring["engine"] is None:
        print(f"[WRONG_WAY] ⚠️ Scoring engine not available. Would penalize: {driver_id}")
        return
    
    ViolationType = scoring["ViolationType"]
    
    # Capture evidence snapshot
    evidence_path = _capture_evidence_snapshot(
        track_id, "wrong_way", bbox=bbox,
        extra_text=f"Wrong-Way Driving at {speed:.0f} km/h"
    )
    
    try:
        driver, violation = scoring["engine"].record_violation(
            driver_id=driver_id,
            violation_type=ViolationType.WRONG_WAY,
            location="Traffic Camera",
            license_plate=plate_text,
            snapshot_path=evidence_path,
            notes=f"Wrong-way driving: Moving against traffic flow at {speed:.0f} km/h",
        )
        print(f"[WRONG_WAY] 🚨 VIOLATION DB SAVED: {driver_id} | Speed: {speed:.0f} km/h | Fine: LKR {violation.fine_amount}")
        
        # Update junction safety score
        try:
            from app.services.lane_weaving_service import get_junction_safety
            junction = get_junction_safety()
            junction.apply_penalty('wrong_way_driving')
        except Exception as je:
            print(f"[WRONG_WAY] Junction safety update error: {je}")
        
        penalized_vehicles[track_id] = time.time()
        
    except Exception as e:
        print(f"[WRONG_WAY] Error saving to DB: {e}")


def get_north_signal_state() -> str:
    """Get current signal state for North lane."""
    controller = get_traffic_controller()
    if controller is None:
        return 'unknown'
    
    try:
        status = controller.get_all_states()
        return status.get('lanes', {}).get('north', {}).get('state', 'unknown')
    except:
        return 'unknown'


# ============================================================================
# VISUALIZATION
# ============================================================================

def draw_stop_line(frame: np.ndarray) -> np.ndarray:
    """Draw the stop line on the frame when light is red, within monitored lane only."""
    global _stop_line_config
    
    # Check if stop line is enabled - if not, return frame unchanged
    if not _stop_line_config.get("active", True):
        return frame
    
    h, w = frame.shape[:2]
    signal_state = get_north_signal_state()
    
    # Get stop line configuration
    y_ratio = _stop_line_config.get("y_position", 0.6)
    x_start_ratio = _stop_line_config.get("x_start", 0.0)
    x_end_ratio = _stop_line_config.get("x_end", 1.0)  # Full width by default
    
    stop_line_y = int(h * y_ratio)
    x_start = int(w * x_start_ratio)
    x_end = int(w * x_end_ratio)
    
    if signal_state == 'red':
        # Draw thick red line only in monitored lane
        cv2.line(frame, (x_start, stop_line_y), (x_end, stop_line_y), (0, 0, 255), 4)
        # Draw vertical boundaries to show monitored zone
        cv2.line(frame, (x_start, stop_line_y - 30), (x_start, stop_line_y + 30), (0, 0, 255), 2)
        cv2.line(frame, (x_end, stop_line_y - 30), (x_end, stop_line_y + 30), (0, 0, 255), 2)
        # Add label
        cv2.putText(frame, "STOP LINE - RED LIGHT", (x_start + 10, stop_line_y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
    elif signal_state == 'yellow':
        # Draw yellow line (warning)
        cv2.line(frame, (x_start, stop_line_y), (x_end, stop_line_y), (0, 255, 255), 2)
        cv2.putText(frame, "STOP LINE - YELLOW", (x_start + 10, stop_line_y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    else:
        # When green, show faint line to help admins see the position
        cv2.line(frame, (x_start, stop_line_y), (x_end, stop_line_y), (100, 100, 100), 1)
    
    return frame


def draw_parking_zones(frame: np.ndarray) -> np.ndarray:
    """Draw the parking zone boundaries on the frame (full resolution)."""
    for zone in parking_zones:
        polygon = np.array(zone["polygon"], dtype=np.int32)
        color = zone.get("color", (0, 0, 255))
        
        # Draw filled polygon with transparency
        overlay = frame.copy()
        cv2.fillPoly(overlay, [polygon], color)
        cv2.addWeighted(overlay, 0.2, frame, 0.8, 0, frame)
        
        # Draw boundary
        cv2.polylines(frame, [polygon], True, color, 2)
        
        # Draw zone label
        x, y = zone["polygon"][0]
        cv2.putText(frame, zone["name"], (x + 5, y + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    
    return frame


def draw_detections(
    frame: np.ndarray,
    result: FrameResult,
    show_labels: bool = True,
    show_track_id: bool = True,
    show_speed: bool = True,
    show_parking_zones: bool = True,
    show_stop_line: bool = True,
    box_thickness: int = 2,
) -> np.ndarray:
    """
    Draw detection boxes, plates, speed, parking status.
    
    Flashing purple for penalized vehicles.
    """
    annotated = frame.copy()
    
    # Draw stop line first (when light is red)
    if show_stop_line:
        annotated = draw_stop_line(annotated)
    
    # Draw parking zones
    if show_parking_zones:
        annotated = draw_parking_zones(annotated)
    
    colors = {
        "car": (0, 255, 0),
        "motorcycle": (0, 200, 255),
        "bus": (255, 100, 0),
        "truck": (255, 0, 255),
        "speeding": (0, 0, 255),
        "warning": (0, 165, 255),
        "violation": (255, 0, 255),
        "penalized": (255, 0, 255),  # Purple
    }
    plate_color = (255, 255, 0)
    
    # Draw plate boxes
    for px1, py1, px2, py2 in result.plate_boxes:
        cv2.rectangle(annotated, (px1, py1), (px2, py2), plate_color, box_thickness)
    
    current_time = time.time()
    
    for det in result.detections:
        x1, y1, x2, y2 = det.bbox
        
        # Choose color based on status
        if det.is_penalized:
            # Flashing purple effect
            if int(current_time * 4) % 2 == 0:
                color = colors["penalized"]
            else:
                color = (128, 0, 128)  # Darker purple
        elif det.parking_status == "violation":
            color = colors["violation"]
        elif det.parking_status == "warning":
            color = colors["warning"]
        elif det.is_speeding:
            color = colors["speeding"]
        else:
            color = colors.get(det.class_name, (0, 255, 0))
        
        # Draw vehicle box
        thickness = 3 if det.is_penalized else box_thickness
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, thickness)
        
        # Draw speed above box
        if show_speed and det.speed_kmh > 0:
            speed_text = f"{det.speed_kmh:.0f} km/h"
            if det.is_speeding:
                speed_text += " SPEEDING!"
            
            font = cv2.FONT_HERSHEY_SIMPLEX
            (tw, th), _ = cv2.getTextSize(speed_text, font, 0.6, 2)
            
            speed_color = (0, 0, 255) if det.is_speeding else (255, 255, 255)
            cv2.rectangle(annotated, (x1, y1 - th - 25), (x1 + tw + 4, y1 - 15), (0, 0, 0), -1)
            cv2.putText(annotated, speed_text, (x1 + 2, y1 - 18), font, 0.6, speed_color, 2)
        
        # Build label
        if show_labels or show_track_id:
            label_parts = []
            
            if show_track_id and det.track_id >= 0:
                label_parts.append(f"ID:{det.track_id}")
            
            if show_labels:
                label_parts.append(det.class_name)
            
            label = " | ".join(label_parts)
            
            if det.plate_text:
                label += f" | {det.plate_text}"
            elif det.has_plate:
                label += " [Plate]"
            
            # Parking timer
            if det.parking_time > 0:
                label += f" | Parked: {det.parking_time:.0f}s"
                if det.parking_status:
                    label += f" [{det.parking_status.upper()}]"
            
            if det.is_penalized:
                label += " | PENALIZED!"
            
            font = cv2.FONT_HERSHEY_SIMPLEX
            (tw, th), _ = cv2.getTextSize(label, font, 0.5, 1)
            
            cv2.rectangle(annotated, (x1, y1 - th - 10), (x1 + tw + 4, y1), color, -1)
            cv2.putText(annotated, label, (x1 + 2, y1 - 5), font, 0.5, (255, 255, 255), 1)
    
    return annotated


def draw_frame_info(frame: np.ndarray, result: FrameResult, extra_info: str = "") -> np.ndarray:
    """Draw frame information overlay."""
    info_parts = [
        f"Frame: {result.frame_id}",
        f"Vehicles: {result.vehicle_count}",
        f"Plates: {len(result.plate_boxes)}",
        f"Speeding: {result.speeding_count}",
        f"Parking: W={result.parking_warnings} V={result.parking_violations}",
        f"{result.inference_time_ms:.0f}ms",
    ]
    
    if result.signal_state:
        info_parts.append(f"Signal: {result.signal_state.upper()}")
    
    if extra_info:
        info_parts.append(extra_info)
    
    info_text = " | ".join(info_parts)
    
    font = cv2.FONT_HERSHEY_SIMPLEX
    (tw, th), _ = cv2.getTextSize(info_text, font, 0.6, 2)
    
    cv2.rectangle(frame, (5, 5), (tw + 15, th + 15), (0, 0, 0), -1)
    cv2.putText(frame, info_text, (10, th + 8), font, 0.6, (0, 255, 0), 2)
    
    return frame


# ============================================================================
# VIDEO PROCESSING
# ============================================================================

def process_video(
    video_path: str,
    vehicle_model: Any = None,
    plate_model: Any = None,
    confidence: float = 0.5,
    skip_frames: int = 0,
    max_frames: Optional[int] = None,
    enable_plate_detection: bool = True,
) -> Generator[FrameResult, None, None]:
    """Process a video file with full detection pipeline."""
    global _frame_counter, _prev_detections, _prev_plate_boxes
    
    _frame_counter = 0
    _prev_detections = []
    _prev_plate_boxes = []
    
    if vehicle_model is None:
        vehicle_model = load_vehicle_model()
    if plate_model is None and enable_plate_detection:
        plate_model = load_plate_model()
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {video_path}")
    
    frame_id = 0
    processed = 0
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            if skip_frames > 0 and frame_id % (skip_frames + 1) != 0:
                frame_id += 1
                continue
            
            result = detect_and_track(
                vehicle_model=vehicle_model,
                frame=frame,
                frame_id=frame_id,
                confidence=confidence,
                plate_model=plate_model,
                run_plate_detection=enable_plate_detection,
            )
            
            yield result
            
            processed += 1
            frame_id += 1
            
            if max_frames and processed >= max_frames:
                break
    finally:
        cap.release()


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def reset_state():
    """Reset all global tracking state. Called when user stops streaming."""
    global _frame_counter, _prev_detections, _prev_plate_boxes
    global plate_history, ocr_cooldown, speed_history, parking_tracker, penalized_vehicles
    global _red_light_violators, _last_emergency_detection_time, _wrong_way_tracker
    global _current_analysis_frame, _red_light_plate_cooldown
    
    _frame_counter = 0
    _prev_detections = []
    _prev_plate_boxes = []
    plate_history.clear()
    ocr_cooldown.clear()
    speed_history.clear()
    parking_tracker.clear()
    penalized_vehicles.clear()
    _red_light_violators.clear()
    _red_light_plate_cooldown.clear()
    _wrong_way_tracker.clear()
    _last_emergency_detection_time = 0
    _current_analysis_frame = None
    
    print("🔄 Detection state fully reset (tracking, speed, parking, plates, red-light, wrong-way, emergency)")


def set_parking_zones(zones: List[Dict]):
    """Update parking zones at runtime."""
    global parking_zones
    parking_zones = zones
    print(f"📍 Updated parking zones: {len(zones)} zones")


def detect_plates(plate_model, frame, vehicle_detections, confidence=0.3):
    """Legacy compatibility function."""
    plates, plate_map = detect_plates_in_crops(plate_model, frame, vehicle_detections, confidence)
    legacy_map = {tid: info["bbox"] for tid, info in plate_map.items()}
    return plates, legacy_map


# ============================================================================
# MAIN - Standalone testing
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Full Integration Detection")
    parser.add_argument("--video", type=str, help="Path to video file")
    parser.add_argument("--confidence", type=float, default=0.5)
    parser.add_argument("--no-plates", action="store_true")
    parser.add_argument("--display", action="store_true")
    args = parser.parse_args()
    
    print("🚀 Full Integration Detection Pipeline")
    print(f"   YOLO Interval: {YOLO_DETECTION_INTERVAL}")
    print(f"   Plate Interval: {PLATE_DETECTION_INTERVAL}")
    print(f"   OCR Cooldown: {OCR_COOLDOWN_SECONDS}s")
    print(f"   Speeding: {SPEEDING_THRESHOLD_KMH} km/h")
    print(f"   Parking Warning: {PARKING_WARNING_SECONDS}s")
    print(f"   Parking Violation: {PARKING_VIOLATION_SECONDS}s")
    print(f"   Parking Zones: {len(parking_zones)}")
    
    vehicle_model, plate_model = get_models()
    
    video_path = args.video or str(Path(__file__).parent.parent.parent.parent / "data" / "videos" / "SriLankan_Traffic_Video.mp4")
    
    print(f"📹 Processing: {video_path}")
    reset_state()
    
    for result in process_video(
        video_path,
        vehicle_model=vehicle_model,
        plate_model=plate_model if not args.no_plates else None,
        confidence=args.confidence,
        enable_plate_detection=not args.no_plates,
    ):
        annotated = draw_detections(result.image, result)
        annotated = draw_frame_info(annotated, result)
        
        print(f"F{result.frame_id}: V={result.vehicle_count} P={len(result.plate_boxes)} S={result.speeding_count} Park={result.parking_warnings}/{result.parking_violations} {result.inference_time_ms:.0f}ms")
        
        if args.display:
            cv2.imshow("Detection", annotated)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    
    if args.display:
        cv2.destroyAllWindows()
    
    print("✅ Complete!")
