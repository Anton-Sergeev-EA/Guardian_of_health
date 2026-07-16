"""
Unit tests for voice commands
"""

import unittest
from src.voice.commands import CommandRegistry, VoiceCommand


class TestCommandRegistry(unittest.TestCase):
    """Test suite for validating the voice command parsing and confidence scoring."""
    
    def setUp(self):
        self.registry = CommandRegistry()
    
    def test_parse_russian_commands(self):
        """Test parsing of various Russian voice command phrasing variations."""
        test_cases = [
            ("статус", VoiceCommand.STATUS),
            ("покажи статус", VoiceCommand.STATUS),
            ("пауза", VoiceCommand.PAUSE),
            ("сделай паузу", VoiceCommand.PAUSE),
            ("отчет", VoiceCommand.REPORT),
            ("покажи отчет", VoiceCommand.REPORT),
            ("выход", VoiceCommand.QUIT),
            ("завершить работу", VoiceCommand.QUIT),
            ("помощь", VoiceCommand.HELP),
            ("что умеешь", VoiceCommand.HELP)
        ]
        
        for text, expected_cmd in test_cases:
            with self.subTest(text=text):
                cmd, confidence = self.registry.parse_command(text)
                self.assertEqual(cmd, expected_cmd)
                self.assertGreater(confidence, 0.3)
    
    def test_parse_english_commands(self):
        """Test parsing of various English voice command phrasing variations."""
        test_cases = [
            ("status", VoiceCommand.STATUS),
            ("show status", VoiceCommand.STATUS),
            ("pause", VoiceCommand.PAUSE),
            ("report", VoiceCommand.REPORT),
            ("quit", VoiceCommand.QUIT),
            ("help", VoiceCommand.HELP)
        ]
        
        for text, expected_cmd in test_cases:
            with self.subTest(text=text):
                cmd, confidence = self.registry.parse_command(text)
                self.assertEqual(cmd, expected_cmd)
                self.assertGreater(confidence, 0.3)
    
    def test_unknown_commands(self):
        """Test that random gibberish or empty strings do not trigger any command."""
        test_cases = ["abcdef", "12345", "random text", ""]
        
        for text in test_cases:
            with self.subTest(text=text):
                cmd, confidence = self.registry.parse_command(text)
                self.assertIsNone(cmd)
                self.assertEqual(confidence, 0.0)
    
    def test_confidence_scoring(self):
        """Test that confidence matches the fuzzy-matching quality of input phrase."""
        # Exact match should have very high confidence.
        cmd, confidence_exact = self.registry.parse_command("статус")
        self.assertGreater(confidence_exact, 0.8)
        
        # Partial match should yield lower but acceptable confidence.
        cmd, confidence_partial = self.registry.parse_command("статус системы")
        self.assertGreater(confidence_partial, 0.5)
        self.assertLess(confidence_partial, confidence_exact)
        
        # Very loose match should fall below acceptable threshold or return low confidence.
        cmd, confidence_loose = self.registry.parse_command("ста")
        self.assertLess(confidence_loose, 0.4)


if __name__ == '__main__':
    unittest.main()
