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
        batch: Batch size (default: 8, reduced for CPU training)
        pretrained_model: Base model to use (default: 'yolov8n.pt')
        project_name: Name for the training run
    
    Returns:
        Path to the best trained model weights
    """
    print("=" * 60)
    print("🚗 INTELLIGENT TRAFFIC MANAGEMENT SYSTEM")
    print("📋 License Plate Detection Model Training")
    print("=" * 60)
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Get data path
    data_yaml = get_data_yaml_path()
    print(f"📁 Dataset: {data_yaml}")
    print(f"🔧 Base Model: {pretrained_model}")
    print(f"🖥️  Device: {device}")
    print(f"📊 Epochs: {epochs}")
    print(f"📐 Image Size: {imgsz}")
    print(f"📦 Batch Size: {batch}")
    print()
    
    # Load pretrained model
    print("⏳ Loading pretrained YOLOv8 Nano model...")
    model = YOLO(pretrained_model)
    print("✅ Model loaded successfully!")
    print()
    
    # Configure output directory
    output_dir = PROJECT_ROOT / "runs" / "detect"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Start training
    print("🚀 Starting training...")
    print("-" * 60)
    
    results = model.train(
        data=str(data_yaml),
        epochs=epochs,
        imgsz=imgsz,
        device=device,
        batch=batch,
        project=str(output_dir),
        name=project_name,
        exist_ok=True,  # Overwrite existing run
