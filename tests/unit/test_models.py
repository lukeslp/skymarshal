"""
Unit tests for Skymarshal data models and utility functions.

Tests core data structures, enums, and utility functions that form
the foundation of the application.
"""
import pytest
from datetime import datetime
from skymarshal.models import (
    ContentItem, UserSettings, SearchFilters, DeleteMode, ContentType,
    parse_datetime, merge_content_items
)


class TestContentItem:
    """Test ContentItem dataclass."""

    def test_content_item_creation(self):
        """Test basic ContentItem creation."""
        item = ContentItem(
            uri="at://did:plc:test/app.bsky.feed.post/123",
            cid="bafyrei123",
            content_type="post",
            text="Test post",
            like_count=5,
            repost_count=2,
            reply_count=1
        )

        assert item.uri == "at://did:plc:test/app.bsky.feed.post/123"
        assert item.content_type == "post"
        assert item.text == "Test post"
        assert item.like_count == 5
        assert item.repost_count == 2
        assert item.reply_count == 1
        assert item.engagement_score == 0.0  # Default

    def test_content_item_defaults(self):
        """Test ContentItem with minimal required fields."""
        item = ContentItem(
            uri="at://did:plc:test/app.bsky.feed.post/456",
            cid="bafyrei456",
            content_type="reply"
        )

        assert item.text is None
        assert item.created_at is None
        assert item.reply_count == 0
        assert item.repost_count == 0
        assert item.like_count == 0
        assert item.engagement_score == 0.0
        assert item.raw_data is None


class TestUserSettings:
    """Test UserSettings dataclass."""

    def test_user_settings_defaults(self):
        """Test UserSettings default values."""
        settings = UserSettings()

        assert settings.download_limit_default == 500
        assert settings.default_categories == ['posts', 'likes', 'reposts']
        assert settings.records_page_size == 100
        assert settings.hydrate_batch_size == 25
        assert settings.category_workers == 3
        assert settings.file_list_page_size == 10
        assert settings.high_engagement_threshold == 20
        assert settings.use_subject_engagement_for_reposts is True
        assert settings.fetch_order == 'newest'
        assert settings.avg_likes_per_post == 0.0
        assert settings.avg_engagement_per_post == 0.0

    def test_user_settings_custom_values(self):
        """Test UserSettings with custom values."""
        settings = UserSettings(
            download_limit_default=1000,
            default_categories=['posts'],
            high_engagement_threshold=50
        )

        assert settings.download_limit_default == 1000
        assert settings.default_categories == ['posts']
        assert settings.high_engagement_threshold == 50


class TestSearchFilters:
    """Test SearchFilters dataclass."""

    def test_search_filters_defaults(self):
        """Test SearchFilters default values."""
        filters = SearchFilters()

        assert filters.keywords is None
        assert filters.min_engagement == 0
        assert filters.max_engagement == 999999
        assert filters.min_likes == 0
        assert filters.max_likes == 999999
        assert filters.min_reposts == 0
        assert filters.max_reposts == 999999
        assert filters.min_replies == 0
        assert filters.max_replies == 999999
        assert filters.content_type == ContentType.ALL
        assert filters.start_date is None
        assert filters.end_date is None
        assert filters.subject_contains is None
        assert filters.subject_handle_contains is None


class TestEnums:
    """Test enum definitions."""

    def test_delete_mode_values(self):
        """Test DeleteMode enum values."""
        assert DeleteMode.ALL_AT_ONCE.value == "all"
        assert DeleteMode.INDIVIDUAL.value == "individual"
        assert DeleteMode.BATCH.value == "batch"
        assert DeleteMode.CANCEL.value == "cancel"

    def test_content_type_values(self):
        """Test ContentType enum values."""
        assert ContentType.ALL.value == "all"
        assert ContentType.POSTS.value == "posts"
        assert ContentType.REPLIES.value == "replies"
        assert ContentType.COMMENTS.value == "comments"
        assert ContentType.REPOSTS.value == "reposts"
        assert ContentType.LIKES.value == "likes"


class TestParseDatetime:
    """Test parse_datetime utility function."""

    def test_parse_none(self):
        """Test parsing None returns None."""
        result = parse_datetime(None)
        assert result is None

    def test_parse_empty_string(self):
        """Test parsing empty string returns None."""
        result = parse_datetime("")
        assert result is None
        result = parse_datetime("   ")
        assert result is None

    def test_parse_date_only(self):
        """Test parsing YYYY-MM-DD format."""
        result = parse_datetime("2023-12-25")
        assert result is not None
        assert result.year == 2023
        assert result.month == 12
        assert result.day == 25

    def test_parse_iso_with_z(self):
        """Test parsing ISO8601 with Z timezone."""
        result = parse_datetime("2023-12-25T15:30:45.123Z")
        assert result is not None
        assert result.year == 2023
        assert result.month == 12
        assert result.day == 25
        assert result.hour == 15
        assert result.minute == 30
        assert result.second == 45

    def test_parse_iso_with_offset(self):
        """Test parsing ISO8601 with timezone offset."""
        result = parse_datetime("2023-12-25T15:30:45.123+00:00")
        assert result is not None
        assert result.year == 2023
        assert result.month == 12
        assert result.day == 25

    def test_parse_invalid_date(self):
        """Test parsing invalid date returns None."""
        result = parse_datetime("not-a-date")
        assert result is None

        result = parse_datetime("2023-13-45")  # Invalid month/day
        assert result is None

    def test_parse_with_default(self):
        """Test parsing with default_on_error parameter."""
        default = datetime(2020, 1, 1)
        result = parse_datetime("invalid", default)
        assert result == default


class TestMergeContentItems:
    """Test merge_content_items utility function."""

    def test_merge_empty_lists(self):
        """Test merging empty lists."""
        result = merge_content_items("posts", [], [])
        assert result == []

    def test_merge_new_items_only(self):
        """Test merging with only new items."""
        new_items = [
            {"uri": "at://test/1", "text": "First"},
            {"uri": "at://test/2", "text": "Second"}
        ]
        result = merge_content_items("posts", new_items, [])
        assert len(result) == 2
        assert result[0]["uri"] == "at://test/1"
        assert result[1]["uri"] == "at://test/2"

    def test_merge_existing_items_only(self):
        """Test merging with only existing items."""
        existing_items = [
            {"uri": "at://test/1", "text": "First"},
            {"uri": "at://test/2", "text": "Second"}
        ]
        result = merge_content_items("posts", [], existing_items)
        assert len(result) == 2

    def test_merge_with_duplicates(self):
        """Test merging with duplicate URIs (new should overwrite existing)."""
        new_items = [
            {"uri": "at://test/1", "text": "Updated First"},
            {"uri": "at://test/3", "text": "Third"}
        ]
        existing_items = [
            {"uri": "at://test/1", "text": "Original First"},
            {"uri": "at://test/2", "text": "Second"}
        ]
        result = merge_content_items("posts", new_items, existing_items)
        assert len(result) == 3

        # Find the updated item
        updated_item = next(item for item in result if item["uri"] == "at://test/1")
        assert updated_item["text"] == "Updated First"

    def test_merge_with_dates_newest_first(self):
        """Test merging with date sorting (newest first)."""
        new_items = [
            {"uri": "at://test/1", "created_at": "2023-01-01T10:00:00Z"},
            {"uri": "at://test/2", "created_at": "2023-01-02T10:00:00Z"}
        ]
        result = merge_content_items("posts", new_items, [], fetch_order="newest")
        assert len(result) == 2
        # Should be sorted newest first
        assert result[0]["uri"] == "at://test/2"  # 2023-01-02 comes first
        assert result[1]["uri"] == "at://test/1"  # 2023-01-01 comes second

    def test_merge_with_dates_oldest_first(self):
        """Test merging with date sorting (oldest first)."""
        new_items = [
            {"uri": "at://test/1", "created_at": "2023-01-02T10:00:00Z"},
            {"uri": "at://test/2", "created_at": "2023-01-01T10:00:00Z"}
        ]
        result = merge_content_items("posts", new_items, [], fetch_order="oldest")
        assert len(result) == 2
        # Should be sorted oldest first
        assert result[0]["uri"] == "at://test/2"  # 2023-01-01 comes first
        assert result[1]["uri"] == "at://test/1"  # 2023-01-02 comes second