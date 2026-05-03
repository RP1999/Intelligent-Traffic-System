"""
Intelligent Traffic Management System - Video Ingestion Module
Download YouTube videos and stream frames to simulate live CCTV feed
"""

import os
import sys
import time
import subprocess
from pathlib import Path
from typing import Generator, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

import cv2
import numpy as np

# Add parent to path for imports when running as script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.config import get_settings

settings = get_settings()


@dataclass
class Frame:
    """Container for a video frame with metadata."""
    frame_id: int
    timestamp: float
    image: np.ndarray
    width: int
    height: int
    fps: float


class VideoIngestionError(Exception):
    """Custom exception for video ingestion errors."""
    pass


def download_youtube_video(
    url: str,
    output_path: Optional[Path] = None,
    max_resolution: int = 720,
    quiet: bool = False
) -> Path:
    """
    Download a YouTube video using yt-dlp.
    
    Args:
        url: YouTube video URL
        output_path: Optional output file path (auto-generated if None)
        max_resolution: Maximum video height (default 720p for CPU performance)
        quiet: Suppress yt-dlp output
    
    Returns:
        Path to the downloaded video file
    """
    if output_path is None:
        # Generate filename from timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = settings.videos_dir / f"traffic_{timestamp}.mp4"
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # yt-dlp command with format selection for best quality up to max_resolution
    cmd = [
        "yt-dlp",
        "-f", f"bestvideo[height<={max_resolution}][ext=mp4]+bestaudio[ext=m4a]/best[height<={max_resolution}][ext=mp4]/best",
        "--merge-output-format", "mp4",
        "-o", str(output_path),
        "--no-playlist",
    ]
    
    if quiet:
        cmd.extend(["--quiet", "--no-warnings"])
    
    cmd.append(url)
    
    print(f"📥 Downloading video from: {url}")
    print(f"📁 Output: {output_path}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=quiet)
        print(f"✅ Download complete: {output_path}")
        return output_path
    except subprocess.CalledProcessError as e:
        raise VideoIngestionError(f"Failed to download video: {e}")
    except FileNotFoundError:
        raise VideoIngestionError(
            "yt-dlp not found. Install it with: pip install yt-dlp"
        )


def get_video_info(video_path: Path) -> dict:
    """Get video metadata using OpenCV."""
    cap = cv2.VideoCapture(str(video_path))
    
    if not cap.isOpened():
        raise VideoIngestionError(f"Cannot open video: {video_path}")
    
    info = {
        "path": str(video_path),
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "fps": cap.get(cv2.CAP_PROP_FPS),
        "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        "duration_seconds": int(cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS)),
    }
    
    cap.release()
    return info


def frame_generator(
    video_source: str,
    target_fps: Optional[float] = None,
    target_resolution: Optional[Tuple[int, int]] = None,
    loop: bool = True,
    simulate_realtime: bool = True,
) -> Generator[Frame, None, None]:
    """
    Generate frames from a video source (file path or URL).
    
    Args:
        video_source: Path to video file or URL
        target_fps: Target FPS (None = use source FPS)
        target_resolution: Target (width, height) for resizing
        loop: Whether to loop the video when it ends
        simulate_realtime: Add delays to simulate real-time playback
    
    Yields:
        Frame objects with image data and metadata
    """
    cap = cv2.VideoCapture(video_source)
    
    if not cap.isOpened():
        raise VideoIngestionError(f"Cannot open video source: {video_source}")
    
    source_fps = cap.get(cv2.CAP_PROP_FPS)
    if source_fps <= 0:
        source_fps = settings.default_fps
    
    fps = target_fps if target_fps else source_fps
    frame_delay = 1.0 / fps if simulate_realtime else 0
    
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    if target_resolution:
        width, height = target_resolution
    
    frame_id = 0
    start_time = time.time()
    
    print(f"🎬 Starting video stream: {video_source}")
    print(f"   Resolution: {width}x{height} @ {fps:.1f} FPS")
    print(f"   Simulate realtime: {simulate_realtime}")
    
    try:
        while True:
            ret, image = cap.read()
            
            if not ret:
                if loop:
                    # Reset to beginning
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    print("🔄 Video looped")
                    continue
                else:
                    print("📼 Video ended")
                    break
            
            # Resize if needed
            if target_resolution:
                image = cv2.resize(image, target_resolution)
            
            timestamp = time.time() - start_time
            
            yield Frame(
                frame_id=frame_id,
                timestamp=timestamp,
                image=image,
                width=width,
                height=height,
                fps=fps,
            )
            
            frame_id += 1
            
            # Simulate real-time playback
            if simulate_realtime and frame_delay > 0:
                time.sleep(frame_delay)
                
    finally:
        cap.release()
        print(f"🛑 Stream ended. Total frames: {frame_id}")


def save_sample_frames(
    video_source: str,
    output_dir: Path,
    num_frames: int = 10,
    interval: int = 30,
) -> list:
    """
    Extract and save sample frames from a video for testing.
    
    Args:
        video_source: Path to video file
        output_dir: Directory to save frames
        num_frames: Number of frames to extract
        interval: Frame interval between extractions
    
    Returns:
        List of saved frame paths
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    cap = cv2.VideoCapture(video_source)
    if not cap.isOpened():
        raise VideoIngestionError(f"Cannot open video: {video_source}")
    
    saved_paths = []
    frame_idx = 0
    saved_count = 0
    
    while saved_count < num_frames:
        ret, frame = cap.read()
        if not ret:
            break
        
        if frame_idx % interval == 0:
            output_path = output_dir / f"frame_{frame_idx:06d}.jpg"
            cv2.imwrite(str(output_path), frame)
            saved_paths.append(output_path)
            saved_count += 1
            print(f"💾 Saved: {output_path}")
        
        frame_idx += 1
    
    cap.release()
    print(f"✅ Saved {len(saved_paths)} sample frames")
    return saved_paths


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    """Command-line interface for video ingestion."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Video Ingestion Module - Download and stream traffic videos"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Download command
    download_parser = subparsers.add_parser("download", help="Download a YouTube video")
    download_parser.add_argument("url", help="YouTube video URL")
    download_parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output file path"
    )
    download_parser.add_argument(
        "-r", "--resolution",
        type=int,
        default=720,
        help="Maximum resolution (default: 720)"
    )
    
    # Info command
    info_parser = subparsers.add_parser("info", help="Get video information")
    info_parser.add_argument("video", type=Path, help="Video file path")
    
    # Stream command (test frame generator)
    stream_parser = subparsers.add_parser("stream", help="Test frame streaming")
    stream_parser.add_argument("video", help="Video file path or URL")
    stream_parser.add_argument(
        "-n", "--num-frames",
        type=int,
        default=100,
        help="Number of frames to process"
    )
    stream_parser.add_argument(
        "--no-display",
        action="store_true",
        help="Don't show video window"
    )
    
    # Extract command
    extract_parser = subparsers.add_parser("extract", help="Extract sample frames")
    extract_parser.add_argument("video", type=Path, help="Video file path")
    extract_parser.add_argument(
        "-o", "--output",
        type=Path,
        default=settings.videos_dir / "samples",
        help="Output directory"
    )
    extract_parser.add_argument(
        "-n", "--num-frames",
        type=int,
        default=10,
        help="Number of frames to extract"
    )
    
    args = parser.parse_args()
    
    if args.command == "download":
        output = download_youtube_video(
            args.url,
            output_path=args.output,
            max_resolution=args.resolution,
        )
        info = get_video_info(output)
        print(f"\n📊 Video Info:")
        for key, value in info.items():
            print(f"   {key}: {value}")
    
    elif args.command == "info":
        info = get_video_info(args.video)
        print(f"📊 Video Info:")
        for key, value in info.items():
            print(f"   {key}: {value}")
    
    elif args.command == "stream":
        gen = frame_generator(
            args.video,
            target_resolution=settings.input_resolution,
            loop=False,
            simulate_realtime=True,
        )
        
        for i, frame in enumerate(gen):
            if i >= args.num_frames:
                break
            
            print(f"Frame {frame.frame_id}: {frame.width}x{frame.height} @ {frame.timestamp:.2f}s")
            
            if not args.no_display:
                cv2.imshow("Video Stream", frame.image)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        
        cv2.destroyAllWindows()
    
    elif args.command == "extract":
        save_sample_frames(
            str(args.video),
            args.output,
            num_frames=args.num_frames,
        )
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
