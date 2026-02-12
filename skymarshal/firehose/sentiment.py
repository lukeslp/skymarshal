"""Sentiment analysis using VADER (vaderSentiment).

Ported from firehose/server/sentiment.ts.
Classification thresholds: >0.05 positive, <-0.05 negative, else neutral.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)

# Lazy-load the analyzer to avoid import-time cost
_analyzer = None


def _get_analyzer():
    global _analyzer
    if _analyzer is None:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

        _analyzer = SentimentIntensityAnalyzer()
    return _analyzer


@dataclass
class SentimentResult:
    score: float = 0.0
    comparative: float = 0.0
    classification: str = "neutral"  # "positive", "negative", "neutral"
    positive_words: List[str] = field(default_factory=list)
    negative_words: List[str] = field(default_factory=list)


def analyze_sentiment(text: str) -> SentimentResult:
    """Analyze sentiment of text using VADER.

    Returns a SentimentResult with compound score, comparative score,
    and classification (positive/negative/neutral).
    """
    if not text or not text.strip():
        return SentimentResult()

    analyzer = _get_analyzer()
    scores = analyzer.polarity_scores(text)

    # VADER compound score ranges from -1 to +1
    compound = scores["compound"]

    # Compute comparative score (normalized by word count, like the npm sentiment lib)
    word_count = len(text.split())
    comparative = compound / max(word_count, 1)

    # Classification thresholds match the TypeScript implementation
    if comparative > 0.05:
        classification = "positive"
    elif comparative < -0.05:
        classification = "negative"
    else:
        classification = "neutral"

    return SentimentResult(
        score=compound,
        comparative=comparative,
        classification=classification,
    )
