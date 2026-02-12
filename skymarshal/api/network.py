"""Network visualization API blueprint.

Provides endpoints for fetching follower/following network data and running
graph analytics (community detection, PageRank, centrality).
Uses the real NetworkFetcher + GraphAnalytics from skymarshal.network.
"""

from __future__ import annotations

import logging
import secrets
import threading
from typing import Any, Dict

from flask import Blueprint, jsonify, request, session

from skymarshal.api import get_services, socketio
from skymarshal.network.analysis import GraphAnalytics
from skymarshal.network.cache import NetworkCache
from skymarshal.network.client import BlueskyClient
from skymarshal.network.fetcher import NetworkFetcher
from skymarshal.services import ContentService

logger = logging.getLogger(__name__)

network_bp = Blueprint("network", __name__)

# In-memory job tracking
_jobs: Dict[str, Dict[str, Any]] = {}

# Shared instances (initialized lazily)
_cache: NetworkCache | None = None


def _get_cache() -> NetworkCache:
    global _cache
    if _cache is None:
        _cache = NetworkCache()
    return _cache


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
# Network fetch (async job)
# ---------------------------------------------------------------------------


@network_bp.route("/fetch", methods=["POST"])
@_auth_guard
def fetch_network():
    """Start a network fetch job for a given handle.

    Expects JSON: {
        "handle": "user.bsky.social",
        "mode": "balanced",  // "fast", "balanced", "detailed"
        "include_followers": true,
        "include_following": true,
        "max_followers": 500,
        "max_following": 500,
        "bypass_cache": false
    }
    Returns: {"job_id": "..."}
    """
    service = _require_service()
    data = request.get_json(silent=True) or {}
    handle = data.get("handle") or service.auth.current_handle
    mode = data.get("mode", "balanced")
    include_followers = data.get("include_followers", True)
    include_following = data.get("include_following", True)
    max_followers = data.get("max_followers", 500)
    max_following = data.get("max_following", 500)
    bypass_cache = data.get("bypass_cache", False)

    # Check cache first
    cache = _get_cache()
    cache_key = cache.make_key(
        handle,
        include_followers=include_followers,
        include_following=include_following,
        max_followers=max_followers,
        max_following=max_following,
        mode=mode,
    )

    if not bypass_cache:
        cached = cache.get(cache_key)
        if cached:
            job_id = secrets.token_hex(8)
            _jobs[job_id] = {
                "status": "complete",
                "handle": handle,
                "progress": 100,
                "message": "Loaded from cache",
                "result": cached,
                "error": None,
            }
            return jsonify({"success": True, "job_id": job_id, "cached": True})

    job_id = secrets.token_hex(8)
    _jobs[job_id] = {
        "status": "running",
        "handle": handle,
        "progress": 0,
        "message": "Starting network fetch...",
        "result": None,
        "error": None,
    }

    def _run_fetch():
        try:
            # Create a dedicated client for this fetch
            client = BlueskyClient()
            analytics = GraphAnalytics()
            fetcher = NetworkFetcher(client, analytics=analytics)

            def progress_callback(operation: str, current: int, total: int) -> None:
                pct = int((current / max(total, 1)) * 100)
                _jobs[job_id]["message"] = operation
                _jobs[job_id]["progress"] = pct
                socketio.emit("job:progress", {"job_id": job_id, **_jobs[job_id]})

            result = fetcher.fetch_network(
                handle=handle,
                include_followers=include_followers,
                include_following=include_following,
                max_followers=max_followers,
                max_following=max_following,
                mode=mode,
                progress_callback=progress_callback,
            )

            # Cache the result
            cache.set(cache_key, result)

            _jobs[job_id]["status"] = "complete"
            _jobs[job_id]["progress"] = 100
            _jobs[job_id]["message"] = "Done"
            _jobs[job_id]["result"] = result
            socketio.emit("job:progress", {"job_id": job_id, **_jobs[job_id]})

            client.close()

        except Exception as exc:
            logger.error("Network fetch error: %s", exc)
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["error"] = str(exc)
            _jobs[job_id]["message"] = f"Error: {exc}"
            socketio.emit("job:progress", {"job_id": job_id, **_jobs[job_id]})

    thread = threading.Thread(target=_run_fetch, daemon=True)
    thread.start()

    return jsonify({"success": True, "job_id": job_id})


# ---------------------------------------------------------------------------
# Job status & result
# ---------------------------------------------------------------------------


@network_bp.route("/status/<job_id>", methods=["GET"])
@_auth_guard
def job_status(job_id: str):
    """Check status of a network fetch job."""
    job = _jobs.get(job_id)
    if not job:
        return jsonify({"success": False, "error": "Job not found"}), 404
    return jsonify(
        {
            "success": True,
            "status": job["status"],
            "progress": job["progress"],
            "message": job["message"],
            "error": job["error"],
        }
    )


@network_bp.route("/result/<job_id>", methods=["GET"])
@_auth_guard
def job_result(job_id: str):
    """Get the result of a completed network fetch job."""
    job = _jobs.get(job_id)
    if not job:
        return jsonify({"success": False, "error": "Job not found"}), 404
    if job["status"] != "complete":
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Job is {job['status']}",
                    "status": job["status"],
                }
            ),
            400,
        )
    return jsonify({"success": True, "data": job["result"]})


# ---------------------------------------------------------------------------
# Cache management
# ---------------------------------------------------------------------------


@network_bp.route("/cache/clear", methods=["POST"])
@_auth_guard
def clear_cache():
    """Clear the network cache."""
    _require_service()
    count = _get_cache().clear()
    return jsonify({"success": True, "cleared": count})
