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
