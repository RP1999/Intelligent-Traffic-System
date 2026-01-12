"""
Intelligent Traffic Management System - Text-to-Speech Service
Uses edge-tts for natural voices with pyttsx3 as offline fallback.

Fixed: Thread-safe TTS with queue-based processing to prevent concurrent access issues.
"""

import os
import sys
import asyncio
import subprocess
import traceback
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict
import threading
import hashlib
import queue
import time

# Determine paths
TTS_DIR = Path(__file__).parent
WARNINGS_DIR = TTS_DIR / "warnings"

# TTS Request Queue for thread-safe processing
_tts_queue: queue.Queue = queue.Queue()
_tts_worker_started = False
_tts_worker_stop = False  # Flag to signal worker to stop
_tts_paused = False  # Flag to pause TTS when no active stream
_tts_lock = threading.Lock()


def set_tts_paused(paused: bool):
    """Pause or resume TTS playback globally."""
    global _tts_paused
    _tts_paused = paused
    if paused:
