"""Analytics API blueprint.

Wraps ContentAnalytics (sentiment, time patterns, engagement correlation,
word frequency) and the analytics module analyzers.
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request, session

from skymarshal.api import get_services
from skymarshal.services import ContentService
from skymarshal.services.analytics import ContentAnalytics

logger = logging.getLogger(__name__)

analytics_bp = Blueprint("analytics", __name__)


def _require_service() -> ContentService:
    token = session.get("api_token")
    if not token:
        raise PermissionError("Authentication required")
    service = get_services().get(token)
    if not service or not service.auth.is_authenticated():
        raise PermissionError("Authentication required")
    return service


def _auth_guard(f):
    from functools import wraps

    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except PermissionError as e:
            return jsonify({"success": False, "error": str(e)}), 401

    return wrapper


# ---------------------------------------------------------------------------
# Full insights
# ---------------------------------------------------------------------------

@analytics_bp.route("/insights", methods=["GET"])
@_auth_guard
def insights():
    """Generate comprehensive analytics (sentiment, time patterns, engagement, words)."""
    service = _require_service()

    try:
        items = service.ensure_content_loaded(
            categories=["posts", "likes", "reposts"],
            limit=999999,
        )
        data = ContentAnalytics.generate_insights(items)
        return jsonify({"success": True, "analytics": data})
    except RuntimeError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


# ---------------------------------------------------------------------------
# Individual analytics endpoints
# ---------------------------------------------------------------------------

@analytics_bp.route("/sentiment", methods=["GET"])
@_auth_guard
def sentiment():
    """Sentiment analysis across all posts."""
    service = _require_service()

    try:
        items = service.ensure_content_loaded(
            categories=["posts", "likes", "reposts"],
            limit=999999,
        )
        data = ContentAnalytics.analyze_sentiments(items)
        return jsonify({"success": True, "sentiment": data})
    except RuntimeError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@analytics_bp.route("/time-patterns", methods=["GET"])
@_auth_guard
def time_patterns():
    """Posting time patterns and engagement by time."""
    service = _require_service()

    try:
        items = service.ensure_content_loaded(
            categories=["posts", "likes", "reposts"],
            limit=999999,
        )
        data = ContentAnalytics.analyze_time_patterns(items)
        return jsonify({"success": True, "time_patterns": data})
    except RuntimeError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@analytics_bp.route("/engagement", methods=["GET"])
@_auth_guard
def engagement_correlation():
    """Word/topic correlation with engagement levels."""
    service = _require_service()

    try:
        items = service.ensure_content_loaded(
            categories=["posts", "likes", "reposts"],
            limit=999999,
        )
        data = ContentAnalytics.analyze_engagement_correlation(items)
        return jsonify({"success": True, "engagement": data})
    except RuntimeError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@analytics_bp.route("/words", methods=["GET"])
@_auth_guard
def word_frequency():
    """Most frequently used words in posts."""
    service = _require_service()

    try:
        items = service.ensure_content_loaded(
            categories=["posts", "likes", "reposts"],
            limit=999999,
        )
        data = ContentAnalytics.analyze_word_frequency(items)
        return jsonify({"success": True, "word_frequency": data})
    except RuntimeError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


# ---------------------------------------------------------------------------
# Follower analytics (wraps FollowerAnalyzer if available)
# ---------------------------------------------------------------------------

@analytics_bp.route("/followers", methods=["POST"])
@_auth_guard
def follower_analytics():
    """Analyze followers for the authenticated user.

    Expects JSON: {"handle": "optional — defaults to current user"}
    """
    service = _require_service()
    data = request.get_json(silent=True) or {}
    handle = data.get("handle") or service.auth.current_handle

    try:
        from skymarshal.analytics.follower_analyzer import FollowerAnalyzer

        analyzer = FollowerAnalyzer(service.auth)
        result = analyzer.analyze(handle)
        return jsonify({"success": True, "followers": result})
    except ImportError:
        return jsonify({"success": False, "error": "Follower analyzer not available"}), 501
    except Exception as exc:
        logger.error("Follower analytics error: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 400


# ---------------------------------------------------------------------------
# Post analytics (wraps PostAnalyzer if available)
# ---------------------------------------------------------------------------

@analytics_bp.route("/posts", methods=["POST"])
@_auth_guard
def post_analytics():
    """Analyze post engagement patterns.

    Expects JSON: {"limit": 100}
    """
    service = _require_service()
    data = request.get_json(silent=True) or {}
    limit = int(data.get("limit", 100))

    try:
        from skymarshal.analytics.post_analyzer import PostAnalyzer

        analyzer = PostAnalyzer(service.auth)
        result = analyzer.analyze(limit=limit)
        return jsonify({"success": True, "posts": result})
    except ImportError:
        return jsonify({"success": False, "error": "Post analyzer not available"}), 501
    except Exception as exc:
        logger.error("Post analytics error: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 400
