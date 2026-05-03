"""
Intelligent Traffic Management System - Video Streaming Router
TWO-THREAD ARCHITECTURE v3

Architecture:
=============
  Thread 1 — DISPLAY (video_display_loop)
    Reads video at native 30 FPS, draws cached detection overlays,
    encodes full-resolution JPEG, updates VideoState for WebSocket.
    NEVER calls YOLO → always smooth, no stutter.

  Thread 2 — ANALYSIS (video_analysis_loop)
    Grabs the latest raw frame from a shared buffer, runs full YOLO
    pipeline (vehicle tracking, plate OCR, speed, violations) at 3 FPS.
    Results are cached so Thread 1 can draw them on every frame.

Key Design Decisions:
- Both threads use full 1920×1080 — NO resize anywhere
- Zone coordinates match perfectly between Zone Editor and live feed
- YOLO at 3 FPS gives 3× more speed/tracking data without blocking video
- On stop: both threads halt, ALL detection state is reset
"""

import asyncio
import time
import json
import base64
import threading
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.detection.yolo_detector import (
    load_vehicle_model,
    load_plate_model,
    detect_and_track,
    draw_detections,
    draw_frame_info,
    FrameResult,
    set_parking_zones,
)
from app.tts.tts_service import set_tts_paused

settings = get_settings()
router = APIRouter(prefix="/video", tags=["Video"])


# ============================================================================
# THREAD-SAFE VIDEO STATE
# ============================================================================

@dataclass
class VideoState:
    """Thread-safe container for video stream state."""
    # Core frame data
    latest_frame_bytes: Optional[bytes] = None  # JPEG for streaming (with detections)
    latest_snapshot: Optional[bytes] = None     # Clean snapshot for Zone Editor (NO boxes/zones)
    raw_frame_captured: bool = False            # Flag to capture clean frame once
    
    # Detection stats
    vehicle_count: int = 0
    total_detections: int = 0
    plates_detected: int = 0
    frames_processed: int = 0
    
    # State
    running: bool = False
    video_source: Optional[str] = None
    start_time: Optional[float] = None
    last_frame_time: Optional[float] = None
    
    # Lock for thread safety
    lock: threading.Lock = field(default_factory=threading.Lock)
    
    def update_frame(self, frame_bytes: bytes, vehicle_count: int, 
                     plates: int = 0, raw_snapshot: Optional[bytes] = None):
        """Thread-safe frame update."""
        with self.lock:
            self.latest_frame_bytes = frame_bytes
            self.vehicle_count = vehicle_count
            self.frames_processed += 1
            self.total_detections += vehicle_count
            self.plates_detected += plates
            self.last_frame_time = time.time()
            
            # Capture clean snapshot (without boxes/zones) for Zone Editor
            if raw_snapshot is not None and not self.raw_frame_captured:
                self.latest_snapshot = raw_snapshot
                self.raw_frame_captured = True
                print("[SNAPSHOT] ✅ Clean frame captured for Zone Editor (no boxes)")
    
    def get_frame(self) -> Optional[bytes]:
        """Thread-safe frame retrieval."""
        with self.lock:
            return self.latest_frame_bytes
    
    def get_snapshot(self) -> Optional[bytes]:
        """Thread-safe snapshot retrieval."""
        with self.lock:
            return self.latest_snapshot
    
    def request_new_snapshot(self):
        """Request a fresh clean snapshot on next frame."""
        with self.lock:
            self.raw_frame_captured = False
    
    def get_stats(self) -> dict:
        """Thread-safe stats retrieval."""
        with self.lock:
            return {
                "running": self.running,
                "video_source": self.video_source,
                "vehicle_count": self.vehicle_count,
                "total_detections": self.total_detections,
                "plates_detected": self.plates_detected,
                "frames_processed": self.frames_processed,
                "uptime_seconds": time.time() - self.start_time if self.start_time else 0,
            }
    
    def reset(self):
        """Reset state for new stream."""
        with self.lock:
            self.latest_frame_bytes = None
            # Keep snapshot so Zone Editor still works
            self.vehicle_count = 0
            self.total_detections = 0
            self.plates_detected = 0
            self.frames_processed = 0
            self.running = False
            self.start_time = None
            self.raw_frame_captured = False  # Allow new clean capture on restart


# Global state instance
_video_state = VideoState()

# Worker thread references (two threads)
_display_thread: Optional[threading.Thread] = None
_analysis_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()

# Shared frame buffer: display thread writes latest raw frame here,
# analysis thread reads it for YOLO processing.
_analysis_frame: Optional[np.ndarray] = None
_analysis_frame_id: int = 0
_analysis_lock = threading.Lock()

# Cached analysis result — written by analysis thread, read by display thread
_cached_result: Optional[FrameResult] = None
_cached_vehicle_count: int = 0
_cached_plate_count: int = 0
_result_lock = threading.Lock()

# WebSocket clients
_ws_clients: set = set()
_ws_lock = asyncio.Lock()

# Video capture for seeking
_video_capture: Optional[cv2.VideoCapture] = None
_video_total_frames: int = 0
_video_capture_lock = threading.Lock()
_seek_target_frame: Optional[int] = None


# ============================================================================
# ZONE LOADING
# ============================================================================

def load_zones_from_db_sync():
    """Synchronous zone loading using the sync Firestore client."""
    from app.db.firestore_client import get_sync_db, Collections

    try:
        db = get_sync_db()
        q = db.collection(Collections.PARKING_ZONES).where(
            "active", "==", True
        )
        rows = [(doc.id, doc.to_dict()) for doc in q.stream()]

        if not rows:
            print("[ZONES] No active zones in Firestore, disabling violation detection")
            set_parking_zones([])
            return

        zones = []
        for doc_id, row in rows:
            raw_coords = row.get("coordinates", [])
            if isinstance(raw_coords, str):
                import json as _json
                raw_coords = _json.loads(raw_coords)
            # Handle both dict format {x:,y:} and list format [x,y]
            if raw_coords and isinstance(raw_coords[0], dict):
                polygon = [(int(p["x"]), int(p["y"])) for p in raw_coords]
            else:
                polygon = [(int(p[0]), int(p[1])) for p in raw_coords]

            zone_type = row.get("zone_type", "red")
            if zone_type in ("red", "no_parking"):
                color = (0, 0, 255)
            elif zone_type in ("yellow", "loading"):
                color = (0, 255, 255)
            elif zone_type in ("blue", "handicap"):
                color = (255, 0, 0)
            else:
                color = (0, 0, 255)

            zones.append({
                "id": f"zone_{doc_id}",
                "name": row.get("label") or f"Zone {doc_id}",
                "polygon": polygon,
                "color": color,
            })

        set_parking_zones(zones)
        print(f"[ZONES] Loaded {len(zones)} zones from Firestore")

    except Exception as e:
        print(f"[ZONES] Error loading zones: {e}")
        import traceback
        traceback.print_exc()


# ============================================================================
# THREAD 1 — DISPLAY (reads video, draws overlays, encodes JPEG)
# ============================================================================

def video_display_loop():
    """
    Display thread: reads video at native FPS, draws cached detections,
    encodes full-resolution JPEG, updates VideoState for WebSocket.
    NEVER calls YOLO — always smooth, no stutter.
    """
    global _video_state, _analysis_frame, _analysis_frame_id
    global _video_capture, _video_total_frames, _video_capture_lock, _seek_target_frame

    JPEG_QUALITY = 80
    SNAPSHOT_JPEG_QUALITY = 90

    print("[DISPLAY] 🚀 Display thread starting...")

    # Find video source
    video_path = str(settings.data_dir / "videos" / "SriLankan_Traffic_Video.mp4")
    if not Path(video_path).exists():
        videos_dir = Path(settings.data_dir) / "videos"
        if videos_dir.exists():
            video_files = list(videos_dir.glob("*.mp4"))
            if video_files:
                video_path = str(video_files[0])
            else:
                print("[DISPLAY] ❌ No video files found!")
                return

    print(f"[DISPLAY] 📹 Opening video: {video_path}")
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)

    if not cap.isOpened():
        print(f"[DISPLAY] ❌ Cannot open video: {video_path}")
        return

    # Store video capture globally for seeking
    with _video_capture_lock:
        _video_capture = cap
        _video_total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        print(f"[DISPLAY] 📊 Total frames: {_video_total_frames}")

    native_fps = cap.get(cv2.CAP_PROP_FPS)
    if native_fps <= 0 or native_fps > 120:
        native_fps = 25.0
    frame_interval = 1.0 / native_fps

    print(f"[DISPLAY] Video FPS: {native_fps:.1f}, frame interval: {frame_interval*1000:.1f}ms")

    _video_state.running = True
    _video_state.video_source = video_path
    _video_state.start_time = time.time()
    set_tts_paused(False)

    frame_idx = 0
    log_interval = int(native_fps * 10)  # Log every ~10 seconds

    print("[DISPLAY] ▶️ Display loop started (full resolution, no YOLO)")

    try:
        while not _stop_event.is_set():
            loop_start = time.time()

            # Apply pending seek request (set by API thread) in display thread only.
            with _video_capture_lock:
                if _seek_target_frame is not None:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, _seek_target_frame)
                    frame_idx = _seek_target_frame
                    _seek_target_frame = None

            ret, frame = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                frame_idx = 0
                continue

            frame_idx += 1

            # ── Publish frame for analysis thread ────────────────────
            with _analysis_lock:
                _analysis_frame = frame.copy()
                _analysis_frame_id = frame_idx

            # ── Snapshot: capture one clean full-res frame ───────────
            raw_snapshot_bytes = None
            if not _video_state.raw_frame_captured:
                _, raw_buf = cv2.imencode('.jpg', frame,
                                          [cv2.IMWRITE_JPEG_QUALITY, SNAPSHOT_JPEG_QUALITY])
                raw_snapshot_bytes = raw_buf.tobytes()

            # ── Draw cached detection overlays ───────────────────────
            with _result_lock:
                last_result = _cached_result
                vcount = _cached_vehicle_count
                pcount = _cached_plate_count

            display_frame = frame  # No copy needed — we draw on it directly
            if last_result is not None:
                display_frame = draw_detections(display_frame, last_result)
                display_frame = draw_frame_info(display_frame, last_result)

            # ── Encode JPEG at full resolution ───────────────────────
            _, buffer = cv2.imencode('.jpg', display_frame,
                                     [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
            frame_bytes = buffer.tobytes()

            _video_state.update_frame(
                frame_bytes=frame_bytes,
                vehicle_count=vcount,
                plates=pcount,
                raw_snapshot=raw_snapshot_bytes,
            )

            if log_interval > 0 and frame_idx % log_interval == 0:
                print(f"[DISPLAY] Frame {frame_idx}: {vcount} vehicles, {pcount} plates")

            # ── Sleep to match native FPS ────────────────────────────
            elapsed = time.time() - loop_start
            sleep_time = max(0.001, frame_interval - elapsed)
            time.sleep(sleep_time)

    except Exception as e:
        print(f"[DISPLAY] ❌ Error: {e}")
        import traceback; traceback.print_exc()
    finally:
        cap.release()
        # Clear global video capture
        with _video_capture_lock:
            _video_capture = None
            _video_total_frames = 0
            _seek_target_frame = None
        _video_state.running = False
        set_tts_paused(True)
        print("[DISPLAY] 🛑 Display thread stopped")


# ============================================================================
# THREAD 2 — ANALYSIS (runs YOLO independently at 3 FPS)
# ============================================================================

def video_analysis_loop():
    """
    Analysis thread: grabs the latest raw frame from the shared buffer,
    runs the full YOLO pipeline at ANALYSIS_FPS.
    Results are stored in _cached_result for the display thread to draw.
    """
    global _cached_result, _cached_vehicle_count, _cached_plate_count

    ANALYSIS_FPS = 3
    analysis_interval = 1.0 / ANALYSIS_FPS

    print("[ANALYSIS] 🚀 Analysis thread starting...")

    # Get traffic controller
    try:
        from app.fuzzy.traffic_controller import get_four_way_controller
        traffic_controller = get_four_way_controller()
        print("[ANALYSIS] ✅ Traffic controller connected")
    except Exception as e:
        print(f"[ANALYSIS] ⚠️ Traffic controller not available: {e}")
        traffic_controller = None

    # Load zones
    load_zones_from_db_sync()

    # Load YOLO models
    print("[ANALYSIS] 🔄 Loading YOLO models...")
    vehicle_model = load_vehicle_model("cpu")
    plate_model = load_plate_model("cpu")
    print("[ANALYSIS] ✅ Models loaded")

    last_processed_id = 0

    print(f"[ANALYSIS] ▶️ Analysis loop started (YOLO at {ANALYSIS_FPS} FPS)")

    try:
        while not _stop_event.is_set():
            loop_start = time.time()

            # Grab the latest frame from shared buffer
            with _analysis_lock:
                frame = _analysis_frame
                fid = _analysis_frame_id

            if frame is None or fid == last_processed_id:
                # No new frame yet — wait briefly
                time.sleep(0.01)
                continue

            last_processed_id = fid

            # Run full YOLO pipeline on FULL RESOLUTION frame
            result = detect_and_track(
                vehicle_model=vehicle_model,
                frame=frame,
                frame_id=fid,
                confidence=0.5,
                plate_model=plate_model,
                run_plate_detection=True,
            )

            vc = len(result.detections)
            pc = len(result.plate_boxes)

            # Publish result for display thread
            with _result_lock:
                _cached_result = result
                _cached_vehicle_count = vc
                _cached_plate_count = pc

            # Update traffic controller
            if traffic_controller:
                traffic_controller.update_north_count(vc)
                traffic_controller.auto_tick()

            # Throttle to ANALYSIS_FPS
            elapsed = time.time() - loop_start
            sleep_time = max(0.001, analysis_interval - elapsed)
            time.sleep(sleep_time)

    except Exception as e:
        print(f"[ANALYSIS] ❌ Error: {e}")
        import traceback; traceback.print_exc()
    finally:
        print("[ANALYSIS] 🛑 Analysis thread stopped")


def start_video_worker():
    """Start both display and analysis threads."""
    global _display_thread, _analysis_thread, _stop_event
    global _analysis_frame, _cached_result, _cached_vehicle_count, _cached_plate_count
    global _seek_target_frame

    if _display_thread and _display_thread.is_alive():
        print("[WORKER] Already running")
        return

    # Re-enable traffic controller auto-tick
    try:
        from app.fuzzy.traffic_controller import get_four_way_controller
        controller = get_four_way_controller()
        controller.auto_tick_enabled = True
        print("[WORKER] ✅ Traffic controller auto-tick enabled")
    except Exception as e:
        print(f"[WORKER] ⚠️ Could not enable traffic controller: {e}")

    # Clear shared state
    _analysis_frame = None
    _cached_result = None
    _cached_vehicle_count = 0
    _cached_plate_count = 0
    _seek_target_frame = None

    _stop_event.clear()

    _display_thread = threading.Thread(target=video_display_loop, daemon=True, name="display")
    _analysis_thread = threading.Thread(target=video_analysis_loop, daemon=True, name="analysis")

    _display_thread.start()
    _analysis_thread.start()
    print("[WORKER] ✅ Display + Analysis threads started")


def stop_video_worker():
    """Stop both threads and ALL associated services.

    CRITICAL: When user disconnects, this must:
    1. Stop display + analysis threads
    2. Reset ALL detection state (tracking, speed, parking, penalties)
    3. Disable traffic controller auto-tick
    4. Pause TTS and clean cache
    """
    global _display_thread, _analysis_thread, _stop_event
    global _analysis_frame, _cached_result, _cached_vehicle_count, _cached_plate_count
    global _seek_target_frame

    print("[WORKER] ⏹️ Stopping ALL threads and detection pipelines...")

    _stop_event.set()

    if _display_thread:
        _display_thread.join(timeout=5.0)
    if _analysis_thread:
        _analysis_thread.join(timeout=5.0)

    _video_state.reset()
    _analysis_frame = None
    _cached_result = None
    _cached_vehicle_count = 0
    _cached_plate_count = 0
    _seek_target_frame = None
    
    # CRITICAL: Reset ALL YOLO detection state
    # Without this, stale tracking/speed/parking data persists across sessions
    try:
        from app.detection.yolo_detector import reset_state as reset_detection_state
        reset_detection_state()
        print("[WORKER] 🔄 Detection state fully reset (tracking, speed, parking, penalties)")
    except Exception as e:
        print(f"[WORKER] ⚠️ Could not reset detection state: {e}")
    
    # Stop traffic controller auto-tick to prevent continued updates
    try:
        from app.fuzzy.traffic_controller import get_four_way_controller
        controller = get_four_way_controller()
        controller.auto_tick_enabled = False
        print("[WORKER] ⏹️ Traffic controller auto-tick disabled")
    except Exception as e:
        print(f"[WORKER] ⚠️ Could not stop traffic controller: {e}")
    
    # Clean up TTS audio files to prevent disk buildup
    try:
        from app.tts.tts_service import get_tts_service
        tts = get_tts_service()
        tts.cleanup_old_warnings(max_files=20)
        print("[WORKER] 🧹 TTS cache cleaned")
    except Exception as e:
        print(f"[WORKER] ⚠️ Could not clean TTS: {e}")
    
    print("[WORKER] ⏹️ Worker thread stopped — all detections halted")


# ============================================================================
# API ENDPOINTS - Lightweight, just serve from memory
# ============================================================================

# NOTE: Worker starts lazily when first client connects (WebSocket or snapshot request)
# This prevents video processing when no one is watching


@router.get("/snapshot")
async def get_snapshot():
    """
    Return the latest snapshot for Zone Editor.
    INSTANT response - just reads from memory.
    Starts video worker if not already running.
    """
    # Lazy start: Start worker if not running
    if not _video_state.running:
        start_video_worker()
        # Wait up to 15 seconds for first frame (YOLO models take time to load)
        import asyncio
        for _ in range(150):  # Max 15 seconds (model loading can take 5-10s)
            await asyncio.sleep(0.1)
            if _video_state.get_snapshot() is not None:
                break
    
    snapshot = _video_state.get_snapshot()
    
    if snapshot is None:
        raise HTTPException(status_code=503, detail="No snapshot available yet. Video stream starting...")
    
    return Response(
        content=snapshot,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
        }
    )


@router.get("/status")
async def get_stream_status():
    """Get current video streaming status - reads from memory."""
    return _video_state.get_stats()


@router.post("/snapshot/refresh")
async def refresh_snapshot():
    """
    Request a fresh clean snapshot for Zone Editor.
    The next frame processed will be captured as a clean snapshot.
    """
    _video_state.request_new_snapshot()
    
    # Wait for new snapshot (max 2 seconds)
    for _ in range(20):
        await asyncio.sleep(0.1)
        if _video_state.raw_frame_captured:
            break
    
    return {"status": "refreshed", "message": "New clean snapshot will be captured"}


@router.post("/stop")
async def stop_stream():
    """Stop the video worker thread."""
    stop_video_worker()
    return {"status": "stopped", "message": "Video worker stopped"}


@router.post("/start")
async def start_stream():
    """Start the video worker thread."""
    start_video_worker()
    return {"status": "started", "message": "Video worker started"}


@router.post("/seek")
async def seek_video(data: dict):
    """Seek video to a position (0.0 to 1.0)."""
    global _video_total_frames, _video_capture_lock, _seek_target_frame
    
    position = data.get("position", 0.0)
    position = max(0.0, min(1.0, position))  # Clamp to 0-1

    if not _video_state.running or _video_total_frames <= 0:
        return {"status": "error", "message": "Video not ready"}

    target_frame = int(position * max(_video_total_frames - 1, 0))

    # Queue seek request; display thread applies it before next read.
    with _video_capture_lock:
        _seek_target_frame = target_frame

    print(f"[SEEK] ⏩ Queued seek to {(position * 100):.1f}% (frame {target_frame}/{_video_total_frames})")

    return {
        "status": "success",
        "position": position,
        "frame": target_frame,
        "total_frames": _video_total_frames,
    }


@router.get("/list")
async def list_videos():
    """List available video files."""
    video_dir = settings.data_dir / "videos"
    
    if not video_dir.exists():
        return {"videos": []}
    
    videos = []
    for ext in ["*.mp4", "*.avi", "*.mkv", "*.webm"]:
        for f in video_dir.glob(ext):
            cap = cv2.VideoCapture(str(f))
            videos.append({
                "name": f.name,
                "path": str(f),
                "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
                "fps": cap.get(cv2.CAP_PROP_FPS),
                "frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            })
            cap.release()
    
    return {"videos": videos}


@router.websocket("/ws")
async def websocket_video_stream(websocket: WebSocket):
    """
    WebSocket endpoint for video streaming.
    LIGHTWEIGHT: Just sends frames from memory, no processing here.
    Lazy-starts the video worker if not already running.
    """
    await websocket.accept()
    print("[WS] 📡 Client connected")
    
    # Lazy start: Start worker if not running
    if not _video_state.running:
        start_video_worker()
        # Wait a bit for first frame
        for _ in range(30):  # Max 3 seconds
            await asyncio.sleep(0.1)
            if _video_state.get_frame() is not None:
                break
    
    try:
        while True:
            # Get latest frame from shared state
            frame_bytes = _video_state.get_frame()
            
            if frame_bytes:
                # Encode to Base64 and send
                base64_frame = base64.b64encode(frame_bytes).decode('utf-8')
                await websocket.send_text(base64_frame)
            
            # Target ~20 FPS for streaming
            await asyncio.sleep(0.05)
            
    except WebSocketDisconnect:
        print("[WS] 📴 Client disconnected")
    except Exception as e:
        print(f"[WS] ❌ Error: {e}")


@router.get("/stream")
async def stream_video_mjpeg():
    """
    MJPEG stream endpoint (fallback for non-WebSocket clients).
    Just reads frames from memory.
    """
    async def generate():
        while _video_state.running:
            frame_bytes = _video_state.get_frame()
            if frame_bytes:
                yield (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' +
                    frame_bytes +
                    b'\r\n'
                )
            await asyncio.sleep(0.033)  # ~30 FPS
    
    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
