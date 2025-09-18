"""
Skymarshal Data Models and Enums

File Purpose: Core data structures and enumerations for Bluesky content management
Primary Functions/Classes: ContentItem, UserSettings, SearchFilters, DeleteMode, ContentType
Inputs and Outputs (I/O): Data structure definitions, no direct I/O operations

This module defines the fundamental data structures used throughout the application
for representing Bluesky content, user preferences, search criteria, and operational modes.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import lru_cache
from typing import Any, Dict, List, Optional

from rich.console import Console

# Shared console instance for all Skymarshal modules
console = Console()


# Performance utilities for large dataset processing
@lru_cache(maxsize=10000)
def calculate_engagement_score(likes: int, reposts: int, replies: int) -> float:
    """Cached engagement score calculation to avoid repeated computations.

    Weighting: Likes (1x) + Reposts (2x) + Replies (2.5x)
    Rationale: Replies require most effort, reposts show strong approval,
    likes are the baseline engagement. Adjusted for Bluesky engagement patterns.
    """
    return likes + (2 * reposts) + (2.5 * replies)


def bulk_update_engagement_scores(items: List[Any]) -> None:
    """Efficiently update engagement scores for a list of ContentItems."""
    for item in items:
        if hasattr(item, "update_engagement_score"):
            item.update_engagement_score()


class DeleteMode(Enum):
    """Different deletion approval modes."""

    ALL_AT_ONCE = "all"
    INDIVIDUAL = "individual"
    BATCH = "batch"
    CANCEL = "cancel"


class ContentType(Enum):
    """Content type options."""

    ALL = "all"
    POSTS = "posts"
    REPLIES = "replies"
    COMMENTS = "comments"
    REPOSTS = "reposts"
    LIKES = "likes"


@dataclass
class ContentItem:
    """Represents a piece of content from Bluesky."""

    uri: str
    cid: str
    content_type: str
    text: Optional[str] = None
    created_at: Optional[str] = None
    reply_count: int = 0
    repost_count: int = 0
    like_count: int = 0
    engagement_score: float = 0.0
    raw_data: Optional[Dict] = None

    def update_engagement_score(self) -> float:
        """Update and return the cached engagement score."""
        self.engagement_score = calculate_engagement_score(
            self.like_count, self.repost_count, self.reply_count
        )
        return self.engagement_score


@dataclass
class UserSettings:
    """User-adjustable defaults and batch sizes."""

    download_limit_default: int = 500
    default_categories: List[str] = field(
        default_factory=lambda: ["posts", "likes", "reposts"]
    )
    records_page_size: int = 100
    hydrate_batch_size: int = 25
    category_workers: int = 3
    file_list_page_size: int = 10
    high_engagement_threshold: int = 20
    use_subject_engagement_for_reposts: bool = True
    fetch_order: str = "newest"
    # Derived metrics (updated at runtime after data load)
    avg_likes_per_post: float = 0.0
    avg_engagement_per_post: float = 0.0


@dataclass
class SearchFilters:
    """Search and filter criteria."""

    keywords: List[str] = None
    min_engagement: int = 0
    max_engagement: int = 999999
    min_likes: int = 0
    max_likes: int = 999999
    min_reposts: int = 0
    max_reposts: int = 999999
    min_replies: int = 0
    max_replies: int = 999999
    content_type: ContentType = ContentType.ALL
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    subject_contains: Optional[str] = None
    subject_handle_contains: Optional[str] = None


def parse_datetime(
    date_str: Optional[str], default_on_error: Optional[datetime] = None
) -> Optional[datetime]:
    """
    Unified date parsing utility for all Skymarshal modules.

    Handles various ISO8601 formats including:
    - YYYY-MM-DD (date only)
    - YYYY-MM-DDTHH:MM:SS.sssZ (with Z timezone)
    - YYYY-MM-DDTHH:MM:SS.sss+00:00 (with timezone offset)

    Args:
        date_str: Date string to parse, can be None
        default_on_error: Value to return on parse error (None by default)

    Returns:
        Parsed datetime object, default_on_error on failure, or None if date_str is None
    """
    if not date_str:
        return None

    try:
        # Handle simple date format (YYYY-MM-DD)
        if len(date_str) == 10 and date_str[4] == "-" and date_str[7] == "-":
            return datetime.fromisoformat(date_str)
        # Handle ISO8601 with Z timezone marker
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except Exception:
        return default_on_error


def merge_content_items(
    category: str,
    new_items: List[Dict],
    existing_items: List[Dict],
    fetch_order: str = "newest",
) -> List[Dict]:
    """
    Unified content merging utility for deduplicating and sorting content items.

    Args:
        category: Content category ('posts', 'likes', 'reposts')
        new_items: New items to merge in
        existing_items: Existing items to merge with
        fetch_order: Sort order ('newest' or 'oldest')

    Returns:
        Merged and sorted list of content items
    """
    # Merge by URI, with new items overwriting existing ones
    existed = {
        item.get("uri"): item
        for item in existing_items
        if isinstance(item, dict) and item.get("uri")
    }
    for item in new_items:
        existed[item.get("uri")] = item
    items = list(existed.values())

    # Sort by creation date if applicable - optimized single-pass categorization
    if category in ("posts", "likes", "reposts"):

        def to_dt(s):
            return parse_datetime(s) or datetime.min

        # Single pass to separate items with/without dates
        items_with_dates = []
        items_without_dates = []
        for item in items:
            if item.get("created_at"):
                items_with_dates.append(item)
            else:
                items_without_dates.append(item)

        # Sort items with dates
        items_with_dates.sort(
            key=lambda it: to_dt(it.get("created_at")),
            reverse=(fetch_order == "newest"),
        )

        # Combine: items with dates first (sorted), then items without dates
        items = items_with_dates + items_without_dates

    return items
