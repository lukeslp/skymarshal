"""
Skymarshal Authentication Management

File Purpose: Handle Bluesky authentication, session management, and client operations
Primary Functions/Classes: AuthManager
Inputs and Outputs (I/O): User credentials, AT Protocol authentication, session state

This module manages all authentication-related operations including login, session validation,
re-authentication flows, and client initialization for AT Protocol operations.
"""

from typing import Optional

from atproto import Client
from rich.prompt import Confirm, Prompt

from .exceptions import APIError, AuthenticationError, handle_error, wrap_api_errors
from .models import console


class AuthManager:
    """Manages authentication state and operations."""

    def __init__(self, ui_manager=None):
        self.client: Optional[Client] = None
        self.current_did: Optional[str] = None
        self.current_handle: Optional[str] = None
        self.ui = ui_manager

    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return self.client is not None and self.current_handle is not None

    def logout(self) -> None:
        """Clear authentication state to force fresh login."""
        self.client = None
        self.current_did = None
        self.current_handle = None

    def normalize_handle(self, handle: str) -> str:
        """Normalize handle: drop leading @ and append .bsky.social if missing domain."""
        if not handle:
            return handle
        h = handle.strip().lstrip("@")
        # If no dot present, assume default Bluesky domain
        if "." not in h:
            h = f"{h}.bsky.social"
        return h

    def authenticate_client(self, handle: str, password: str) -> bool:
        """Authenticate client for API operations."""
        try:
            self.client = Client()
            profile = self.client.login(handle, password)
            self.current_handle = handle
            self.current_did = profile.did if hasattr(profile, "did") else None
            return True
        except Exception as e:
            # Reset state on failure
            self.client = None
            self.current_handle = None
            self.current_did = None
            handle_error(console, e, "Authentication", show_details=False)
            return False

    def ensure_authentication(self) -> bool:
        """Ensure we have an authenticated client."""
        if self.client and self.is_authenticated():
            return True

        console.print("[yellow]Re-authentication required[/]")

        # If no UI manager available, fall back to old behavior
        if not self.ui:
            console.print("Bluesky handle: @", end="")
            handle = self.normalize_handle(input())
            password = Prompt.ask("[bold white]App Password: [/]", password=True)
        else:
            # Get handle with navigation
            while True:
                handle, action = self.ui.input_with_navigation(
                    "Bluesky handle: @", context="handle"
                )
                if action in ["back", "main"]:
                    return False
                if handle:
                    handle = self.normalize_handle(handle)
                    break

            # Get password with navigation
            while True:
                password, action = self.ui.input_with_navigation(
                    "App Password: ", password=True, context="password"
                )
                if action in ["back", "main"]:
                    return False
                if password:
                    break

        if self.authenticate_client(handle, password):
            try:
                prof = self.client.get_profile(handle)
                self.current_did = prof.did
            except Exception as e:
                handle_error(console, e, "Profile retrieval", show_details=False)
                self.current_did = None
            return True

        return False

    def validate_and_ensure_authentication_with_retry(self) -> bool:
        """Authentication with retry loop for startup flows."""
        try:
            while True:
                console.print("[bold bright_blue]Log in to Bluesky[/]")
                console.print()
                if self.ensure_authentication():
                    console.print(f"Logged in as @{self.current_handle}.")
                    return True
                console.print("Authentication failed", style="red")
                if not Prompt.ask("[bold white]Try logging in again?[/]", default=True):
                    return False
        except Exception as e:
            handle_error(console, e, "Authentication with retry", show_details=True)
            return False

    @wrap_api_errors
    def call_with_reauth(self, func, *args, **kwargs):
        """Call an API function; on auth failure, prompt re-auth and retry once.

        Note: This method should be used sparingly to avoid re-auth loops.
        For bulk operations, consider calling the API directly and handling
        auth failures gracefully.
        """
        try:
            return func(*args, **kwargs)
        except Exception as e:
            msg = str(e).lower()
            if any(
                s in msg
                for s in ["auth", "unauthorized", "token", "expired", "forbidden"]
            ):
                # Only attempt re-auth if we don't already have a client
                # This prevents re-auth loops in bulk operations
                if not self.is_authenticated():
                    console.print("[yellow]Re-authentication required[/]")
                    if not self.ensure_authentication():
                        raise AuthenticationError(
                            "Re-authentication failed",
                            "Unable to authenticate after retry",
                            e,
                        )
                    return func(*args, **kwargs)
                else:
                    # Already authenticated but still failing - likely a real auth issue
                    raise AuthenticationError(
                        "Authentication failed",
                        "API call failed despite valid authentication",
                        e,
                    )
            raise
