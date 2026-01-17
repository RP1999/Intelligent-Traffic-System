"""
Intelligent Traffic Management System - YOLOv8 License Plate Model Training
This script trains a YOLOv8 Nano model on the Sri Lankan license plate dataset.

Research Component for University Grading
==========================================
This module demonstrates custom object detection model training using:
- Transfer learning from YOLOv8n pretrained weights
- Custom dataset preparation with Roboflow
- CPU-based training for accessibility

Usage:
    python -m app.training.train

Output:
    Trained model saved to: runs/detect/plate_detector/weights/best.pt
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ultralytics import YOLO


def get_data_yaml_path() -> Path:
    """Get the absolute path to the data.yaml file."""
    # Dataset is located at: <project_root>/data/plates/data.yaml
    data_yaml = PROJECT_ROOT / "data" / "plates" / "data.yaml"
    
    if not data_yaml.exists():
        raise FileNotFoundError(
            f"data.yaml not found at: {data_yaml}\n"
            "Please ensure the dataset is downloaded to data/plates/"
