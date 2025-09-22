"""Utility functions for the site_codex Flask app.

These helpers wrap the existing Skymarshal managers to provide a single
call that authenticates the user, downloads their CAR archive, imports it,
hydrates engagement metrics, and returns aggregate statistics for display.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from skymarshal.auth import AuthManager
from skymarshal.data_manager import DataManager
from skymarshal.exceptions import AuthenticationError
from skymarshal.models import ContentItem, UserSettings

SESSION_FILE = Path.home() / ".skymarshal" / "session.json"


class ProcessingError(RuntimeError):
    """Raised when any stage of the data pipeline fails."""


@dataclass
class UserDataResult:
    """Bundle of derived statistics returned to the UI."""

    handle: str
    car_path: Path
    export_path: Path
    statistics: Dict[str, float]
    top_posts: List[Dict[str, object]]


def _ensure_storage_dirs(base_dir: Path) -> None:
    """Create the Skymarshal storage directories that DataManager expects."""
    base_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / "cars").mkdir(parents=True, exist_ok=True)
    (base_dir / "json").mkdir(parents=True, exist_ok=True)


def _calculate_statistics(
    items: Iterable[ContentItem],
) -> Tuple[Dict[str, float], List[Dict[str, object]]]:
    """Derive engagement metrics from the exported content items."""
    posts = []
    likes = 0
    reposts = 0
    replies_total = 0
    quotes_total = 0

    total_engagement = 0
    engaged_posts = 0

    for item in items:
        if item.content_type == "post":
            posts.append(item)
            raw = item.raw_data or {}
            reply_list = raw.get("replies") or []
            quote_list = raw.get("quotes") or []

            reply_count = max(item.reply_count or 0, len(reply_list))
            quote_count = max(item.quote_count or 0, len(quote_list))

            replies_total += reply_count
            quotes_total += quote_count

            engagement = (
                (item.like_count or 0)
                + (item.repost_count or 0)
                + reply_count
                + quote_count
            )
            total_engagement += engagement
            if engagement:
                engaged_posts += 1
        elif item.content_type == "like":
            likes += 1
        elif item.content_type == "repost":
            reposts += 1

    post_count = len(posts)
    avg_engagement = total_engagement / post_count if post_count else 0.0
    engagement_rate = (engaged_posts / post_count * 100) if post_count else 0.0

    top_posts = sorted(
        (
            {
                "uri": post.uri,
                "text": (post.text or "").strip(),
                "likes": post.like_count,
                "reposts": post.repost_count,
                "replies": max(post.reply_count or 0, len((post.raw_data or {}).get("replies") or [])),
                "quotes": max(post.quote_count or 0, len((post.raw_data or {}).get("quotes") or [])),
                "engagement": (post.like_count or 0)
                + (post.repost_count or 0)
                + max(post.reply_count or 0, len((post.raw_data or {}).get("replies") or []))
                + max(post.quote_count or 0, len((post.raw_data or {}).get("quotes") or [])),
                "created_at": post.created_at,
                "samples": {
                    "likes": (post.raw_data or {}).get("likes", [])[:10],
                    "reposted_by": (post.raw_data or {}).get("reposted_by", [])[:10],
                    "quotes": (post.raw_data or {}).get("quotes", [])[:10],
                    "replies": (post.raw_data or {}).get("replies", [])[:10],
                },
            }
            for post in posts
        ),
        key=lambda entry: entry["engagement"],
        reverse=True,
    )[:5]

    return (
        {
            "total_items": float(post_count + likes + reposts),
            "posts": float(post_count),
            "likes": float(likes),
            "reposts": float(reposts),
            "replies": float(replies_total),
            "quotes": float(quotes_total),
            "total_engagement": float(total_engagement),
            "avg_engagement": float(avg_engagement),
            "engagement_rate": float(engagement_rate),
            "top_posts_count": float(len(top_posts)),
        },
        top_posts,
    )


def process_user_data(handle: str, password: str) -> UserDataResult:
    """Authenticate, fetch, import, and analyze the user's data."""
    if not handle or not password:
        raise ProcessingError("Handle and password are required.")

    auth_manager = AuthManager()
    normalized = auth_manager.normalize_handle(handle)

    if not auth_manager.authenticate_client(normalized, password):
        raise ProcessingError("Authentication failed. Please recheck credentials.")

    # Persist session so subsequent operations can reuse the token.
    try:
        auth_manager.save_session()
    except Exception:
        # Non-fatal: continue even if session persistence fails
        pass

    base_dir = Path.home() / ".skymarshal"
    _ensure_storage_dirs(base_dir)

    settings = UserSettings()
    settings.hydrate_batch_size = min(settings.hydrate_batch_size, 15)
    settings.interaction_detail_limit = min(settings.interaction_detail_limit, 100)

    data_manager = DataManager(
        auth_manager,
        settings,
        base_dir,
        base_dir / "cars",
        base_dir / "json",
    )

    car_path = data_manager.download_car(normalized)
    if not car_path:
        raise ProcessingError("Unable to download CAR backup from Bluesky.")

    export_path = data_manager.import_car_replace(car_path, normalized)
    if not export_path:
        raise ProcessingError("Unable to import CAR backup into JSON export.")

    items = data_manager.load_exported_data(export_path)
    try:
        data_manager.hydrate_items(items, collect_details=True)
    except AuthenticationError as exc:
        raise ProcessingError("Authentication expired while hydrating engagement data. Please try again.") from exc
    except Exception as exc:
        raise ProcessingError("Failed to refresh engagement data from Bluesky.") from exc

    stats, top_posts = _calculate_statistics(items)

    return UserDataResult(
        handle=normalized,
        car_path=car_path,
        export_path=export_path,
        statistics=stats,
        top_posts=top_posts,
    )


def has_saved_session() -> bool:
    """Return True when a persisted session file exists."""
    try:
        return SESSION_FILE.exists()
    except OSError:
        return False


def logout_user() -> bool:
    """Clear any persisted session and report whether one previously existed."""
    manager = AuthManager()
    try:
        had_session = manager.try_resume_session()
    except Exception:
        had_session = False

    had_file = has_saved_session()

    try:
        manager.logout()
    except Exception:
        pass

    return had_session or had_file
