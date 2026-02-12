"""Network visualization API blueprint.

Provides endpoints for fetching follower/following network data and running
graph analytics (community detection, PageRank, centrality). Full implementation
ported from blueballs in Phase 3 — this provides the route skeleton and a
basic direct-API implementation.
"""

from __future__ import annotations

import logging
import secrets
import threading
from typing import Any, Dict

from flask import Blueprint, jsonify, request, session

from skymarshal.api import get_services, socketio
from skymarshal.services import ContentService

logger = logging.getLogger(__name__)

network_bp = Blueprint("network", __name__)

# In-memory job tracking
_jobs: Dict[str, Dict[str, Any]] = {}


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

    Expects JSON: {"handle": "user.bsky.social", "depth": 1}
    Returns: {"job_id": "..."}

    Progress is emitted via SocketIO event 'job:progress'.
    """
    service = _require_service()
    data = request.get_json(silent=True) or {}
    handle = data.get("handle") or service.auth.current_handle
    depth = min(int(data.get("depth", 1)), 2)  # Cap at depth 2

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
            _jobs[job_id]["message"] = "Fetching profile..."
            _jobs[job_id]["progress"] = 10
            socketio.emit("job:progress", {"job_id": job_id, **_jobs[job_id]})

            client = service.auth.client
            if not client:
                raise RuntimeError("Not authenticated")

            # Fetch the target profile
            profile = client.get_profile(handle)
            nodes = []
            links = []

            # Add the ego node
            ego_node = {
                "id": profile.did,
                "handle": profile.handle,
                "displayName": getattr(profile, "display_name", "") or profile.handle,
                "avatar": getattr(profile, "avatar", ""),
                "followersCount": getattr(profile, "followers_count", 0),
                "followsCount": getattr(profile, "follows_count", 0),
                "group": 0,
            }
            nodes.append(ego_node)

            # Fetch follows
            _jobs[job_id]["message"] = "Fetching following..."
            _jobs[job_id]["progress"] = 30
            socketio.emit("job:progress", {"job_id": job_id, **_jobs[job_id]})

            follows = []
            cursor = None
            for _ in range(10):  # Max 10 pages = 1000 follows
                resp = client.get_follows(handle, cursor=cursor, limit=100)
                follows.extend(resp.follows)
                cursor = resp.cursor
                if not cursor:
                    break

            # Fetch followers
            _jobs[job_id]["message"] = "Fetching followers..."
            _jobs[job_id]["progress"] = 50
            socketio.emit("job:progress", {"job_id": job_id, **_jobs[job_id]})

            followers = []
            cursor = None
            for _ in range(10):  # Max 10 pages
                resp = client.get_followers(handle, cursor=cursor, limit=100)
                followers.extend(resp.followers)
                cursor = resp.cursor
                if not cursor:
                    break

            # Build graph
            _jobs[job_id]["message"] = "Building graph..."
            _jobs[job_id]["progress"] = 70
            socketio.emit("job:progress", {"job_id": job_id, **_jobs[job_id]})

            follow_dids = set()
            follower_dids = set()

            for f in follows:
                did = f.did
                follow_dids.add(did)
                nodes.append({
                    "id": did,
                    "handle": f.handle,
                    "displayName": getattr(f, "display_name", "") or f.handle,
                    "avatar": getattr(f, "avatar", ""),
                    "group": 1,  # following
                })
                links.append({"source": profile.did, "target": did, "type": "follows"})

            for f in followers:
                did = f.did
                follower_dids.add(did)
                if did not in follow_dids:
                    nodes.append({
                        "id": did,
                        "handle": f.handle,
                        "displayName": getattr(f, "display_name", "") or f.handle,
                        "avatar": getattr(f, "avatar", ""),
                        "group": 2,  # follower only
                    })
                links.append({"source": did, "target": profile.did, "type": "follows"})

            # Mark mutuals
            mutuals = follow_dids & follower_dids
            for node in nodes:
                if node["id"] in mutuals:
                    node["group"] = 3  # mutual

            _jobs[job_id]["message"] = "Running graph analysis..."
            _jobs[job_id]["progress"] = 85
            socketio.emit("job:progress", {"job_id": job_id, **_jobs[job_id]})

            # Basic graph stats
            stats = {
                "total_nodes": len(nodes),
                "total_edges": len(links),
                "following_count": len(follow_dids),
                "follower_count": len(follower_dids),
                "mutual_count": len(mutuals),
            }

            # Try NetworkX analysis if available
            try:
                import networkx as nx

                G = nx.DiGraph()
                for node in nodes:
                    G.add_node(node["id"])
                for link in links:
                    G.add_edge(link["source"], link["target"])

                # PageRank
                pagerank = nx.pagerank(G, max_iter=100)
                for node in nodes:
                    node["pagerank"] = round(pagerank.get(node["id"], 0), 6)

                # Community detection on undirected version
                UG = G.to_undirected()
                try:
                    communities = list(nx.community.louvain_communities(UG))
                    palette = [
                        "#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231",
                        "#911eb4", "#42d4f4", "#f032e6", "#bfef45", "#fabed4",
                    ]
                    for i, comm in enumerate(communities):
                        for did in comm:
                            for node in nodes:
                                if node["id"] == did and node["id"] != profile.did:
                                    node["community"] = i
                                    node["communityColor"] = palette[i % len(palette)]
                except Exception:
                    pass  # Community detection is optional

                stats["has_graph_analysis"] = True
            except ImportError:
                stats["has_graph_analysis"] = False

            _jobs[job_id]["status"] = "complete"
            _jobs[job_id]["progress"] = 100
            _jobs[job_id]["message"] = "Done"
            _jobs[job_id]["result"] = {
                "nodes": nodes,
                "links": links,
                "stats": stats,
            }
            socketio.emit("job:progress", {"job_id": job_id, **_jobs[job_id]})

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
    return jsonify({
        "success": True,
        "status": job["status"],
        "progress": job["progress"],
        "message": job["message"],
        "error": job["error"],
    })


@network_bp.route("/result/<job_id>", methods=["GET"])
@_auth_guard
def job_result(job_id: str):
    """Get the result of a completed network fetch job."""
    job = _jobs.get(job_id)
    if not job:
        return jsonify({"success": False, "error": "Job not found"}), 404
    if job["status"] != "complete":
        return jsonify({
            "success": False,
            "error": f"Job is {job['status']}",
            "status": job["status"],
        }), 400
    return jsonify({"success": True, "data": job["result"]})
