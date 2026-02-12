"""Authentication API blueprint.

Wraps the existing AuthManager to provide REST endpoints for login, logout,
and session validation. The React frontend calls these before using power-tool
features (search, delete, analytics, etc.).
"""

from __future__ import annotations

import logging
import secrets

from flask import Blueprint, jsonify, request, session

from skymarshal.api import get_services
from skymarshal.services import ContentService

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)


def _get_current_service() -> ContentService | None:
    """Return the ContentService for the current session, if any."""
    token = session.get("api_token")
    if not token:
        return None
    return get_services().get(token)


def _require_auth():
    """Return the authenticated ContentService or raise 401."""
    service = _get_current_service()
    if service is None or not service.auth.is_authenticated():
        return None
    return service


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@auth_bp.route("/login", methods=["POST"])
def login():
    """Authenticate with Bluesky credentials.

    Expects JSON: {"handle": "user.bsky.social", "password": "xxxx-xxxx-xxxx-xxxx"}
    Returns: {"success": true, "handle": "...", "did": "..."}
    """
    data = request.get_json(silent=True) or {}
    handle = (data.get("handle") or "").strip()
    password = data.get("password") or ""

    if not handle or not password:
        return jsonify({"success": False, "error": "Handle and password are required"}), 400

    service = ContentService()
    if not service.login(handle, password):
        return jsonify({"success": False, "error": "Authentication failed. Check your app password."}), 401

    # Store service instance keyed by a random token
    token = secrets.token_hex(32)
    session["api_token"] = token
    session.permanent = True
    get_services()[token] = service

    logger.info("User logged in: %s", service.auth.current_handle)

    return jsonify({
        "success": True,
        "handle": service.auth.current_handle,
        "did": service.auth.current_did,
    })


# ---------------------------------------------------------------------------
# Session check
# ---------------------------------------------------------------------------

@auth_bp.route("/session", methods=["GET"])
def check_session():
    """Check if the current session is valid.

    Returns: {"authenticated": true/false, "handle": "...", "did": "..."}
    """
    service = _require_auth()
    if service is None:
        return jsonify({"authenticated": False})

    return jsonify({
        "authenticated": True,
        "handle": service.auth.current_handle,
        "did": service.auth.current_did,
    })


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Clear the current session."""
    token = session.get("api_token")
    if token:
        services = get_services()
        svc = services.pop(token, None)
        if svc:
            svc.auth.logout()
    session.clear()
    return jsonify({"success": True})
