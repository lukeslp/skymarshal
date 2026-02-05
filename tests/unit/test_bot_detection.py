"""
Unit tests for BotDetector.
"""
import pytest
from skymarshal.bot_detection import BotDetector

class TestBotDetector:
    def test_analyze_indicators(self):
        """Test bot detection heuristics."""
        bd = BotDetector()
        profiles = [
            {"handle": "bot1", "followers_count": 1, "following_count": 1000}, # Ratio 0.001 (Severe)
            {"handle": "user1", "followers_count": 100, "following_count": 100}, # Ratio 1.0
            {"handle": "sus1", "followers_count": 10, "following_count": 200}, # Ratio 0.05 (Suspect)
            {"handle": "inactive", "followers_count": 0, "following_count": 0}, # Skipped
        ]
        
        suspects = bd.analyze_indicators(profiles)
        
        # Expect 2 suspects: bot1 and sus1
        assert len(suspects) == 2
        
        # Sorts by ratio ascending (most severe first)
        assert suspects[0]["handle"] == "bot1"
        assert suspects[0]["bot_probability"] == "high"
        
        assert suspects[1]["handle"] == "sus1"
        assert suspects[1]["bot_probability"] == "medium"

    def test_format_report(self):
        """Test report formatting."""
        bd = BotDetector()
        suspects = [
            {"handle": "bot1", "ratio": 0.001, "followers_count": 1, "following_count": 1000}
        ]
        
        report = bd.format_report(suspects)
        assert "POTENTIAL BOT INDICATORS REPORT" in report
        assert "bot1" in report
        assert "Ratio: 0.001" in report
