"""
Content Analyzer Module (stub)

LLM-based content analysis has been removed. This module preserves the class
interface so existing imports continue to work, but all methods return
"not available" responses. Use ContentAnalytics in services/analytics.py
for lexicon-based sentiment analysis instead.
"""

from datetime import datetime
from typing import List, Dict, Optional, Any


class ContentAnalyzer:
    """Stub — LLM content analysis has been removed.

    All methods return graceful "not available" responses.
    For sentiment analysis, use ContentAnalytics from services/analytics.py.
    """

    def __init__(self, auth_manager=None, api_key: str = None):
        self.auth_manager = auth_manager

    def analyze_content_vibe(self, posts: List[Dict], max_posts: int = 10) -> Dict[str, Any]:
        return {"error": "Content analysis is not available"}

    def summarize_content(self, posts: List[Dict], max_posts: int = 20) -> Dict[str, Any]:
        return {"error": "Content summarization is not available"}

    def analyze_sentiment(self, posts: List[Dict], max_posts: int = 15) -> Dict[str, Any]:
        return {"error": "LLM sentiment analysis is not available. Use /api/analytics/sentiment for lexicon-based analysis."}

    def categorize_content(self, posts: List[Dict], max_posts: int = 20) -> Dict[str, Any]:
        return {"error": "Content categorization is not available"}

    def display_analysis_results(self, analysis: Dict[str, Any]):
        pass

    async def run_complete_analysis(self, posts: List[Dict], analysis_types: List[str] = None) -> Dict[str, Any]:
        return {
            "posts_analyzed": 0,
            "timestamp": datetime.now().isoformat(),
            "analyses": {},
            "error": "Content analysis is not available",
        }
