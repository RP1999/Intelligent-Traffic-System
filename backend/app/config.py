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
    
    # --- Detection Settings ---
    detection_confidence: float = 0.5
    tracking_confidence: float = 0.4
    frame_skip: int = 3  # Process every Nth frame for CPU optimization (higher = smoother)
    input_resolution: tuple = (1280, 720)  # Downscale input to this resolution
    
    # --- Parking Violation Settings ---
    # Reduced defaults for demo sensitivity
    parking_duration_threshold: int = 10  # Seconds before parking violation (demo)
    parking_speed_threshold: float = 2.0  # km/h - below this is considered stopped
    parking_min_overlap: float = 0.3  # Min bbox overlap to consider vehicle in zone
    parking_snapshot_dir: Path = data_dir / "snapshots"
    
    # --- Scoring Settings ---
    initial_driver_score: int = 100
    score_reset_hour: int = 0  # Midnight reset
    
    # --- Fine Calculation ---
    base_fine_amount: float = 500.0  # Base fine in currency
    duration_multiplier: float = 0.1  # Additional fine per minute
    traffic_impact_multiplier: float = 0.2  # Additional fine based on congestion
    
    # --- SSE Settings ---
    sse_retry_timeout: int = 3000  # milliseconds
    
    # --- Video Ingestion ---
    default_fps: int = 30
    frame_buffer_size: int = 100
    
