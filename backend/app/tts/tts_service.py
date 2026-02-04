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
        # Clear the queue when pausing to stop pending announcements
        while not _tts_queue.empty():
            try:
                _tts_queue.get_nowait()
                _tts_queue.task_done()
            except:
                break
        print("[TTS] ⏸️ TTS paused - no active stream")
    else:
        print("[TTS] ▶️ TTS resumed - stream active")


def is_tts_paused() -> bool:
    """Check if TTS is currently paused."""
    return _tts_paused

# Pre-cached common warning messages (text -> filename)
COMMON_WARNINGS: Dict[str, str] = {
    "parking_warning": "Warning. Vehicle detected in no parking zone.",
    "parking_violation": "Parking violation confirmed. Fine will be issued.",
    "speeding_warning": "Speed violation detected. Please slow down.",
    "general_warning": "Traffic violation detected.",
}


class TTSService:
    """
    Text-to-Speech service with multiple backends.
    
    Primary: edge-tts (natural Microsoft voices, requires internet)
    Fallback: pyttsx3 (offline, uses system TTS)
    """
    
    def __init__(self, voice: str = "en-US-AriaNeural"):
        """
        Initialize TTS service.
        
        Args:
            voice: Edge TTS voice name
        """
        self.voice = voice
        self._ensure_directories()
        self._edge_tts_available = self._check_edge_tts()
        self._pyttsx3_available = self._check_pyttsx3()
        self._pyttsx3_engine = None
        self._pyttsx3_lock = threading.Lock()  # Lock for pyttsx3 engine access
        self._warning_cache: Dict[str, Path] = {}  # text_hash -> filepath
        self._last_play_time = 0  # Track last audio play time
        
        print(f"🔊 TTS Service initialized")
        print(f"   Voice: {self.voice}")
        print(f"   Warnings dir: {WARNINGS_DIR}")
        print(f"   edge-tts: {self._edge_tts_available}")
        print(f"   pyttsx3: {self._pyttsx3_available}")
        
        # Start the TTS worker thread
        self._start_tts_worker()
        
        # Pre-load cached warning files
        self._preload_common_warnings()
    
    def _start_tts_worker(self):
        """Start the background TTS worker thread (singleton pattern)."""
        global _tts_worker_started
        
        with _tts_lock:
            if _tts_worker_started:
                return
            _tts_worker_started = True
        
        def _worker():
            """Process TTS requests from the queue sequentially."""
            global _tts_worker_stop
            
            def _speak_with_pyttsx3(text_to_speak):
                """Speak text using a FRESH pyttsx3 engine each time (fixes Windows SAPI5 hanging)."""
                try:
                    import pyttsx3
                    # Create a NEW engine for each message - this prevents SAPI5 from hanging
                    engine = pyttsx3.init()
                    engine.setProperty('rate', 150)
                    engine.setProperty('volume', 0.9)
                    engine.say(text_to_speak)
                    engine.runAndWait()
                    engine.stop()  # Explicitly stop
                    del engine  # Clean up
                    return True
                except Exception as e:
                    print(f"[TTS Worker] pyttsx3 speak failed: {e}")
                    return False
            
            while not _tts_worker_stop:
                try:
                    # Short timeout for responsive shutdown
                    try:
                        request = _tts_queue.get(timeout=1)
                    except queue.Empty:
                        continue
                    
                    if request is None:  # Shutdown signal
                        break
                    
                    # Skip TTS if paused (no active stream)
                    if _tts_paused:
                        _tts_queue.task_done()
                        continue
                    
                    text, filename, play_immediately, service_ref = request
                    
                    spoken = False
                    filepath = None
                    
                    # Try edge-tts first (in a new event loop for this thread)
                    if service_ref._edge_tts_available and play_immediately:
                        try:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                filepath = loop.run_until_complete(
                                    service_ref.generate_warning_async(text, filename)
                                )
                                # Check both existence AND meaningful size (>100 bytes)
                                if filepath and filepath.exists() and filepath.stat().st_size > 100:
                                    service_ref.play_audio(filepath)
                                    spoken = True
                                    time.sleep(3.0)  # Wait for audio to finish
                                else:
                                    print(f"[TTS Worker] edge-tts produced no audio, falling back to pyttsx3")
                            finally:
                                loop.close()
                        except Exception as edge_err:
                            print(f"[TTS Worker] edge-tts error: {edge_err}, falling back to pyttsx3")
                    
                    # Fallback to pyttsx3 direct speech
                    if not spoken and play_immediately and service_ref._pyttsx3_available:
                        print(f"[TTS Worker] 🔊 Speaking: {text[:45]}...")
                        if _speak_with_pyttsx3(text):
                            print(f"[TTS Worker] ✅ Spoke successfully")
                            spoken = True
                            service_ref._last_play_time = time.time()
                    
                    _tts_queue.task_done()
                    
                except Exception as e:
                    print(f"[TTS Worker] Error: {e}")
                    traceback.print_exc()
        
        worker_thread = threading.Thread(target=_worker, daemon=True, name="TTSWorker")
        worker_thread.start()
        print("   🧵 TTS Worker thread started")
    
    def _preload_common_warnings(self):
        """Load existing warning files into cache for instant playback."""
        if not WARNINGS_DIR.exists():
            return
        
        # Look for common warning files (support multiple formats for cross-platform)
        audio_extensions = ['.mp3', '.aiff', '.wav']
        for warning_key, text in COMMON_WARNINGS.items():
            for ext in audio_extensions:
                filepath = WARNINGS_DIR / f"{warning_key}{ext}"
                if filepath.exists():
                    text_hash = self._hash_text(text)
                    self._warning_cache[text_hash] = filepath
                    self._warning_cache[warning_key] = filepath
                    print(f"   📦 Cached: {filepath.name}")
                    break  # Use first found format
    
    def _hash_text(self, text: str) -> str:
        """Generate a hash for caching text-based lookups."""
        return hashlib.md5(text.lower().strip().encode()).hexdigest()[:16]
    
    def play_cached_warning(self, warning_key: str) -> bool:
        """
        Play a pre-generated cached warning instantly (non-blocking).
        
        Args:
            warning_key: One of 'parking_warning', 'parking_violation', 
                        'speeding_warning', 'general_warning'
        
        Returns:
            True if played successfully
        """
        # First check direct key lookup
        if warning_key in self._warning_cache:
            return self.play_audio(self._warning_cache[warning_key])
        
        # Try to find the file with various extensions (cross-platform support)
        audio_extensions = ['.mp3', '.aiff', '.wav']
        for ext in audio_extensions:
            filepath = WARNINGS_DIR / f"{warning_key}{ext}"
            if filepath.exists():
                self._warning_cache[warning_key] = filepath
                return self.play_audio(filepath)
        
        # Try alternative naming patterns
        alt_patterns = [
            f"{warning_key}_test",
            f"warning_{warning_key}",
        ]
        for pattern in alt_patterns:
            for ext in audio_extensions:
                alt_path = WARNINGS_DIR / f"{pattern}{ext}"
                if alt_path.exists():
                    self._warning_cache[warning_key] = alt_path
                    return self.play_audio(alt_path)
        
        print(f"[TTS] ⚠️ No cached audio for: {warning_key}")
        return False
    
    def play_any_warning(self) -> bool:
        """Play any available warning file (for testing)."""
        if WARNINGS_DIR.exists():
            # Search for any audio file (cross-platform)
            for ext in ['*.mp3', '*.aiff', '*.wav']:
                files = list(WARNINGS_DIR.glob(ext))
                if files:
                    return self.play_audio(files[0])
        return False
    
    def _ensure_directories(self):
        """Create necessary directories."""
        if not WARNINGS_DIR.exists():
            WARNINGS_DIR.mkdir(parents=True, exist_ok=True)
            print(f"📁 Created warnings directory: {WARNINGS_DIR}")
    
    def _check_edge_tts(self) -> bool:
        """Check if edge-tts is installed."""
        try:
            import edge_tts
            return True
        except ImportError:
            return False
    
    def _check_pyttsx3(self) -> bool:
        """Check if pyttsx3 is installed."""
        try:
            import pyttsx3
            return True
        except ImportError:
            return False
    
    def _get_pyttsx3_engine(self):
        """Get or create pyttsx3 engine (lazy initialization)."""
        if self._pyttsx3_engine is None and self._pyttsx3_available:
            try:
                import pyttsx3
                self._pyttsx3_engine = pyttsx3.init()
                self._pyttsx3_engine.setProperty('rate', 150)
                self._pyttsx3_engine.setProperty('volume', 0.9)
            except Exception as e:
                print(f"[TTS] Could not init pyttsx3: {e}")
        return self._pyttsx3_engine
    
    async def generate_warning_async(
        self, 
        text: str, 
        filename: Optional[str] = None
    ) -> Optional[Path]:
        """
        Generate a warning audio file asynchronously.
        
        Args:
            text: The text to convert to speech
            filename: Optional filename (without extension). 
                      If None, generates timestamp-based name.
        
        Returns:
            Path to the generated MP3 file, or None if failed
        """
        if not self._edge_tts_available:
            print(f"[TTS] ⚠️ edge-tts not available. Would say: {text}")
            return None
