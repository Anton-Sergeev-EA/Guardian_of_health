"""
Voice Commander - Offline voice recognition using Vosk with thread-safe queueing.
"""

import os
import json
import time
import threading
import queue
from pathlib import Path
from typing import Optional, Callable, Dict, Any, Tuple

from commands import CommandRegistry, VoiceCommand

# Vosk imports with safe fallback.
try:
    from vosk import Model, KaldiRecognizer
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False

# PyAudio imports with safe fallback.
try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False


class VoiceCommander:
    """
    Offline voice command recognition engine powered by Vosk.
    
    Features:
    - Real-time background thread speech recognition.
    - Thread-safe queueing to prevent Qt GUI thread crashes.
    - Automatic fallback for missing models and audio hardware.
    - Adjustable cooldown timer for hotword detection.
    """
    
    def __init__(
        self,
        language: str = 'ru',
        model_path: Optional[Path] = None,
        cooldown: float = 1.5
    ):
        self.language = language
        self.cooldown = cooldown
        
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        
        # Thread-safe queue to pass commands safely to PyQt6 or other thread loops.
        self.command_queue: queue.Queue = queue.Queue()
        self.callback: Optional[Callable[[VoiceCommand, str], None]] = None
        
        self.registry = CommandRegistry()
        self.last_command_time = 0.0
        
        # Resolve model path dynamically.
        if model_path is None:
            model_path = self._get_default_model_path(language)
        
        self.model_path = model_path
        self.model: Optional[Model] = None
        self.recognizer: Optional[KaldiRecognizer] = None
        
        self.audio: Optional[pyaudio.PyAudio] = None
        self.stream: Optional[pyaudio.Stream] = None
        
        # Safe defaults for voice recording.
        self.sample_rate = 16000
        self.chunk_size = 4000
        
        # Initialize modules if environment allows.
        if VOSK_AVAILABLE and PYAUDIO_AVAILABLE:
            self._init_vosk()
            self._init_audio()
        else:
            self._print_warnings()
    
    def _get_default_model_path(self, language: str) -> Path:
        """Get the default path configuration for the Vosk model."""
        base_dir = Path(__file__).parent / 'models'
        
        model_names = {
            'ru': 'vosk-model-small-ru-0.22',
            'en': 'vosk-model-small-en-us-0.15'
        }
        
        model_name = model_names.get(language, 'vosk-model-small-ru-0.22')
        return base_dir / model_name
    
    def _init_vosk(self):
        """Load the Vosk acoustic model into memory."""
        if not self.model_path.exists():
            print(f"[VOICE] Model directory not found: {self.model_path}")
            print("[VOICE] Please download a model from https://alphacephei.com/vosk/models")
            return
        
        try:
            self.model = Model(str(self.model_path))
            self.recognizer = KaldiRecognizer(self.model, self.sample_rate)
            self.recognizer.SetWords(True)
            print(f"[VOICE] Model loaded successfully: {self.model_path.name}")
        except Exception as e:
            print(f"[VOICE] Failed to initialize Vosk engine: {e}")
            self.model = None
            self.recognizer = None
    
    def _init_audio(self):
        """Initialize PyAudio components and scan hardware devices."""
        try:
            self.audio = pyaudio.PyAudio()
            device_count = self.audio.get_device_count()
            
            input_device_index = None
            for i in range(device_count):
                device_info = self.audio.get_device_info_by_index(i)
                if device_info.get('maxInputChannels', 0) > 0:
                    input_device_index = i
                    print(f"[VOICE] Input device selected: {device_info.get('name')}")
                    break
            
            if input_device_index is None:
                print("[VOICE] Error: No valid microphone found on this system.")
                self.audio.terminate()
                self.audio = None
                
        except Exception as e:
            print(f"[VOICE] Audio hardware init failure: {e}")
            self.audio = None
    
    def _print_warnings(self):
        """Log driver/dependency warning flags to stdout."""
        if not VOSK_AVAILABLE:
            print("[VOICE] WARNING: Vosk package is not installed. Voice controls will be disabled.")
            print("        Install command: pip install vosk")
        if not PYAUDIO_AVAILABLE:
            print("[VOICE] WARNING: PyAudio package is not installed. Voice controls will be disabled.")
            print("        Install command: pip install pyaudio")
    
    def start(self, callback: Callable[[VoiceCommand, str], None]) -> bool:
        """
        Start recording thread and voice command capture.
        
        :param callback: Thread-safe callback invoked when a command matches.
        """
        if not self.is_available():
            return False
        
        if self.is_running:
            return True
        
        self.callback = callback
        self.is_running = True
        
        # Drain the old queue to clear out outdated commands.
        while not self.command_queue.empty():
            try:
                self.command_queue.get_nowait()
            except queue.Empty:
                break
        
        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.thread.start()
        
        print("[VOICE] Voice Commander started. Now listening...")
        return True
    
    def stop(self):
        """Safely terminate recording stream and join working threads."""
        if not self.is_running:
            return
            
        self.is_running = False
        
        # Safely shut down PyAudio stream.
        if self.stream is not None:
            try:
                if self.stream.is_active():
                    self.stream.stop_stream()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
        
        # Terminate PyAudio instance.
        if self.audio is not None:
            try:
                self.audio.terminate()
            except Exception:
                pass
            self.audio = None
            
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
            self.thread = None
        
        print("[VOICE] Voice Commander stopped.")
    
    def _listen_loop(self):
        """Continuous stream reading loop executed inside background thread."""
        if not self.audio or not self.recognizer:
            self.is_running = False
            return
        
        try:
            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size,
                stream_callback=self._audio_callback
            )
            
            self.stream.start_stream()
            
            # Keep thread alive while recording is running.
            while self.is_running and self.stream.is_active():
                # Process queued commands inside loop safely.
                try:
                    cmd, text = self.command_queue.get(timeout=0.1)
                    if self.callback:
                        self.callback(cmd, text)
                except queue.Empty:
                    continue
                
        except Exception as e:
            print(f"[VOICE] Runtime recording error encountered: {e}")
            self.is_running = False
    
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Low-level PyAudio stream callback (non-blocking)."""
        if not self.is_running:
            return (None, pyaudio.paComplete)
        
        if status == pyaudio.paInputOverflow:
            return (in_data, pyaudio.paContinue)
        
        try:
            # Send current raw chunk data to Kaldi engine.
            if self.recognizer.AcceptWaveform(in_data):
                result = json.loads(self.recognizer.Result())
                text = result.get('text', '').strip()
                if text:
                    self._process_text(text)
            else:
                # Can be used to print partial recognized words if needed.
                pass
        except Exception:
            pass
        
        return (in_data, pyaudio.paContinue)
    
    def _process_text(self, text: str):
        """Analyze recognized speech and queue verified commands."""
        current_time = time.time()
        
        # Prevent rapid-fire double triggers.
        if current_time - self.last_command_time < self.cooldown:
            return
        
        cmd, confidence = self.registry.parse_command(text)
        
        if cmd and confidence >= 0.3:
            self.last_command_time = current_time
            print(f"[VOICE] Match: {cmd.value} (confidence: {confidence:.2f}) from speech input: '{text}'")
            
            # Push payload to the queue for thread-safe main thread consumption.
            self.command_queue.put((cmd, text))
            
    def is_available(self) -> bool:
        """Verify if all dependencies are loaded and operational."""
        return VOSK_AVAILABLE and PYAUDIO_AVAILABLE and self.model is not None
    
    def get_status(self) -> Dict[str, Any]:
        """Fetch general status configuration of the Voice Commander module."""
        return {
            'available': self.is_available(),
            'running': self.is_running,
            'language': self.language,
            'model_loaded': self.model is not None
        }
    