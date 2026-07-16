"""
Unit tests for eye tracker
"""

import unittest
import numpy as np
from unittest.mock import Mock, patch
from src.analytics.eye_tracker import EyeTracker, EyeMetrics


class TestEyeTracker(unittest.TestCase):
    """Test suite for validating eye tracking and blink detection logic."""
    
    def setUp(self):
        # Mock configuration load to ensure tests run in isolation from disk config.yaml.
        self.config_patcher = patch('src.analytics.eye_tracker.get_config')
        self.mock_get_config = self.config_patcher.start()
        
        # Define mock configuration attributes used by EyeTracker.
        mock_cfg = Mock()
        mock_cfg.analytics.eye.ear_threshold = 0.2
        mock_cfg.analytics.eye.blink_threshold = 0.25
        mock_cfg.analytics.eye.smoothing_window = 3
        self.mock_get_config.return_value = mock_cfg
        
        self.tracker = EyeTracker()
        
    def tearDown(self):
        self.config_patcher.stop()
    
    def test_ear_calculation(self):
        """Test EAR calculation based on 8 key vertical/horizontal eye coordinate points."""
        # Open eye coordinates.
        eye_points = [
            np.array([0.0, 0.0]),   # p1.
            np.array([0.1, 0.05]),  # p2.
            np.array([0.15, 0.06]), # p3.
            np.array([0.25, 0.0]),  # p4.
            np.array([0.15, -0.06]),# p5.
            np.array([0.1, -0.05]), # p6.
            np.array([0.05, -0.02]),# p7.
            np.array([0.2, -0.02])  # p8.
        ]
        ear = self.tracker._calculate_ear(eye_points)
        self.assertGreater(ear, 0.2)
        
        # Closed eye coordinates.
        eye_points = [
            np.array([0.0, 0.0]),
            np.array([0.1, 0.01]),
            np.array([0.15, 0.01]),
            np.array([0.25, 0.0]),
            np.array([0.15, -0.01]),
            np.array([0.1, -0.01]),
            np.array([0.05, 0.0]),
            np.array([0.2, 0.0])
        ]
        ear = self.tracker._calculate_ear(eye_points)
        self.assertLess(ear, 0.2)
    
    def test_analyze_no_landmarks(self):
        """Test analyze gracefully handles missing/None landmarks structure."""
        result = self.tracker.analyze(None)
        self.assertEqual(result.fatigue_score, 0.0)
    
    def test_blink_detection(self):
        """Test blink state machine across sequential frames (open -> closed -> open)."""
        # First frame - open eyes (EAR above threshold).
        landmarks = self._create_mock_landmarks(ear=0.3)
        result1 = self.tracker.analyze(landmarks)
        self.assertFalse(result1.is_blinking)
        self.assertEqual(result1.blink_count, 0)
        
        # Second frame - closed eyes (EAR below threshold - register blink start).
        landmarks = self._create_mock_landmarks(ear=0.1)
        result2 = self.tracker.analyze(landmarks)
        self.assertTrue(result2.is_blinking)
        self.assertEqual(result2.blink_count, 1)
    
    def _create_mock_landmarks(self, ear: float):
        """Create mock MediaPipe face landmarks with specified EAR values."""
        class MockLandmarks:
            def __init__(self):
                self.landmark = [Mock() for _ in range(470)]
                for lm in self.landmark:
                    lm.x = 0.5
                    lm.y = 0.5
                    lm.visibility = 1.0
                
                # Adjust left eye landmarks (vertical points indices).
                left_indices = EyeTracker.LEFT_EYE_INDICES
                for i, idx in enumerate(left_indices):
                    if i in [1, 5]:  # Upper eyelids.
                        self.landmark[idx].y = 0.5 + ear * 0.15
                    elif i in [2, 4]:  # Lower eyelids.
                        self.landmark[idx].y = 0.5 - ear * 0.15
                
                # Adjust right eye landmarks.
                right_indices = EyeTracker.RIGHT_EYE_INDICES
                for i, idx in enumerate(right_indices):
                    if i in [1, 5]:
                        self.landmark[idx].y = 0.5 + ear * 0.15
                    elif i in [2, 4]:
                        self.landmark[idx].y = 0.5 - ear * 0.15
        
        return MockLandmarks()


if __name__ == '__main__':
    unittest.main()
