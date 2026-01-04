"""
Intelligent Traffic Management System - Video Streaming Router
PROFESSIONAL WORKER THREAD ARCHITECTURE

Architecture:
=============
- Background Worker Thread: Runs YOLO detection continuously
- Thread-Safe VideoState: Stores latest frame, snapshot, vehicle count
- Lightweight Endpoints: Just serve data from memory (no processing)

Benefits:
- API endpoints (zones, logs) respond instantly
- Zone Editor snapshot always available
- Traffic controller gets real-time vehicle counts
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
import aiosqlite
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

# Database path
DB_PATH = settings.data_dir.parent / "backend" / "traffic.db"


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

# Worker thread reference
_worker_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()

# WebSocket clients
_ws_clients: set = set()
_ws_lock = asyncio.Lock()


# ============================================================================
# ZONE LOADING
# ============================================================================

def load_zones_from_db_sync():
    """Synchronous zone loading for worker thread."""
    import sqlite3
    
    try:
        if not DB_PATH.exists():
            print(f"[ZONES] DB not found at {DB_PATH}")
            return
        
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM parking_zones WHERE active = 1 ORDER BY id")
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            print("[ZONES] No active zones in DB, disabling violation detection")
            set_parking_zones([])
            return
        
        zones = []
        for row in rows:
            coords = json.loads(row["coordinates"])
            polygon = [(int(p[0]), int(p[1])) for p in coords]
            
            zone_type = row["zone_type"]
            if zone_type in ("red", "no_parking"):
                color = (0, 0, 255)
            elif zone_type in ("yellow", "loading"):
                color = (0, 255, 255)
            elif zone_type in ("blue", "handicap"):
                color = (255, 0, 0)
            else:
                color = (0, 0, 255)
            
            zones.append({
                "id": f"zone_{row['id']}",
                "name": row["label"] or f"Zone {row['id']}",
                "polygon": polygon,
                "color": color,
            })
        
        set_parking_zones(zones)
        print(f"[ZONES] ✅ Loaded {len(zones)} zones from DB")
        
    except Exception as e:
        print(f"[ZONES] ❌ Error loading zones: {e}")


# ============================================================================
# BACKGROUND WORKER THREAD
# ============================================================================

def video_worker_loop():
    """
    Background worker thread that runs YOLO detection continuously.
    Updates VideoState with latest frames - endpoints just read from memory.
    """
    global _video_state
    
    print("[WORKER] 🚀 Video worker thread starting...")
    
    # Get traffic controller for signal updates
    try:
        from app.fuzzy.traffic_controller import get_four_way_controller
        traffic_controller = get_four_way_controller()
        print("[WORKER] ✅ Traffic controller connected")
    except Exception as e:
        print(f"[WORKER] ⚠️ Traffic controller not available: {e}")
        traffic_controller = None
    
    # Load zones from database
    load_zones_from_db_sync()
    
    # Find video source
    video_path = str(settings.data_dir / "videos" / "SriLankan_Traffic_Video.mp4")
    if not Path(video_path).exists():
        videos_dir = Path(settings.data_dir) / "videos"
        if videos_dir.exists():
            video_files = list(videos_dir.glob("*.mp4"))
            if video_files:
                video_path = str(video_files[0])
            else:
                print("[WORKER] ❌ No video files found!")
                return
    
    print(f"[WORKER] 📹 Opening video: {video_path}")
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)
    
    if not cap.isOpened():
        print(f"[WORKER] ❌ Cannot open video: {video_path}")
        return
    
    # Load YOLO models
    print("[WORKER] 🔄 Loading YOLO models...")
    vehicle_model = load_vehicle_model("cpu")
    plate_model = load_plate_model("cpu")
    print("[WORKER] ✅ Models loaded")
    
    # Update state
    _video_state.running = True
    _video_state.video_source = video_path
    _video_state.start_time = time.time()
    
    # Enable TTS
    set_tts_paused(False)
    
    frame_idx = 0
    frame_skip = 3
    is_first_frame = True
    log_interval = 100
    
    print("[WORKER] ▶️ Video processing loop started")
    
    try:
        while not _stop_event.is_set():
            loop_start = time.time()
            
            # Skip frames for performance
            if frame_skip > 1:
                current_pos = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
                cap.set(cv2.CAP_PROP_POS_FRAMES, current_pos + frame_skip - 1)
            
            ret, frame = cap.read()
            if not ret:
                # Loop video
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                frame_idx = 0
                continue
            
            frame_idx += frame_skip
            
            # Capture clean snapshot BEFORE drawing any boxes (for Zone Editor)
            # IMPORTANT: Capture at FULL resolution to match zone coordinates
            raw_snapshot_bytes = None
            if not _video_state.raw_frame_captured:
                # Encode clean frame at FULL resolution (no scaling)
                # Zone coordinates are stored in original resolution, so snapshot must match
                _, raw_buffer = cv2.imencode('.jpg', frame.copy(), [cv2.IMWRITE_JPEG_QUALITY, 90])
                raw_snapshot_bytes = raw_buffer.tobytes()
            
            # Run YOLO detection
            result = detect_and_track(
                vehicle_model=vehicle_model,
                frame=frame,
                frame_id=frame_idx,
                confidence=0.5,
                plate_model=plate_model,
                run_plate_detection=True,
            )
            
            vehicle_count = len(result.detections)
            plate_count = len(result.plate_boxes)
            
            # CRITICAL: Update traffic controller with real vehicle count
            if traffic_controller:
                traffic_controller.update_north_count(vehicle_count)
                traffic_controller.auto_tick()
            
            # Draw detections and info
            frame = draw_detections(frame, result)
            frame = draw_frame_info(frame, result)
            
            # Resize for streaming
            scale = 0.75
            frame = cv2.resize(frame, None, fx=scale, fy=scale)
            
            # Encode to JPEG
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            frame_bytes = buffer.tobytes()
            
            # Update thread-safe state
            _video_state.update_frame(
                frame_bytes=frame_bytes,
                vehicle_count=vehicle_count,
                plates=plate_count,
                raw_snapshot=raw_snapshot_bytes
            )
            
            # Log progress periodically
            if frame_idx % log_interval == 0:
                print(f"[WORKER] Frame {frame_idx}: {vehicle_count} vehicles, {plate_count} plates")
            
            # CRITICAL: Sleep to yield CPU to main API thread
            elapsed = time.time() - loop_start
            sleep_time = max(0.01, 0.033 - elapsed)  # Target ~30 FPS, min 10ms yield
            time.sleep(sleep_time)
            
    except Exception as e:
        print(f"[WORKER] ❌ Error in worker loop: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        cap.release()
        _video_state.running = False
        set_tts_paused(True)
        print("[WORKER] 🛑 Video worker thread stopped")


def start_video_worker():
    """Start the background video worker thread."""
    global _worker_thread, _stop_event
    
    if _worker_thread and _worker_thread.is_alive():
        print("[WORKER] Already running")
        return
    
    # Re-enable traffic controller auto-tick before starting
    try:
        from app.fuzzy.traffic_controller import get_four_way_controller
        controller = get_four_way_controller()
        controller.auto_tick_enabled = True
        print("[WORKER] ✅ Traffic controller auto-tick enabled")
    except Exception as e:
        print(f"[WORKER] ⚠️ Could not enable traffic controller: {e}")
    
    _stop_event.clear()
    _worker_thread = threading.Thread(target=video_worker_loop, daemon=True)
    _worker_thread.start()
    print("[WORKER] ✅ Worker thread started")


def stop_video_worker():
    """Stop the background video worker thread and all associated services."""
    global _worker_thread, _stop_event
    
    _stop_event.set()
    if _worker_thread:
        _worker_thread.join(timeout=5.0)
    _video_state.reset()
    
    # CRITICAL: Stop traffic controller auto-tick to prevent continued updates
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
        tts.cleanup_old_warnings(max_files=20)  # Keep only 20 recent files
        print("[WORKER] 🧹 TTS cache cleaned")
    except Exception as e:
        print(f"[WORKER] ⚠️ Could not clean TTS: {e}")
    
    print("[WORKER] ⏹️ Worker thread stopped")


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
