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
