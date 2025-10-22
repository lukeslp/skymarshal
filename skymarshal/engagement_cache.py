"""
Skymarshal Engagement Cache

File Purpose: SQLite-based caching for engagement data (likes, reposts, replies)
Primary Functions/Classes: EngagementCache
Inputs and Outputs (I/O): SQLite database operations, engagement data storage/retrieval

This module provides an efficient caching layer for engagement data to minimize API calls.
Cache entries have configurable TTL (time-to-live) values based on post age, with automatic
expiration and cleanup of stale entries.
"""

import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .models import ContentItem, console, parse_datetime


class EngagementCache:
    """SQLite-based cache for engagement data with TTL support."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize engagement cache.

        Args:
            db_path: Path to SQLite database file. Defaults to ~/.skymarshal/engagement_cache.db
        """
        if db_path is None:
            db_path = Path.home() / ".skymarshal" / "engagement_cache.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database schema
        self._init_db()

    def _init_db(self):
        """Initialize database schema if not exists."""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS engagement (
                    uri TEXT PRIMARY KEY,
                    like_count INTEGER NOT NULL DEFAULT 0,
                    repost_count INTEGER NOT NULL DEFAULT 0,
                    reply_count INTEGER NOT NULL DEFAULT 0,
                    last_updated INTEGER NOT NULL,
                    ttl INTEGER NOT NULL DEFAULT 3600,
                    created_at TEXT
                )
            """
            )

            # Create index for faster expiration queries
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_expiration 
                ON engagement(last_updated, ttl)
            """
            )

            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def get(self, uri: str) -> Optional[Dict[str, int]]:
        """Get cached engagement data if fresh.

        Args:
            uri: Content URI

        Returns:
            Dict with like_count, repost_count, reply_count if cache is fresh, None otherwise
        """
        with self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT like_count, repost_count, reply_count, last_updated, ttl
                FROM engagement
                WHERE uri = ?
            """,
                (uri,),
            ).fetchone()

            if row:
                last_updated = row["last_updated"]
                ttl = row["ttl"]
                current_time = int(time.time())

                # Check if cache entry is still fresh
                if current_time - last_updated < ttl:
                    return {
                        "like_count": row["like_count"],
                        "repost_count": row["repost_count"],
                        "reply_count": row["reply_count"],
                    }

        return None

    def get_batch(self, uris: List[str]) -> Dict[str, Dict[str, int]]:
        """Get cached engagement data for multiple URIs.

        Args:
            uris: List of content URIs

        Returns:
            Dict mapping URI to engagement data for fresh cache entries
        """
        if not uris:
            return {}

        results = {}
        current_time = int(time.time())

        with self._get_connection() as conn:
            # SQLite has a limit on the number of parameters, so batch the queries
            batch_size = 999
            for i in range(0, len(uris), batch_size):
                batch = uris[i : i + batch_size]
                placeholders = ",".join("?" * len(batch))

                rows = conn.execute(
                    f"""
                    SELECT uri, like_count, repost_count, reply_count, last_updated, ttl
                    FROM engagement
                    WHERE uri IN ({placeholders})
                """,
                    batch,
                ).fetchall()

                for row in rows:
                    last_updated = row["last_updated"]
                    ttl = row["ttl"]

                    # Only return fresh cache entries
                    if current_time - last_updated < ttl:
                        results[row["uri"]] = {
                            "like_count": row["like_count"],
                            "repost_count": row["repost_count"],
                            "reply_count": row["reply_count"],
                        }

        return results

    def set(
        self,
        uri: str,
        like_count: int,
        repost_count: int,
        reply_count: int,
        ttl: Optional[int] = None,
        created_at: Optional[str] = None,
    ):
        """Cache engagement data for a URI.

        Args:
            uri: Content URI
            like_count: Number of likes
            repost_count: Number of reposts
            reply_count: Number of replies
            ttl: Time-to-live in seconds (auto-calculated if None)
            created_at: Content creation timestamp (for auto-TTL calculation)
        """
        # Auto-calculate TTL based on post age if not provided
        if ttl is None:
            ttl = self._calculate_ttl(created_at)

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO engagement
                (uri, like_count, repost_count, reply_count, last_updated, ttl, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    uri,
                    like_count,
                    repost_count,
                    reply_count,
                    int(time.time()),
                    ttl,
                    created_at,
                ),
            )
            conn.commit()

    def set_batch(self, items: List[ContentItem], ttl: Optional[int] = None):
        """Cache engagement data for multiple items.

        Args:
            items: List of ContentItem objects
            ttl: Time-to-live in seconds (auto-calculated if None)
        """
        if not items:
            return

        current_time = int(time.time())

        with self._get_connection() as conn:
            data = [
                (
                    item.uri,
                    item.like_count,
                    item.repost_count,
                    item.reply_count,
                    current_time,
                    ttl if ttl else self._calculate_ttl(item.created_at),
                    item.created_at,
                )
                for item in items
                if item.uri
            ]

            conn.executemany(
                """
                INSERT OR REPLACE INTO engagement
                (uri, like_count, repost_count, reply_count, last_updated, ttl, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                data,
            )
            conn.commit()

    def _calculate_ttl(self, created_at: Optional[str]) -> int:
        """Calculate TTL based on post age.

        Strategy:
        - Posts < 7 days old: 1 hour TTL (engagement still active)
        - Posts 7-30 days old: 6 hours TTL (engagement slowing down)
        - Posts > 30 days old: 24 hours TTL (engagement mostly stable)
        - Unknown age: 1 hour TTL (conservative)

        Args:
            created_at: ISO timestamp string

        Returns:
            TTL in seconds
        """
        if not created_at:
            return 3600  # 1 hour default

        try:
            post_date = parse_datetime(created_at)
            if not post_date:
                return 3600

            age = datetime.now(post_date.tzinfo) - post_date
            age_days = age.days

            if age_days < 7:
                return 3600  # 1 hour
            elif age_days < 30:
                return 21600  # 6 hours
            else:
                return 86400  # 24 hours

        except Exception:
            return 3600  # 1 hour on error

    def clear_expired(self) -> int:
        """Remove expired cache entries.

        Returns:
            Number of entries removed
        """
        current_time = int(time.time())

        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                DELETE FROM engagement
                WHERE (last_updated + ttl) < ?
            """,
                (current_time,),
            )
            deleted = cursor.rowcount
            conn.commit()

        return deleted

    def clear_all(self):
        """Clear all cache entries."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM engagement")
            conn.commit()

    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics.

        Returns:
            Dict with total entries, fresh entries, and expired entries
        """
        current_time = int(time.time())

        with self._get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) as count FROM engagement").fetchone()[
                "count"
            ]

            fresh = conn.execute(
                """
                SELECT COUNT(*) as count FROM engagement
                WHERE (last_updated + ttl) >= ?
            """,
                (current_time,),
            ).fetchone()["count"]

            expired = total - fresh

        return {
            "total_entries": total,
            "fresh_entries": fresh,
            "expired_entries": expired,
        }

    def apply_cached_engagement(
        self, items: List[ContentItem]
    ) -> Tuple[List[ContentItem], List[ContentItem]]:
        """Apply cached engagement data to items.

        Args:
            items: List of ContentItem objects

        Returns:
            Tuple of (cached_items, uncached_items)
        """
        if not items:
            return [], []

        # Get all URIs
        uris = [item.uri for item in items if item.uri]
        if not uris:
            return [], items

        # Fetch cached data
        cached_data = self.get_batch(uris)

        # Split items into cached and uncached
        cached_items = []
        uncached_items = []

        for item in items:
            if item.uri in cached_data:
                # Apply cached engagement
                data = cached_data[item.uri]
                item.like_count = data["like_count"]
                item.repost_count = data["repost_count"]
                item.reply_count = data["reply_count"]
                item.update_engagement_score()
                cached_items.append(item)
            else:
                uncached_items.append(item)

        return cached_items, uncached_items

    def vacuum(self):
        """Optimize database by reclaiming space and defragmenting."""
        with self._get_connection() as conn:
            conn.execute("VACUUM")

    def get_cache_size(self) -> int:
        """Get database file size in bytes.

        Returns:
            Size in bytes
        """
        if self.db_path.exists():
            return self.db_path.stat().st_size
        return 0

    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"EngagementCache(db={self.db_path}, "
            f"total={stats['total_entries']}, "
            f"fresh={stats['fresh_entries']}, "
            f"expired={stats['expired_entries']})"
        )
