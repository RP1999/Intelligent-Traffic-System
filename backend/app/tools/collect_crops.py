"""
Smart Data Collector for Sri Lankan Traffic Video
==================================================

Data-Centric Approach: Extract vehicle crops from video for manual annotation
and fine-tuning the license plate detection model.

Smart Features:
1. Uses YOLOv8 tracking (persist=True) to maintain consistent vehicle IDs
2. Anti-duplicate logic: Max 3 crops per vehicle
3. Spacing logic: Save each vehicle only once per 30 frames (1 second)
4. Processes FULL video until the end (not capped at 500 crops)
5. Filters out tiny/blurry crops (< 60x60 pixels)

The Algorithm:
- saved_counts = {track_id: N} - tracks how many crops per vehicle
- last_saved_frame = {track_id: frame_number} - prevents instant duplicates
- If saved_counts[track_id] < 3 AND (now - last_saved_frame[track_id]) >= 30:
    Save the crop and update both dictionaries

Usage:
    python app/tools/collect_crops.py

Output:
    Creates: backend/data/raw_crops/crop_{track_id}_{sequence}.jpg
    
Next Steps:
    1. Manually annotate crops with license plate locations using Roboflow/LabelImg
    2. Convert annotations to YOLO format
    3. Retrain best_plate.pt model on this fine-tuned dataset
"""

import sys
import time
import shutil
from pathlib import Path
from typing import Dict

import cv2

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.config import get_settings
from app.detection.yolo_detector import load_vehicle_model, track_vehicles

settings = get_settings()


# ============================================================================
# CONFIGURATION
# ============================================================================

VIDEO_PATH = Path(settings.data_dir) / "videos" / "SriLankan_Traffic_Video.mp4"
OUTPUT_DIR = Path(settings.data_dir) / "raw_crops"
VEHICLE_CLASS_IDS = [2, 3, 5, 7]  # car, motorcycle/tuk-tuk, bus, truck

# Smart Filtering & Deduplication
MIN_CROP_SIZE = 60  # Ignore crops smaller than 60x60 pixels
MAX_CROPS_PER_VEHICLE = 3  # Save max 3 different angles per vehicle
FRAME_SPACING = 30  # Only save vehicle once every 30 frames (1 second @ 30fps)

# Class names for logging
VEHICLE_NAMES = {
    2: "car",
    3: "motorcycle/tuk-tuk",
    5: "bus",
    7: "truck",
}


# ============================================================================
# SMART CROP COLLECTION WITH DEDUPLICATION
# ============================================================================

def collect_vehicle_crops():
    """
    Main data collection loop with smart deduplication.
    
    Extracts vehicle crops with:
    - Max 3 crops per vehicle track
    - Minimum 30-frame spacing per vehicle (prevents instant duplicates)
    - Processes ENTIRE video until the end
    """
    
    print("=" * 80)
    print("🎬 SMART VEHICLE CROP COLLECTOR - Anti-Duplicate Mode")
    print("=" * 80)
    print()
    
    # Verify paths
    if not VIDEO_PATH.exists():
        print(f"❌ Video not found: {VIDEO_PATH}")
        return
    
    # Clear output directory
    if OUTPUT_DIR.exists():
        print(f"🗑️  Clearing existing crops from {OUTPUT_DIR}...")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"📹 Video Source: {VIDEO_PATH.name}")
    print(f"📁 Output Directory: {OUTPUT_DIR}")
    print(f"⚙️  Smart Collection Settings:")
    print(f"   - Minimum crop size: {MIN_CROP_SIZE}x{MIN_CROP_SIZE} pixels")
    print(f"   - Max crops per vehicle: {MAX_CROPS_PER_VEHICLE}")
    print(f"   - Frame spacing: {FRAME_SPACING} frames (1 second)")
    print()
    
    # Load model with tracking
    print("🔄 Loading YOLOv8n vehicle detection model...")
    vehicle_model = load_vehicle_model(device="cpu")
    print("✅ Model loaded\n")
    
    # Open video
    print("▶️  Opening video...")
    cap = cv2.VideoCapture(str(VIDEO_PATH))
    if not cap.isOpened():
        print(f"❌ Cannot open video: {VIDEO_PATH}")
        return
    
    video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"✅ Video loaded: {total_frames:,} frames @ {video_fps:.1f} FPS")
    print(f"   Duration: ~{total_frames / video_fps / 60:.1f} minutes\n")
    
    # Deduplication tracking
    saved_counts: Dict[int, int] = {}  # track_id -> number of crops saved
    last_saved_frame: Dict[int, int] = {}  # track_id -> last frame number saved
    
    # Statistics
    frame_idx = 0
    crop_count = 0
    total_vehicles_detected = 0
    total_vehicles_skipped = 0
    skip_reasons = {
        "too_small": 0,
        "duplicate_count": 0,
        "frame_spacing": 0,
    }
    class_counts = {cid: 0 for cid in VEHICLE_CLASS_IDS}
    unique_vehicle_ids = set()
    
    print("🔍 Processing video frames...")
    print("-" * 80)
    
    start_time = time.time()
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print()
                print("⏹️  End of video reached!")
                break
            
            # Progress indicator
            if frame_idx % 300 == 0:  # Update every 300 frames
                progress = (frame_idx / total_frames) * 100
                print(f"\rFrame {frame_idx:,}/{total_frames:,} ({progress:.1f}%) | "
                      f"Crops collected: {crop_count} | Unique vehicles: {len(unique_vehicle_ids)}", 
                      end="", flush=True)
            
            # Detect vehicles with tracking
            detections = track_vehicles(vehicle_model, frame, confidence=0.5)
            
            if detections:
                total_vehicles_detected += len(detections)
            
            # Process each detection
            for det in detections:
                track_id = det.track_id
                x1, y1, x2, y2 = det.bbox
                crop_w = x2 - x1
                crop_h = y2 - y1
                
                # Initialize tracking for this vehicle if new
                if track_id not in saved_counts:
                    saved_counts[track_id] = 0
                    last_saved_frame[track_id] = -999
                
                unique_vehicle_ids.add(track_id)
                
                # ===== FILTER 1: Minimum size =====
                if crop_w < MIN_CROP_SIZE or crop_h < MIN_CROP_SIZE:
                    skip_reasons["too_small"] += 1
                    total_vehicles_skipped += 1
                    continue
                
                # ===== FILTER 2: Already saved 3 crops from this vehicle =====
                if saved_counts[track_id] >= MAX_CROPS_PER_VEHICLE:
                    skip_reasons["duplicate_count"] += 1
                    total_vehicles_skipped += 1
                    continue
                
                # ===== FILTER 3: Not enough frames since last save =====
                frames_since_last_save = frame_idx - last_saved_frame[track_id]
                if frames_since_last_save < FRAME_SPACING:
                    skip_reasons["frame_spacing"] += 1
                    total_vehicles_skipped += 1
                    continue
                
                # ===== SAVE THE CROP =====
                vehicle_crop = frame[y1:y2, x1:x2].copy()
                
                # Filename format: crop_<track_id>_<sequence_number>.jpg
                sequence_num = saved_counts[track_id] + 1
                class_name = VEHICLE_NAMES.get(det.class_id, "unknown")
                filename = f"crop_{track_id:04d}_{sequence_num}_{class_name}.jpg"
                filepath = OUTPUT_DIR / filename
                
                # Save crop
                success = cv2.imwrite(str(filepath), vehicle_crop)
                
                if success:
                    # Update tracking dictionaries
                    saved_counts[track_id] += 1
                    last_saved_frame[track_id] = frame_idx
                    
                    # Update statistics
                    crop_count += 1
                    class_counts[det.class_id] = class_counts.get(det.class_id, 0) + 1
            
            frame_idx += 1
    
    except KeyboardInterrupt:
        print()
        print("\n⚠️  Collection interrupted by user (Ctrl+C)")
    
    finally:
        cap.release()
    
    elapsed = time.time() - start_time
    
    # Summary
    print()
    print()
    print("=" * 80)
    print("📊 COLLECTION SUMMARY")
    print("=" * 80)
    print(f"⏱️  Time elapsed: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
    print(f"🎬 Frames processed: {frame_idx:,}")
    print(f"✅ Crops saved: {crop_count}")
    print(f"📍 Total vehicle instances detected: {total_vehicles_detected:,}")
    print(f"⏭️  Total skipped: {total_vehicles_skipped:,}")
    print(f"🎯 Unique vehicle tracks: {len(unique_vehicle_ids)}")
    print()
    
    print("📈 Crops by vehicle class:")
    for class_id in VEHICLE_CLASS_IDS:
        count = class_counts.get(class_id, 0)
        name = VEHICLE_NAMES.get(class_id, "unknown")
        if count > 0:
            percentage = (count * 100 / crop_count) if crop_count > 0 else 0
            print(f"   - {name:20s}: {count:3d} crops ({percentage:5.1f}%)")
    print()
    
    print("🚫 Skip Breakdown:")
    print(f"   - Too small (< {MIN_CROP_SIZE}x{MIN_CROP_SIZE}): {skip_reasons['too_small']:,}")
    print(f"   - Already saved {MAX_CROPS_PER_VEHICLE} crops: {skip_reasons['duplicate_count']:,}")
    print(f"   - Frame spacing < {FRAME_SPACING}f: {skip_reasons['frame_spacing']:,}")
    print()
    
    print(f"💾 Output directory: {OUTPUT_DIR}")
    if crop_count > 0:
        print(f"📂 Total files: {len(list(OUTPUT_DIR.glob('*.jpg')))}")
    print()
    
    if crop_count > 0:
        print("✨ Next steps:")
        print("  1. Review the collected crops in the output directory")
        print("  2. Manually annotate crops with license plate locations")
        print("     → Use Roboflow (roboflow.com) or LabelImg (free, local)")
        print("     → For each image, draw bounding boxes around license plates")
        print("  3. Export annotations in YOLO format (.txt files)")
        print("  4. Organize files: images/ and labels/ subdirectories")
        print("     train/ (70%), val/ (15%), test/ (15%)")
        print("  5. Create data.yaml with dataset configuration")
        print("  6. Retrain model:")
        print("     from ultralytics import YOLO")
        print("     model = YOLO('best_plate.pt')")
        print("     results = model.train(data='data.yaml', epochs=50)")
        print()
    else:
        print("⚠️  No crops were saved. Check video path and detection settings.")
    
    print("=" * 80)


if __name__ == "__main__":
    collect_vehicle_crops()
