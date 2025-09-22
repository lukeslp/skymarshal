#!/usr/bin/env python3
"""
Minimal single-page Flask site for Skymarshal

Flow:
1) Authenticate user (handle + app password)
2) Download their CAR file
3) Import data from CAR and hydrate with like/repost/reply
4) Display simple statistics

This reuses core Skymarshal managers: AuthManager, DataManager, models.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from datetime import datetime
from typing import Any, Dict
import time
import requests

from flask import Flask, render_template, request, jsonify, session, redirect, url_for

# Import Skymarshal components
from skymarshal.auth import AuthManager
from skymarshal.data_manager import DataManager
from skymarshal.models import UserSettings, calculate_engagement_score, parse_datetime

# Import local utilities
from utils import (
    normalize_handle, 
    create_bluesky_client, 
    PostDataExporter,
    EngagementAggregator,
    safe_getattr
)
from background_tasks import (
    get_task_manager, 
    get_car_download_manager, 
    get_parallel_hydration_manager,
    TaskStatus,
    TaskType
)
# from improved_hydration import (
#     BlueskyEngagementHydrator,
#     hydrate_bluesky_posts,
#     PostEngagement,
# )
try:
    from atproto import Client as ATClient
    from atproto import models as ATModels
except Exception:
    ATClient = None  # type: ignore
    ATModels = None  # type: ignore

# Optional settings manager for defaults
try:
    from skymarshal.settings import SettingsManager
except Exception:
    SettingsManager = None  # type: ignore

app = Flask(
    __name__,
    template_folder=str(Path(__file__).parent / "templates"),
    static_folder=str(Path(__file__).parent / "static"),
)
app.secret_key = os.environ.get("SKYM_SECRET", secrets.token_hex(32))
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=False,  # Set True behind HTTPS
)

# Fast hydrate mode: prefer single get_posts pass; skip exact per-edge endpoints by default
# Default OFF so we do precise counts unless explicitly enabled
FAST_HYDRATE = os.environ.get("SKY_FAST_HYDRATE", "0") == "1"
HYDRATE_BUDGET_S = float(os.environ.get("SKY_HYDRATE_BUDGET_S", "10"))

# In-memory store of AuthManager per session
_auth_by_sid: Dict[str, AuthManager] = {}


def get_settings() -> UserSettings:
    if SettingsManager is not None:
        settings_file = Path.home() / ".car_inspector_settings.json"
        return SettingsManager(settings_file).settings
    return UserSettings()


def get_dirs():
    base = Path.home() / ".skymarshal"
    cars = base / "cars"
    json_dir = base / "json"
    base.mkdir(parents=True, exist_ok=True)
    cars.mkdir(parents=True, exist_ok=True)
    json_dir.mkdir(parents=True, exist_ok=True)
    return base, cars, json_dir


def get_auth() -> AuthManager | None:
    sid = session.get("sid")
    if not sid:
        return None

    auth = _auth_by_sid.get(sid)
    # If missing or not authenticated, try to reconstruct from stored session payload
    if auth is None or not auth.is_authenticated():
        try:
            stored = session.get("auth_session")
            handle = session.get("handle")
            did = session.get("did")
            if stored and isinstance(stored, dict):
                new_auth = AuthManager()
                # Import session payload (refresh token capable)
                if new_auth._import_session_payload(stored):  # type: ignore[attr-defined]
                    new_auth.current_handle = handle
                    new_auth.current_did = did
                    _auth_by_sid[sid] = new_auth
                    auth = new_auth
            # Fallback to disk-based session if available
            if (auth is None or not auth.is_authenticated()):
                new_auth2 = AuthManager()
                if new_auth2.try_resume_session():
                    _auth_by_sid[sid] = new_auth2
                    auth = new_auth2
            # Final fallback for guest mode: construct a minimal public client if possible
            if (auth is None or not auth.is_authenticated()) and handle and ATClient is not None:
                guest = AuthManager()
                try:
                    guest.client = ATClient()
                except Exception:
                    guest = None  # type: ignore[assignment]
                if guest is not None:
                    guest.current_handle = handle
                    guest.current_did = did
                    _auth_by_sid[sid] = guest
                    auth = guest
        except Exception:
            pass
    return auth


def _web_safe_hydrate(
    auth: AuthManager | None,
    settings: UserSettings,
    base: Path,
    cars_dir: Path,
    json_dir: Path,
    items,
) -> Dict[str, int]:
    """Hydrate engagement counts without interactive prompts and return quotes per URI.
    
    Uses the simplified, working hydration approach from WORKING/ implementations.
    """
    # Get client for hydration
    client = None
    if auth and safe_getattr(auth, "client", None) is not None:
        client = auth.client
    elif ATClient is not None:
        client = create_bluesky_client()
    
    if client is None:
        print("DEBUG: No client available for hydration")
        return {}
    
    print(f"DEBUG: Starting hydration for {len(items)} items")
    
    # Use the working hydration approach - simple and direct
    from improved_hydration import BlueskyEngagementHydrator
    
    # Create hydrator with conservative settings
    hydrator = BlueskyEngagementHydrator(client=client, rate_limit_delay=0.4)
    
    # Filter to posts and replies only
    posts_to_hydrate = [item for item in items 
                       if getattr(item, "content_type", "") in ("post", "reply") 
                       and getattr(item, "uri", None)]
    
    if not posts_to_hydrate:
        print("DEBUG: No posts found to hydrate")
        return {}
    
    print(f"DEBUG: Hydrating {len(posts_to_hydrate)} posts using detailed engagement")
    
    quotes_by_uri = {}
    
    # For small datasets, use detailed engagement (individual calls per post)
    if len(posts_to_hydrate) <= 50:
        print("DEBUG: Using detailed engagement for small dataset")
        for i, item in enumerate(posts_to_hydrate):
            try:
                uri = item.uri
                print(f"DEBUG: Hydrating {i+1}/{len(posts_to_hydrate)}: {uri}")
                
                # Get detailed engagement using the working method
                pe = hydrator.get_detailed_engagement(uri)
                
                # Update the item with engagement data
                item.like_count = pe.like_count
                item.repost_count = pe.repost_count
                item.reply_count = pe.reply_count
                quotes_by_uri[uri] = pe.quote_count
                
                # Update engagement score if available
                if hasattr(item, "update_engagement_score"):
                    item.update_engagement_score()
                
                print(f"DEBUG: Hydrated {uri}: L={pe.like_count} R={pe.repost_count} Rep={pe.reply_count} Q={pe.quote_count}")
                
            except Exception as e:
                print(f"DEBUG: Failed to hydrate {getattr(item, 'uri', 'unknown')}: {e}")
                continue
    else:
        # For larger datasets, use batch processing with fast hydrate
        print("DEBUG: Using batch processing for large dataset")
        try:
            engagement_data = hydrator.hydrate_posts_batch(posts_to_hydrate, detailed=False)
            
            # Update items with batch results
            for item in posts_to_hydrate:
                uri = getattr(item, "uri", None)
                if uri and uri in engagement_data:
                    pe = engagement_data[uri]
                    item.like_count = pe.like_count
                    item.repost_count = pe.repost_count
                    item.reply_count = pe.reply_count
                    quotes_by_uri[uri] = pe.quote_count
                    
                    if hasattr(item, "update_engagement_score"):
                        item.update_engagement_score()
            
            print(f"DEBUG: Batch hydrated {len(engagement_data)} items")
            
        except Exception as e:
            print(f"DEBUG: Batch hydration failed, falling back to detailed: {e}")
            # Fallback to detailed for each item
            for item in posts_to_hydrate:
                try:
                    uri = item.uri
                    pe = hydrator.get_detailed_engagement(uri)
                    item.like_count = pe.like_count
                    item.repost_count = pe.repost_count
                    item.reply_count = pe.reply_count
                    quotes_by_uri[uri] = pe.quote_count
                    
                    if hasattr(item, "update_engagement_score"):
                        item.update_engagement_score()
                        
                except Exception as e2:
                    print(f"DEBUG: Failed fallback hydration for {getattr(item, 'uri', 'unknown')}: {e2}")
                    continue
    
    print(f"DEBUG: Hydration complete. Updated {len(quotes_by_uri)} items with quote counts")
    return quotes_by_uri


# Removed complex hydration functions - now using simplified BlueskyEngagementHydrator approach


@app.route("/", methods=["GET"]) 
def index():
    if session.get("sid") and session.get("handle"):
        # Pre-fill stats/handle for template
        stats = session.get("stats")
        return render_template(
            "index.html",
            logged_in=True,
            handle=session.get("handle"),
            stats=stats,
        )
    return render_template("index.html", logged_in=False, handle=None, stats=None)


@app.route("/login", methods=["POST"]) 
def login():
    data = request.get_json(force=True)  # type: ignore
    handle = (data or {}).get("handle", "").strip()
    password = (data or {}).get("password", "").strip()
    if not handle or not password:
        return jsonify({"success": False, "error": "Handle and app password required"}), 400

    auth = AuthManager()
    norm = normalize_handle(handle)

    if not auth.authenticate_client(norm, password):
        # Allow non-app passwords: proceed with limited guest mode (no write, public hydration only)
        sid = secrets.token_hex(16)
        session["sid"] = sid
        session["handle"] = norm
        session["did"] = None
        session["auth_session"] = None
        session.modified = True
        # Provide a minimal client for public GETs if possible
        try:
            if ATClient is not None:
                placeholder = AuthManager()
                placeholder.client = ATClient()
                placeholder.current_handle = norm
                _auth_by_sid[sid] = placeholder
        except Exception:
            _auth_by_sid[sid] = auth
        return jsonify({"success": True, "auth": "guest"})

    # Persist to session (authenticated)
    sid = secrets.token_hex(16)
    session["sid"] = sid
    session["handle"] = norm
    session["did"] = getattr(auth, "current_did", None)
    # Save session to disk and store payload in Flask session for rehydration across reloads
    try:
        auth.save_session()
        payload = auth._export_session_payload()  # type: ignore[attr-defined]
        if isinstance(payload, dict):
            session["auth_session"] = payload
    except Exception:
        pass
    session.modified = True
    _auth_by_sid[sid] = auth

    return jsonify({"success": True, "auth": "ok"})


@app.route("/download", methods=["POST"]) 
def download_car():
    # Require auth
    auth = get_auth()
    handle = session.get("handle")
    if not auth or not handle:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    # Prepare managers
    settings = get_settings()
    base, cars_dir, json_dir = get_dirs()
    data_manager = DataManager(auth, settings, base, cars_dir, json_dir)

    # Start background CAR download
    car_manager = get_car_download_manager()
    task_id = car_manager.start_car_download(auth, handle, data_manager)

    # Store task ID in session for tracking
    session["car_download_task_id"] = task_id
    session.modified = True

    return jsonify({
        "success": True, 
        "task_id": task_id,
        "message": "CAR download started in background"
    })


@app.route("/process", methods=["POST"]) 
def process_car():
    # Require at least a handle and either an authenticated or guest client
    auth = get_auth()
    handle = session.get("handle")
    car_path = session.get("car_path")
    if not handle:
        return jsonify({"success": False, "error": "Missing handle"}), 400
    if not auth:
        return jsonify({"success": False, "error": "Missing client"}), 400
    # If no CAR yet, try to locate most recent matching CAR as fallback
    if not car_path:
        base, cars_dir, _ = get_dirs()
        try:
            pattern = f"{handle.replace('.', '_')}*.car"
            candidates = sorted(cars_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
            if candidates:
                car_path = str(candidates[0])
                session["car_path"] = car_path
                session.modified = True
        except Exception:
            pass
    if not car_path:
        return jsonify({"success": False, "error": "No CAR found. Download first."}), 400

    settings = get_settings()
    base, cars_dir, json_dir = get_dirs()
    data_manager = DataManager(auth, settings, base, cars_dir, json_dir)

    # Import CAR and replace JSON
    # For testing, process only posts to reduce workload
    out_json = data_manager.import_car_replace(Path(car_path), handle=handle, categories={"posts"})
    if not out_json:
        return jsonify({"success": False, "error": "Import failed"}), 500

    # Load items and hydrate engagement if authenticated (web-safe, non-interactive)
    items_all = data_manager.load_exported_data(out_json)
    # Limit to the most recent 100 posts for faster testing
    posts_sorted = sorted(
        [it for it in items_all if it.content_type == "post"],
        key=lambda it: parse_datetime(it.created_at) or datetime.min,
        reverse=True,
    )
    items = posts_sorted[:100]
    # Use existing hydrator to ensure per-edge counts (likes/reposts/replies/quotes)
    quotes_by_uri = _web_safe_hydrate(auth, settings, base, cars_dir, json_dir, items)

    # Save the hydrated data back to the JSON file
    try:
        import json as json_lib
        
        # Check if hydration actually worked
        hydrated_items = [item for item in items if (item.like_count > 0 or item.repost_count > 0 or item.reply_count > 0)]
        print(f"DEBUG: Found {len(hydrated_items)} items with engagement data after hydration")
        
        # Use utility for consistent export format
        export_data_dict = PostDataExporter.export_post_data(
            items_all, handle, quotes_by_uri=quotes_by_uri
        )
        
        with open(out_json, 'w') as f:
            json_lib.dump(export_data_dict['posts'], f, indent=2, default=str)
        print(f"DEBUG: Saved {len(export_data_dict['posts'])} items with hydrated engagement data")
        print(f"DEBUG: Items with engagement: {len([x for x in export_data_dict['posts'] if x['like_count'] > 0 or x['repost_count'] > 0 or x['reply_count'] > 0])}")
    except Exception as e:
        print(f"DEBUG: Failed to save hydrated data: {e}")

    # Compute engagement metrics for user's posts (likes/reposts/replies received)
    posts = items  # recent posts only
    
    # Add quote counts to items for aggregation
    for item in posts:
        item.quote_count = quotes_by_uri.get(getattr(item, "uri", ""), 0)
    
    # Use utility for consistent engagement calculation
    engagement_stats = EngagementAggregator.calculate_totals(posts)

    stats = {
        "counts": {
            "posts": engagement_stats["posts"],
            "total_items": engagement_stats["posts"],
        },
        "engagement": {
            "likes_received": engagement_stats["likes_received"],
            "reposts_received": engagement_stats["reposts_received"],
            "replies_received": engagement_stats["replies_received"],
            "quotes_received": engagement_stats["quotes_received"],
            "total_engagement": engagement_stats["total_engagement"],
            "avg_engagement": engagement_stats["avg_engagement"],
        },
    }

    # Persist json path for subsequent page render
    session["json_path"] = str(out_json)
    session["stats"] = stats
    session.modified = True

    return jsonify({"success": True, "stats": stats})


@app.route("/stats", methods=["GET"]) 
def stats():
    if not session.get("sid"):
        return redirect(url_for("index"))
    stats = session.get("stats")
    handle = session.get("handle")
    return render_template("index.html", logged_in=True, handle=handle, stats=stats)


@app.route("/refresh-engagement", methods=["POST"])
def refresh_engagement():
    """Refresh engagement data for existing JSON file"""
    try:
        auth = get_auth()
        handle = session.get("handle")
        json_path = session.get("json_path")
        
        if not auth or not handle:
            return jsonify({"success": False, "error": "Authentication required"}), 401
        
        if not json_path or not Path(json_path).exists():
            return jsonify({"success": False, "error": "No data file found"}), 404
        
        settings = get_settings()
        base, cars_dir, json_dir = get_dirs()
        data_manager = DataManager(auth, settings, base, cars_dir, json_dir)
        
        # Load existing data
        items = data_manager.load_exported_data(Path(json_path))
        
        # Find posts that need hydration
        posts_to_hydrate = [item for item in items if item.content_type in ['post', 'reply']]
        
        if not posts_to_hydrate:
            return jsonify({"success": True, "message": "No posts found to hydrate", "hydrated": 0})
        
        # Limit to first 100 for faster processing
        posts_to_hydrate = posts_to_hydrate[:100]
        
        # Hydrate engagement data
        quotes_by_uri = _web_safe_hydrate(auth, settings, base, cars_dir, json_dir, posts_to_hydrate)
        
        # Save updated data back to JSON
        try:
            import json as json_lib
            export_data = []
            for item in items:
                item_dict = {
                    'uri': item.uri,
                    'cid': item.cid,
                    'content_type': item.content_type,
                    'text': item.text,
                    'created_at': item.created_at,
                    'like_count': getattr(item, 'like_count', 0),
                    'repost_count': getattr(item, 'repost_count', 0),
                    'reply_count': getattr(item, 'reply_count', 0),
                    'quote_count': quotes_by_uri.get(getattr(item, 'uri', ''), 0),
                    'engagement_score': getattr(item, 'engagement_score', 0),
                    'raw_data': item.raw_data
                }
                export_data.append(item_dict)
            
            with open(json_path, 'w') as f:
                json_lib.dump(export_data, f, indent=2, default=str)
            
            return jsonify({
                "success": True, 
                "message": f"Successfully updated engagement for {len(posts_to_hydrate)} items",
                "hydrated": len(posts_to_hydrate)
            })
            
        except Exception as e:
            return jsonify({"success": False, "error": f"Failed to save data: {str(e)}"})
            
    except Exception as e:
        return jsonify({"success": False, "error": f"Refresh failed: {str(e)}"})


@app.route("/task-status/<task_id>", methods=["GET"])
def get_task_status(task_id: str):
    """Get status of a background task."""
    task_manager = get_task_manager()
    task = task_manager.get_task(task_id)
    
    if not task:
        return jsonify({"success": False, "error": "Task not found"}), 404
    
    return jsonify({
        "success": True,
        "task": {
            "id": task.task_id,
            "type": task.task_type.value,
            "status": task.status.value,
            "progress": {
                "current": task.progress.current,
                "total": task.progress.total,
                "percentage": task.progress.percentage,
                "message": task.progress.message
            },
            "result": task.result,
            "error": task.error,
            "duration": task.duration,
            "metadata": task.metadata
        }
    })

@app.route("/download-car", methods=["GET"])
def download_car_file():
    """Download completed CAR file."""
    handle = request.args.get("handle")
    path = request.args.get("path")
    
    if not handle:
        return jsonify({"success": False, "error": "Handle required"}), 400
    
    # Check if user has access to this handle's data
    session_handle = session.get("handle")
    if session_handle != handle:
        return jsonify({"success": False, "error": "Access denied"}), 403
    
    # Get CAR download status
    car_manager = get_car_download_manager()
    download_task = car_manager.get_download_status(handle)
    
    if not download_task or download_task.status != TaskStatus.COMPLETED:
        return jsonify({"success": False, "error": "CAR file not ready"}), 404
    
    # Get CAR path from task result
    if download_task.result and "car_path" in download_task.result:
        car_path = Path(download_task.result["car_path"])
        if car_path.exists():
            from flask import send_file
            return send_file(
                car_path,
                as_attachment=True,
                download_name=f"{handle}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.car"
            )
    
    return jsonify({"success": False, "error": "CAR file not found"}), 404

@app.route("/car-download-status", methods=["GET"])
def car_download_status():
    """Get CAR download status for current user."""
    handle = session.get("handle")
    if not handle:
        return jsonify({"success": False, "error": "Not authenticated"}), 401
    
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
        "download_url": download_task.result.get("download_url") if download_task.result else None,
        "file_size": download_task.result.get("file_size") if download_task.result else None,
        "duration": download_task.duration
    })

@app.route("/start-parallel-hydration", methods=["POST"])
def start_parallel_hydration():
    """Start parallel hydration for multiple users (future feature)."""
    # This would be used for batch processing multiple users
    # For now, return not implemented
    return jsonify({
        "success": False, 
        "error": "Parallel hydration not implemented in this interface"
    }), 501

@app.route("/logout", methods=["POST"]) 
def logout():
    sid = session.get("sid")
    try:
        if sid and sid in _auth_by_sid:
            # Best-effort logout/cleanup
            try:
                _auth_by_sid[sid].logout()
            except Exception:
                pass
            _auth_by_sid.pop(sid, None)
        
        # Cancel any background tasks for this session
        task_manager = get_task_manager()
        task_id = session.get("car_download_task_id")
        if task_id:
            task_manager.cancel_task(task_id)
        
        session.clear()
    except Exception:
        session.clear()
    return jsonify({"success": True})


if __name__ == "__main__":
    # Default to 5003 to avoid conflicts
    port = int(os.environ.get("PORT", "5003"))
    app.run(debug=True, host="0.0.0.0", port=port)
