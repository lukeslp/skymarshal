"""Content management API blueprint.

Wraps ContentService for search, delete, load, export, and share operations.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from flask import Blueprint, Response, jsonify, request, send_file, session

from skymarshal.api import get_services
from skymarshal.services import ContentService, SearchRequest
from skymarshal.services.analytics import ContentAnalytics
from skymarshal.web.share_manager import SharedPostManager

logger = logging.getLogger(__name__)

content_bp = Blueprint("content", __name__)

# Share manager for post permalinks
_share_db_path = Path.home() / ".skymarshal" / "shared_posts.db"
_share_db_path.parent.mkdir(parents=True, exist_ok=True)
_share_manager = SharedPostManager(_share_db_path)


def _require_service() -> ContentService:
    """Return the authenticated ContentService or abort 401."""
    token = session.get("api_token")
    if not token:
        raise PermissionError("Authentication required")
    service = get_services().get(token)
    if not service or not service.auth.is_authenticated():
        raise PermissionError("Authentication required")
    return service


def _auth_guard(f):
    """Decorator that returns 401 JSON on PermissionError."""
    from functools import wraps

    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except PermissionError as e:
            return jsonify({"success": False, "error": str(e)}), 401

    return wrapper


def _get_int(payload: dict, name: str) -> Optional[int]:
    value = payload.get(name)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Content loading
# ---------------------------------------------------------------------------

@content_bp.route("/content/load", methods=["POST"])
@_auth_guard
def load_content():
    """Load user content from Bluesky.

    Accepts JSON: {"limit": 500, "force_refresh": false}
    """
    service = _require_service()
    data = request.get_json(silent=True) or {}
    limit = _get_int(data, "limit") or 500
    force_refresh = bool(data.get("force_refresh", False))

    try:
        items = service.ensure_content_loaded(
            categories=["posts", "likes", "reposts"],
            limit=limit,
            force_refresh=force_refresh,
        )
        summary = service.summarize()
        return jsonify({
            "success": True,
            "loaded_count": len(items),
            "summary": summary,
        })
    except RuntimeError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@content_bp.route("/content/summary", methods=["GET"])
@_auth_guard
def content_summary():
    """Return content statistics for the authenticated user."""
    service = _require_service()
    summary = service.summarize()
    return jsonify({"success": True, "summary": summary})


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

@content_bp.route("/search", methods=["POST"])
@_auth_guard
def search():
    """Search loaded content with filters.

    Expects JSON: {keyword, content_types, start_date, end_date,
                   min_likes, max_likes, min_reposts, max_reposts,
                   min_replies, max_replies, limit}
    """
    service = _require_service()

    # Ensure content is loaded
    try:
        items = service.ensure_content_loaded(
            categories=["posts", "likes", "reposts"],
            limit=999999,
        )
    except RuntimeError as exc:
        return jsonify({"success": False, "error": f"Failed to load data: {exc}"}), 400

    payload = request.get_json(silent=True) or {}

    search_req = SearchRequest(
        keyword=(payload.get("keyword") or None),
        content_types=payload.get("content_types"),
        start_date=(payload.get("start_date") or None),
        end_date=(payload.get("end_date") or None),
        min_likes=_get_int(payload, "min_likes"),
        max_likes=_get_int(payload, "max_likes"),
        min_reposts=_get_int(payload, "min_reposts"),
        max_reposts=_get_int(payload, "max_reposts"),
        min_replies=_get_int(payload, "min_replies"),
        max_replies=_get_int(payload, "max_replies"),
        limit=_get_int(payload, "limit") or 250,
    )

    try:
        results, total = service.search(search_req)

        # Hydrate only search results for performance
        if results and items:
            uri_set = {r.get("uri") for r in results}
            result_items = [item for item in items if item.uri in uri_set]
            if result_items:
                try:
                    service.data_manager.hydrate_items(result_items)
                    item_map = {item.uri: item for item in result_items}
                    for r in results:
                        item = item_map.get(r.get("uri"))
                        if item:
                            r["likes"] = item.like_count or 0
                            r["reposts"] = item.repost_count or 0
                            r["replies"] = item.reply_count or 0
                            r["engagement_score"] = item.engagement_score or 0
                except Exception as hydrate_err:
                    logger.warning("Could not hydrate search results: %s", hydrate_err)

    except RuntimeError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    summary = service.summarize()
    return jsonify({
        "success": True,
        "results": results,
        "total": total,
        "summary": summary,
    })


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@content_bp.route("/delete", methods=["POST"])
@_auth_guard
def delete():
    """Delete content by URIs.

    Expects JSON: {"uris": ["at://...", ...]}
    """
    service = _require_service()
    payload = request.get_json(silent=True) or {}
    uris = payload.get("uris") or []

    if not isinstance(uris, list):
        return jsonify({"success": False, "error": "uris must be an array"}), 400

    deleted, errors = service.delete([str(u) for u in uris if u])
    return jsonify({
        "success": True,
        "deleted": deleted,
        "errors": errors,
        "failed": len(errors),
    })


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

@content_bp.route("/export/csv", methods=["GET"])
@_auth_guard
def export_csv():
    """Export all loaded content as CSV."""
    service = _require_service()

    try:
        items = service.ensure_content_loaded(
            categories=["posts", "likes", "reposts"],
            limit=999999,
        )
    except RuntimeError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Content Type", "Text", "Created At", "Likes", "Reposts",
        "Replies", "Engagement Score", "URI",
    ])
    for item in items:
        writer.writerow([
            item.content_type,
            (item.text or "").replace("\n", " ").strip(),
            item.created_at or "",
            item.like_count or 0,
            item.repost_count or 0,
            item.reply_count or 0,
            f"{item.engagement_score:.2f}" if item.engagement_score else "0.00",
            item.uri,
        ])

    output.seek(0)
    handle = service.auth.current_handle or "export"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"skymarshal_{handle}_{timestamp}.csv"

    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename,
    )


@content_bp.route("/export/car", methods=["GET"])
@_auth_guard
def export_car():
    """Download a CAR backup for the current user."""
    service = _require_service()
    handle = service.auth.current_handle
    if not handle:
        return jsonify({"success": False, "error": "No authenticated user"}), 400

    try:
        import io as _io
        from contextlib import redirect_stdout, redirect_stderr

        with redirect_stdout(_io.StringIO()), redirect_stderr(_io.StringIO()):
            backup_path = service.data_manager.create_timestamped_backup(handle)

        if not backup_path:
            return jsonify({"success": False, "error": "Failed to create CAR backup"}), 400

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"skymarshal_{handle}_{timestamp}.car"
        return send_file(
            backup_path,
            mimetype="application/octet-stream",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as exc:
        logger.error("CAR backup error: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500


# ---------------------------------------------------------------------------
# Share
# ---------------------------------------------------------------------------

@content_bp.route("/share", methods=["POST"])
@_auth_guard
def share_post():
    """Create a shared permalink for a post."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    share_id = _share_manager.create_share(data)
    return jsonify({"success": True, "share_id": share_id})


@content_bp.route("/share/<share_id>", methods=["GET"])
def view_shared_post(share_id: str):
    """Retrieve a shared post by ID (public access)."""
    post_data = _share_manager.get_share(share_id)
    if not post_data:
        return jsonify({"success": False, "error": "Not found"}), 404
    return jsonify({"success": True, "post": post_data})
