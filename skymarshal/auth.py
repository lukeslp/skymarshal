"""
Skymarshal Authentication Management

File Purpose: Handle Bluesky authentication, session management, and client operations
Primary Functions/Classes: AuthManager
Inputs and Outputs (I/O): User credentials, AT Protocol authentication, session state

This module manages all authentication-related operations including login, session validation,
re-authentication flows, and client initialization for AT Protocol operations.
"""

import json
from pathlib import Path
from typing import Optional, Any, Dict

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
        # Persist session to user config dir
        self._session_file = Path.home() / ".skymarshal" / "session.json"

    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return self.client is not None and self.current_handle is not None

    def logout(self) -> None:
        """Clear authentication state to force fresh login."""
        self.client = None
        self.current_did = None
        self.current_handle = None
        # Best-effort cleanup of persisted session
        try:
            if self._session_file.exists():
                self._session_file.unlink()
        except Exception:
            pass

    # ---- Session persistence helpers -------------------------------------------------

    def _ensure_session_dir(self) -> None:
        try:
            self._session_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def _export_session_payload(self) -> Optional[Dict[str, Any]]:
        """Export session data from the client if supported by the library."""
        if not self.client:
            return None
        # atproto Client may expose export_session/import_session or resume_session
        try:
            if hasattr(self.client, "export_session"):
                payload = self.client.export_session()
                if isinstance(payload, dict):
                    return payload
        except Exception:
            pass
        # Fallback: try to access a generic "session" attribute if available
        try:
            payload = getattr(self.client, "session", None)
            if isinstance(payload, dict):
                return payload
        except Exception:
            pass
        return None

    def _import_session_payload(self, payload: Dict[str, Any]) -> bool:
        """Import session data into a new client if supported.

        Returns True on success.
        """
        try:
            self.client = Client()
            # Prefer an explicit import/resume API if available
            if hasattr(self.client, "import_session"):
                self.client.import_session(payload)  # type: ignore[attr-defined]
                return True
            if hasattr(self.client, "resume_session"):
                self.client.resume_session(payload)  # type: ignore[attr-defined]
                return True
        except Exception as e:
            handle_error(console, e, "Session import", show_details=False)
            self.client = None
            return False
        return False

    def save_session(self) -> None:
        """Persist the current session to disk (best effort)."""
        try:
            payload = self._export_session_payload()
            if not payload:
                return
            data = {
                "handle": self.current_handle,
                "did": self.current_did,
                "session": payload,
            }
            self._ensure_session_dir()
            with open(self._session_file, "w") as f:
                json.dump(data, f)
        except Exception:
            # Non-fatal
            pass

    def try_resume_session(self) -> bool:
        """Attempt to restore a previous session from disk."""
        try:
            if not self._session_file.exists():
                return False
            with open(self._session_file, "r") as f:
                data = json.load(f)
            payload = data.get("session")
            if not isinstance(payload, dict):
                return False
            if self._import_session_payload(payload):
                self.current_handle = data.get("handle")
                self.current_did = data.get("did")
                return True
            return False
        except Exception:
            return False

    def normalize_handle(self, handle: str) -> str:
        """Normalize handle: drop leading @, convert @ to . for custom domains, append .bsky.social if needed."""
        if not handle:
            return handle
        h = handle.strip().lstrip("@")
        # Replace any remaining @ with . (for email-style custom domain handles)
        # AT Protocol uses dots, not @ symbols, so adam@blacksky.com → adam.blacksky.com
        h = h.replace("@", ".")
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

        # First, try to resume a saved session silently
        if self.try_resume_session():
            console.print("[green]Resumed saved session[/]")
            return True

        console.print("[yellow]Re-authentication required[/]")

        # If no UI manager available, fall back to old behavior
        if not self.ui:
            console.print("[dim]Examples: username.bsky.social or custom.domain[/]")
            console.print("Bluesky handle: ", end="")
            handle = self.normalize_handle(input())
            password = Prompt.ask("[bold white]App Password: [/]", password=True)
        else:
            # Get handle with navigation
            console.print("[dim]Examples: username.bsky.social or custom.domain[/]")
            while True:
                handle, action = self.ui.input_with_navigation(
                    "Bluesky handle: ", context="handle"
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
            # Persist session for future runs
            self.save_session()
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
