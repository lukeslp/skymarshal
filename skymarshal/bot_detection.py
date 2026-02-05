"""
Skymarshal Bot Detection

File Purpose: Identify potential bot/spam accounts
Primary Functions/Classes: BotDetector
Inputs and Outputs (I/O): Profile data analysis

This module provides logic to analyze user profiles and identify potential bot or spam accounts
based on heuristics like follower-to-following ratios.
"""

from typing import Dict, List, Optional
from .models import console

class BotDetector:
    """Analyzes profiles for bot indicators."""

    def __init__(self, settings_manager=None):
        self.settings = settings_manager
        # Default threshold: following many but followed by few
        self.ratio_threshold_severe = 0.01  # Very likely bot/spam
        self.ratio_threshold_suspect = 0.1  # Suspicious

    def analyze_indicators(self, profiles: List[Dict], top_n: int = 20) -> List[Dict]:
        """
        Identify potential bot accounts based on follower/following ratio.
        
        Args:
            profiles: List of profile dicts (must have followers_count, following_count)
            top_n: Number of results to return
            
        Returns:
            List of suspect profiles sorted by likelihood (lowest ratio first)
        """
        suspects = []
        
        for p in profiles:
            followers = p.get("followers_count", 0) or 0
            following = p.get("following_count", 0) or 0
            
            # Skip accounts with no following (inactive rather than bot spam)
            # or accounts with reasonable follower counts (unless ratio is terrible)
            if following == 0:
                continue
                
            ratio = followers / following
            
            # Heuristic: < 0.1 means they follow 10x more people than follow them
            if ratio < self.ratio_threshold_suspect:
                severity = "medium"
                if ratio < self.ratio_threshold_severe:
                    severity = "high"
                
                # Clone dict to avoid modifying original
                suspect = p.copy()
                suspect["bot_probability"] = severity
                suspect["ratio"] = ratio
                suspects.append(suspect)
                
        # Sort by ratio ascending (lowest ratio = most likely spam bot)
        suspects.sort(key=lambda x: x["ratio"])
        
        return suspects[:top_n]

    def format_report(self, suspects: List[Dict]) -> str:
        """Generate a text report of suspects."""
        if not suspects:
            return "No suspicious accounts detected."
            
        lines = ["POTENTIAL BOT INDICATORS REPORT", "=" * 40]
        for i, s in enumerate(suspects, 1):
            lines.append(f"#{i} @{s.get('handle')} | Ratio: {s['ratio']:.3f} | Followers: {s.get('followers_count')} / Following: {s.get('following_count')}")
            
        return "\n".join(lines)
