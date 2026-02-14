"""
Unit tests for Skymarshal authentication management.

Tests AuthManager class including handle normalization,
authentication state management, and client operations.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from skymarshal.auth import AuthManager
from skymarshal.exceptions import AuthenticationError, APIError


class TestAuthManager:
    """Test AuthManager class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.ui_manager = Mock()
        self.auth_manager = AuthManager(ui_manager=self.ui_manager)

    def test_initial_state(self):
        """Test AuthManager initial state."""
        assert self.auth_manager.client is None
        assert self.auth_manager.current_did is None
        assert self.auth_manager.current_handle is None
        assert not self.auth_manager.is_authenticated()

    def test_is_authenticated_false_when_no_client(self):
        """Test is_authenticated returns False when no client."""
        assert not self.auth_manager.is_authenticated()

    def test_is_authenticated_false_when_no_handle(self):
        """Test is_authenticated returns False when client exists but no handle."""
        self.auth_manager.client = Mock()
        assert not self.auth_manager.is_authenticated()

    def test_is_authenticated_true_when_both_exist(self):
        """Test is_authenticated returns True when both client and handle exist."""
        self.auth_manager.client = Mock()
        self.auth_manager.current_handle = "test.bsky.social"
        assert self.auth_manager.is_authenticated()

    def test_logout_clears_authentication_state(self):
        """Test logout method clears all authentication state."""
        # Setup authenticated state
        self.auth_manager.client = Mock()
        self.auth_manager.current_handle = "test.bsky.social"
        self.auth_manager.current_did = "did:plc:test123"

        # Verify we're authenticated
        assert self.auth_manager.is_authenticated()

        # Call logout
        self.auth_manager.logout()

        # Verify all state is cleared
        assert self.auth_manager.client is None
        assert self.auth_manager.current_handle is None
        assert self.auth_manager.current_did is None
        assert not self.auth_manager.is_authenticated()

    def test_normalize_handle_empty_string(self):
        """Test handle normalization with empty string."""
        result = self.auth_manager.normalize_handle("")
        assert result == ""

    def test_normalize_handle_removes_at_symbol(self):
        """Test handle normalization removes @ symbol."""
        result = self.auth_manager.normalize_handle("@testuser")
        assert result == "testuser.bsky.social"

    def test_normalize_handle_adds_domain(self):
        """Test handle normalization adds .bsky.social domain."""
        result = self.auth_manager.normalize_handle("testuser")
        assert result == "testuser.bsky.social"

    def test_normalize_handle_preserves_custom_domain(self):
        """Test handle normalization converts @ to . for custom domains (AT Protocol format)."""
        # Email-style custom domain should be converted to AT Protocol format
        result = self.auth_manager.normalize_handle("user@example.com")
        assert result == "user.example.com"

        result = self.auth_manager.normalize_handle("@user.example.com")
        assert result == "user.example.com"

    def test_normalize_handle_whitespace(self):
        """Test handle normalization handles whitespace."""
        result = self.auth_manager.normalize_handle("  @testuser  ")
        assert result == "testuser.bsky.social"

    @patch('skymarshal.auth.Client')
    def test_authenticate_client_success(self, mock_client_class):
        """Test successful client authentication."""
        mock_client = Mock()
        mock_profile = Mock()
        mock_profile.did = "did:plc:test123"
        mock_client.login.return_value = mock_profile
        mock_client_class.return_value = mock_client

        result = self.auth_manager.authenticate_client("test.bsky.social", "password")

        assert result is True
        assert self.auth_manager.client == mock_client
        assert self.auth_manager.current_handle == "test.bsky.social"
        assert self.auth_manager.current_did == "did:plc:test123"
        mock_client.login.assert_called_once_with("test.bsky.social", "password")

    @patch('skymarshal.auth.Client')
    def test_authenticate_client_failure(self, mock_client_class):
        """Test failed client authentication."""
        mock_client = Mock()
        mock_client.login.side_effect = Exception("Login failed")
        mock_client_class.return_value = mock_client

        result = self.auth_manager.authenticate_client("test.bsky.social", "wrong_password")

        assert result is False
        assert self.auth_manager.client is None
        assert self.auth_manager.current_handle is None
        assert self.auth_manager.current_did is None

    @patch('skymarshal.auth.Client')
    def test_authenticate_client_profile_without_did(self, mock_client_class):
        """Test authentication when profile doesn't have DID attribute."""
        mock_client = Mock()
        mock_profile = Mock(spec=[])  # Profile without 'did' attribute
        mock_client.login.return_value = mock_profile
        mock_client_class.return_value = mock_client

        result = self.auth_manager.authenticate_client("test.bsky.social", "password")

        assert result is True
        assert self.auth_manager.current_did is None

    @patch('skymarshal.models.console')
    @patch('skymarshal.auth.Prompt')
    def test_ensure_authentication_already_authenticated(self, mock_prompt, mock_console):
        """Test ensure_authentication when already authenticated."""
        self.auth_manager.client = Mock()
        self.auth_manager.current_handle = "test.bsky.social"

        result = self.auth_manager.ensure_authentication()

        assert result is True
        mock_console.print.assert_not_called()
        mock_prompt.ask.assert_not_called()

    @patch('skymarshal.auth.console')
    @patch('skymarshal.auth.Prompt')
    @patch('builtins.input')
    def test_ensure_authentication_no_ui_manager(self, mock_input, mock_prompt, mock_console):
        """Test ensure_authentication without UI manager (fallback mode)."""
        self.auth_manager.ui = None
        mock_input.return_value = "testuser"
        mock_prompt.ask.return_value = "password"

        with patch.object(self.auth_manager, 'authenticate_client', return_value=True) as mock_auth:
            result = self.auth_manager.ensure_authentication()

        assert result is True
        mock_console.print.assert_called()
        mock_prompt.ask.assert_called_once_with("[bold white]App Password: [/]", password=True)
        mock_auth.assert_called_once_with("testuser.bsky.social", "password")

    def test_ensure_authentication_with_ui_manager_success(self):
        """Test ensure_authentication with UI manager successful flow."""
        # Mock UI manager responses
        self.ui_manager.input_with_navigation.side_effect = [
            ("testuser", "continue"),  # Handle input
            ("password", "continue")   # Password input
        ]

        with patch.object(self.auth_manager, 'authenticate_client', return_value=True) as mock_auth:
            with patch.object(self.auth_manager, 'normalize_handle', return_value="testuser.bsky.social"):
                result = self.auth_manager.ensure_authentication()

        assert result is True
        mock_auth.assert_called_once_with("testuser.bsky.social", "password")

    def test_ensure_authentication_with_ui_manager_user_cancels(self):
        """Test ensure_authentication when user cancels via navigation."""
        self.ui_manager.input_with_navigation.return_value = ("", "back")

        result = self.auth_manager.ensure_authentication()

        assert result is False

    @patch('skymarshal.auth.Confirm.ask')
    def test_validate_and_ensure_authentication_with_retry_success(self, mock_confirm):
        """Test startup authentication method with successful login."""
        with patch.object(self.auth_manager, 'ensure_authentication', return_value=True):
            self.auth_manager.current_handle = "test.bsky.social"
            result = self.auth_manager.validate_and_ensure_authentication_with_retry()

        assert result is True
        mock_confirm.ask.assert_not_called()

    @patch('skymarshal.auth.Prompt.ask')
    def test_validate_and_ensure_authentication_with_retry_failure_then_success(self, mock_prompt):
        """Test startup authentication with failure then success."""
        mock_prompt.return_value = True  # User wants to retry

        with patch.object(self.auth_manager, 'ensure_authentication', side_effect=[False, True]):
            self.auth_manager.current_handle = "test.bsky.social"
            result = self.auth_manager.validate_and_ensure_authentication_with_retry()

        assert result is True
        mock_prompt.assert_called_once()

    @patch('skymarshal.auth.Prompt.ask')
    def test_validate_and_ensure_authentication_with_retry_user_gives_up(self, mock_prompt):
        """Test startup authentication when user gives up retrying."""
        mock_prompt.return_value = False  # User doesn't want to retry

        with patch.object(self.auth_manager, 'ensure_authentication', return_value=False):
            result = self.auth_manager.validate_and_ensure_authentication_with_retry()

        assert result is False
        mock_prompt.assert_called_once()

    def test_call_with_reauth_success_first_try(self):
        """Test call_with_reauth succeeds on first try."""
        mock_func = Mock(return_value="success")

        result = self.auth_manager.call_with_reauth(mock_func, "arg1", kwarg1="value1")

        assert result == "success"
        mock_func.assert_called_once_with("arg1", kwarg1="value1")

    def test_call_with_reauth_auth_error_no_retry(self):
        """Test call_with_reauth with non-auth error."""
        mock_func = Mock(side_effect=Exception("network timeout"))

        with pytest.raises(APIError, match="Network error"):
            self.auth_manager.call_with_reauth(mock_func)

    def test_call_with_reauth_auth_error_retry_success(self):
        """Test call_with_reauth with auth error, successful retry."""
        mock_func = Mock(side_effect=[
            Exception("authentication failed"),  # First call fails
            "success"  # Second call succeeds
        ])

        with patch.object(self.auth_manager, 'ensure_authentication', return_value=True):
            result = self.auth_manager.call_with_reauth(mock_func)

        assert result == "success"
        assert mock_func.call_count == 2

    def test_call_with_reauth_auth_error_retry_fails_auth(self):
        """Test call_with_reauth with auth error, re-auth fails."""
        mock_func = Mock(side_effect=Exception("authentication failed"))

        with patch.object(self.auth_manager, 'ensure_authentication', return_value=False):
            with pytest.raises(AuthenticationError, match="Authentication required"):
                self.auth_manager.call_with_reauth(mock_func)