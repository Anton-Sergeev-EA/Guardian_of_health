"""
FocusGuardian - Main Application Orchestrator.
"""

import sys
import time
import json
import sqlite3
import threading
import queue
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
import numpy as np
import cv2

# Import C++ engine.
from src.core import video_engine

# Analytics.
from src.analytics.posture_analyzer import PostureAnalyzer, PostureMetrics
from src.analytics.eye_tracker import EyeTracker, EyeMetrics
from src.analytics.fatigue_detector import FatigueDetector, FatigueMetrics

# Voice.
from src.voice.voice_commander import VoiceCommander
from src.voice.commands import VoiceCommand

# MediaPipe.
try:
    import mediapipe as mp
    HAS_MEDIAPIPE = True
except ImportError:
    HAS_MEDIAPIPE = False
    print("[ERROR] MediaPipe not installed!")


class FocusGuardian:
    """Main application orchestrator."""
    
    def __init__(
        self,
        cam_id: int = 0,
        width: int = 640,
        height: int = 480,
        enable_voice: bool = True,
        enable_db: bool = True
    ):
        print("=" * 70)
        print("  🧘 FOCUS GUARDIAN v2.2 - AI Health Assistant")
        print("  C++ Engine + Threaded MediaPipe + Voice + Web Interface")
        print("=" * 70)
        
        # Video engine (C++).
        self.engine = video_engine.VideoEngine(cam_id, width, height)
        self.engine.start()
        print(f"[INIT] Video engine started: {width}x{height}")
        
        # ML components.
        self.mp_pose = None
        self.mp_face = None
        self.pose = None
        self.face_mesh = None
        self._init_mediapipe()
        
        # Analytics.
        self.posture_analyzer = PostureAnalyzer()
        self.eye_tracker = EyeTracker()
        self.fatigue_detector = FatigueDetector()
        
        # State.
        self.running = True
        self.paused = False
        self.last_frame = None
        self.frame_counter = 0
        self.inference_skip = 2
        self.face_detected = False
        
        # Threading Queues (Decoupling Capture and Processing)
        self.frame_queue = queue.Queue(maxsize=3)  # Keeping size small to ensure lowest latency
        self.db_queue = queue.Queue()
        
        # Latest results.
        self.latest_posture: Optional[PostureMetrics] = None
        self.latest_eyes: Optional[EyeMetrics] = None
        self.latest_fatigue: Optional[FatigueMetrics] = None
        
        # Session data.
        self.session_start = datetime.now()
        self.session_id = self.session_start.strftime('%Y%m%d_%H%M%S')
        self.session_data = {
            'total_blinks': 0,
            'slouch_events': 0,
            'critical_slouch_events': 0,
            'closed_eyes_events': 0,
            'total_frames': 0,
            'face_present_frames': 0,
            'breaks_taken': 0,
            'productivity_score': 1.0
        }
        
        # Database.
        self.db_path = None
        self.conn = None
        if enable_db:
            self._init_database()
        
        # Voice.
        self.voice = None
        if enable_voice:
            self._init_voice()
        
        # Notification cooldown.
        self.last_notification_time = 0
        self.notification_cooldown = 60
        
        # FPS tracking.
        self.fps = 0
        self.fps_counter = 0
        self.fps_timer = time.time()
        
        # Start Thread Pool
        self._start_threads()
        
        print("[INIT] FocusGuardian ready")
    
    def _init_mediapipe(self):
        """Initialize MediaPipe models."""
        if not HAS_MEDIAPIPE:
            print("[ML] ⚠️ MediaPipe not available")
            return
        
        print("[ML] Loading models...")
        self.mp_pose = mp.solutions.pose
        self.mp_face = mp.solutions.face_mesh
        
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=0,  # 0=lite (highly optimized for laptop CPUs)
            enable_segmentation=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        self.face_mesh = self.mp_face.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        print("[ML] Models loaded")
    
    def _init_database(self):
        """Initialize SQLite database."""
        db_dir = Path.home() / '.focus_guardian'
        db_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = db_dir / 'logs.db'
        
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS posture_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                spine_angle REAL,
                neck_angle REAL,
                shoulder_angle REAL,
                is_slouching INTEGER,
                severity TEXT,
                blink_rate INTEGER,
                fatigue_level TEXT,
                session_id TEXT
            )
        ''')
        self.conn.commit()
        print(f"[DB] Logging to: {self.db_path}")
    
    def _init_voice(self):
        """Initialize voice commander."""
        try:
            self.voice = VoiceCommander(language='ru')
            if self.voice.is_available():
                self.voice.start(self._handle_voice_command)
                print("[VOICE] 🎤 Voice commands active")
            else:
                print("[VOICE] ⚠️ Voice commands unavailable")
                self.voice = None
        except Exception as e:
            print(f"[VOICE] Init error: {e}")
            self.voice = None

    def _start_threads(self):
        """Spawns dedicated background worker threads."""
        # Frame Processing worker thread.
        self.processing_thread = threading.Thread(target=self.processing_loop, daemon=True)
        self.processing_thread.start()

        # Database async writer thread.
        self.db_writer_thread = threading.Thread(target=self.db_writer_loop, daemon=True)
        self.db_writer_thread.start()
        
        # Frame Grabber thread
        self.capture_thread = threading.Thread(target=self.capture_loop, daemon=True)
        self.capture_thread.start()
    
    def capture_loop(self):
        """Dedicated high-speed thread for grabbing camera frames."""
        print("[LOOP] Starting capture...")
        
        while self.running:
            if self.paused:
                time.sleep(0.1)
                continue

            loop_start = time.perf_counter()
            
            try:
                frame = self.engine.get_frame()
            except Exception as e:
                print(f"[LOOP] Capture error: {e}")
                time.sleep(0.01)
                continue
            
            if frame is None or frame.size == 0:
                time.sleep(0.001)
                continue
            
            self.last_frame = np.asarray(frame)
            self.session_data['total_frames'] += 1
            
            # FPS tracking
            self.fps_counter += 1
            if time.time() - self.fps_timer >= 1.0:
                self.fps = self.fps_counter
                self.fps_counter = 0
                self.fps_timer = time.time()
            
            # Safe push to processing queue without blocking the capture loop
            if self.frame_queue.full():
                try:
                    self.frame_queue.get_nowait()  # Drop oldest frame to maintain realtime state
                except queue.Empty:
                    pass
            
            self.frame_queue.put(self.last_frame)
            
            # Precise CPU control (Capping at ~60 FPS)
            elapsed = (time.perf_counter() - loop_start) * 1000
            if elapsed < 15:
                time.sleep((15 - elapsed) / 1000)
        
        print("[LOOP] Capture stopped")

    def processing_loop(self):
        """Dedicated background thread for executing ML inference (MediaPipe)."""
        print("[THREAD] Processing loop started")
        while self.running:
            try:
                # Wait for a fresh frame from the queue (blocks until available)
                frame = self.frame_queue.get(timeout=1.0)
                self.frame_counter += 1
                
                # Perform inference according to skip settings
                if self.frame_counter % self.inference_skip == 0:
                    self._process_frame(frame)
                    
                self.frame_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[THREAD] Processing loop error: {e}")
        print("[THREAD] Processing loop stopped")
    
    def _process_frame(self, frame: np.ndarray):
        """Process frame with MediaPipe"""
        if not HAS_MEDIAPIPE:
            return
        
        try:
            # Convert to BGR for MediaPipe
            bgr_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            # Run inference
            pose_results = self.pose.process(bgr_frame)
            face_results = self.face_mesh.process(bgr_frame)
            
            # Analyze posture
            if pose_results.pose_landmarks:
                self.face_detected = True
                self.session_data['face_present_frames'] += 1
                
                posture = self.posture_analyzer.analyze(pose_results.pose_landmarks)
                self.latest_posture = posture
                
                if posture.is_slouching:
                    self.session_data['slouch_events'] += 1
                    if posture.severity == 'critical':
                        self.session_data['critical_slouch_events'] += 1
                        self._send_notification(
                            "⚠️ Critical slouching!",
                            f"Spine angle: {posture.spine_angle:.1f}°",
                            is_critical=True
                        )
                    else:
                        self._send_notification(
                            "🧘 Fix your posture!",
                            f"Angle: {posture.spine_angle:.1f}°"
                        )
            else:
                self.face_detected = False
            
            # Analyze eyes
            if face_results.multi_face_landmarks:
                face = face_results.multi_face_landmarks[0]
                eyes = self.eye_tracker.analyze(face)
                self.latest_eyes = eyes
                self.session_data['total_blinks'] = eyes.blink_count
                
                if eyes.is_eyes_closed:
                    self.session_data['closed_eyes_events'] += 1
                    self._send_notification(
                        "😴 Eyes closed!",
                        "You look tired. Take a break.",
                        is_critical=True
                    )
            
            # Fatigue analysis
            fatigue = self.fatigue_detector.update(self.latest_eyes, self.latest_posture)
            self.latest_fatigue = fatigue
            self.session_data['productivity_score'] = fatigue.productivity_score
            
            if fatigue.break_recommended:
                self._send_notification(
                    "☕ Time for a break!",
                    f"Reason: {fatigue.break_reason}",
                    is_critical=True
                )
                self.session_data['breaks_taken'] += 1
                
            # Async database logging every 10 seconds (approx 300 frames)
            if self.frame_counter % (10 * 30) == 0:
                self._queue_db_log()
                
        except Exception as e:
            print(f"[PROCESS] Error: {e}")
    
    def _send_notification(self, title: str, message: str, is_critical: bool = False):
        """Send notification with cooldown"""
        current_time = time.time()
        if not is_critical and current_time - self.last_notification_time < self.notification_cooldown:
            return
        
        self.last_notification_time = current_time
        
        # Console
        print(f"\n[NOTIFY] {title}")
        print(f"         {message}")
        
        # System notification
        try:
            from plyer import notification
            notification.notify(
                title=title,
                message=message,
                timeout=10 if is_critical else 5
            )
        except ImportError:
            pass
    
    def _queue_db_log(self):
        """Saves telemetry variables and places them safely in the DB queue."""
        if not self.conn:
            return
        
        log_payload = {
            'timestamp': datetime.now().isoformat(),
            'spine_angle': self.latest_posture.spine_angle if self.latest_posture else 0.0,
            'neck_angle': self.latest_posture.neck_angle if self.latest_posture else 0.0,
            'shoulder_angle': self.latest_posture.shoulder_angle if self.latest_posture else 0.0,
            'is_slouching': 1 if self.latest_posture and self.latest_posture.is_slouching else 0,
            'severity': self.latest_posture.severity if self.latest_posture else 'unknown',
            'blink_rate': self.latest_eyes.blink_count if self.latest_eyes else 0,
            'fatigue_level': self.latest_fatigue.fatigue_level if self.latest_fatigue else 'low',
            'session_id': self.session_id
        }
        self.db_queue.put(log_payload)

    def db_writer_loop(self):
        """Dedicated writer thread to prevent SQLite I/O bottlenecks on processing streams."""
        print("[THREAD] Async DB Writer started")
        while self.running:
            try:
                payload = self.db_queue.get(timeout=2.0)
                
                self.conn.execute('''
                    INSERT INTO posture_logs 
                    (timestamp, spine_angle, neck_angle, shoulder_angle, 
                     is_slouching, severity, blink_rate, fatigue_level, session_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    payload['timestamp'],
                    payload['spine_angle'],
                    payload['neck_angle'],
                    payload['shoulder_angle'],
                    payload['is_slouching'],
                    payload['severity'],
                    payload['blink_rate'],
                    payload['fatigue_level'],
                    payload['session_id']
                ))
                self.conn.commit()
                self.db_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[DB] Async write error: {e}")
        print("[THREAD] Async DB Writer stopped")
    
    def _handle_voice_command(self, cmd: VoiceCommand, text: str):
        """Handle voice commands"""
        if cmd == VoiceCommand.STATUS:
            status = self.get_status()
            print(f"[VOICE] Status: {json.dumps(status, indent=2)}")
            
        elif cmd == VoiceCommand.PAUSE:
            self.pause_monitoring()
            print("[VOICE] ⏸️ Paused")
            
        elif cmd == VoiceCommand.RESUME:
            self.resume_monitoring()
            print("[VOICE] ▶️ Resumed")
            
        elif cmd == VoiceCommand.REPORT:
            self._generate_report()
            
        elif cmd == VoiceCommand.RESET:
            self.reset_session()
            print("[VOICE] 🔄 Session reset")
            
        elif cmd == VoiceCommand.QUIT:
            print("[VOICE] 👋 Goodbye!")
            self.stop()
            sys.exit(0)
            
        elif cmd == VoiceCommand.HELP:
            help_text = self.voice.registry.get_help_text('ru')
            print(help_text)
            
        elif cmd == VoiceCommand.BREAK:
            print("[VOICE] ☕ Take a 5-minute break!")
            
        elif cmd == VoiceCommand.POSTURE:
            if self.latest_posture:
                angle = self.latest_posture.spine_angle
                status = "good" if not self.latest_posture.is_slouching else "bad"
                print(f"[VOICE] Posture: {status} (angle: {angle:.1f}°)")
                
        elif cmd == VoiceCommand.BLINKS:
            if self.latest_eyes:
                print(f"[VOICE] Blinks: {self.latest_eyes.blink_count}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status"""
        return {
            'fps': self.fps,
            'face_detected': self.face_detected,
            'posture': {
                'angle': self.latest_posture.spine_angle if self.latest_posture else 0,
                'neck_angle': self.latest_posture.neck_angle if self.latest_posture else 0,
                'is_slouching': self.latest_posture.is_slouching if self.latest_posture else False,
                'severity': self.latest_posture.severity if self.latest_posture else 'unknown'
            },
            'eyes': {
                'ear': self.latest_eyes.avg_ear if self.latest_eyes else 0,
                'blinks': self.latest_eyes.blink_count if self.latest_eyes else 0,
                'is_closed': self.latest_eyes.is_eyes_closed if self.latest_eyes else False
            },
            'fatigue': {
                'level': self.latest_fatigue.fatigue_level if self.latest_fatigue else 'low',
                'score': self.latest_fatigue.productivity_score if self.latest_fatigue else 1.0
            },
            'session': {
                'id': self.session_id,
                'duration': (datetime.now() - self.session_start).seconds // 60,
                'slouches': self.session_data['slouch_events'],
                'critical_slouches': self.session_data['critical_slouch_events'],
                'blinks': self.session_data['total_blinks'],
                'breaks': self.session_data['breaks_taken']
            },
            'session_start_ts': self.session_start.timestamp(),
            'timestamp': time.time()
        }
    
    def pause_monitoring(self):
        """Pause monitoring safely without spawning/terminating system threads."""
        self.paused = True
        print("[PAUSE] Monitoring paused")
    
    def resume_monitoring(self):
        """Resume monitoring instantly."""
        self.paused = False
        print("[RESUME] Monitoring resumed")
    
    def reset_session(self):
        """Reset session data."""
        self.session_start = datetime.now()
        self.session_id = self.session_start.strftime('%Y%m%d_%H%M%S')
        self.session_data = {k: 0 for k in self.session_data}
        self.session_data['total_frames'] = 0
        self.session_data['breaks_taken'] = 0
        self.session_data['productivity_score'] = 1.0
        self.eye_tracker.reset()
        self.posture_analyzer.reset()
        self.fatigue_detector.reset()
        print("[RESET] Session reset")
    
    def _generate_report(self):
        """Generate and print session report."""
        duration = (datetime.now() - self.session_start).seconds // 60
        print("\n" + "=" * 70)
        print("  📊 SESSION REPORT.")
        print("=" * 70)
        print(f"  Session ID: {self.session_id}")
        print(f"  Duration: {duration} minutes")
        print(f"  Face detection: {self.session_data['face_present_frames'] / max(1, self.session_data['total_frames']) * 100:.1f}%")
        print(f"  Total blinks: {self.session_data['total_blinks']}")
        print(f"  Slouch events: {self.session_data['slouch_events']}")
        print(f"  Critical slouches: {self.session_data['critical_slouch_events']}")
        print(f"  Eyes closed events: {self.session_data['closed_eyes_events']}")
        print(f"  Breaks taken: {self.session_data['breaks_taken']}")
        print(f"  Productivity score: {self.session_data['productivity_score']:.2f}")
        print("=" * 70 + "\n")
    
    def stop(self):
        """Stop everything."""
        self.running = False
        
        # Log final data.
        if self.conn:
            self._queue_db_log()
            # Wait briefly for writer to commit remaining items
            time.sleep(0.5)
            self.conn.close()
        
        # Stop voice.
        if self.voice:
            self.voice.stop()
        
        # Close MediaPipe.
        if self.pose:
            self.pose.close()
        if self.face_mesh:
            self.face_mesh.close()
        
        # Stop video engine.
        self.engine.stop()
        
        print("[SHUTDOWN] FocusGuardian stopped.")
