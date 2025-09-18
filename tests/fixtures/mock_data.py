"""
Mock data and fixtures for Skymarshal tests.

Provides realistic test data that mirrors actual Bluesky API responses
and data structures used throughout the application.
"""
from datetime import datetime
from typing import List, Dict, Any
from skymarshal.models import ContentItem, UserSettings


def create_mock_content_item(
    uri: str = "at://did:plc:test123/app.bsky.feed.post/123",
    cid: str = "bafyrei123456789",
    content_type: str = "post",
    text: str = "This is a test post",
    created_at: str = "2023-01-01T10:00:00Z",
    like_count: int = 5,
    repost_count: int = 2,
    reply_count: int = 1,
    **kwargs
) -> ContentItem:
    """Create a mock ContentItem with default or custom values."""
    return ContentItem(
        uri=uri,
        cid=cid,
        content_type=content_type,
        text=text,
        created_at=created_at,
        like_count=like_count,
        repost_count=repost_count,
        reply_count=reply_count,
        engagement_score=like_count + 2*repost_count + 2.5*reply_count,
        **kwargs
    )


def create_mock_posts_dataset(count: int = 10) -> List[ContentItem]:
    """Create a dataset of mock posts with varying engagement."""
    posts = []
    base_date = datetime(2023, 1, 1)

    for i in range(count):
        # Create varied engagement patterns
        like_count = i * 2 if i % 3 != 0 else 0  # Some posts have no likes
        repost_count = i // 2 if i % 5 != 0 else 0
        reply_count = i // 3 if i % 7 != 0 else 0

        # Stagger creation dates
        created_at = base_date.replace(day=min(28, i + 1))

        post = create_mock_content_item(
            uri=f"at://did:plc:test123/app.bsky.feed.post/{i+1:03d}",
            cid=f"bafyrei{i+1:09d}",
            text=f"Test post number {i+1} with varying content length {'.' * (i % 20)}",
            created_at=created_at.isoformat() + "Z",
            like_count=like_count,
            repost_count=repost_count,
            reply_count=reply_count
        )
        posts.append(post)

    return posts


def create_mock_likes_dataset(count: int = 5) -> List[ContentItem]:
    """Create a dataset of mock likes."""
    likes = []

    for i in range(count):
        like = create_mock_content_item(
            uri=f"at://did:plc:test123/app.bsky.feed.like/{i+1:03d}",
            cid=f"bafyreilike{i+1:06d}",
            content_type="like",
            text=None,  # Likes don't have text
            created_at=f"2023-01-{i+1:02d}T12:00:00Z",
            like_count=0,  # Likes themselves don't have engagement
            repost_count=0,
            reply_count=0,
            raw_data={
                "subject_uri": f"at://did:plc:other/app.bsky.feed.post/{i+1}",
                "subject_like_count": i * 3,
                "subject_repost_count": i,
                "subject_reply_count": i // 2
            }
        )
        likes.append(like)

    return likes


def create_mock_reposts_dataset(count: int = 3) -> List[ContentItem]:
    """Create a dataset of mock reposts."""
    reposts = []

    for i in range(count):
        repost = create_mock_content_item(
            uri=f"at://did:plc:test123/app.bsky.feed.repost/{i+1:03d}",
            cid=f"bafyreirp{i+1:07d}",
            content_type="repost",
            text=None,  # Reposts don't have text
            created_at=f"2023-01-{i+10:02d}T15:00:00Z",
            like_count=0,  # Reposts themselves don't have engagement
            repost_count=0,
            reply_count=0,
            raw_data={
                "subject_uri": f"at://did:plc:other/app.bsky.feed.post/{i+10}",
                "subject_like_count": (i + 1) * 5,
                "subject_repost_count": i + 2,
                "subject_reply_count": i + 1
            }
        )
        reposts.append(repost)

    return reposts


def create_mixed_content_dataset() -> List[ContentItem]:
    """Create a mixed dataset with posts, likes, and reposts."""
    posts = create_mock_posts_dataset(7)
    likes = create_mock_likes_dataset(3)
    reposts = create_mock_reposts_dataset(2)

    return posts + likes + reposts


def create_mock_user_settings() -> UserSettings:
    """Create mock user settings for testing."""
    return UserSettings(
        download_limit_default=100,
        default_categories=['posts', 'likes'],
        records_page_size=50,
        hydrate_batch_size=10,
        category_workers=2,
        high_engagement_threshold=15,
        fetch_order='newest'
    )


def create_mock_json_export_data() -> Dict[str, Any]:
    """Create mock JSON export data structure."""
    posts = create_mock_posts_dataset(5)
    likes = create_mock_likes_dataset(2)
    reposts = create_mock_reposts_dataset(1)

    # Convert ContentItems back to dict format (as they would be saved)
    export_data = {
        "posts": [
            {
                "uri": post.uri,
                "cid": post.cid,
                "text": post.text,
                "created_at": post.created_at,
                "like_count": post.like_count,
                "repost_count": post.repost_count,
                "reply_count": post.reply_count,
                "raw_data": post.raw_data
            }
            for post in posts
        ],
        "likes": [
            {
                "uri": like.uri,
                "cid": like.cid,
                "created_at": like.created_at,
                "raw_data": like.raw_data
            }
            for like in likes
        ],
        "reposts": [
            {
                "uri": repost.uri,
                "cid": repost.cid,
                "created_at": repost.created_at,
                "raw_data": repost.raw_data
            }
            for repost in reposts
        ]
    }

    return export_data


def create_mock_atproto_profile(handle: str = "test.bsky.social") -> object:
    """Create a mock AT Protocol profile response."""
    class MockProfile:
        def __init__(self, handle: str):
            self.did = f"did:plc:{handle.replace('.', '').replace('@', '')}"
            self.handle = handle
            self.display_name = f"Test User ({handle})"
            self.description = "Test user profile"

    return MockProfile(handle)


def create_mock_atproto_records_response(records: List[Dict[str, Any]], cursor: str = None) -> object:
    """Create a mock AT Protocol listRecords response."""
    class MockRecord:
        def __init__(self, uri: str, cid: str, value: Dict[str, Any]):
            self.uri = uri
            self.cid = cid
            self.value = value

    class MockResponse:
        def __init__(self, records_data: List[Dict[str, Any]], cursor: str = None):
            self.records = [
                MockRecord(
                    uri=record["uri"],
                    cid=record["cid"],
                    value=record.get("value", {})
                )
                for record in records_data
            ]
            self.cursor = cursor

    return MockResponse(records, cursor)


# Test data constants
SAMPLE_POST_URI = "at://did:plc:test123/app.bsky.feed.post/sample123"
SAMPLE_LIKE_URI = "at://did:plc:test123/app.bsky.feed.like/sample456"
SAMPLE_REPOST_URI = "at://did:plc:test123/app.bsky.feed.repost/sample789"

SAMPLE_HANDLE = "testuser.bsky.social"
SAMPLE_DID = "did:plc:testuser123456789"

# Performance test data
def create_large_dataset(post_count: int = 1000, like_count: int = 500, repost_count: int = 100) -> List[ContentItem]:
    """Create a large dataset for performance testing."""
    items = []

    # Create posts with realistic distribution
    for i in range(post_count):
        # Simulate real engagement patterns
        like_count_val = max(0, int((i % 50) * (1.2 + (i % 10) * 0.1)))
        repost_count_val = max(0, int(like_count_val * 0.1))
        reply_count_val = max(0, int(like_count_val * 0.05))

        post = create_mock_content_item(
            uri=f"at://did:plc:test123/app.bsky.feed.post/perf{i:06d}",
            cid=f"bafyreiperformance{i:08d}",
            text=f"Performance test post {i} " + "content " * (i % 20),
            created_at=f"2023-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}T{(i % 24):02d}:00:00Z",
            like_count=like_count_val,
            repost_count=repost_count_val,
            reply_count=reply_count_val
        )
        items.append(post)

    # Add likes and reposts
    items.extend(create_mock_likes_dataset(like_count))
    items.extend(create_mock_reposts_dataset(repost_count))

    return items
