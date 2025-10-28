"""Unit tests for the unified ContentService layer."""

from pathlib import Path
from typing import List
from unittest.mock import MagicMock

import pytest

from skymarshal.models import ContentItem
from skymarshal.services import ContentService, SearchRequest


@pytest.fixture()
def auth_manager() -> MagicMock:
    manager = MagicMock()
    manager.normalize_handle.side_effect = lambda handle: f"{handle}.bsky.social"
    manager.authenticate_client.return_value = True
    manager.save_session.return_value = None
    manager.current_handle = "tester.bsky.social"
    return manager


@pytest.fixture()
def content_items() -> List[ContentItem]:
    post = ContentItem(
        uri="at://did:plc:test/app.bsky.feed.post/abc",
        cid="abc",
        content_type="post",
        text="hello world",
        created_at="2024-01-01T00:00:00Z",
        like_count=4,
        repost_count=1,
        reply_count=1,
    )
    like = ContentItem(
        uri="at://did:plc:test/app.bsky.feed.like/def",
        cid="def",
        content_type="like",
    )
    repost = ContentItem(
        uri="at://did:plc:test/app.bsky.feed.repost/ghi",
        cid="ghi",
        content_type="repost",
    )
    return [post, like, repost]


@pytest.fixture()
def service(tmp_path: Path, auth_manager: MagicMock) -> ContentService:
    storage_root = tmp_path / "storage"
    settings_path = tmp_path / "settings.json"
    service = ContentService(
        auth_manager=auth_manager,
        storage_root=storage_root,
        settings_path=settings_path,
        prefer_car_backup=False,
    )
    service.data_manager = MagicMock()
    service.data_manager.export_user_data = MagicMock()
    service.data_manager.load_exported_data = MagicMock()
    service.data_manager.create_timestamped_backup = MagicMock()
    service.data_manager.import_backup_replace = MagicMock()
    service.search_manager = MagicMock()
    service.deletion_manager = MagicMock()
    return service


def test_login_normalizes_and_authenticates(service: ContentService, auth_manager: MagicMock) -> None:
    assert service.login("tester", "secret") is True
    auth_manager.normalize_handle.assert_called_once_with("tester")
    auth_manager.authenticate_client.assert_called_once_with("tester.bsky.social", "secret")
    auth_manager.save_session.assert_called_once()


def test_ensure_content_loaded_exports_and_caches(
    service: ContentService,
    auth_manager: MagicMock,
    content_items: List[ContentItem],
    tmp_path: Path,
) -> None:
    export_path = tmp_path / "export.json"
    service.data_manager.export_user_data.return_value = export_path
    service.data_manager.load_exported_data.return_value = content_items

    first = service.ensure_content_loaded(limit=200)
    second = service.ensure_content_loaded()

    assert first is second
    service.data_manager.export_user_data.assert_called_once()
    service.data_manager.load_exported_data.assert_called_once_with(export_path)


def test_ensure_content_loaded_uses_cached_file_on_export_failure(
    service: ContentService,
    content_items: List[ContentItem],
) -> None:
    cached_path = service._json_dir / "tester_bsky_social.json"
    cached_path.write_text("{}")

    service.data_manager.export_user_data.return_value = None
    service.data_manager.load_exported_data.return_value = content_items

    items = service.ensure_content_loaded()

    assert items == content_items
    service.data_manager.load_exported_data.assert_called_once_with(cached_path)


def test_ensure_content_loaded_downloads_car_when_export_and_cache_missing(
    service: ContentService,
    content_items: List[ContentItem],
    tmp_path: Path,
) -> None:
    service._prefer_car_backup = True
    backup_path = tmp_path / "backup.car"
    backup_path.write_text("car")

    exported_json = tmp_path / "tester_bsky_social.json"

    service.data_manager.export_user_data.side_effect = RuntimeError("boom")
    service.data_manager.create_timestamped_backup.return_value = backup_path
    service.data_manager.import_backup_replace.return_value = exported_json
    service.data_manager.load_exported_data.return_value = content_items

    items = service.ensure_content_loaded(force_refresh=True)

    assert items == content_items
    service.data_manager.import_backup_replace.assert_called_once()
    service.data_manager.load_exported_data.assert_called_once_with(exported_json)
    assert not backup_path.exists()


def test_search_builds_filters_and_limits_results(
    service: ContentService,
    content_items: List[ContentItem],
) -> None:
    service._content_cache[service.auth.current_handle] = content_items

    def fake_search(items, filters):  # type: ignore[no-untyped-def]
        assert filters.keywords == ["hello"]
        assert filters.min_engagement == 5
        assert filters.max_engagement == 10
        return items

    service.search_manager.search_content_with_filters.side_effect = fake_search

    request = SearchRequest(
        keyword="hello",
        min_engagement=5,
        max_engagement=10,
        limit=1,
    )
    results, total = service.search(request)

    assert total == 3
    assert len(results) == 1
    assert results[0]["uri"] == content_items[0].uri


def test_delete_updates_cache(service: ContentService, content_items: List[ContentItem]) -> None:
    service._content_cache[service.auth.current_handle] = content_items.copy()
    service.deletion_manager.delete_records_by_uri.return_value = (1, [])

    deleted, errors = service.delete([content_items[0].uri])

    assert deleted == 1
    assert errors == []
    assert len(service._content_cache[service.auth.current_handle]) == 2


def test_summarize_counts_items(service: ContentService, content_items: List[ContentItem]) -> None:
    service._content_cache[service.auth.current_handle] = content_items
    summary = service.summarize()
    assert summary["posts"] == 1
    assert summary["likes"] == 1
    assert summary["reposts"] == 1
    assert summary["total"] == 3
