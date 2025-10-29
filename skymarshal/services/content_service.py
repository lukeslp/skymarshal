"""Unified service layer for Skymarshal content workflows.

This module consolidates authentication, data loading, search, and deletion
operations drawn from the CLI utilities and auxiliary scripts across the
repository. It exposes a light-weight API suitable for both command line and
web front-ends.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, TypedDict

from ..auth import AuthManager
from ..data_manager import DataManager
from ..deletion import DeletionManager
from ..models import (
    ContentItem,
    ContentType,
    SearchFilters,
    UserSettings,
    bulk_update_engagement_scores,
    calculate_engagement_score,
)
from ..search import SearchManager
from ..settings import SettingsManager


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class SearchResult(TypedDict):
    """Serialized representation of a content item for UI consumers."""

    uri: str
    content_type: str
    text: str
    created_at: Optional[str]
    likes: int
    reposts: int
    replies: int
    engagement_score: float
    has_media: bool


@dataclass(frozen=True)
class SearchRequest:
    """Structured search request parameters."""

    keyword: Optional[str] = None
    content_types: Optional[Sequence[str]] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    min_engagement: Optional[int] = None
    max_engagement: Optional[int] = None
    limit: int = 250


class ContentService:
    """High-level orchestrator for Skymarshal content operations."""

    def __init__(
        self,
        *,
        settings_path: Optional[Path] = None,
        storage_root: Optional[Path] = None,
        auth_manager: Optional[AuthManager] = None,
        prefer_car_backup: Optional[bool] = None,
    ) -> None:
        self._storage_root = storage_root or Path.home() / ".skymarshal"
        self._storage_root.mkdir(parents=True, exist_ok=True)
        backups_dir = self._storage_root / "backups"
        json_dir = self._storage_root / "json"
        backups_dir.mkdir(parents=True, exist_ok=True)
        json_dir.mkdir(parents=True, exist_ok=True)
        self._json_dir = json_dir

        self._settings_path = settings_path or Path.home() / ".car_inspector_settings.json"
        self._settings_manager = SettingsManager(self._settings_path)
        self._settings: UserSettings = self._settings_manager.settings

        self.auth: AuthManager = auth_manager or AuthManager()
        self.data_manager = DataManager(
            self.auth,
            self._settings,
            self._storage_root,
            backups_dir,
            json_dir,
        )
        self.search_manager = SearchManager(self.auth, self._settings)
        self.deletion_manager = DeletionManager(self.auth, self._settings)

        self._content_cache: Dict[str, List[ContentItem]] = {}
        self._content_files: Dict[str, Path] = {}
        env_pref = _env_flag("SKYMARSHAL_USE_CAR")
        self._prefer_car_backup = env_pref if prefer_car_backup is None else prefer_car_backup

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def login(self, handle: str, password: str) -> bool:
        """Authenticate against Bluesky using the provided credentials."""

        normalized = self.auth.normalize_handle(handle)
        if not normalized:
            return False

        authenticated = self.auth.authenticate_client(normalized, password)
        if authenticated:
            self.auth.save_session()
        return authenticated

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def ensure_content_loaded(
        self,
        *,
        categories: Optional[Iterable[str]] = None,
        limit: Optional[int] = None,
        force_refresh: bool = False,
    ) -> List[ContentItem]:
        """Ensure content for the authenticated user is loaded locally."""

        handle = self.auth.current_handle
        if not handle:
            raise RuntimeError("Authentication required before loading content")

        if not force_refresh and handle in self._content_cache:
            return self._content_cache[handle]

        export_limit = limit or self._settings.download_limit_default
        export_categories = set(categories or ["posts", "likes", "reposts"])

        export_path = None
        export_error: Optional[Exception] = None

        if not self._prefer_car_backup:
            export_path, export_error = self._export_via_api(
                handle,
                export_limit,
                export_categories,
            )

        if not export_path:
            export_path = self._find_existing_export(handle)

        if not export_path:
            export_path = self._export_via_backup(handle, export_categories)

        if not export_path and export_error:
            raise RuntimeError(
                "Failed to export Bluesky data for the current account"
            ) from export_error
        if not export_path:
            raise RuntimeError("Failed to export Bluesky data for the current account")

        export_path = Path(export_path)

        items = self.data_manager.load_exported_data(export_path)
        bulk_update_engagement_scores(items)

        self._content_cache[handle] = items
        self._content_files[handle] = export_path
        return items

    def _export_via_api(
        self,
        handle: str,
        limit: int,
        categories: Iterable[str],
    ) -> Tuple[Optional[Path], Optional[Exception]]:
        try:
            path = self.data_manager.export_user_data(
                handle,
                limit=limit,
                categories=set(categories),
                replace_existing=True,
            )
            return path, None
        except Exception as exc:  # Defensive: ensure callers can inspect failure
            return None, exc

    def _export_via_backup(
        self,
        handle: str,
        categories: Iterable[str],
    ) -> Optional[Path]:
        try:
            backup_path = self.data_manager.create_timestamped_backup(handle)
            if not backup_path:
                return None
            try:
                export_path = self.data_manager.import_backup_replace(
                    backup_path,
                    handle,
                    set(categories),
                )
            finally:
                try:
                    Path(backup_path).unlink()
                except OSError:
                    pass
            return export_path
        except Exception:
            return None

    def _find_existing_export(self, handle: str) -> Optional[Path]:
        """Locate the most recent cached export for a handle."""

        safe_name = handle.replace('.', '_')
        primary = self._json_dir / f"{safe_name}.json"
        if primary.exists():
            return primary

        candidates = sorted(
            self._json_dir.glob(f"{safe_name}_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return candidates[0] if candidates else None

    # ------------------------------------------------------------------
    # Search utilities
    # ------------------------------------------------------------------

    def search(self, request: SearchRequest) -> Tuple[List[SearchResult], int]:
        """Return filtered content and total count for the current user."""

        items = self.ensure_content_loaded()
        filters = self._build_filters(request)
        filtered = self.search_manager.search_content_with_filters(items, filters)

        # Apply multi-type filtering manually when needed
        desired_types = {
            ct.lower() for ct in (request.content_types or []) if ct
        }
        if desired_types:
            filtered = [
                item
                for item in filtered
                if item.content_type.lower() in desired_types
            ]

        # Filter out items with no text AND no engagement (likely deleted/invalid posts)
        filtered = [
            item
            for item in filtered
            if item.text or (item.like_count or 0) > 0 or (item.repost_count or 0) > 0 or (item.reply_count or 0) > 0
        ]

        total = len(filtered)

        limit_value = request.limit if request.limit > 0 else len(filtered)
        limited = filtered[: min(limit_value, len(filtered))]
        results = [self._to_search_result(item) for item in limited]
        return results, total

    def _build_filters(self, request: SearchRequest) -> SearchFilters:
        """Create SearchFilters object from the incoming request."""

        filters = SearchFilters()
        if request.keyword:
            filters.keywords = [request.keyword]

        if request.min_engagement is not None:
            filters.min_engagement = max(0, request.min_engagement)
        if request.max_engagement is not None:
            filters.max_engagement = max(filters.min_engagement, request.max_engagement)

        filters.start_date = request.start_date
        filters.end_date = request.end_date
        filters.content_type = ContentType.ALL
        return filters

    def _to_search_result(self, item: ContentItem) -> SearchResult:
        """Serialize a content item for presentation layers."""

        raw = item.raw_data or {}
        has_media = bool(raw.get("embed") or raw.get("image"))
        text = item.text or ""
        likes = int(item.like_count or 0)
        reposts = int(item.repost_count or 0)
        replies = int(item.reply_count or 0)
        score = (
            float(item.engagement_score)
            if item.engagement_score
            else calculate_engagement_score(likes, reposts, replies)
        )
        return {
            "uri": item.uri,
            "content_type": item.content_type,
            "text": text.strip(),
            "created_at": item.created_at,
            "likes": likes,
            "reposts": reposts,
            "replies": replies,
            "engagement_score": score,
            "has_media": has_media,
        }

    # ------------------------------------------------------------------
    # Deletion
    # ------------------------------------------------------------------

    def delete(self, uris: Sequence[str]) -> Tuple[int, List[str]]:
        """Delete provided URIs for the authenticated user."""

        if not uris:
            return 0, []

        deleted, errors = self.deletion_manager.delete_records_by_uri(list(uris))

        handle = self.auth.current_handle
        if deleted and handle and handle in self._content_cache:
            remaining = [
                item for item in self._content_cache[handle] if item.uri not in uris
            ]
            self._content_cache[handle] = remaining
        return deleted, errors

    # ------------------------------------------------------------------
    # Summaries
    # ------------------------------------------------------------------

    def summarize(self) -> Dict[str, int]:
        """Return high-level counts for the current dataset."""

        try:
            items = self.ensure_content_loaded()
        except RuntimeError:
            # No data loaded yet or authentication required
            return {"posts": 0, "likes": 0, "reposts": 0, "replies": 0, "total": 0}
        
        summary = {
            "posts": 0,
            "likes": 0,
            "reposts": 0,
            "replies": 0,
            "total": len(items),
        }
        for item in items:
            key = item.content_type.lower()
            # Map content types to summary keys
            if key == "post":
                summary["posts"] += 1
            elif key == "reply":
                summary["replies"] += 1
            elif key == "like":
                summary["likes"] += 1
            elif key == "repost":
                summary["reposts"] += 1
        return summary

    def loaded_file(self) -> Optional[Path]:
        """Return the backing JSON file for the current session, if any."""

        handle = self.auth.current_handle
        if not handle:
            return None
        return self._content_files.get(handle)
