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

    Attempts one silent re-auth using stored payload if auth errors occur.
    """
    deadline = time.time() + HYDRATE_BUDGET_S
    print(f"DEBUG: Starting hydration with {len(list(items))} items, FAST_HYDRATE={FAST_HYDRATE}")
    
    # Small dataset: go straight to exact endpoints for precise metrics
    try:
        if len(list(items)) <= 50:
            print(f"DEBUG: Small dataset path - using exact endpoints")
            client = None
            if auth and getattr(auth, "client", None) is not None:
                client = auth.client
                print(f"DEBUG: Using authenticated client")
            elif ATClient is not None:
                try:
                    client = ATClient()
                    print(f"DEBUG: Using unauthenticated client")
                except Exception:
                    client = None
            if client is not None:
                print(f"DEBUG: Calling _hydrate_post_edges_exact with {len(items)} items")
                result = _hydrate_post_edges_exact(client, items)
                print(f"DEBUG: _hydrate_post_edges_exact returned {len(result)} quotes")
                return result
            else:
                print(f"DEBUG: No client available for small dataset path")
    except Exception as e:
        print(f"DEBUG: Small dataset path failed: {e}")
        pass

    # Large dataset: optionally fast path first
    if FAST_HYDRATE:
        try:
            client = None
            if auth and getattr(auth, "client", None) is not None:
                client = auth.client
            elif ATClient is not None:
                try:
                    client = ATClient()
                except Exception:
                    client = None
            if client is not None:
                index = {getattr(it, "uri", None): it for it in items if getattr(it, "uri", None)}
                uris = [it.uri for it in items if getattr(it, "content_type", "") in ("post", "reply") and it.uri]
                for i in range(0, len(uris), 25):
                    if time.time() > deadline:
                        break
                    batch = uris[i : i + 25]
                    posts = []
                    try:
                        resp = client.get_posts(uris=batch)
                        posts = getattr(resp, "posts", []) or []
                    except Exception:
                        try:
                            params = [("uris", u) for u in batch]
                            r = requests.get("https://api.bsky.app/xrpc/app.bsky.feed.getPosts", params=params, timeout=3.0)
                            if r.ok:
                                posts = r.json().get("posts", [])
                        except Exception:
                            posts = []
                    for p in posts:
                        uri = getattr(p, "uri", None) if hasattr(p, "uri") else p.get("uri")
                        it = index.get(uri)
                        if not it:
                            continue
                        like_v = getattr(p, "like_count", None) if hasattr(p, "like_count") else p.get("likeCount", 0)
                        repost_v = getattr(p, "repost_count", None) if hasattr(p, "repost_count") else p.get("repostCount", 0)
                        reply_v = getattr(p, "reply_count", None) if hasattr(p, "reply_count") else p.get("replyCount", 0)
                        it.like_count = int(like_v or 0)
                        it.repost_count = int(repost_v or 0)
                        it.reply_count = int(reply_v or 0)
                        if hasattr(it, "update_engagement_score"):
                            it.update_engagement_score()
        except Exception:
            pass

    if not auth or not auth.is_authenticated():
        # Attempt unauthenticated hydration via public AppView endpoints if available
        if ATClient is None:
            return {}
        try:
            client = ATClient()
            # conservative chunk
            chunk_size = 20
            index = {getattr(it, "uri", None): it for it in items if getattr(it, "uri", None)}
            uris = [it.uri for it in items if getattr(it, "content_type", "") in ("post", "reply") and it.uri]
            for i in range(0, len(uris), chunk_size):
                batch = uris[i : i + chunk_size]
                attempts = 0
                backoff = 1.0
                while attempts < 3:
                    try:
                        resp = client.get_posts(uris=batch)
                        posts = getattr(resp, "posts", []) or []
                        for p in posts:
                            uri = getattr(p, "uri", None)
                            it = index.get(uri)
                            if not it:
                                continue
                            it.like_count = int(getattr(p, "like_count", 0) or 0)
                            it.repost_count = int(getattr(p, "repost_count", 0) or 0)
                            it.reply_count = int(getattr(p, "reply_count", 0) or 0)
                            if hasattr(it, "update_engagement_score"):
                                it.update_engagement_score()
                        break
                    except Exception:
                        attempts += 1
                        time.sleep(backoff)
                        backoff = min(backoff * 2, 8.0)
            # Refine counts using exact endpoints and collect quotes
            return _hydrate_post_edges_exact(client, items)
        except Exception:
            return {}

    dm = DataManager(auth, settings, base, cars_dir, json_dir)
    # Posts + replies
    pr_items = [it for it in items if getattr(it, "content_type", "") in ("post", "reply")]
    rp_items = [it for it in items if getattr(it, "content_type", "") == "repost"] if settings.use_subject_engagement_for_reposts else []

    # Use conservative chunk size to reduce auth/rate pressure
    chunk_size = max(1, min(20, getattr(settings, "hydrate_batch_size", 25)))

    def hydrate_with_retries(callable_fn, chunk_label: str):
        attempts = 0
        backoff = 1.0
        while attempts < 3:
            try:
                callable_fn()
                return True
            except Exception as e:
                msg = str(e).lower()
                # Try single-session rebuild on auth errors
                if any(s in msg for s in ("auth", "unauthorized", "token", "expired", "forbidden")):
                    try:
                        stored = session.get("auth_session")
                        if stored and isinstance(stored, dict):
                            rebuilt = AuthManager()
                            if rebuilt._import_session_payload(stored):  # type: ignore[attr-defined]
                                rebuilt.current_handle = session.get("handle")
                                rebuilt.current_did = session.get("did")
                                _auth_by_sid[session.get("sid")] = rebuilt  # type: ignore[index]
                                nonlocal dm
                                dm = DataManager(rebuilt, settings, base, cars_dir, json_dir)
                                # Retry immediately after rebuild (does not consume backoff attempt)
                                callable_fn()
                                return True
                    except Exception:
                        pass
                # Backoff for transient/rate issues
                attempts += 1
                time.sleep(backoff)
                backoff = min(backoff * 2, 8.0)
        return False

    # Hydrate posts/replies in chunks (for larger datasets)
    for i in range(0, len(pr_items), chunk_size):
        chunk = pr_items[i : i + chunk_size]
        hydrate_with_retries(lambda c=chunk: dm._hydrate_post_engagement(c), "posts")  # type: ignore[attr-defined]

    # Hydrate repost subject metrics in chunks (optional)
    for i in range(0, len(rp_items), chunk_size):
        chunk = rp_items[i : i + chunk_size]
        hydrate_with_retries(lambda c=chunk: dm._hydrate_repost_subject_engagement(c), "reposts")  # type: ignore[attr-defined]

    # Update scores
    for it in items:
        if hasattr(it, "update_engagement_score"):
            it.update_engagement_score()
    # Refine counts using exact endpoints and collect quotes
    client = getattr(dm, "auth", None)
    client = getattr(client, "client", None)
    if client is None and ATClient is not None:
        try:
            client = ATClient()
        except Exception:
            client = None
    if client is not None:
        return _hydrate_post_edges_exact(client, items)
    return {}


def _safe_get(obj, name: str, default=None):
    try:
        return getattr(obj, name)
    except Exception:
        return default


def _count_paginated_items(client, method_name: str, uri: str, list_key: str, per_page: int = 100, max_pages: int = 50, deadline: float | None = None) -> int:
    total = 0
    cursor = None
    pages = 0
    attempts = 0
    while pages < max_pages:
        if deadline is not None and time.time() > deadline:
            break
        try:
            # Always prefer HTTP AppView with short timeout to avoid client-level hangs
            endpoint = None
            if method_name == "get_likes":
                endpoint = "https://api.bsky.app/xrpc/app.bsky.feed.getLikes"
            elif method_name == "get_reposted_by":
                endpoint = "https://api.bsky.app/xrpc/app.bsky.feed.getRepostedBy"
            elif method_name == "get_quotes":
                endpoint = "https://api.bsky.app/xrpc/app.bsky.feed.getQuotes"
            if endpoint is None:
                break
            params = {"uri": uri, "limit": per_page}
            if cursor:
                params["cursor"] = cursor
            r = requests.get(endpoint, params=params, timeout=3.0)
            if not r.ok:
                raise RuntimeError(f"HTTP {r.status_code}")
            data = r.json()
            items = data.get(list_key, []) or []
            total += len(items)
            cursor = data.get("cursor")
            if not cursor:
                break
            pages += 1
            attempts = 0  # reset on success
        except Exception:
            attempts += 1
            if attempts >= 3:
                break
            time.sleep(min(0.4 * (2 ** (attempts - 1)), 2.0))
    return total


def _count_post_replies(client, uri: str, max_depth: int = 1, deadline: float | None = None) -> int:
    try:
        if deadline is not None and time.time() > deadline:
            return 0
        # Prefer HTTP with timeout
        params = {"uri": uri, "depth": max_depth, "parentHeight": 0}
        try:
            r = requests.get("https://api.bsky.app/xrpc/app.bsky.feed.getPostThread", params=params, timeout=3.0)
            if not r.ok:
                raise RuntimeError("thread http failed")
            data = r.json()
            root = data.get("thread")
        except Exception:
            # Fallback to client if HTTP fails
            if ATModels is not None:
                model_params = ATModels.AppBskyFeedGetPostThread.Params(uri=uri, depth=max_depth, parent_height=0)
                resp = client.app.bsky.feed.get_post_thread(model_params)
                root = _safe_get(resp, "thread", None)
            else:
                method = _safe_get(_safe_get(_safe_get(client, "app", None), "bsky", None), "feed", None)
                method = _safe_get(method, "get_post_thread")
                if not callable(method):
                    return 0
                resp = method({"uri": uri, "depth": max_depth, "parentHeight": 0})
                root = _safe_get(resp, "thread", None)

        if root is None:
            return 0

        def traverse(node) -> int:
            total = 0
            replies = _safe_get(node, "replies", None) or []
            for r in replies:
                post = _safe_get(r, "post", None)
                if post is not None:
                    total += 1
                total += traverse(r)
            return total

        return traverse(root)
    except Exception:
        return 0


def _hydrate_post_edges_exact(client, items) -> Dict[str, int]:
    """Use feed endpoints to get precise counts per post and collect quotes per URI."""
    quotes_by_uri: Dict[str, int] = {}
    posts = [it for it in items if getattr(it, "content_type", "") in ("post", "reply") and getattr(it, "uri", None)]
    # Process one-by-one with per-post retries/backoff to avoid sticking
    deadline = time.time() + HYDRATE_BUDGET_S
    for it in posts:
        uri = it.uri
        likes = reposts = quotes = replies = 0
        tries = 0
        delay = 0.5
        while tries < 3:
            if time.time() > deadline:
                break
            try:
                # Likes
                likes = _count_paginated_items(client, "get_likes", uri, "likes", deadline=deadline)
                # Reposts
                reposts = _count_paginated_items(client, "get_reposted_by", uri, "reposted_by", deadline=deadline)
                # Quotes
                quotes = _count_paginated_items(client, "get_quotes", uri, "posts", deadline=deadline)
                # Replies (limited depth)
                replies = _count_post_replies(client, uri, max_depth=1, deadline=deadline)
                break
            except Exception:
                tries += 1
                time.sleep(delay)
                delay = min(delay * 2, 4.0)

        # Apply
        it.like_count = int(likes)
        it.repost_count = int(reposts)
        it.reply_count = int(replies)
        if hasattr(it, "update_engagement_score"):
            it.update_engagement_score()
        try:
            print(f"DEBUG: Hydrated {uri}: likes={likes}, reposts={reposts}, replies={replies}, quotes={quotes}")
            print(f"DEBUG: Item after update: like_count={it.like_count}, repost_count={it.repost_count}, reply_count={it.reply_count}")
        except Exception:
            pass
        quotes_by_uri[uri] = int(quotes)

    return quotes_by_uri


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
    norm = auth.normalize_handle(handle)

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

    # Download timestamped CAR
    car_path = data_manager.download_car(handle)
    if not car_path:
        return jsonify({"success": False, "error": "CAR download failed"}), 500

    session["car_path"] = str(car_path)
    session.modified = True
    return jsonify({"success": True, "car": str(car_path)})


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
        
        export_data = []
        for item in items_all:  # Save all items, not just the 100 processed
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
        
        with open(out_json, 'w') as f:
            json_lib.dump(export_data, f, indent=2, default=str)
        print(f"DEBUG: Saved {len(export_data)} items with hydrated engagement data")
        print(f"DEBUG: Items with engagement: {len([x for x in export_data if x['like_count'] > 0 or x['repost_count'] > 0 or x['reply_count'] > 0])}")
    except Exception as e:
        print(f"DEBUG: Failed to save hydrated data: {e}")

    # Compute engagement metrics for user's posts (likes/reposts/replies received)
    posts = items  # recent posts only
    total_likes_received = sum(int(getattr(it, "like_count", 0) or 0) for it in posts)
    total_reposts_received = sum(int(getattr(it, "repost_count", 0) or 0) for it in posts)
    total_replies_received = sum(int(getattr(it, "reply_count", 0) or 0) for it in posts)
    total_engagement = sum(
        int(
            calculate_engagement_score(
                int(it.like_count or 0), int(it.repost_count or 0), int(it.reply_count or 0)
            )
        )
        for it in posts
    )
    avg_engagement = (total_engagement / len(posts)) if posts else 0.0
    total_quotes_received = 0
    try:
        if isinstance(quotes_by_uri, dict):
            total_quotes_received = sum(int(quotes_by_uri.get(getattr(it, "uri", ""), 0) or 0) for it in posts)
    except Exception:
        total_quotes_received = 0

    stats = {
        "counts": {
            "posts": len(posts),
            "total_items": len(posts),
        },
        "engagement": {
            "likes_received": total_likes_received,
            "reposts_received": total_reposts_received,
            "replies_received": total_replies_received,
            "quotes_received": total_quotes_received,
            "total_engagement": int(total_engagement),
            "avg_engagement": round(avg_engagement, 2),
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
        session.clear()
    except Exception:
        session.clear()
    return jsonify({"success": True})


if __name__ == "__main__":
    # Default to 5003 to avoid conflicts
    port = int(os.environ.get("PORT", "5003"))
    app.run(debug=True, host="0.0.0.0", port=port)
