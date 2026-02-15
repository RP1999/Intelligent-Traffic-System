"""
Intelligent Traffic Management System - FastAPI Application
Main entry point with health checks, SSE endpoints, and API routing
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from app.config import get_settings
from app.routers import video_router, parking_router
from app.routers.scoring import router as scoring_router
from app.routers.signal import router as signal_router
from app.routers.junction import router as junction_router
from app.routers.auth import router as auth_router
from app.routers.driver import router as driver_router
from app.routers.admin import router as admin_router
from app.routers.community import router as community_router
from app.routers.config import router as config_router
from app.routers.settings import router as settings_router
from app.routers.risk import router as risk_router
from app.routers.iot_junction import router as iot_junction_router
from app.db.database import init_db

settings = get_settings()

# --- Setup Logging to File ---
# Log file path - clears on server restart
LOG_DIR = Path(settings.data_dir) / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "server.log"

# Clear log file on startup (overwrite mode)
with open(LOG_FILE, "w") as f:
    f.write(f"=== ITMS Server Log Started at {datetime.now().isoformat()} ===\n\n")

# Configure logging to write to both file and console
class TeeStream:
    """Tee stream that writes to both console and file."""
    def __init__(self, file_path: Path, original_stream):
        self.file = open(file_path, "a", encoding="utf-8", buffering=1)
        self.original = original_stream
    
    def write(self, data):
        self.original.write(data)
        try:
            self.file.write(data)
            self.file.flush()
        except Exception:
            pass  # Ignore file write errors
    
    def flush(self):
        self.original.flush()
        try:
            self.file.flush()
        except Exception:
            pass

# Redirect stdout and stderr to also write to log file
sys.stdout = TeeStream(LOG_FILE, sys.__stdout__)
sys.stderr = TeeStream(LOG_FILE, sys.__stderr__)

# Configure uvicorn/fastapi loggers to also write to log file
file_handler = logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Add file handler to uvicorn and fastapi loggers
for logger_name in ['uvicorn', 'uvicorn.error', 'uvicorn.access', 'fastapi']:
    logger = logging.getLogger(logger_name)
    logger.addHandler(file_handler)
    logger.setLevel(logging.DEBUG)

print(f"📝 Server logs: {LOG_FILE}")

# --- Event Queue for SSE ---
# Simple in-memory queue for broadcasting events to connected clients
event_queue: asyncio.Queue = asyncio.Queue()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - startup and shutdown events."""
    # Startup
    print(f"🚦 {settings.app_name} v{settings.app_version} starting...")
    print(f"📁 Data directory: {settings.data_dir}")
    print(f"🎯 Vehicle model: {settings.vehicle_model}")
    print(f"🔖 Plate model: {settings.plate_model}")
    # Initialize database tables (retry on Firestore 429 quota errors)
    for _attempt in range(3):
        try:
            await init_db()
            print("✅ Database initialized")
            # Seed default admin user if Firestore is empty
            from app.routers.auth import ensure_tables_exist
            await ensure_tables_exist()

            # Initialize dynamic fine calculator with saved settings
            from app.routers.settings import initialize_fine_calculator
            await initialize_fine_calculator()
            break  # success
        except Exception as e:
            if "429" in str(e) and _attempt < 2:
                wait = 2 ** (_attempt + 1)  # 2s, 4s
                print(f"⚠️ Firestore quota hit, retrying in {wait}s...")
                await asyncio.sleep(wait)
            else:
                print(f"⚠️ Database init failed: {e}")

    # Pre-load YOLO models, EasyOCR, TTS, and scoring engine at startup
    # so they're ready before the first video starts
    import threading
    def _preload_models():
        try:
            from app.detection.yolo_detector import (
                load_vehicle_model, load_plate_model, get_ocr_service,
                get_scoring_engine, get_tts_service as get_detector_tts,
                get_lane_weaving_service, get_behavior_service,
                load_stop_line_config,
            )
            print("🔄 Pre-loading YOLO vehicle model...")
            load_vehicle_model("cpu")
            print("✅ Vehicle model pre-loaded")

            print("🔄 Pre-loading plate detection model...")
            load_plate_model("cpu")
            print("✅ Plate model pre-loaded")

            print("🔄 Pre-loading EasyOCR...")
            get_ocr_service()
            # Also directly initialize the OCR reader itself
            from app.services.ocr_service import get_ocr_reader
            get_ocr_reader()
            print("✅ EasyOCR pre-loaded")

            print("🔄 Pre-loading scoring engine...")
            get_scoring_engine()
            print("✅ Scoring engine pre-loaded")

            print("🔄 Pre-loading TTS service...")
            get_detector_tts()
            print("✅ TTS service pre-loaded")

            print("🔄 Pre-loading lane weaving service (Member 2)...")
            get_lane_weaving_service()
            print("✅ Lane weaving service pre-loaded")

            print("🔄 Pre-loading behavior detection service (Member 4)...")
            get_behavior_service()
            print("✅ Behavior detection service pre-loaded")
            
            print("🔄 Loading stop line configuration...")
            load_stop_line_config()
            print("✅ Stop line config loaded")

            print("🎉 All models and services pre-loaded successfully!")
        except Exception as e:
            print(f"⚠️ Model pre-loading error (non-fatal): {e}")

    preload_thread = threading.Thread(target=_preload_models, daemon=True)
    preload_thread.start()
    # Block until models are ready so the first video connection
    # immediately gets annotated frames (zones, boxes, etc.).
    preload_thread.join()

    # Start AWS DynamoDB -> Firestore IoT junction sync loop.
    try:
        from app.services.iot_junction_service import get_iot_junction_service
        await get_iot_junction_service().start_background_sync()
    except Exception as e:
        print(f"⚠️ IoT junction sync startup skipped: {e}")

    yield
    # Shutdown
    print("🛑 Shutting down...")
    try:
        from app.services.iot_junction_service import get_iot_junction_service
        await get_iot_junction_service().stop_background_sync()
    except Exception:
        pass
    # Clean up TTS audio files
    try:
        from app.tts import get_tts_service
        tts = get_tts_service()
        if tts:
            tts.cleanup_all_warnings()
    except:
        pass


# --- FastAPI App ---
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-powered traffic management with violation detection, driver scoring, and adaptive signals",
    lifespan=lifespan,
)

# --- CORS Middleware (allow Flutter web app) ---
# Allow requests from both localhost and 127.0.0.1 variants
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# --- Global Exception Handler (ensures CORS headers on 500 errors) ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )

# --- Include Routers ---
app.include_router(video_router)
app.include_router(parking_router)
app.include_router(scoring_router)
app.include_router(signal_router)
app.include_router(junction_router)  # Member 2 & 4: Junction Safety, Behavior, Risk
app.include_router(auth_router)       # Authentication: JWT login/register
app.include_router(driver_router)     # Driver mobile app endpoints
app.include_router(admin_router)      # Admin dashboard endpoints
app.include_router(community_router)  # Public community endpoints
app.include_router(config_router)     # Admin zone configuration & audit logs
app.include_router(settings_router)   # Admin system settings
app.include_router(risk_router)       # Member 4: Accident Risk Prediction
app.include_router(iot_junction_router)  # IoT prototype integration module

# --- Static Files (for simulation UI and videos) ---
from pathlib import Path
static_dir = Path(__file__).parent / "wokwi"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Mount videos directory for serving annotated videos
videos_dir = Path(settings.data_dir) / "videos"
if videos_dir.exists():
    app.mount("/videos", StaticFiles(directory=str(videos_dir)), name="videos")

# Mount snapshots directory for serving violation evidence images
snapshots_dir = Path(settings.data_dir) / "snapshots"
snapshots_dir.mkdir(parents=True, exist_ok=True)
app.mount("/evidence", StaticFiles(directory=str(snapshots_dir)), name="evidence")
app.mount("/snapshots", StaticFiles(directory=str(snapshots_dir)), name="snapshots")


@app.get("/simulation", tags=["Simulation"])
async def simulation_page():
    """Serve the traffic signal simulation page."""
