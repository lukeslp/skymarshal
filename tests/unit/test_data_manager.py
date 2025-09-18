"""
Unit tests for Skymarshal DataManager.

Tests data operations including file management, export/import,
and the new consolidated download methods.
"""
import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from skymarshal.data_manager import DataManager
from skymarshal.models import UserSettings, ContentItem


class TestDataManager:
    """Test DataManager class."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create temporary directories for testing
        self.temp_dir = Path(tempfile.mkdtemp())
        self.skymarshal_dir = self.temp_dir / "skymarshal"
        self.cars_dir = self.skymarshal_dir / "cars"
        self.json_dir = self.skymarshal_dir / "json"

        # Create directories
        self.skymarshal_dir.mkdir()
        self.cars_dir.mkdir()
        self.json_dir.mkdir()

        # Mock auth manager
        self.mock_auth = Mock()
        self.mock_auth.client = Mock()
        self.mock_auth.current_handle = "test.bsky.social"
        self.mock_auth.current_did = "did:plc:test123"

        # Create settings
        self.settings = UserSettings()

        # Initialize DataManager
        self.data_manager = DataManager(
            auth_manager=self.mock_auth,
            settings=self.settings,
            skymarshal_dir=self.skymarshal_dir,
            cars_dir=self.cars_dir,
            json_dir=self.json_dir
        )

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_initialization(self):
        """Test DataManager initialization."""
        assert self.data_manager.auth == self.mock_auth
        assert self.data_manager.settings == self.settings
        assert self.data_manager.skymarshal_dir == self.skymarshal_dir
        assert self.data_manager.cars_dir == self.cars_dir
        assert self.data_manager.json_dir == self.json_dir

    def test_get_user_files_json_empty(self):
        """Test getting user files when directory is empty."""
        files = self.data_manager.get_user_files("test.bsky.social", "json")
        assert files == []

    def test_get_user_files_json_with_files(self):
        """Test getting user JSON files."""
        # Create test JSON files
        test_file1 = self.json_dir / "test_bsky_social.json"
        test_file2 = self.json_dir / "other_bsky_social.json"
        test_file3 = self.json_dir / "wrong_format.json"

        test_file1.write_text('{"test": "data"}')
        test_file2.write_text('{"test": "data"}')
        test_file3.write_text('{"test": "data"}')

        files = self.data_manager.get_user_files("test.bsky.social", "json")
        assert len(files) == 1
        assert test_file1 in files
        assert test_file2 not in files

    def test_get_user_files_car(self):
        """Test getting user CAR files."""
        # Create test CAR files
        test_file1 = self.cars_dir / "test_bsky_social.car"
        test_file2 = self.cars_dir / "test_bsky_social_20231225_120000.car"

        test_file1.write_bytes(b"fake car data")
        test_file2.write_bytes(b"fake car data")

        files = self.data_manager.get_user_files("test.bsky.social", "car")
        assert len(files) == 2
        assert test_file1 in files
        assert test_file2 in files

    def test_validate_file_access_valid(self):
        """Test file access validation with valid file."""
        test_file = self.json_dir / "test_bsky_social.json"
        test_file.write_text('{"test": "data"}')

        result = self.data_manager.validate_file_access(test_file, "test.bsky.social")
        assert result is True

    def test_validate_file_access_wrong_user(self):
        """Test file access validation with wrong user."""
        test_file = self.json_dir / "other_bsky_social.json"
        test_file.write_text('{"test": "data"}')

        result = self.data_manager.validate_file_access(test_file, "test.bsky.social")
        assert result is False

    def test_validate_file_access_nonexistent(self):
        """Test file access validation with nonexistent file."""
        test_file = self.json_dir / "nonexistent.json"

        result = self.data_manager.validate_file_access(test_file, "test.bsky.social")
        assert result is False

    def test_load_exported_data_success(self):
        """Test loading exported data successfully."""
        test_data = {
            "posts": [
                {
                    "uri": "at://did:plc:test/app.bsky.feed.post/1",
                    "cid": "bafyrei123",
                    "type": "posts",
                    "text": "Test post",
                    "created_at": "2023-01-01T10:00:00Z",
                    "engagement": {
                        "likes": 5,
                        "reposts": 2,
                        "replies": 1,
                        "score": 12
                    }
                }
            ],
            "likes": [],
            "reposts": []
        }

        test_file = self.json_dir / "test_bsky_social.json"
        test_file.write_text(json.dumps(test_data))

        content_items = self.data_manager.load_exported_data(test_file)

        assert len(content_items) == 1
        item = content_items[0]
        assert isinstance(item, ContentItem)
        assert item.uri == "at://did:plc:test/app.bsky.feed.post/1"
        assert item.text == "Test post"
        assert item.like_count == 5
        assert item.content_type == "posts"

    def test_load_exported_data_invalid_json(self):
        """Test loading exported data with invalid JSON."""
        test_file = self.json_dir / "test_bsky_social.json"
        test_file.write_text("invalid json")

        with pytest.raises(Exception):
            self.data_manager.load_exported_data(test_file)

    def test_clear_local_data_success(self):
        """Test clearing local data successfully."""
        handle = "test.bsky.social"
        safe_handle = "test_bsky_social"

        # Create test files
        json_file = self.json_dir / f"{safe_handle}.json"
        car_file1 = self.cars_dir / f"{safe_handle}.car"
        car_file2 = self.cars_dir / f"{safe_handle}_20231225_120000.car"

        json_file.write_text('{"test": "data"}')
        car_file1.write_bytes(b"car data")
        car_file2.write_bytes(b"car data")

        deleted_count = self.data_manager.clear_local_data(handle)

        assert deleted_count == 3
        assert not json_file.exists()
        assert not car_file1.exists()
        assert not car_file2.exists()

    def test_clear_local_data_no_files(self):
        """Test clearing local data when no files exist."""
        deleted_count = self.data_manager.clear_local_data("nonexistent.bsky.social")
        assert deleted_count == 0

    def test_clear_local_data_empty_handle(self):
        """Test clearing local data with empty handle."""
        deleted_count = self.data_manager.clear_local_data("")
        assert deleted_count == 0

    @patch('skymarshal.data_manager.console')
    def test_download_and_export_data_not_authenticated(self, mock_console):
        """Test download_and_export_data when not authenticated."""
        self.mock_auth.is_authenticated.return_value = False

        result = self.data_manager.download_and_export_data("test.bsky.social")

        assert result is None
        mock_console.print.assert_called_with("Authentication required for data download")

    @patch('skymarshal.data_manager.console')
    def test_download_and_export_data_auth_failure(self, mock_console):
        """Test download_and_export_data with authentication failure."""
        self.mock_auth.is_authenticated.return_value = True
        self.mock_auth.authenticate_client.return_value = False

        result = self.data_manager.download_and_export_data("test.bsky.social", password="wrong")

        assert result is None
        mock_console.print.assert_called_with("Authentication failed")

    def test_download_and_export_data_success(self):
        """Test download_and_export_data success."""
        self.mock_auth.is_authenticated.return_value = True

        with patch.object(self.data_manager, 'export_user_data') as mock_export:
            mock_export.return_value = Path("/fake/path/export.json")

            result = self.data_manager.download_and_export_data(
                "test.bsky.social",
                limit=100,
                categories={'posts'},
                replace_existing=True
            )

            assert result == Path("/fake/path/export.json")
            mock_export.assert_called_once_with(
                "test.bsky.social", 100, {'posts'}, None, None, True
            )

    @patch('skymarshal.data_manager.console')
    def test_download_car_and_import_download_fails(self, mock_console):
        """Test download_car_and_import when CAR download fails."""
        with patch.object(self.data_manager, 'download_car', return_value=None):
            result = self.data_manager.download_car_and_import("test.bsky.social")

        assert result is None
        mock_console.print.assert_any_call("Failed to download .car file")

    def test_download_car_and_import_success_replace_mode(self):
        """Test download_car_and_import success in replace mode."""
        fake_car_path = Path("/fake/car/file.car")
        fake_json_path = Path("/fake/json/file.json")

        with patch.object(self.data_manager, 'download_car', return_value=fake_car_path):
            with patch.object(self.data_manager, 'import_car_replace', return_value=fake_json_path):
                result = self.data_manager.download_car_and_import(
                    "test.bsky.social",
                    categories={'posts'},
                    replace_mode=True
                )

        assert result == fake_json_path

    def test_download_car_and_import_success_merge_mode(self):
        """Test download_car_and_import success in merge mode."""
        fake_car_path = Path("/fake/car/file.car")
        fake_json_path = Path("/fake/json/file.json")

        with patch.object(self.data_manager, 'download_car', return_value=fake_car_path):
            with patch.object(self.data_manager, 'import_car_merge', return_value=fake_json_path):
                result = self.data_manager.download_car_and_import(
                    "test.bsky.social",
                    categories={'posts'},
                    replace_mode=False
                )

        assert result == fake_json_path

    def create_sample_content_items(self, count=3):
        """Helper method to create sample ContentItem objects."""
        items = []
        for i in range(count):
            item = ContentItem(
                uri=f"at://did:plc:test/app.bsky.feed.post/{i+1}",
                cid=f"bafyrei{i+1}",
                content_type="post",
                text=f"Test post {i+1}",
                created_at=f"2023-01-0{i+1}T10:00:00Z",
                like_count=i * 2,
                repost_count=i,
                reply_count=i // 2
            )
            items.append(item)
        return items

    def test_hydrate_items_no_items(self):
        """Test hydrating empty list of items."""
        items = []
        self.data_manager.hydrate_items(items)
        assert len(items) == 0

    def test_hydrate_items_no_posts_or_replies(self):
        """Test hydrating items with no posts or replies."""
        items = [
            ContentItem(uri="at://test/1", cid="123", content_type="like"),
            ContentItem(uri="at://test/2", cid="456", content_type="repost")
        ]

        # Should not make any API calls
        self.data_manager.hydrate_items(items)

        # Items should remain unchanged
        assert items[0].content_type == "like"
        assert items[1].content_type == "repost"
