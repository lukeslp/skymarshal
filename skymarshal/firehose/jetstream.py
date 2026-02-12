"""Jetstream WebSocket client for real-time Bluesky posts.

Ported from firehose/server/firehose.ts.
Uses websocket-client (sync) — designed to run in a background greenlet
via socketio.start_background_task() for eventlet compatibility.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

JETSTREAM_URI = (
    "wss://jetstream2.us-east.bsky.network/subscribe"
    "?wantedCollections=app.bsky.feed.post"
    "&wantedEvents=identity"
)
MAX_TEXT_LENGTH = 10000
RECONNECT_DELAY = 5


@dataclass
class FirehosePost:
    text: str
    uri: str
    cid: str
    author_did: str
    author_handle: str
    created_at: str
    sentiment: str  # "positive", "negative", "neutral"
    sentiment_score: float
    language: str = "unknown"
    has_images: bool = False
    has_video: bool = False
    has_link: bool = False
    is_reply: bool = False
    is_quote: bool = False


@dataclass
class FirehoseStats:
    total_posts: int = 0
    posts_per_minute: float = 0.0
    sentiment_counts: Dict[str, int] = field(
        default_factory=lambda: {"positive": 0, "negative": 0, "neutral": 0}
    )
    duration: int = 0
    running: bool = False


class JetstreamClient:
    """Sync WebSocket client for Bluesky Jetstream.

    Connects to the Jetstream WebSocket API and processes incoming posts.
    Designed to run in a background thread/greenlet.

    Usage with Flask-SocketIO:
        client = JetstreamClient(on_post=handle_post)
        socketio.start_background_task(client.run)
    """

    def __init__(
        self,
        *,
        on_post: Optional[Callable[[FirehosePost], None]] = None,
        on_stats: Optional[Callable[[FirehoseStats], None]] = None,
        uri: str = JETSTREAM_URI,
    ) -> None:
        self._uri = uri
        self._on_post = on_post
        self._on_stats = on_stats
        self._running = False
        self._handle_cache: Dict[str, str] = {}  # DID -> handle

        # Statistics
        self._total_processed = 0
        self._sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}
        self._start_time: Optional[float] = None
        self._recent_timestamps: List[float] = []
        self._recent_posts: List[FirehosePost] = []

    @property
    def running(self) -> bool:
        return self._running

    def get_stats(self) -> FirehoseStats:
        """Return current statistics."""
        now = time.time()

        # Calculate posts per minute from last 60 seconds
        self._recent_timestamps = [
            ts for ts in self._recent_timestamps if now - ts < 60
        ]
        ppm = 0.0
        if self._recent_timestamps:
            oldest = min(self._recent_timestamps)
            elapsed = now - oldest
            if elapsed > 0:
                ppm = round((len(self._recent_timestamps) / elapsed) * 60)

        duration = int(now - self._start_time) if self._start_time else 0

        return FirehoseStats(
            total_posts=self._total_processed,
            posts_per_minute=ppm,
            sentiment_counts=dict(self._sentiment_counts),
            duration=duration,
            running=self._running,
        )

    def get_recent_posts(self, limit: int = 50) -> List[FirehosePost]:
        return self._recent_posts[:limit]

    def stop(self) -> None:
        """Signal the client to stop."""
        logger.info("Jetstream client stopping...")
        self._running = False

    def run(self) -> None:
        """Main loop — connect and process messages. Auto-reconnects on failure.

        This method blocks and should be run in a background task:
            socketio.start_background_task(client.run)
        """
        import websocket  # websocket-client (sync)

        self._running = True
        self._start_time = time.time()
        logger.info("Jetstream client starting...")

        while self._running:
            try:
                ws = websocket.WebSocket()
                ws.settimeout(30)
                ws.connect(self._uri)
                logger.info("Connected to Jetstream")

                while self._running:
                    try:
                        raw = ws.recv()
                        if raw:
                            self._handle_message(raw)
                    except websocket.WebSocketTimeoutException:
                        continue  # Normal — no message within timeout
                    except websocket.WebSocketConnectionClosedException:
                        logger.warning("Jetstream connection closed")
                        break

                ws.close()

            except Exception as exc:
                logger.error("Jetstream connection error: %s", exc)

            if self._running:
                logger.info("Reconnecting in %ds...", RECONNECT_DELAY)
                time.sleep(RECONNECT_DELAY)

        logger.info("Jetstream client stopped")

    def _handle_message(self, raw: str) -> None:
        """Parse and process a Jetstream message."""
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            return

        # Handle identity events (DID -> handle mapping)
        if message.get("kind") == "identity":
            identity = message.get("identity", {})
            handle = identity.get("handle")
            did = identity.get("did") or message.get("did")
            if handle and did:
                self._handle_cache[did] = handle
            return

        # Only process post commits
        if message.get("kind") != "commit":
            return
        commit = message.get("commit", {})
        if commit.get("operation") != "create":
            return

        record = commit.get("record")
        if not record or not record.get("text"):
            return

        text = record["text"]
        if len(text) > MAX_TEXT_LENGTH:
            text = text[:MAX_TEXT_LENGTH]

        # Analyze sentiment and features
        from skymarshal.firehose.sentiment import analyze_sentiment
        from skymarshal.firehose.features import extract_features

        sentiment_result = analyze_sentiment(text)
        features = extract_features(text, record)

        # Build post object
        author_did = message.get("did", "")
        author_handle = self._handle_cache.get(author_did, author_did)

        uri = commit.get("uri") or (
            f"at://{author_did}/app.bsky.feed.post/{commit.get('rkey', '')}"
        )

        post = FirehosePost(
            text=text,
            uri=uri,
            cid=commit.get("cid", ""),
            author_did=author_did,
            author_handle=author_handle,
            created_at=record.get("createdAt", ""),
            sentiment=sentiment_result.classification,
            sentiment_score=sentiment_result.comparative,
            language=features.language,
            has_images=features.has_images,
            has_video=features.has_video,
            has_link=features.has_link,
            is_reply=features.is_reply,
            is_quote=features.is_quote,
        )

        # Update statistics
        self._total_processed += 1
        self._sentiment_counts[sentiment_result.classification] += 1
        self._recent_timestamps.append(time.time())

        # Keep recent posts buffer
        self._recent_posts.insert(0, post)
        if len(self._recent_posts) > 100:
            self._recent_posts.pop()

        # Emit post to callback
        if self._on_post:
            try:
                self._on_post(post)
            except Exception as exc:
                logger.error("Error in post callback: %s", exc)
