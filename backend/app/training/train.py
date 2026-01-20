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
        )
    
    return data_yaml


def train_plate_detector(
    epochs: int = 10,
    imgsz: int = 640,
    device: str = "cpu",
    batch: int = 8,
    pretrained_model: str = "yolov8n.pt",
    project_name: str = "plate_detector",
):
    """
    Train YOLOv8 Nano model for license plate detection.
    
    Args:
        epochs: Number of training epochs (default: 10 for POC)
        imgsz: Image size for training (default: 640)
        device: Training device - 'cpu' or 'cuda:0' (default: 'cpu')
