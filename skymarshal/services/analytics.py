"""Analytics module for content analysis and insights."""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from typing import Dict, List, Tuple, Optional

from ..models import ContentItem


class ContentAnalytics:
    """Provides analytics and insights for Bluesky content."""

    # Simple sentiment lexicon (positive/negative words)
    POSITIVE_WORDS = {
        "good", "great", "awesome", "excellent", "amazing", "wonderful", "fantastic",
        "love", "happy", "joy", "beautiful", "perfect", "best", "excited", "fun",
        "thanks", "thank", "appreciate", "grateful", "nice", "helpful", "enjoy",
        "congrats", "congratulations", "success", "win", "winning", "brilliant",
        "outstanding", "superb", "incredible", "lovely", "delightful", "pleased"
    }

    NEGATIVE_WORDS = {
        "bad", "terrible", "awful", "horrible", "worst", "hate", "angry", "sad",
        "disappointed", "disappointing", "poor", "fail", "failed", "failure", "wrong",
        "problem", "issue", "error", "broken", "useless", "stupid", "annoying",
        "frustrating", "frustrated", "difficult", "hard", "sucks", "sorry", "unfortunately",
        "unfortunately", "concern", "worried", "worry", "afraid", "scared"
    }

    @staticmethod
    def analyze_sentiment(text: str) -> Dict[str, float]:
        """
        Analyze sentiment of text using lexicon-based approach.

        Returns:
            Dict with 'score' (-1 to 1), 'positive', 'negative', 'neutral' counts
        """
        if not text:
            return {"score": 0.0, "positive": 0, "negative": 0, "neutral": 1}

        # Normalize text
        words = re.findall(r'\b\w+\b', text.lower())

        positive_count = sum(1 for word in words if word in ContentAnalytics.POSITIVE_WORDS)
        negative_count = sum(1 for word in words if word in ContentAnalytics.NEGATIVE_WORDS)

        # Calculate normalized score (-1 to 1)
        total_sentiment_words = positive_count + negative_count
        if total_sentiment_words == 0:
            score = 0.0
        else:
            score = (positive_count - negative_count) / total_sentiment_words

        return {
            "score": round(score, 3),
            "positive": positive_count,
            "negative": negative_count,
            "neutral": 1 if total_sentiment_words == 0 else 0
        }

    @staticmethod
    def analyze_sentiments(items: List[ContentItem]) -> Dict:
        """Analyze sentiment across all items."""
        if not items:
            return {
                "average_score": 0.0,
                "positive_posts": 0,
                "negative_posts": 0,
                "neutral_posts": 0,
                "total_analyzed": 0
            }

        sentiments = []
        positive_count = 0
        negative_count = 0
        neutral_count = 0

        for item in items:
            if item.content_type in ("post", "reply") and item.text:
                result = ContentAnalytics.analyze_sentiment(item.text)
                sentiments.append(result["score"])

                if result["score"] > 0.1:
                    positive_count += 1
                elif result["score"] < -0.1:
                    negative_count += 1
                else:
                    neutral_count += 1

        avg_score = sum(sentiments) / len(sentiments) if sentiments else 0.0

        return {
            "average_score": round(avg_score, 3),
            "positive_posts": positive_count,
            "negative_posts": negative_count,
            "neutral_posts": neutral_count,
            "total_analyzed": len(sentiments),
            "percentage_positive": round(100 * positive_count / len(sentiments), 1) if sentiments else 0,
            "percentage_negative": round(100 * negative_count / len(sentiments), 1) if sentiments else 0,
            "percentage_neutral": round(100 * neutral_count / len(sentiments), 1) if sentiments else 0
        }

    @staticmethod
    def analyze_time_patterns(items: List[ContentItem]) -> Dict:
        """Analyze posting time patterns and engagement by time."""
        if not items:
            return {
                "by_hour": {},
                "by_day_of_week": {},
                "best_hour": None,
                "best_day": None,
                "total_analyzed": 0
            }

        posts_and_replies = [item for item in items if item.content_type in ("post", "reply")]

        hour_counts = Counter()
        day_counts = Counter()
        hour_engagement = {}
        day_engagement = {}

        for item in posts_and_replies:
            if not item.created_at:
                continue

            try:
                # Parse ISO timestamp
                dt = datetime.fromisoformat(item.created_at.replace('Z', '+00:00'))
                hour = dt.hour
                day = dt.strftime('%A')  # Monday, Tuesday, etc.

                hour_counts[hour] += 1
                day_counts[day] += 1

                # Track engagement by time
                engagement = (item.like_count or 0) + (item.repost_count or 0) + (item.reply_count or 0)

                if hour not in hour_engagement:
                    hour_engagement[hour] = []
                hour_engagement[hour].append(engagement)

                if day not in day_engagement:
                    day_engagement[day] = []
                day_engagement[day].append(engagement)

            except (ValueError, AttributeError):
                continue

        # Calculate average engagement by time
        hour_avg_engagement = {
            hour: sum(engagements) / len(engagements)
            for hour, engagements in hour_engagement.items()
        }
        day_avg_engagement = {
            day: sum(engagements) / len(engagements)
            for day, engagements in day_engagement.items()
        }

        # Find best times
        best_hour = max(hour_avg_engagement.items(), key=lambda x: x[1])[0] if hour_avg_engagement else None
        best_day = max(day_avg_engagement.items(), key=lambda x: x[1])[0] if day_avg_engagement else None

        # Order days properly
        day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        ordered_day_counts = {day: day_counts.get(day, 0) for day in day_order}
        ordered_day_engagement = {day: round(day_avg_engagement.get(day, 0), 1) for day in day_order}

        return {
            "by_hour": dict(sorted(hour_counts.items())),
            "by_day_of_week": ordered_day_counts,
            "hour_engagement": {k: round(v, 1) for k, v in sorted(hour_avg_engagement.items())},
            "day_engagement": ordered_day_engagement,
            "best_hour": best_hour,
            "best_day": best_day,
            "total_analyzed": len(posts_and_replies)
        }

    @staticmethod
    def analyze_engagement_correlation(items: List[ContentItem], top_n: int = 20) -> Dict:
        """Analyze which words/topics correlate with higher engagement."""
        if not items:
            return {
                "high_engagement_words": [],
                "low_engagement_words": [],
                "total_analyzed": 0
            }

        posts_and_replies = [item for item in items if item.content_type in ("post", "reply") and item.text]

        # Track words and their associated engagement
        word_engagements = {}

        for item in posts_and_replies:
            engagement = (item.like_count or 0) + (item.repost_count or 0) + (item.reply_count or 0)
            words = re.findall(r'\b\w+\b', item.text.lower())

            # Skip very short words and common words
            stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "from", "as", "is", "was", "are", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "must", "can", "this", "that", "these", "those", "i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us", "them", "my", "your", "his", "its", "our", "their"}

            for word in words:
                if len(word) > 3 and word not in stop_words:
                    if word not in word_engagements:
                        word_engagements[word] = []
                    word_engagements[word].append(engagement)

        # Calculate average engagement per word (only for words used 3+ times)
        word_avg_engagement = {
            word: sum(engagements) / len(engagements)
            for word, engagements in word_engagements.items()
            if len(engagements) >= 3
        }

        # Sort by engagement
        sorted_words = sorted(word_avg_engagement.items(), key=lambda x: x[1], reverse=True)

        high_engagement = [
            {"word": word, "avg_engagement": round(eng, 1), "count": len(word_engagements[word])}
            for word, eng in sorted_words[:top_n]
        ]

        low_engagement = [
            {"word": word, "avg_engagement": round(eng, 1), "count": len(word_engagements[word])}
            for word, eng in sorted_words[-top_n:]
        ]

        return {
            "high_engagement_words": high_engagement,
            "low_engagement_words": low_engagement,
            "total_analyzed": len(posts_and_replies),
            "unique_words": len(word_avg_engagement)
        }

    @staticmethod
    def analyze_word_frequency(items: List[ContentItem], top_n: int = 50) -> Dict:
        """Analyze most frequently used words in posts."""
        if not items:
            return {
                "top_words": [],
                "total_words": 0,
                "total_analyzed": 0
            }

        posts_and_replies = [item for item in items if item.content_type in ("post", "reply") and item.text]

        all_words = []
        for item in posts_and_replies:
            words = re.findall(r'\b\w+\b', item.text.lower())
            all_words.extend(words)

        # Common stop words to exclude
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "from", "as", "is", "was", "are", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "must", "can", "this", "that", "these", "those", "i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us", "them", "my", "your", "his", "its", "our", "their", "so", "just", "now", "out", "up", "get", "got", "like", "one", "two"}

        # Filter out short words and stop words
        filtered_words = [word for word in all_words if len(word) > 3 and word not in stop_words]

        word_counts = Counter(filtered_words)
        top_words = [
            {"word": word, "count": count, "percentage": round(100 * count / len(filtered_words), 2)}
            for word, count in word_counts.most_common(top_n)
        ]

        return {
            "top_words": top_words,
            "total_words": len(all_words),
            "unique_words": len(word_counts),
            "total_analyzed": len(posts_and_replies)
        }

    @staticmethod
    def generate_insights(items: List[ContentItem]) -> Dict:
        """Generate comprehensive insights from all analytics."""
        sentiment = ContentAnalytics.analyze_sentiments(items)
        time_patterns = ContentAnalytics.analyze_time_patterns(items)
        engagement_correlation = ContentAnalytics.analyze_engagement_correlation(items)
        word_frequency = ContentAnalytics.analyze_word_frequency(items)

        return {
            "sentiment": sentiment,
            "time_patterns": time_patterns,
            "engagement_correlation": engagement_correlation,
            "word_frequency": word_frequency
        }
