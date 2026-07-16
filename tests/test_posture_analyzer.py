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
        # Mock configuration load to ensure tests run in isolation from disk config.yaml.
        self.config_patcher = patch('src.analytics.posture_analyzer.get_config')
        self.mock_get_config = self.config_patcher.start()
        
        # Define mock configuration attributes used by PostureAnalyzer.
        mock_cfg = Mock()
        mock_cfg.analytics.posture.slouch_threshold = 15.0
        mock_cfg.analytics.posture.critical_threshold = 25.0
        mock_cfg.analytics.posture.smoothing_window = 5
        self.mock_get_config.return_value = mock_cfg
        
        self.analyzer = PostureAnalyzer()
    
    def tearDown(self):
        self.config_patcher.stop()
    
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
    
    def _create_mock_landmarks(self, angle: float):
        """Create mock MediaPipe-like landmark structures with a specified deviation angle."""
        class MockLandmarks:
            def __init__(self):
                self.landmark = [Mock() for _ in range(25)]
                for lm in self.landmark:
                    lm.x = 0.5
                    lm.y = 0.5
                    lm.visibility = 1.0
                
                rad = math.radians(angle)
                # Left/Right Shoulders (Indices 11, 12).
                self.landmark[11].x = 0.5 - 0.1
                self.landmark[11].y = 0.5 - 0.1 * math.cos(rad)
                self.landmark[12].x = 0.5 + 0.1
                self.landmark[12].y = 0.5 - 0.1 * math.cos(rad)
                
                # Left/Right Hips (Indices 23, 24).
                self.landmark[23].x = 0.5 - 0.08
                self.landmark[23].y = 0.5 + 0.2
                self.landmark[24].x = 0.5 + 0.08
                self.landmark[24].y = 0.5 + 0.2
                
                # Nose (Index 0).
                self.landmark[0].x = 0.5
                self.landmark[0].y = 0.5 - 0.15
        
        return MockLandmarks()


if __name__ == '__main__':
    unittest.main()
