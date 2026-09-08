"""
Unit tests for posture analyzer.
"""

import math
import unittest
import numpy as np
from unittest.mock import Mock, patch
from src.analytics.posture_analyzer import PostureAnalyzer, PostureMetrics


class TestPostureAnalyzer(unittest.TestCase):
    """Test suite for validating posture detection logic."""

    def setUp(self):
        # PostureAnalyzer takes its thresholds as explicit constructor arguments
        # (no internal config lookup), so tests just pass them directly - this
        # keeps the test isolated from disk config.yaml without needing to mock
        # a get_config() that the module doesn't actually call.
        self.analyzer = PostureAnalyzer(
            slouch_threshold=15.0,
            critical_threshold=25.0,
            smoothing_window=5,
        )

    def test_angle_calculation(self):
        """Test angle calculation between two vectors."""
        v1 = np.array([1, 0])
        v2 = np.array([0, 1])
        angle = self.analyzer._angle_between(v1, v2)
        self.assertAlmostEqual(angle, 90.0, places=5)

        v1 = np.array([1, 0])
        v2 = np.array([1, 0])
        angle = self.analyzer._angle_between(v1, v2)
        self.assertAlmostEqual(angle, 0.0, places=5)

    def test_landmark_confidence(self):
        """Test landmark confidence extraction from mediaPipe landmarks."""
        mock_landmark = Mock()
        mock_landmark.visibility = 0.8
        confidence = self.analyzer._landmark_confidence(mock_landmark)
        self.assertEqual(confidence, 0.8)

        # Test default confidence fallback.
        mock_landmark = Mock()
        del mock_landmark.visibility
        confidence = self.analyzer._landmark_confidence(mock_landmark)
        self.assertEqual(confidence, 1.0)

    @patch('src.analytics.posture_analyzer.PostureAnalyzer._angle_between')
    def test_analyze_no_landmarks(self, mock_angle):
        """Test analyze with empty/none landmarks structure."""
        result = self.analyzer.analyze(None)
        self.assertEqual(result.severity, 'unknown')

    def test_analyze_good_posture(self):
        """Test correct categorization of good posture."""
        # Create mock landmarks with a 5-degree tilt.
        landmarks = self._create_mock_landmarks(angle=5.0)
        result = self.analyzer.analyze(landmarks)

        self.assertFalse(result.is_slouching)
        self.assertEqual(result.severity, 'good')
        self.assertLess(result.spine_angle, 15.0)

    def test_analyze_slouching(self):
        """Test correct detection of mild slouching (warning)."""
        # Create mock landmarks with a 20-degree tilt (above slouch threshold).
        landmarks = self._create_mock_landmarks(angle=20.0)
        result = self.analyzer.analyze(landmarks)

        self.assertTrue(result.is_slouching)
        self.assertEqual(result.severity, 'warning')

    def test_analyze_critical_slouching(self):
        """Test correct detection of severe slouching (critical)."""
        # Create mock landmarks with a 30-degree tilt (above critical threshold).
        landmarks = self._create_mock_landmarks(angle=30.0)
        result = self.analyzer.analyze(landmarks)

        self.assertTrue(result.is_slouching)
        self.assertEqual(result.severity, 'critical')

    def test_is_slouching_is_a_native_bool(self):
        """
        is_slouching is compared from np.mean(...), which yields numpy.bool_
        rather than a real Python bool unless explicitly cast. That's not a
        problem for truthiness checks in Python, but json.dumps() (used by
        Flask's jsonify() in the web dashboard's /api/status endpoint) raises
        TypeError on numpy.bool_ - confirmed by actually hitting that
        endpoint and getting a 500, not just by reading the type hint.
        """
        landmarks = self._create_mock_landmarks(angle=30.0)
        result = self.analyzer.analyze(landmarks)
        self.assertIsInstance(result.is_slouching, bool)

    def _create_mock_landmarks(self, angle: float):
        """
        Create mock MediaPipe-like landmark structures tilted by `angle` degrees
        from vertical, pivoting at the hips.

        The previous version of this fixture varied only the shoulder points'
        *height* by cos(angle) while keeping both shoulders' x-coordinates fixed
        at the hip midline - so the shoulder->hip vector always pointed straight
        up regardless of `angle`, and every test here silently exercised a 0deg
        spine angle no matter what value was requested. Tilting the shoulder
        center horizontally by spine_length*sin(angle) actually rotates the
        vector, so the analyzer receives the geometry the test claims to send.
        """
        class MockLandmarks:
            def __init__(self):
                self.landmark = [Mock() for _ in range(25)]
                for lm in self.landmark:
                    lm.x = 0.5
                    lm.y = 0.5
                    lm.visibility = 1.0

                rad = math.radians(angle)
                spine_length = 0.3
                hip_x, hip_y = 0.5, 0.7
                shoulder_x = hip_x + spine_length * math.sin(rad)
                shoulder_y = hip_y - spine_length * math.cos(rad)

                # Left/Right Shoulders (Indices 11, 12).
                self.landmark[11].x = shoulder_x - 0.1
                self.landmark[11].y = shoulder_y
                self.landmark[12].x = shoulder_x + 0.1
                self.landmark[12].y = shoulder_y

                # Left/Right Hips (Indices 23, 24) - the pivot point.
                self.landmark[23].x = hip_x - 0.08
                self.landmark[23].y = hip_y
                self.landmark[24].x = hip_x + 0.08
                self.landmark[24].y = hip_y

                # Nose (Index 0), carried along with the shoulder tilt.
                self.landmark[0].x = shoulder_x
                self.landmark[0].y = shoulder_y - 0.15

        return MockLandmarks()


if __name__ == '__main__':
    unittest.main()
