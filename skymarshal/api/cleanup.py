"""Cleanup API blueprint.

Wraps FollowingCleaner for account cleanup workflows — detecting inactive
accounts, bots, and managing unfollows.
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request, session

from skymarshal.api import get_services
from skymarshal.services import ContentService

logger = logging.getLogger(__name__)

cleanup_bp = Blueprint("cleanup", __name__)


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
# Analyze following for cleanup candidates
# ---------------------------------------------------------------------------

@cleanup_bp.route("/analyze", methods=["POST"])
@_auth_guard
def analyze_following():
    """Analyze the authenticated user's following list for cleanup candidates.

    Returns accounts that are inactive, low-quality, or likely bots.
    """
    service = _require_service()

    try:
        from skymarshal.cleanup.following_cleaner import FollowingCleaner

        cleaner = FollowingCleaner(service.auth)
        candidates = cleaner.find_cleanup_candidates()

        return jsonify({
            "success": True,
            "candidates": candidates,
            "total": len(candidates),
        })
    except ImportError:
        return jsonify({"success": False, "error": "Following cleaner not available"}), 501
    except Exception as exc:
        logger.error("Cleanup analysis error: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 400


# ---------------------------------------------------------------------------
# Unfollow
# ---------------------------------------------------------------------------

@cleanup_bp.route("/unfollow", methods=["POST"])
@_auth_guard
def unfollow():
    """Unfollow one or more accounts.

    Expects JSON: {"dids": ["did:plc:...", ...]}
    """
    service = _require_service()
    data = request.get_json(silent=True) or {}
    dids = data.get("dids") or []

    if not isinstance(dids, list) or not dids:
        return jsonify({"success": False, "error": "dids must be a non-empty array"}), 400

    client = service.auth.client
    if not client:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    unfollowed = []
    errors = []

    for did in dids:
        try:
            # Find the follow record to delete
            # The follow record URI is at://ego-did/app.bsky.graph.follow/<rkey>
            # We need to find the rkey for this specific follow
            resp = client.get_follows(service.auth.current_handle, limit=100)
            target_follow = None
            cursor = None

            while True:
                for f in resp.follows:
                    if f.did == did:
                        # Found the follow — extract the rkey from the viewer state
                        viewer = getattr(f, "viewer", None)
                        if viewer:
                            following_uri = getattr(viewer, "following", None)
                            if following_uri:
                                target_follow = following_uri
                                break
                if target_follow:
                    break
                cursor = resp.cursor
                if not cursor:
                    break
                resp = client.get_follows(service.auth.current_handle, cursor=cursor, limit=100)

            if target_follow:
                # Delete the follow record
                rkey = target_follow.split("/")[-1]
                client.delete_record(
                    repo=service.auth.current_did,
                    collection="app.bsky.graph.follow",
                    rkey=rkey,
                )
                unfollowed.append(did)
            else:
                errors.append(f"Follow record not found for {did}")

        except Exception as exc:
            errors.append(f"{did}: {exc}")

    return jsonify({
        "success": True,
        "unfollowed": len(unfollowed),
        "errors": errors,
    })
