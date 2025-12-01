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
