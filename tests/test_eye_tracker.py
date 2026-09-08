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
        # EyeTracker takes its threshold/window as explicit constructor arguments
        # (no internal config lookup), so tests just pass them directly - this
        # keeps the test isolated from disk config.yaml without needing to mock
        # a get_config() that the module doesn't actually call.
        self.tracker = EyeTracker(ear_threshold=0.2, smoothing_window=3)

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

        # Second frame - clearly closed eyes. Chosen well below the threshold
        # (rather than e.g. 0.1) because analyze() smooths EAR over a 3-frame
        # window: after only two frames the smoothed value is an average with
        # the still-open first frame, so a borderline "closed" value can land
        # back above threshold and mask a real blink.
        landmarks = self._create_mock_landmarks(ear=0.05)
        result2 = self.tracker.analyze(landmarks)
        self.assertTrue(result2.is_blinking)
        self.assertEqual(result2.blink_count, 1)

    def _create_mock_landmarks(self, ear: float):
        """
        Create mock MediaPipe face landmarks whose computed EAR equals `ear`.

        The previous version of this fixture only ever moved the upper/lower
        eyelid points (p2/p3/p5/p6) and left the outer corners (p1/p4) at their
        default (0.5, 0.5) for every eye - so the horizontal distance ||p1-p4||
        used in the EAR denominator was always exactly 0, and _calculate_ear's
        divide-by-zero guard made every call return 0.0 regardless of the `ear`
        argument. Every eye-tracker test was silently exercising the same
        "EAR is always 0" code path. Placing all 6 points with a real horizontal
        spread (h) and setting the vertical gaps to ear*h makes the fixture
        actually produce the requested EAR.
        """
        class MockLandmarks:
            def __init__(self):
                self.landmark = [Mock() for _ in range(470)]
                for lm in self.landmark:
                    lm.x = 0.5
                    lm.y = 0.5
                    lm.visibility = 1.0

                h = 0.1  # horizontal eye width (p1 -> p4)
                v = ear * h  # vertical eyelid gap needed to hit the target EAR
                for indices, center_x in (
                    (EyeTracker.LEFT_EYE_INDICES, 0.35),
                    (EyeTracker.RIGHT_EYE_INDICES, 0.65),
                ):
                    p1, p2, p3, p4, p5, p6 = indices
                    self.landmark[p1].x = center_x - h / 2
                    self.landmark[p1].y = 0.5
                    self.landmark[p4].x = center_x + h / 2
                    self.landmark[p4].y = 0.5
                    self.landmark[p2].x = center_x - h / 4
                    self.landmark[p2].y = 0.5 - v / 2
                    self.landmark[p6].x = center_x - h / 4
                    self.landmark[p6].y = 0.5 + v / 2
                    self.landmark[p3].x = center_x + h / 4
                    self.landmark[p3].y = 0.5 - v / 2
                    self.landmark[p5].x = center_x + h / 4
                    self.landmark[p5].y = 0.5 + v / 2

        return MockLandmarks()


if __name__ == '__main__':
    unittest.main()
