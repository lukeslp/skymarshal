"""Firehose API blueprint + SocketIO event handlers.

Provides real-time Bluesky post streaming via SocketIO events:
- 'firehose:post' — emitted for each incoming post
- 'firehose:stats' — emitted every second with current statistics

Also provides REST endpoints for stats and control.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Optional

from flask import Blueprint, jsonify, session

from skymarshal.api import get_services, socketio
from skymarshal.firehose.jetstream import FirehosePost, JetstreamClient

logger = logging.getLogger(__name__)

firehose_bp = Blueprint("firehose", __name__)

# Singleton Jetstream client
_client: Optional[JetstreamClient] = None


def get_jetstream_client() -> JetstreamClient:
    """Get or create the singleton JetstreamClient."""
    global _client
    if _client is None:
        _client = JetstreamClient(
            on_post=_broadcast_post,
        )
    return _client


def _broadcast_post(post: FirehosePost) -> None:
    """Broadcast a post to all connected SocketIO clients."""
    payload = {
        "text": post.text,
        "uri": post.uri,
        "cid": post.cid,
        "author": {
            "did": post.author_did,
            "handle": post.author_handle,
        },
        "createdAt": post.created_at,
        "sentiment": post.sentiment,
        "sentimentScore": post.sentiment_score,
        "language": post.language,
        "hasImages": post.has_images,
        "hasVideo": post.has_video,
        "hasLink": post.has_link,
        "isReply": post.is_reply,
        "isQuote": post.is_quote,
    }
    # Include media if present
    if post.media:
        payload["media"] = post.media

    socketio.emit("firehose:post", payload)


def start_firehose() -> None:
    """Start the Jetstream client in a background task.

    Should be called after Flask-SocketIO is initialized:
        socketio.start_background_task(start_firehose_background)
    """
    client = get_jetstream_client()
    if not client.running:
        logger.info("Starting Jetstream client in background...")
        socketio.start_background_task(client.run)

        # Start stats broadcast loop
        socketio.start_background_task(_stats_loop)


def _stats_loop() -> None:
    """Broadcast firehose stats every second."""
    import time

    client = get_jetstream_client()
    while client.running:
        stats = client.get_stats()
        socketio.emit(
            "firehose:stats",
            {
                "totalPosts": stats.total_posts,
                "postsPerMinute": stats.posts_per_minute,
                "sentimentCounts": stats.sentiment_counts,
                "duration": stats.duration,
                "running": stats.running,
            },
        )
        time.sleep(1)


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------


@firehose_bp.route("/stats", methods=["GET"])
def firehose_stats():
    """Get current firehose statistics."""
    client = get_jetstream_client()
    stats = client.get_stats()
    return jsonify(
        {
            "success": True,
            "stats": {
                "totalPosts": stats.total_posts,
                "postsPerMinute": stats.posts_per_minute,
                "sentimentCounts": stats.sentiment_counts,
                "duration": stats.duration,
                "running": stats.running,
            },
        }
    )


def _is_authenticated() -> bool:
    """Check if the current session has a valid API token."""
    token = session.get("api_token")
    if not token:
        return False
    service = get_services().get(token)
    return service is not None and service.auth.is_authenticated()


@firehose_bp.route("/start", methods=["POST"])
def firehose_start():
    """Start the firehose if not already running. Requires authentication."""
    if not _is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    client = get_jetstream_client()
    if client.running:
        return jsonify({"success": True, "message": "Already running"})
    start_firehose()
    return jsonify({"success": True, "message": "Firehose started"})


@firehose_bp.route("/stop", methods=["POST"])
def firehose_stop():
    """Stop the firehose. Requires authentication."""
    if not _is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    client = get_jetstream_client()
    if not client.running:
        return jsonify({"success": True, "message": "Already stopped"})
    client.stop()
    return jsonify({"success": True, "message": "Firehose stopped"})


@firehose_bp.route("/recent", methods=["GET"])
def firehose_recent():
    """Get recent posts from the firehose buffer."""
    from flask import request

    limit = min(int(request.args.get("limit", 50)), 100)
    client = get_jetstream_client()
    posts = client.get_recent_posts(limit)
    return jsonify(
        {
            "success": True,
            "posts": [
                {
                    "text": p.text,
                    "uri": p.uri,
                    "author": {"did": p.author_did, "handle": p.author_handle},
                    "createdAt": p.created_at,
                    "sentiment": p.sentiment,
                    "sentimentScore": p.sentiment_score,
                    "language": p.language,
                }
                for p in posts
            ],
        }
    )


# ---------------------------------------------------------------------------
# SocketIO event handlers
# ---------------------------------------------------------------------------


@socketio.on("connect")
def handle_connect():
    """Send initial stats and connected ack when a client connects."""
    from flask_socketio import emit

    logger.info("Client connected")
    emit("connected", {"status": "ok"})

    client = get_jetstream_client()
    stats = client.get_stats()
    emit(
        "firehose:stats",
        {
            "totalPosts": stats.total_posts,
            "postsPerMinute": stats.posts_per_minute,
            "sentimentCounts": stats.sentiment_counts,
            "duration": stats.duration,
            "running": stats.running,
        },
    )
