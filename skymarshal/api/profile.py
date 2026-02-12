"""Profile API blueprint.

Provides profile data, follower/following lists, and bot detection
for the power-tool features. Standard profile viewing goes client-side
directly to bsky.social.
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request, session

from skymarshal.api import get_services
from skymarshal.services import ContentService

logger = logging.getLogger(__name__)

profile_bp = Blueprint("profile", __name__)


def _require_service() -> ContentService:
    token = session.get("api_token")
    if not token:
        raise PermissionError("Authentication required")
    service = get_services().get(token)
    if not service or not service.auth.is_authenticated():
        raise PermissionError("Authentication required")
    return service


def _auth_guard(f):
    from functools import wraps

    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except PermissionError as e:
            return jsonify({"success": False, "error": str(e)}), 401

    return wrapper


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@profile_bp.route("/me", methods=["GET"])
@_auth_guard
def my_profile():
    """Return the authenticated user's profile data."""
    service = _require_service()
    client = service.auth.client
    handle = service.auth.current_handle

    if not client or not handle:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        profile = client.get_profile(handle)
        return jsonify({
            "success": True,
            "profile": {
                "did": profile.did,
                "handle": profile.handle,
                "displayName": getattr(profile, "display_name", "") or "",
                "avatar": getattr(profile, "avatar", "") or "",
                "banner": getattr(profile, "banner", "") or "",
                "description": getattr(profile, "description", "") or "",
                "followersCount": getattr(profile, "followers_count", 0),
                "followsCount": getattr(profile, "follows_count", 0),
                "postsCount": getattr(profile, "posts_count", 0),
            },
        })
    except Exception as exc:
        logger.warning("Failed to get profile: %s", exc)
        return jsonify({
            "success": True,
            "profile": {
                "did": service.auth.current_did or "",
                "handle": handle,
                "displayName": "",
                "avatar": "",
            },
        })


@profile_bp.route("/<handle>", methods=["GET"])
@_auth_guard
def get_profile(handle: str):
    """Return profile data for any handle."""
    service = _require_service()
    client = service.auth.client

    if not client:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        normalized = service.auth.normalize_handle(handle)
        profile = client.get_profile(normalized)
        return jsonify({
            "success": True,
            "profile": {
                "did": profile.did,
                "handle": profile.handle,
                "displayName": getattr(profile, "display_name", "") or "",
                "avatar": getattr(profile, "avatar", "") or "",
                "banner": getattr(profile, "banner", "") or "",
                "description": getattr(profile, "description", "") or "",
                "followersCount": getattr(profile, "followers_count", 0),
                "followsCount": getattr(profile, "follows_count", 0),
                "postsCount": getattr(profile, "posts_count", 0),
            },
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


# ---------------------------------------------------------------------------
# Followers / Following lists
# ---------------------------------------------------------------------------

@profile_bp.route("/<handle>/followers", methods=["GET"])
@_auth_guard
def get_followers(handle: str):
    """Paginated followers for a handle.

    Query params: cursor, limit (max 100)
    """
    service = _require_service()
    client = service.auth.client
    if not client:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    cursor = request.args.get("cursor")
    limit = min(int(request.args.get("limit", 50)), 100)

    try:
        normalized = service.auth.normalize_handle(handle)
        resp = client.get_followers(normalized, cursor=cursor, limit=limit)
        followers = []
        for f in resp.followers:
            followers.append({
                "did": f.did,
                "handle": f.handle,
                "displayName": getattr(f, "display_name", "") or "",
                "avatar": getattr(f, "avatar", "") or "",
            })
        return jsonify({
            "success": True,
            "followers": followers,
            "cursor": resp.cursor,
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@profile_bp.route("/<handle>/following", methods=["GET"])
@_auth_guard
def get_following(handle: str):
    """Paginated following for a handle.

    Query params: cursor, limit (max 100)
    """
    service = _require_service()
    client = service.auth.client
    if not client:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    cursor = request.args.get("cursor")
    limit = min(int(request.args.get("limit", 50)), 100)

    try:
        normalized = service.auth.normalize_handle(handle)
        resp = client.get_follows(normalized, cursor=cursor, limit=limit)
        following = []
        for f in resp.follows:
            following.append({
                "did": f.did,
                "handle": f.handle,
                "displayName": getattr(f, "display_name", "") or "",
                "avatar": getattr(f, "avatar", "") or "",
            })
        return jsonify({
            "success": True,
            "following": following,
            "cursor": resp.cursor,
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


# ---------------------------------------------------------------------------
# Bot detection
# ---------------------------------------------------------------------------

@profile_bp.route("/<handle>/bot-check", methods=["GET"])
@_auth_guard
def bot_check(handle: str):
    """Run bot detection heuristics on a handle's followers."""
    service = _require_service()

    try:
        from skymarshal.bot_detection import BotDetector

        detector = BotDetector(service.auth)
        normalized = service.auth.normalize_handle(handle)
        result = detector.analyze(normalized)
        return jsonify({"success": True, "bot_analysis": result})
    except ImportError:
        return jsonify({"success": False, "error": "Bot detector not available"}), 501
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
