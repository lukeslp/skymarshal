#!/usr/bin/env python3
"""
Simple Flask site: login → fetch last 50 posts → hydrate likes/reposts/quotes/replies
with live progress (Server-Sent Events) and final summary.

Run:
  python web_simple.py  # defaults to port 5006

Dependencies:
  pip install atproto requests flask
"""
from __future__ import annotations

import json
import secrets
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, render_template, request, Response, session, send_from_directory

try:
    from atproto import Client
except Exception:  # pragma: no cover
    Client = None  # type: ignore

from improved_hydration import BlueskyEngagementHydrator
from utils import normalize_handle, PostDataExporter, format_file_safe_name
from batch_processor import create_standard_batch_processor
from background_tasks import get_car_download_manager, get_task_manager, TaskStatus


def _iter_batch_post_payloads(batch_result):
    """Yield post dicts from a BatchResult regardless of payload shape."""

    for payload in getattr(batch_result, "results", []):
        if isinstance(payload, dict):
            candidate_posts = [payload]
        elif isinstance(payload, list):
            candidate_posts = payload
        else:
            continue

        for post_data in candidate_posts:
            if isinstance(post_data, dict) and post_data.get("uri"):
                yield post_data

app = Flask(
    __name__,
    template_folder=str(Path(__file__).parent / "templates"),
    static_folder=str(Path(__file__).parent / "static"),
)
app.secret_key = secrets.token_hex(32)

# In-memory auth store by session id
_auth: Dict[str, Dict[str, Any]] = {}


# Handle normalization moved to utils.py


def _list_last_posts(client: Client, did: str, limit: int = 50) -> List[Dict[str, Any]]:
    posts: List[Dict[str, Any]] = []
    cursor: Optional[str] = None
    per_page = 100
    while len(posts) < limit:
        resp = client.com.atproto.repo.list_records(
            {
                "repo": did,
                "collection": "app.bsky.feed.post",
                "limit": min(per_page, limit - len(posts)),
                "cursor": cursor,
            }
        )
        records = getattr(resp, "records", []) or []
        if not records:
            break
        for rec in records:
            uri = getattr(rec, "uri", None)
            value = getattr(rec, "value", None) or {}
            # Skip replies
            is_reply = False
            if hasattr(value, "reply"):
                is_reply = bool(getattr(value, "reply") or None)
            elif isinstance(value, dict):
                is_reply = value.get("reply") is not None
            if is_reply:
                continue
            text = getattr(value, "text", None) if hasattr(value, "text") else value.get("text") if isinstance(value, dict) else None
            created_at = (
                getattr(value, "created_at", None)
                if hasattr(value, "created_at")
                else value.get("createdAt") if isinstance(value, dict) else None
            )
            if uri:
                posts.append({"uri": uri, "text": text, "created_at": created_at})
            if len(posts) >= limit:
                break
        cursor = getattr(resp, "cursor", None)
        if not cursor:
            break
    return posts


@app.route("/")
def index():
    info = None
    sid = session.get("sid")
    if sid and sid in _auth:
        info = {
            "handle": _auth[sid]["handle"],
            "display_name": _auth[sid].get("display_name"),
        }
    return render_template("simple.html", info=info)


@app.route("/login", methods=["POST"])  # JSON: {handle, password}
def login():
    try:
        data = request.get_json(force=True)
        handle = normalize_handle(data.get("handle", ""))
        password = data.get("password", "")
        if not handle or not password:
            return jsonify({"success": False, "error": "Handle and password required"}), 400
        if Client is None:
            return jsonify({"success": False, "error": "Missing atproto dependency"}), 500
        client = Client()
        client.login(handle, password)
        prof = client.get_profile(handle)
        did = getattr(prof, "did", None)
        display_name = getattr(prof, "display_name", None) or getattr(prof, "displayName", None) or handle
        sid = secrets.token_hex(16)
        session["sid"] = sid
        session.modified = True
        _auth[sid] = {"client": client, "handle": handle, "did": did, "display_name": display_name}
        return jsonify({"success": True, "handle": handle, "display_name": display_name})
    except Exception as e:  # pragma: no cover
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/hydrate-stream")
def hydrate_stream():
    sid = session.get("sid")
    if not sid or sid not in _auth:
        return jsonify({"success": False, "error": "Not authenticated"}), 401
    client: Client = _auth[sid]["client"]
    handle: str = _auth[sid]["handle"]
    did: str = _auth[sid]["did"]
    display_name: str = _auth[sid]["display_name"]

    def send(event: Dict[str, Any]):
        return f"data: {json.dumps(event)}\n\n"

    def generate():
        try:
            limit = 50
            try:
                limit = int(request.args.get("limit", 50))
            except Exception:
                limit = 50
            limit = max(1, min(500, limit))

            yield send({"stage": "start", "message": f"Hello {display_name} (@{handle})"})
            yield send({"stage": "listing", "message": f"Listing last {limit} posts..."})
            posts = _list_last_posts(client, did, limit=limit)
            yield send({"stage": "listed", "count": len(posts)})

            # Use optimized 25-item batch processing instead of individual processing
            total = len(posts)
            hydrated = []
            totals = {"likes": 0, "reposts": 0, "replies": 0, "quotes": 0}

            # Create batch processor for optimal API efficiency
            batch_processor = create_standard_batch_processor(client)
            
            # Extract URIs for batch processing
            uris = [p["uri"] for p in posts]
            post_lookup = {p["uri"]: p for p in posts}
            
            yield send({"stage": "batch_processing", "message": f"Processing {len(uris)} posts in 25-item batches..."})
            
            # Process posts in 25-item batches
            batch_result = batch_processor.batch_get_posts(uris)
            
            processed_count = 0
            for post_data in _iter_batch_post_payloads(batch_result):
                uri = post_data.get("uri")
                original_post = post_lookup.get(uri, {})

                processed_count += 1
                yield send(
                    {
                        "stage": "hydrating",
                        "index": processed_count,
                        "total": total,
                        "uri": uri,
                        "batch_mode": True,
                    }
                )

                # Use detailed hydration for accurate quote/reply counts
                hydrator = BlueskyEngagementHydrator(client=client)
                pe = hydrator.get_detailed_engagement(uri)

                hydrated.append(
                    {
                        "uri": uri,
                        "text": original_post.get("text"),
                        "created_at": original_post.get("created_at"),
                        "like_count": pe.like_count,
                        "repost_count": pe.repost_count,
                        "reply_count": pe.reply_count,
                        "quote_count": pe.quote_count,
                    }
                )
                totals["likes"] += pe.like_count
                totals["reposts"] += pe.repost_count
                totals["replies"] += pe.reply_count
                totals["quotes"] += pe.quote_count
            
            yield send({
                "stage": "batch_complete", 
                "message": f"Batch processing complete! {batch_result.success_rate:.1f}% success rate"
            })

            # Save JSON file under site_gpt5/tmp using utility
            out_dir = Path(__file__).parent / "tmp"
            out_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_name = f"hydrated_{format_file_safe_name(handle, ts)}.json"
            out_path = out_dir / out_name
            
            # Convert hydrated items to content item format for utility
            content_items = []
            for h in hydrated:
                item = type('ContentItem', (), {
                    'uri': h['uri'],
                    'cid': h.get('cid'),
                    'content_type': 'post',
                    'text': h.get('text'),
                    'created_at': h.get('created_at'),
                    'like_count': h['like_count'],
                    'repost_count': h['repost_count'],
                    'reply_count': h['reply_count'], 
                    'quote_count': h['quote_count'],
                    'raw_data': {}
                })()
                content_items.append(item)
            
            export_data = PostDataExporter.export_post_data(
                content_items, handle, did, display_name
            )
            
            with open(out_path, "w") as f:
                json.dump(export_data, f, indent=2)

            yield send({
                "stage": "done",
                "summary": {
                    "username": display_name,
                    "handle": handle,
                    "posts": len(hydrated),
                    "likes": totals["likes"],
                    "comments": totals["replies"],
                    "reposts": totals["reposts"],
                    "quotes": totals["quotes"],
                    "json_path": str(out_path),
                    "download": f"/download-json?name={out_name}",
                },
            })
        except Exception as e:  # pragma: no cover
            yield send({"stage": "error", "error": str(e)})

    return Response(generate(), mimetype="text/event-stream")


@app.route("/download-json")
def download_json():
    name = request.args.get("name")
    if not name:
        return jsonify({"success": False, "error": "Missing file name"}), 400
    # Security: only serve files from tmp/
    tmp_dir = Path(__file__).parent / "tmp"
    target = tmp_dir / name
    if not target.exists() or target.parent != tmp_dir:
        return jsonify({"success": False, "error": "File not found"}), 404
    return send_from_directory(str(tmp_dir), name, as_attachment=True)

@app.route("/start-car-download", methods=["POST"])
def start_car_download():
    """Start background CAR file download."""
    sid = session.get("sid")
    if not sid or sid not in _auth:
        return jsonify({"success": False, "error": "Not authenticated"}), 401
    
    handle = _auth[sid]["handle"]
    client = _auth[sid]["client"]
    
    # Mock DataManager for CAR download (since web_simple doesn't have full Skymarshal integration)
    try:
        from skymarshal.data_manager import DataManager
        from skymarshal.models import UserSettings
        from skymarshal.auth import AuthManager
        
        # Create mock auth manager with the client
        mock_auth = type('MockAuth', (), {
            'client': client,
            'current_handle': handle,
            'is_authenticated': lambda: True
        })()
        
        settings = UserSettings()
        base = Path.home() / ".skymarshal"
        cars_dir = base / "cars" 
        json_dir = base / "json"
        base.mkdir(parents=True, exist_ok=True)
        cars_dir.mkdir(parents=True, exist_ok=True)
        json_dir.mkdir(parents=True, exist_ok=True)
        
        data_manager = DataManager(mock_auth, settings, base, cars_dir, json_dir)
        
        # Start background download
        car_manager = get_car_download_manager()
        task_id = car_manager.start_car_download(mock_auth, handle, data_manager)
        
        return jsonify({
            "success": True,
            "task_id": task_id,
            "message": "CAR download started in background"
        })
        
    except ImportError:
        # Fallback: simple message if Skymarshal not available
        return jsonify({
            "success": False,
            "error": "CAR download requires full Skymarshal installation"
        }), 501

@app.route("/car-download-status", methods=["GET"])
def car_download_status():
    """Get CAR download status."""
    sid = session.get("sid")
    if not sid or sid not in _auth:
        return jsonify({"success": False, "error": "Not authenticated"}), 401
    
    handle = _auth[sid]["handle"]
    car_manager = get_car_download_manager()
    download_task = car_manager.get_download_status(handle)
    
    if not download_task:
        return jsonify({
            "success": True,
            "status": "none",
            "message": "No CAR download in progress"
        })
    
    return jsonify({
        "success": True,
        "status": download_task.status.value,
        "progress": {
            "current": download_task.progress.current,
            "total": download_task.progress.total,
            "percentage": download_task.progress.percentage,
            "message": download_task.progress.message
        },
        "download_url": f"/download-car?handle={handle}" if download_task.status == TaskStatus.COMPLETED else None,
        "file_size": download_task.result.get("file_size") if download_task.result else None,
        "duration": download_task.duration
    })

@app.route("/download-car", methods=["GET"])
def download_car_file():
    """Download completed CAR file."""
    handle = request.args.get("handle")
    sid = session.get("sid")
    
    if not sid or sid not in _auth:
        return jsonify({"success": False, "error": "Not authenticated"}), 401
    
    session_handle = _auth[sid]["handle"]
    if session_handle != handle:
        return jsonify({"success": False, "error": "Access denied"}), 403
    
    car_manager = get_car_download_manager()
    download_task = car_manager.get_download_status(handle)
    
    if not download_task or download_task.status != TaskStatus.COMPLETED:
        return jsonify({"success": False, "error": "CAR file not ready"}), 404
    
    if download_task.result and "car_path" in download_task.result:
        car_path = Path(download_task.result["car_path"])
        if car_path.exists():
            return send_from_directory(
                str(car_path.parent),
                car_path.name,
                as_attachment=True,
                download_name=f"{handle}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.car"
            )
    
    return jsonify({"success": False, "error": "CAR file not found"}), 404


if __name__ == "__main__":
    port = int((Path(__file__).parent / ".env.port").read_text().strip()) if (Path(__file__).parent / ".env.port").exists() else 5006
    app.run(host="0.0.0.0", port=port, debug=True)
