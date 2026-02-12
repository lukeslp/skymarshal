"""Firehose package — Jetstream WebSocket client and feature extraction.

Provides:
- JetstreamClient: Sync WebSocket client for real-time Bluesky posts
- analyze_sentiment: VADER-based sentiment analysis
- extract_features: Post feature extraction (hashtags, mentions, media, etc.)
- FirehosePost / FirehoseStats: Data models
"""

from skymarshal.firehose.features import PostFeatures, extract_features
from skymarshal.firehose.jetstream import FirehosePost, FirehoseStats, JetstreamClient
from skymarshal.firehose.sentiment import SentimentResult, analyze_sentiment

__all__ = [
    "JetstreamClient",
    "FirehosePost",
    "FirehoseStats",
    "PostFeatures",
    "SentimentResult",
    "analyze_sentiment",
    "extract_features",
]
