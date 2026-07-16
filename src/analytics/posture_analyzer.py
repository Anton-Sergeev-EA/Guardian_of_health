"""
Posture Analyzer - Detects slouching and poor posture.
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple
from collections import deque


@dataclass
class PostureMetrics:
    """Metrics for posture analysis."""
    spine_angle: float = 0.0
    neck_angle: float = 0.0
    shoulder_angle: float = 0.0
    is_slouching: bool = False
    severity: str = 'good'  # 'good', 'warning', 'critical', 'unknown', 'error'.
    confidence: float = 0.0


class PostureAnalyzer:
    """
    Analyzes posture using MediaPipe Pose landmarks.
    
    Key landmarks:
    - 11: Left shoulder.
    - 12: Right shoulder.
    - 0: Nose.
    - 23: Left hip.
    - 24: Right hip.
    - 7: Left ear.
    - 8: Right ear.
    """
    
    def __init__(
        self,
        slouch_threshold: float = 15.0,
        critical_threshold: float = 25.0,
        smoothing_window: int = 5
    ):
        self.slouch_threshold = slouch_threshold
        self.critical_threshold = critical_threshold
        self.smoothing_window = smoothing_window
        self.angle_history: deque = deque(maxlen=smoothing_window)
        self.confidence_history: deque = deque(maxlen=smoothing_window)
        
    def analyze(self, pose_landmarks, image_size: Optional[Tuple[int, int]] = None) -> PostureMetrics:
        """
        Analyze posture from MediaPipe pose landmarks.
        
        :param pose_landmarks: MediaPipe landmarks object.
        :param image_size: Optional tuple of (width, height) to correct aspect ratio distortion.
        """
        if pose_landmarks is None:
            return PostureMetrics(severity='unknown')
        
        landmarks = pose_landmarks.landmark
        
        try:
            # Scaling to the actual frame size to eliminate angle distortion.
            w, h = image_size if image_size else (1.0, 1.0)
            
            # Extraction of key points taking into account the aspect ratio.
            left_shoulder = np.array([landmarks[11].x * w, landmarks[11].y * h])
            right_shoulder = np.array([landmarks[12].x * w, landmarks[12].y * h])
            shoulder_center = (left_shoulder + right_shoulder) / 2
            
            nose = np.array([landmarks[0].x * w, landmarks[0].y * h])
            
            left_hip = np.array([landmarks[23].x * w, landmarks[23].y * h])
            right_hip = np.array([landmarks[24].x * w, landmarks[24].y * h])
            hip_center = (left_hip + right_hip) / 2
            
            # Vectors (pointing UP in the screen coordinate system).
            # Shoulders -> Nose.
            neck_vector = nose - shoulder_center 
            # Hips -> Shoulders (CORRECTED: the vector is now pointing up).
            spine_vector = shoulder_center - hip_center 
            
            # Vertical up vector (in the OpenCV/MediaPipe coordinate system, where y goes down).
            vertical = np.array([0.0, -1.0])
            
            # Normalization.
            spine_norm = spine_vector / (np.linalg.norm(spine_vector) + 1e-6)
            neck_norm = neck_vector / (np.linalg.norm(neck_vector) + 1e-6)
            
            # Calculation of angles relative to the vertical.
            spine_angle = self._angle_between(spine_norm, vertical)
            neck_angle = self._angle_between(neck_norm, vertical)
            
            # Horizontal shoulder tilt (left/right).
            shoulder_vec = right_shoulder - left_shoulder
            horizontal = np.array([1.0, 0.0])
            shoulder_angle = self._angle_between(shoulder_vec, horizontal)
            
            # Confidence interval based on the visibility of key points.
            confidence = min(1.0, (
                self._landmark_confidence(landmarks[11]) +
                self._landmark_confidence(landmarks[12]) +
                self._landmark_confidence(landmarks[0]) +
                self._landmark_confidence(landmarks[23]) +
                self._landmark_confidence(landmarks[24])
            ) / 5.0)
            
            # Smoothing.
            self.angle_history.append(spine_angle)
            self.confidence_history.append(confidence)
            
            smoothed_angle = np.mean(self.angle_history)
            avg_confidence = np.mean(self.confidence_history)
            
            # Determining the state of posture.
            is_slouching = smoothed_angle > self.slouch_threshold
            
            if smoothed_angle > self.critical_threshold:
                severity = 'critical'
            elif smoothed_angle > self.slouch_threshold:
                severity = 'warning'
            else:
                severity = 'good'
            
            return PostureMetrics(
                spine_angle=float(smoothed_angle),
                neck_angle=float(neck_angle),
                shoulder_angle=float(shoulder_angle),
                is_slouching=is_slouching,
                severity=severity,
                confidence=float(avg_confidence)
            )
            
        except (IndexError, AttributeError, ValueError):
            return PostureMetrics(severity='error')
    
    @staticmethod
    def _angle_between(v1: np.ndarray, v2: np.ndarray) -> float:
        """Calculate angle between two vectors in degrees."""
        cos_angle = np.clip(np.dot(v1, v2), -1.0, 1.0)
        return np.degrees(np.arccos(cos_angle))
    
    @staticmethod
    def _landmark_confidence(landmark) -> float:
        """Get confidence of a landmark."""
        if hasattr(landmark, 'visibility'):
            return landmark.visibility
        return 1.0
    
    def reset(self):
        """Reset history buffers"""
        self.angle_history.clear()
        self.confidence_history.clear()
