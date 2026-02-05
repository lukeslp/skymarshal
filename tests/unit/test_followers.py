"""
Unit tests for FollowerManager.
"""
from unittest.mock import MagicMock, patch
import pytest
from skymarshal.followers import FollowerManager

class TestFollowerManager:
    @pytest.fixture
    def mock_auth(self):
        auth = MagicMock()
        # Mock response for get_followers
        mock_response = MagicMock()
        mock_response.followers = [
            MagicMock(did="did:1", handle="user1", display_name="User One"),
            MagicMock(did="did:2", handle="user2", display_name="User Two"),
        ]
        mock_response.cursor = None
        auth.client.app.bsky.graph.get_followers.return_value = mock_response
        return auth

    @pytest.fixture
    def mock_settings(self):
        return MagicMock()

    def test_get_followers(self, mock_auth, mock_settings):
        """Test fetching followers list."""
        fm = FollowerManager(mock_auth, mock_settings)
        followers = fm.get_followers("did:target", limit=10)
        
        assert len(followers) == 2
        assert followers[0].did == "did:1"
        mock_auth.client.app.bsky.graph.get_followers.assert_called()

    def test_rank_followers(self, mock_auth, mock_settings):
        """Test ranking followers by count."""
        fm = FollowerManager(mock_auth, mock_settings)
        
        # Mock profile fetch to return detailed data
        mock_p1 = MagicMock()
        mock_p1.did = "did:1"
        mock_p1.handle = "user1"
        mock_p1.followers_count = 100
        mock_p1.follows_count = 10
        mock_p1.posts_count = 5
        
        mock_p2 = MagicMock()
        mock_p2.did = "did:2"
        mock_p2.handle = "user2"
        mock_p2.followers_count = 500
        mock_p2.follows_count = 50
        mock_p2.posts_count = 50

        fm.get_profiles_batch = MagicMock(return_value=[mock_p1, mock_p2])
        
        ranked = fm.rank_followers("did:target", limit=10)
        
        assert len(ranked) == 2
        # Should be sorted by followers_count descending
        assert ranked[0]["handle"] == "user2" 
        assert ranked[0]["followers_count"] == 500
        assert ranked[1]["handle"] == "user1"

    def test_analyze_quality(self, mock_auth, mock_settings):
        """Test identifying quality followers."""
        fm = FollowerManager(mock_auth, mock_settings)
        
        data = [
            {"handle": "user1", "followers_count": 100, "following_count": 2000}, # High following, less selective
            {"handle": "user2", "followers_count": 100, "following_count": 50},   # Selective
        ]
        
        quality = fm.analyze_quality(data, top_n=5)
        
        assert len(quality) == 2
        # Should be sorted by following_count ascending (selectivity)
        assert quality[0]["handle"] == "user2"
        assert quality[1]["handle"] == "user1"
