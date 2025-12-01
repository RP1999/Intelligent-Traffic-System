 """
Intelligent Traffic Management System - Configuration
Environment variables and application settings
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""
    
    # --- Application Info ---
    app_name: str = "Intelligent Traffic Management System"
    app_version: str = "0.1.0"
    debug: bool = True
    
    # --- Paths ---
    base_dir: Path = Path(__file__).resolve().parent.parent.parent
    data_dir: Path = base_dir / "data"
    videos_dir: Path = data_dir / "videos"
    plates_dir: Path = data_dir / "plates"
    models_dir: Path = base_dir / "models"
    db_path: Path = data_dir / "its.db"
    
    # --- YOLOv8 Models ---
    vehicle_model: str = "yolov8n.pt"  # Pretrained for vehicle detection + tracking
    plate_model: str = "best_plate.pt"  # Custom-trained for license plate detection
