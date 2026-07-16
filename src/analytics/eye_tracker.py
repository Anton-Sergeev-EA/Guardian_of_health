"""
Eye Tracker - Detects blinks and eye fatigue using EAR.
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Optional, Tuple
from collections import deque


@dataclass
class EyeMetrics:
    """Metrics for eye tracking."""
    left_ear: float = 0.0
    right_ear: float = 0.0
    avg_ear: float = 0.0
    is_blinking: bool = False
    blink_count: int = 0
    is_eyes_closed: bool = False
    closed_frames: int = 0
    fatigue_score: float = 0.0


class EyeTracker:
    """
    Tracks eyes using MediaPipe Face Mesh landmarks.
    
    EAR (Eye Aspect Ratio) calculation (using standard 6-point landmarks):
    EAR = (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)
    """
    
    # Corrected sequential MediaPipe Face Mesh indices for standard 6-point EAR.
    # Elements are ordered as: [p1, p2, p3, p4, p5, p6].
    LEFT_EYE_INDICES = [33, 160, 158, 133, 153, 144]
    RIGHT_EYE_INDICES = [362, 385, 387, 263, 373, 380]
    
    def __init__(
        self,
        ear_threshold: float = 0.22,
        smoothing_window: int = 3,
        fps: int = 30
    ):
        self.ear_threshold = ear_threshold
        self.smoothing_window = smoothing_window
        self.fps = fps
        
        # Deque of active blink timestamps inside a rolling monitoring window.
        self.blink_timestamps: deque = deque()
        self.ear_history: deque = deque(maxlen=smoothing_window)
        
        self.blink_counter = 0
        self.was_closed = False
        self.closed_frames = 0
        self.frame_counter = 0
        
    def analyze(self, face_landmarks, image_size: Optional[Tuple[int, int]] = None) -> EyeMetrics:
        """
        Analyze eye metrics from MediaPipe face landmarks.
        
        :param face_landmarks: MediaPipe Face Mesh landmarks.
        :param image_size: Optional tuple of (width, height) to prevent aspect ratio distortion.
        """
        if face_landmarks is None:
            return EyeMetrics(fatigue_score=0.0)
        
        self.frame_counter += 1
        
        try:
            landmarks = face_landmarks.landmark
            w, h = image_size if image_size else (1.0, 1.0)
            
            # Extract coordinates and correct aspect ratio scale.
            left_eye = [np.array([landmarks[i].x * w, landmarks[i].y * h]) 
                        for i in self.LEFT_EYE_INDICES]
            right_eye = [np.array([landmarks[i].x * w, landmarks[i].y * h]) 
                         for i in self.RIGHT_EYE_INDICES]
            
            # Compute raw EAR.
            left_ear = self._calculate_ear(left_eye)
            right_ear = self._calculate_ear(right_eye)
            avg_ear = (left_ear + right_ear) / 2.0
            
            # Smooth ear calculation to prevent noise flicker.
            self.ear_history.append(avg_ear)
            smoothed_ear = np.mean(self.ear_history)
            
            # Determine eye closure state.
            is_closed = smoothed_ear < self.ear_threshold
            
            # State-edge detection for counting discrete blinks.
            if is_closed and not self.was_closed:
                self.blink_counter += 1
                self.blink_timestamps.append(self.frame_counter)
            self.was_closed = is_closed
            
            # Calculate consecutive closed frames.
            if is_closed:
                self.closed_frames += 1
            else:
                self.closed_frames = 0
                
            # Clear blinks that are older than 10 seconds to maintain a sliding window.
            cutoff_frame = self.frame_counter - (self.fps * 10)
            while self.blink_timestamps and self.blink_timestamps[0] < cutoff_frame:
                self.blink_timestamps.popleft()
                
            # Dynamic Fatigue Calculation.
            # 1. Micro-sleep penalty (grows exponentially if eyes remain closed for > 500ms).
            microsleep_factor = min(1.0, self.closed_frames / (self.fps * 1.5))
            
            # 2. Blink Rate frequency penalty.
            # Normal humans blink ~15-20 times/min. If 0 blinks or > 8 blinks in 10s, indicate fatigue.
            blinks_in_window = len(self.blink_timestamps)
            if blinks_in_window == 0:
                blink_anomaly = 0.5  # Dry eyes, staring intensely, or micro-sleep.
            elif blinks_in_window > 8:
                blink_anomaly = 0.4  # High frequency fluttering / struggling to stay awake.
            else:
                blink_anomaly = 0.0
                
            fatigue_score = min(1.0, microsleep_factor + blink_anomaly)
            
            return EyeMetrics(
                left_ear=float(left_ear),
                right_ear=float(right_ear),
                avg_ear=float(smoothed_ear),
                is_blinking=is_closed,
                blink_count=self.blink_counter,
                is_eyes_closed=self.closed_frames > (self.fps * 0.5),  # Eyes closed longer than 500ms
                closed_frames=self.closed_frames,
                fatigue_score=float(fatigue_score)
            )
            
        except (IndexError, AttributeError, ValueError):
            return EyeMetrics(fatigue_score=0.0)
    
    @staticmethod
    def _calculate_ear(eye_points: List[np.ndarray]) -> float:
        """
        Calculate Eye Aspect Ratio for a 6-point eye contour.
        Points must be ordered sequentially: [p1, p2, p3, p4, p5, p6]
        """
        if len(eye_points) < 6:
            return 0.0
        
        # Vertical distances: ||p2 - p6|| and ||p3 - p5||.
        v1 = np.linalg.norm(eye_points[1] - eye_points[5])
        v2 = np.linalg.norm(eye_points[2] - eye_points[4])
        
        # Horizontal distance: ||p1 - p4||
        h = np.linalg.norm(eye_points[0] - eye_points[3])
        
        if h == 0:
            return 0.0
        
        return (v1 + v2) / (2.0 * h)
    
    def reset(self):
        """Reset state tracking and history"""
        self.blink_counter = 0
        self.was_closed = False
        self.closed_frames = 0
        self.frame_counter = 0
        self.ear_history.clear()
        self.blink_timestamps.clear()
