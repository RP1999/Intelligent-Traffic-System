"""
Intelligent Traffic Management System - API Routers
"""

from app.routers.video import router as video_router
from app.routers.parking import router as parking_router

__all__ = ["video_router", "parking_router"]
