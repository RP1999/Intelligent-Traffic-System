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
                                if filepath and filepath.exists():
                                    # Play the edge-tts generated file
                                    service_ref.play_audio(filepath)
                                    spoken = True
                                    time.sleep(3.0)  # Wait for audio to finish
                            finally:
                                loop.close()
                        except Exception:
                            pass  # Silently fail, will use pyttsx3
                    
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
        
        try:
            import edge_tts
            
            # Generate filename if not provided
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                filename = f"warning_{timestamp}"
            
            # Ensure .mp3 extension
            if not filename.endswith(".mp3"):
                filename = f"{filename}.mp3"
            
            filepath = WARNINGS_DIR / filename
            
            # Generate audio using subprocesses method for reliability
            communicate = edge_tts.Communicate(text, self.voice)
            
            # Use iterate and write manually for more reliability
            with open(str(filepath), "wb") as f:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        f.write(chunk["data"])
            
            # Check if file was actually written
            if filepath.exists() and filepath.stat().st_size > 0:
                print(f"[TTS] ✅ Generated: {filepath.name} ({filepath.stat().st_size} bytes)")
                return filepath
            else:
                print(f"[TTS] ⚠️ File empty or not created")
                return None
            
        except Exception as e:
            # Silently fail - pyttsx3 fallback will handle it
            return None
    
    def generate_warning(
        self, 
        text: str, 
        filename: Optional[str] = None,
        play_immediately: bool = True
    ) -> Optional[Path]:
        """
        Generate a warning audio file (NON-BLOCKING, QUEUE-BASED).
        
        Adds the TTS request to a queue processed by a dedicated worker thread.
        This ensures sequential processing and prevents thread-safety issues.
        
        Args:
            text: The text to convert to speech
            filename: Optional filename (without extension)
            play_immediately: Whether to play the audio after generation
        
        Returns:
            None (runs async via queue)
        """
        # Add request to the TTS queue (non-blocking)
        try:
            _tts_queue.put_nowait((text, filename, play_immediately, self))
            print(f"[TTS] 🎤 Queued: {text[:50]}...")
        except queue.Full:
            print(f"[TTS] ⚠️ Queue full, dropping: {text[:30]}...")
        
        return None  # Returns immediately, audio processed by worker
    
    def _generate_with_pyttsx3(self, text: str, filename: Optional[str] = None) -> Optional[Path]:
        """Generate audio file using pyttsx3 (cross-platform)."""
        try:
            engine = self._get_pyttsx3_engine()
            if engine is None:
                return None
            
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                filename = f"warning_{timestamp}"
            
            # Remove any existing extension
            if filename.endswith(('.mp3', '.wav', '.aiff')):
                filename = filename.rsplit('.', 1)[0]
            
            # Use platform-appropriate extension
            # macOS pyttsx3 saves to AIFF, Windows to MP3
            if sys.platform == "darwin":
                filename = f"{filename}.aiff"
            else:
                filename = f"{filename}.mp3"
            
            filepath = WARNINGS_DIR / filename
            
            # pyttsx3 can save to file
            engine.save_to_file(text, str(filepath))
            engine.runAndWait()
            
            if filepath.exists() and filepath.stat().st_size > 0:
                print(f"[TTS] ✅ Generated (pyttsx3): {filepath.name}")
                return filepath
            
        except Exception as e:
            print(f"[TTS] pyttsx3 file generation failed: {e}")
        
        return None
    
    def _speak_pyttsx3_direct(self, text: str):
        """Speak directly using pyttsx3 without saving file."""
        try:
            engine = self._get_pyttsx3_engine()
            if engine:
                # Run in a thread to not block
                def _speak():
                    engine.say(text)
                    engine.runAndWait()
                
                thread = threading.Thread(target=_speak, daemon=True)
                thread.start()
                print(f"[TTS] 🔊 Speaking (pyttsx3): {text[:50]}...")
        except Exception as e:
            print(f"[TTS] pyttsx3 direct speak failed: {e}")
    
    def play_audio(self, filepath: Path) -> bool:
        """
        Play an audio file in the background.
        
        Platform-specific implementation:
        - Windows: Uses PowerShell MediaPlayer (auto-closes after playback)
        - macOS: Uses 'afplay' (built-in, supports MP3/WAV/etc.)
        - Linux: Uses 'mpg123' or 'aplay'
        
        Args:
            filepath: Path to the audio file
        
        Returns:
            True if playback started successfully
        """
        if not filepath or not filepath.exists():
            print(f"[TTS] ⚠️ Audio file not found: {filepath}")
            return False
        
        try:
            filepath_str = str(filepath.absolute())
            
            if sys.platform == "win32":
                # Windows: Use PowerShell MediaPlayer which plays and exits cleanly
                # This avoids the media player window staying open
                ps_script = f'''
                Add-Type -AssemblyName presentationCore
                $player = New-Object System.Windows.Media.MediaPlayer
                $player.Open([uri]"{filepath_str}")
                $player.Play()
                Start-Sleep -Milliseconds 100
                while ($player.Position -lt $player.NaturalDuration.TimeSpan) {{
                    Start-Sleep -Milliseconds 200
                }}
                $player.Close()
                '''
                CREATE_NO_WINDOW = 0x08000000
                subprocess.Popen(
                    ['powershell', '-WindowStyle', 'Hidden', '-Command', ps_script],
                    creationflags=CREATE_NO_WINDOW,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            elif sys.platform == "darwin":
                # macOS: Use afplay (built-in macOS audio player)
                # afplay supports MP3, WAV, AAC, AIFF, etc.
                # It blocks until playback finishes, which is fine in our worker thread
                subprocess.Popen(
                    ['afplay', filepath_str],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                # Linux: Try multiple players in order of preference
                players = [
                    ['mpg123', '-q', filepath_str],  # For MP3
                    ['aplay', filepath_str],          # For WAV
                    ['ffplay', '-nodisp', '-autoexit', filepath_str],  # FFmpeg player
                ]
                played = False
                for player_cmd in players:
                    try:
                        subprocess.Popen(
                            player_cmd,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )
                        played = True
                        break
                    except FileNotFoundError:
                        continue
                
                if not played:
                    print(f"[TTS] ⚠️ No audio player found on Linux. Install mpg123, aplay, or ffplay.")
                    return False
            
            print(f"[TTS] 🔊 Playing: {filepath.name}")
            return True
            
        except Exception as e:
            print(f"[TTS] ❌ Error playing audio: {e}")
            return False
    
    def speak(self, text: str, play: bool = True) -> Optional[Path]:
        """
        Convenience method to generate and optionally play a warning.
        
        Args:
            text: Text to speak
            play: Whether to play immediately
        
        Returns:
            Path to audio file
        """
        return self.generate_warning(text, play_immediately=play)
    
    def get_warning_count(self) -> int:
        """Get the number of warning files generated."""
        if WARNINGS_DIR.exists():
            return len(list(WARNINGS_DIR.glob("*.mp3")))
        return 0
    
    def cleanup_all_warnings(self):
        """
        Remove ALL generated warning files (called on shutdown).
        Also signals TTS worker to stop.
        """
        global _tts_worker_stop
        
        # Signal worker to stop
        _tts_worker_stop = True
        try:
            _tts_queue.put_nowait(None)  # Send shutdown signal
        except:
            pass
        
        if not WARNINGS_DIR.exists():
            return
        
        count = 0
        for ext in ['*.mp3', '*.aiff', '*.wav']:
            for f in WARNINGS_DIR.glob(ext):
                try:
                    f.unlink()
                    count += 1
                except:
                    pass
        
        if count > 0:
            print(f"[TTS] 🧹 Cleaned up {count} audio files")
    
    def cleanup_old_warnings(self, max_files: int = 100):
        """
        Remove old warning files to prevent disk buildup.
        
        Args:
            max_files: Maximum number of files to keep
        """
        if not WARNINGS_DIR.exists():
            return
        
        files = sorted(WARNINGS_DIR.glob("*.mp3"), key=lambda f: f.stat().st_mtime)
        
        if len(files) > max_files:
            to_delete = files[:-max_files]
            for f in to_delete:
                f.unlink()
            print(f"[TTS] 🧹 Cleaned up {len(to_delete)} old warning files")


# Global TTS service instance
_tts_service: Optional[TTSService] = None


def get_tts_service() -> TTSService:
    """Get or create the global TTS service instance."""
    global _tts_service
    if _tts_service is None:
        _tts_service = TTSService()
    return _tts_service


# =============================================================================
# Test Block
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("🔊 TTS Service Test")
    print("=" * 60)
    
    # Initialize service
    tts = TTSService()
    
    # Test 1: Generate a test warning
    print("\n📝 Test 1: Generating test audio...")
    filepath = tts.generate_warning(
        "Testing system audio. If you hear this, the text to speech module is working correctly.",
        filename="test_audio",
        play_immediately=True
    )
    
    if filepath:
        print(f"✅ Test file generated: {filepath}")
        print(f"   File size: {filepath.stat().st_size} bytes")
    else:
        print("❌ Failed to generate test file")
    
    # Test 2: Generate a parking warning
    print("\n📝 Test 2: Generating parking warning...")
    filepath2 = tts.generate_warning(
        "Vehicle WP ABC 1234, please move immediately. You are in a no parking zone.",
        filename="parking_warning_test",
        play_immediately=False  # Don't play, just generate
    )
    
    if filepath2:
        print(f"✅ Parking warning generated: {filepath2}")
    
    # Test 3: Generate a speeding warning
    print("\n📝 Test 3: Generating speeding warning...")
    filepath3 = tts.generate_warning(
        "Attention! Vehicle exceeding speed limit. Fine has been recorded.",
        filename="speeding_warning_test",
        play_immediately=False
    )
    
    if filepath3:
        print(f"✅ Speeding warning generated: {filepath3}")
    
    # Summary
    print("\n" + "=" * 60)
    print(f"📊 Summary:")
    print(f"   Warnings directory: {WARNINGS_DIR}")
    print(f"   Total warning files: {tts.get_warning_count()}")
    print("=" * 60)
    
    # List all files
    print("\n📁 Files in warnings directory:")
    for f in WARNINGS_DIR.glob("*.mp3"):
        print(f"   - {f.name} ({f.stat().st_size} bytes)")
