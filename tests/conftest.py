"""
Pytest configuration and shared fixtures for Skymarshal tests.

Provides common setup, teardown, and fixtures used across
unit and integration tests.
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock

from skymarshal.models import UserSettings
from skymarshal.auth import AuthManager
from skymarshal.data_manager import DataManager
from tests.fixtures.mock_data import (
    create_mock_content_item,
    create_mock_posts_dataset,
    create_mixed_content_dataset,
    create_mock_user_settings
)


@pytest.fixture
def temp_dir():
    """Provide a temporary directory that's cleaned up after tests."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def mock_auth():
    """Provide a mock AuthManager with common setup."""
    auth = Mock(spec=AuthManager)
    auth.client = Mock()
    auth.current_handle = "test.bsky.social"
    auth.current_did = "did:plc:test123"
    auth.is_authenticated.return_value = True
    auth.normalize_handle.side_effect = lambda h: h.lstrip('@').strip() + ('.bsky.social' if '.' not in h.lstrip('@').strip() else '')
    return auth


@pytest.fixture
def mock_settings():
    """Provide mock user settings."""
    return create_mock_user_settings()


@pytest.fixture
def skymarshal_dirs(temp_dir):
    """Provide directory structure for Skymarshal data."""
    skymarshal_dir = temp_dir / "skymarshal"
    cars_dir = skymarshal_dir / "cars"
    json_dir = skymarshal_dir / "json"

    # Create directories
    skymarshal_dir.mkdir()
    cars_dir.mkdir()
    json_dir.mkdir()

    return {
        'skymarshal_dir': skymarshal_dir,
        'cars_dir': cars_dir,
        'json_dir': json_dir
    }


@pytest.fixture
def data_manager(mock_auth, mock_settings, skymarshal_dirs):
    """Provide a DataManager instance for testing."""
    return DataManager(
        auth_manager=mock_auth,
        settings=mock_settings,
        **skymarshal_dirs
    )


@pytest.fixture
def sample_content_items():
    """Provide a small dataset of sample content items."""
    return create_mixed_content_dataset()


@pytest.fixture
def sample_posts():
    """Provide a dataset of sample posts."""
    return create_mock_posts_dataset(5)


@pytest.fixture
def sample_content_item():
    """Provide a single sample content item."""
    return create_mock_content_item()


# Performance testing fixtures
@pytest.fixture
def large_dataset():
    """Provide a large dataset for performance testing (use sparingly)."""
    from tests.fixtures.mock_data import create_large_dataset
    return create_large_dataset(100, 50, 20)  # Smaller than full perf test


# Parametrized fixtures for testing different scenarios
@pytest.fixture(params=['post', 'like', 'repost'])
def content_type(request):
    """Parametrized fixture for different content types."""
    return request.param


@pytest.fixture(params=[0, 1, 5, 50])
def engagement_level(request):
    """Parametrized fixture for different engagement levels."""
    return request.param


# Mock API response fixtures
@pytest.fixture
def mock_atproto_profile():
    """Mock AT Protocol profile response."""
    from tests.fixtures.mock_data import create_mock_atproto_profile
    return create_mock_atproto_profile("test.bsky.social")


@pytest.fixture
def mock_atproto_records():
    """Mock AT Protocol records response."""
    from tests.fixtures.mock_data import create_mock_atproto_records_response
    sample_records = [
        {
            "uri": "at://did:plc:test/app.bsky.feed.post/1",
            "cid": "bafyrei123",
            "value": {
                "text": "Test post 1",
                "createdAt": "2023-01-01T10:00:00Z"
            }
        },
        {
            "uri": "at://did:plc:test/app.bsky.feed.post/2",
            "cid": "bafyrei456",
            "value": {
                "text": "Test post 2",
                "createdAt": "2023-01-02T10:00:00Z"
            }
        }
    ]
    return create_mock_atproto_records_response(sample_records)


# Custom markers for different test categories
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests (fast, isolated)"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (slower, may use external resources)"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests as performance tests (slow, large datasets)"
    )
    config.addinivalue_line(
        "markers", "auth: marks tests that require authentication mocking"
    )
    config.addinivalue_line(
        "markers", "api: marks tests that mock API interactions"
    )


# Skip decorators for different test environments
def pytest_collection_modifyitems(config, items):
    """Modify test collection to add automatic markers based on location."""
    for item in items:
        # Add unit marker to tests in unit directory
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)

        # Add integration marker to tests in integration directory
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)

        # Add performance marker to tests with 'performance' in name
        if "performance" in item.name or "perf" in item.name:
            item.add_marker(pytest.mark.performance)