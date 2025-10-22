"""
Tests for Engagement Cache

Test coverage for SQLite-based engagement caching with TTL support.
"""

import tempfile
import time
from pathlib import Path

import pytest

from skymarshal.engagement_cache import EngagementCache
from skymarshal.models import ContentItem


class TestEngagementCache:
    """Test suite for EngagementCache."""

    @pytest.fixture
    def temp_cache(self):
        """Create a temporary cache database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            cache_path = Path(f.name)
        
        cache = EngagementCache(cache_path)
        yield cache
        
        # Cleanup
        cache_path.unlink(missing_ok=True)

    def test_cache_initialization(self, temp_cache):
        """Test cache database initialization."""
        assert temp_cache.db_path.exists()
        stats = temp_cache.get_stats()
        assert stats["total_entries"] == 0
        assert stats["fresh_entries"] == 0
        assert stats["expired_entries"] == 0

    def test_cache_set_and_get(self, temp_cache):
        """Test setting and getting cached engagement data."""
        uri = "at://did:plc:test/app.bsky.feed.post/123"
        temp_cache.set(uri, like_count=10, repost_count=5, reply_count=2, ttl=3600)
        
        result = temp_cache.get(uri)
        assert result is not None
        assert result["like_count"] == 10
        assert result["repost_count"] == 5
        assert result["reply_count"] == 2

    def test_cache_get_expired(self, temp_cache):
        """Test that expired cache entries return None."""
        uri = "at://did:plc:test/app.bsky.feed.post/456"
        # Set with 0 TTL (immediately expired)
        temp_cache.set(uri, like_count=10, repost_count=5, reply_count=2, ttl=0)
        
        time.sleep(0.1)  # Wait a bit
        result = temp_cache.get(uri)
        assert result is None

    def test_cache_get_batch(self, temp_cache):
        """Test batch retrieval of cached data."""
        uris = [
            "at://did:plc:test/app.bsky.feed.post/1",
            "at://did:plc:test/app.bsky.feed.post/2",
            "at://did:plc:test/app.bsky.feed.post/3",
        ]
        
        # Cache data for all URIs
        for i, uri in enumerate(uris, 1):
            temp_cache.set(uri, like_count=i * 10, repost_count=i * 5, reply_count=i * 2, ttl=3600)
        
        # Retrieve batch
        results = temp_cache.get_batch(uris)
        assert len(results) == 3
        assert results[uris[0]]["like_count"] == 10
        assert results[uris[1]]["like_count"] == 20
        assert results[uris[2]]["like_count"] == 30

    def test_cache_set_batch(self, temp_cache):
        """Test batch setting of engagement data."""
        items = [
            ContentItem(
                uri="at://did:plc:test/app.bsky.feed.post/1",
                cid="cid1",
                content_type="post",
                like_count=10,
                repost_count=5,
                reply_count=2,
            ),
            ContentItem(
                uri="at://did:plc:test/app.bsky.feed.post/2",
                cid="cid2",
                content_type="post",
                like_count=20,
                repost_count=10,
                reply_count=4,
            ),
        ]
        
        temp_cache.set_batch(items, ttl=3600)
        
        # Verify data was cached
        result1 = temp_cache.get(items[0].uri)
        result2 = temp_cache.get(items[1].uri)
        
        assert result1["like_count"] == 10
        assert result2["like_count"] == 20

    def test_cache_apply_cached_engagement(self, temp_cache):
        """Test applying cached engagement to items."""
        # Create items
        items = [
            ContentItem(
                uri="at://did:plc:test/app.bsky.feed.post/1",
                cid="cid1",
                content_type="post",
                like_count=0,
                repost_count=0,
                reply_count=0,
            ),
            ContentItem(
                uri="at://did:plc:test/app.bsky.feed.post/2",
                cid="cid2",
                content_type="post",
                like_count=0,
                repost_count=0,
                reply_count=0,
            ),
            ContentItem(
                uri="at://did:plc:test/app.bsky.feed.post/3",
                cid="cid3",
                content_type="post",
                like_count=0,
                repost_count=0,
                reply_count=0,
            ),
        ]
        
        # Cache data for first two items only
        temp_cache.set(items[0].uri, like_count=10, repost_count=5, reply_count=2, ttl=3600)
        temp_cache.set(items[1].uri, like_count=20, repost_count=10, reply_count=4, ttl=3600)
        
        # Apply cached data
        cached, uncached = temp_cache.apply_cached_engagement(items)
        
        assert len(cached) == 2
        assert len(uncached) == 1
        assert cached[0].like_count == 10
        assert cached[1].like_count == 20
        assert uncached[0].uri == items[2].uri

    def test_cache_ttl_calculation(self, temp_cache):
        """Test TTL calculation based on post age."""
        from datetime import datetime, timedelta
        
        # Recent post (< 7 days)
        recent_date = (datetime.now() - timedelta(days=3)).isoformat()
        ttl_recent = temp_cache._calculate_ttl(recent_date)
        assert ttl_recent == 3600  # 1 hour
        
        # Medium age post (7-30 days)
        medium_date = (datetime.now() - timedelta(days=15)).isoformat()
        ttl_medium = temp_cache._calculate_ttl(medium_date)
        assert ttl_medium == 21600  # 6 hours
        
        # Old post (> 30 days)
        old_date = (datetime.now() - timedelta(days=60)).isoformat()
        ttl_old = temp_cache._calculate_ttl(old_date)
        assert ttl_old == 86400  # 24 hours

    def test_cache_clear_expired(self, temp_cache):
        """Test clearing expired cache entries."""
        # Add fresh and expired entries
        temp_cache.set("at://did:plc:test/1", 10, 5, 2, ttl=3600)  # Fresh
        temp_cache.set("at://did:plc:test/2", 10, 5, 2, ttl=0)     # Expired
        
        time.sleep(0.1)
        deleted = temp_cache.clear_expired()
        
        assert deleted == 1
        stats = temp_cache.get_stats()
        assert stats["total_entries"] == 1
        assert stats["fresh_entries"] == 1

    def test_cache_clear_all(self, temp_cache):
        """Test clearing all cache entries."""
        # Add entries
        temp_cache.set("at://did:plc:test/1", 10, 5, 2)
        temp_cache.set("at://did:plc:test/2", 20, 10, 4)
        
        temp_cache.clear_all()
        
        stats = temp_cache.get_stats()
        assert stats["total_entries"] == 0

    def test_cache_stats(self, temp_cache):
        """Test cache statistics."""
        # Add mix of fresh and expired entries
        temp_cache.set("at://did:plc:test/1", 10, 5, 2, ttl=3600)
        temp_cache.set("at://did:plc:test/2", 20, 10, 4, ttl=3600)
        temp_cache.set("at://did:plc:test/3", 30, 15, 6, ttl=0)
        
        time.sleep(0.1)
        stats = temp_cache.get_stats()
        
        assert stats["total_entries"] == 3
        assert stats["fresh_entries"] == 2
        assert stats["expired_entries"] == 1

    def test_cache_update_existing(self, temp_cache):
        """Test updating existing cache entries."""
        uri = "at://did:plc:test/app.bsky.feed.post/123"
        
        # Initial cache
        temp_cache.set(uri, like_count=10, repost_count=5, reply_count=2, ttl=3600)
        result1 = temp_cache.get(uri)
        assert result1["like_count"] == 10
        
        # Update cache
        temp_cache.set(uri, like_count=20, repost_count=10, reply_count=4, ttl=3600)
        result2 = temp_cache.get(uri)
        assert result2["like_count"] == 20

    def test_cache_empty_batch(self, temp_cache):
        """Test batch operations with empty lists."""
        # Empty get_batch
        results = temp_cache.get_batch([])
        assert results == {}
        
        # Empty set_batch
        temp_cache.set_batch([])
        stats = temp_cache.get_stats()
        assert stats["total_entries"] == 0

    def test_cache_repr(self, temp_cache):
        """Test cache string representation."""
        temp_cache.set("at://did:plc:test/1", 10, 5, 2, ttl=3600)
        repr_str = repr(temp_cache)
        assert "EngagementCache" in repr_str
        assert "total=1" in repr_str
        assert "fresh=1" in repr_str

    def test_cache_vacuum(self, temp_cache):
        """Test database vacuum operation."""
        # Add and remove some data to create fragmentation
        for i in range(100):
            temp_cache.set(f"at://did:plc:test/{i}", 10, 5, 2, ttl=0)
        
        temp_cache.clear_expired()
        
        # Vacuum should run without error
        temp_cache.vacuum()
        
        # Database should still be valid
        temp_cache.set("at://did:plc:test/new", 10, 5, 2, ttl=3600)
        result = temp_cache.get("at://did:plc:test/new")
        assert result is not None

    def test_cache_large_batch(self, temp_cache):
        """Test handling of large batches (> 999 parameters)."""
        # Create 1500 URIs (exceeds SQLite parameter limit of 999)
        uris = [f"at://did:plc:test/post/{i}" for i in range(1500)]
        
        # Cache all URIs
        for uri in uris:
            temp_cache.set(uri, like_count=10, repost_count=5, reply_count=2, ttl=3600)
        
        # Retrieve all in batch
        results = temp_cache.get_batch(uris)
        assert len(results) == 1500
