"""Flask interface for Skymarshal - Bluesky content management."""

from __future__ import annotations

import csv
import io
import os
import secrets
from datetime import datetime
from functools import wraps
from typing import Callable, Dict, Optional

from flask import (
    Flask,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from werkzeug.middleware.proxy_fix import ProxyFix

from skymarshal.services import ContentService, SearchRequest
from skymarshal.services.analytics import ContentAnalytics
from skymarshal.web.share_manager import SharedPostManager
from pathlib import Path


app = Flask(__name__)
app.secret_key = secrets.token_hex(32)


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

# Configure for reverse proxy with subpath
# ProxyFix will set SCRIPT_NAME from X-Forwarded-Prefix header
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.wrappers import Response as WerkzeugResponse

class PrefixMiddleware:
    def __init__(self, app, prefix=''):
        self.app = app
        self.prefix = prefix

    def __call__(self, environ, start_response):
        if self.prefix:
            environ['SCRIPT_NAME'] = self.prefix
            if environ['PATH_INFO'].startswith(self.prefix):
                environ['PATH_INFO'] = environ['PATH_INFO'][len(self.prefix):]
        return self.app(environ, start_response)

app.wsgi_app = ProxyFix(PrefixMiddleware(app.wsgi_app, prefix='/skymarshal'), x_for=1, x_proto=1, x_host=1, x_prefix=1)

app.config['SESSION_COOKIE_PATH'] = '/skymarshal'
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

_services: Dict[str, ContentService] = {}
_prefer_car_for_lite = _env_flag("SKYMARSHAL_LITE_USE_CAR")

# Initialize share manager for post permalinks
_share_db_path = Path.home() / ".skymarshal" / "shared_posts.db"
_share_db_path.parent.mkdir(parents=True, exist_ok=True)
share_manager = SharedPostManager(_share_db_path)


@app.route("/")
def index():
    # Redirect to the hub as the main landing page
    return redirect(url_for("hub"))


@app.route("/hub")
def hub():
    """Skymarshal Hub - landing page showing all available tools."""
    session_id = session.get("session_id")
    service = _services.get(session_id) if session_id else None

    is_authenticated = service is not None
    user_handle = session.get("user_handle")
    profile = None
    blocked_count = None
    muted_count = None

    if is_authenticated and service:
        try:
            profile = service.get_profile()
        except Exception:
            pass

    return render_template(
        "hub.html",
        is_authenticated=is_authenticated,
        user_handle=user_handle,
        profile=profile,
        blocked_count=blocked_count,
        muted_count=muted_count,
    )


def _require_service() -> ContentService:
    session_id = session.get("session_id")
    if not session_id:
        raise PermissionError("Authentication required")
    service = _services.get(session_id)
    if not service:
        raise PermissionError("Authentication required")
    return service


def _login_required(view: Callable):
    @wraps(view)
    def wrapper(*args, **kwargs):
        try:
            _require_service()
        except PermissionError:
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapper


def _is_likely_regular_password(pwd: str) -> bool:
    """Check if password looks like a regular password (not an app password)."""
    # App passwords are typically 19 characters with hyphens (xxxx-xxxx-xxxx-xxxx)
    if len(pwd) == 19 and pwd.count('-') == 3:
        parts = pwd.split('-')
        return not (len(parts) == 4 and all(len(part) == 4 for part in parts))
    elif len(pwd) < 15 or ' ' in pwd or any(c.isupper() for c in pwd):
        # Likely a regular password (too short, has spaces, or mixed case)
        return True
    return False


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        handle = request.form.get("handle", "").strip()
        password = request.form.get("password", "")

        if not handle or not password:
            return render_template(
                "lite_login.html",
                error="I need both your handle and password.",
            )

        # Check if using regular password
        used_regular_password = _is_likely_regular_password(password)

        service = ContentService(prefer_car_backup=_prefer_car_for_lite)
        if not service.login(handle, password):
            error_msg = "Authentication failed. Double-check your app password."
            if used_regular_password:
                error_msg = "Hey, looks like you're using your regular password. It's better to use an app password for security - I've got a link below to make one."
            return render_template(
                "lite_login.html",
                error=error_msg,
            )

        # For litemarshal, we'll lazy-load data on first search
        # This makes login instant even for large accounts
        # The data will be loaded when the user first searches

        session_id = secrets.token_hex(16)
        session["session_id"] = session_id
        session["user_handle"] = service.auth.current_handle
        session["used_regular_password"] = used_regular_password
        _services[session_id] = service

        # Store warning message if regular password was used
        if used_regular_password:
            session["password_warning"] = "⚠️ Hey, you're using your regular password. It's a bit safer to use an app password - you can make one in Settings > Privacy & Security > App Passwords."

        return redirect(url_for("dashboard"))

    return render_template("lite_login.html")


@app.route("/logout")
def logout():
    session_id = session.get("session_id")
    if session_id and session_id in _services:
        del _services[session_id]
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@_login_required
def dashboard():
    service = _require_service()
    handle = session.get("user_handle")

    # Load 500 most recent posts on login (fast, gives immediate access)
    # User can explicitly load more if needed
    try:
        items = service.ensure_content_loaded(
            categories=["posts", "likes", "reposts"],
            limit=500,  # Load 500 most recent items initially
        )
        summary = service.summarize()
        loaded_count = len(items) if items else 0
    except RuntimeError as exc:
        summary = {"posts": 0, "likes": 0, "reposts": 0, "replies": 0, "total": 0}
        loaded_count = 0
        error_msg = f"Failed to load data: {str(exc)}"
        return render_template("lite_dashboard.html", summary=summary, handle=handle, error=error_msg, loaded_count=loaded_count)

    return render_template("lite_dashboard.html", summary=summary, handle=handle, loaded_count=loaded_count)


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/search")
def search():
    try:
        service = _require_service()
    except PermissionError:
        return jsonify({"success": False, "error": "Authentication required"}), 401

    # Lazy-load data on first search (fast login, load only when needed)
    try:
        items = service.ensure_content_loaded(
            categories=["posts", "likes", "reposts"],
            limit=999999,  # Load all content - effectively unlimited
        )
    except RuntimeError as exc:
        return jsonify({"success": False, "error": f"Failed to load data: {str(exc)}"}), 400

    payload = request.get_json(silent=True) or {}

    def _get_int(name: str) -> Optional[int]:
        value = payload.get(name)
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    request_obj = SearchRequest(
        keyword=(payload.get("keyword") or None),
        content_types=payload.get("content_types"),
        start_date=(payload.get("start_date") or None),
        end_date=(payload.get("end_date") or None),
        min_likes=_get_int("min_likes"),
        max_likes=_get_int("max_likes"),
        min_reposts=_get_int("min_reposts"),
        max_reposts=_get_int("max_reposts"),
        min_replies=_get_int("min_replies"),
        max_replies=_get_int("max_replies"),
        limit=_get_int("limit") or 250,
    )

    try:
        results, total = service.search(request_obj)

        # Hydrate ONLY the search results (not all 50k items)
        # This dramatically improves performance for large accounts
        if results:
            # Convert search results back to ContentItem objects for hydration
            from skymarshal.models import ContentItem
            result_items = []
            for r in results:
                # Search results are dicts, need to find matching items
                matching = [item for item in items if item.uri == r.get('uri')]
                if matching:
                    result_items.append(matching[0])

            # Hydrate only these result items
            if result_items:
                try:
                    service.data_manager.hydrate_items(result_items)
                    # Update results with hydrated data
                    for i, r in enumerate(results):
                        matching = [item for item in result_items if item.uri == r.get('uri')]
                        if matching:
                            item = matching[0]
                            results[i]['like_count'] = item.like_count or 0
                            results[i]['repost_count'] = item.repost_count or 0
                            results[i]['reply_count'] = item.reply_count or 0
                            results[i]['engagement_score'] = item.engagement_score or 0
                except Exception as hydrate_error:
                    current_app.logger.warning(f"Could not hydrate search results: {hydrate_error}")

    except RuntimeError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    # Get updated summary after data load
    summary = service.summarize()

    return jsonify({"success": True, "results": results, "total": total, "summary": summary})


@app.post("/delete")
def delete():
    try:
        service = _require_service()
    except PermissionError:
        return jsonify({"success": False, "error": "Authentication required"}), 401

    payload = request.get_json(silent=True) or {}
    uris = payload.get("uris") or []
    if not isinstance(uris, list):
        return jsonify({"success": False, "error": "Invalid payload"}), 400

    deleted, errors = service.delete([str(uri) for uri in uris if uri])
    return jsonify({"success": True, "deleted": deleted, "errors": errors, "failed": len(errors)})


@app.post("/load-more")
def load_more():
    """Load additional content beyond the initial 500 items.

    Accepts JSON payload with 'limit' field (number of items to load, or 'all' for everything).
    """
    try:
        service = _require_service()
    except PermissionError:
        return jsonify({"success": False, "error": "Authentication required"}), 401

    payload = request.get_json(silent=True) or {}
    limit_str = payload.get("limit", "500")

    # Parse limit: "all" means unlimited, otherwise parse as integer
    if limit_str == "all":
        limit = 999999
    else:
        try:
            limit = int(limit_str)
            if limit < 1:
                return jsonify({"success": False, "error": "Limit must be positive"}), 400
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "Invalid limit value"}), 400

    try:
        items = service.ensure_content_loaded(
            categories=["posts", "likes", "reposts"],
            force_refresh=True,
            limit=limit,
        )
        # Note: Not hydrating all items for performance
        # Engagement data will be hydrated on-demand during search

        summary = service.summarize()
        loaded_count = len(items) if items else 0

        return jsonify({
            "success": True,
            "summary": summary,
            "loaded_count": loaded_count,
            "message": f"Loaded {loaded_count} items"
        })

    except RuntimeError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@app.post("/refresh")
def refresh():
    """Re-fetch the current limit of content (defaults to what's already loaded)."""
    try:
        service = _require_service()
    except PermissionError:
        return jsonify({"success": False, "error": "Authentication required"}), 401

    try:
        items = service.ensure_content_loaded(
            categories=["posts", "likes", "reposts"],
            force_refresh=True,
            limit=500,  # Refresh the initial 500 items
        )
        summary = service.summarize()
        loaded_count = len(items) if items else 0

    except RuntimeError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    return jsonify({"success": True, "summary": summary, "loaded_count": loaded_count})


@app.get("/export/csv")
def export_csv():
    """Export all loaded content as CSV file.

    Note: Engagement data (likes, reposts, replies) reflects cached/last-fetched values.
    For large accounts (50k+ posts), hydrating all engagement data would take too long.
    """
    try:
        service = _require_service()
    except PermissionError:
        return redirect(url_for("login"))

    try:
        items = service.ensure_content_loaded(
            categories=["posts", "likes", "reposts"],
            limit=999999,  # Export all content
        )
        # Note: Not hydrating all items for performance
        # Use cached engagement data from last hydration (during search)

    except RuntimeError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow([
        "Content Type",
        "Text",
        "Created At",
        "Likes",
        "Reposts",
        "Replies",
        "Engagement Score",
        "URI",
    ])

    # Write data rows
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

    # Prepare file for download
    output.seek(0)
    handle = session.get("user_handle", "export")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"skymarshal_{handle}_{timestamp}.csv"

    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename,
    )


@app.get("/export/car")
def export_car():
    """Download the CAR backup file for the current user."""
    try:
        service = _require_service()
    except PermissionError:
        return redirect(url_for("login"))

    handle = session.get("user_handle")
    if not handle:
        return jsonify({"success": False, "error": "No authenticated user"}), 400

    # Try to create a fresh CAR backup
    try:
        # Suppress Rich console output to avoid "only one live display" error in web context
        import io
        import sys
        from contextlib import redirect_stdout, redirect_stderr

        # Redirect stdout/stderr to suppress Rich console displays
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            backup_path = service.data_manager.create_timestamped_backup(handle)

        if not backup_path:
            return jsonify({
                "success": False,
                "error": "Failed to create CAR backup. Please try refreshing your data first."
            }), 400

        # Get the file for download
        car_file = backup_path
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"skymarshal_{handle}_{timestamp}.car"

        return send_file(
            car_file,
            mimetype="application/octet-stream",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as exc:
        current_app.logger.error(f"CAR backup error: {exc}")
        return jsonify({
            "success": False,
            "error": f"Failed to create CAR backup: {str(exc)}"
        }), 500


@app.get("/analytics")
def analytics():
    """Get analytics and insights for the current user's content.

    Note: Uses cached engagement data for performance.
    For large accounts (50k+ posts), hydrating all items would take too long.
    """
    try:
        service = _require_service()
    except PermissionError:
        return jsonify({"success": False, "error": "Authentication required"}), 401

    try:
        items = service.ensure_content_loaded(
            categories=["posts", "likes", "reposts"],
            limit=999999,  # Analyze all content
        )
        # Note: Not hydrating all items for performance
        # Analytics will use cached engagement data

        # Generate comprehensive analytics
        insights = ContentAnalytics.generate_insights(items)

        return jsonify({"success": True, "analytics": insights})

    except RuntimeError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@app.get("/user-profile")
def user_profile():
    """Return the current user's profile data for avatar/display name."""
    try:
        service = _require_service()
    except PermissionError:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        profile = service.get_profile()
        if profile:
            return jsonify({
                "success": True,
                "profile": {
                    "handle": profile.get("handle", session.get("user_handle")),
                    "displayName": profile.get("displayName", ""),
                    "avatar": profile.get("avatar", ""),
                }
            })
        return jsonify({
            "success": True,
            "profile": {
                "handle": session.get("user_handle", ""),
                "displayName": "",
                "avatar": "",
            }
        })
    except Exception as e:
        current_app.logger.warning(f"Failed to get profile: {e}")
        return jsonify({
            "success": True,
            "profile": {
                "handle": session.get("user_handle", ""),
                "displayName": "",
                "avatar": "",
            }
        })


@app.route('/api/share', methods=['POST'])
@_login_required
def share_post():
    """Create a shared permalink for a post."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        share_id = share_manager.create_share(data)
        share_url = url_for('view_shared_post', share_id=share_id, _external=True)

        return jsonify({
            'success': True,
            'share_id': share_id,
            'share_url': share_url
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/p/<share_id>')
def view_shared_post(share_id):
    """View a shared post (public access)."""
    post_data = share_manager.get_share(share_id)
    if not post_data:
        return f"<h1>Shared post not found</h1><p>The post with ID '{share_id}' does not exist or has been removed.</p>", 404

    return render_template('shared_post.html', post=post_data)


# --- EgoNet Manager Integration ---
from skymarshal.deletion import DeletionManager
import threading
import time

@app.route("/egonet")
@_login_required
def egonet_dashboard():
    """EgoNet Manager Dashboard."""
    handle = session.get("user_handle")
    return render_template("egonet.html", handle=handle)

@app.route("/api/egonet/network")
@_login_required
def api_egonet_network():
    """Get network data (mocked for now, pending real implementation)."""
    # In a real implementation we would fetch this from AppView
    # For now, return a mock graph so the visualizer works immediately
    service = _require_service()
    me = session.get("user_handle")
    
    nodes = [{"id": me, "handle": me, "group": 1}]
    links = []
    
    # Mock some data if we have it, otherwise just return me
    # Ideally we'd validly fetch followers/follows here
    # Since we can't easily wait for a long API call in a synchronous route,
    # we return a small sample or placeholder.
    
    return jsonify({
        "nodes": nodes,
        "links": links
    })

@app.post("/api/egonet/backup")
@_login_required
def api_egonet_backup():
    """Trigger a backup creation."""
    try:
        service = _require_service()
        handle = session.get("user_handle")
        
        # We reuse the logic from export_car but return JSON
        # Run in thread to not block? Backup can be fast enough for small repos,
        # but large ones might timeout.
        # Ideally we'd use a task queue. For now, we block (lite version).
        
        backup_path = service.data_manager.create_timestamped_backup(handle)
        
        if backup_path:
            return jsonify({"status": "success", "message": f"Backup created at {backup_path}"})
        else:
            return jsonify({"status": "error", "message": "Backup failed"})
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.post("/api/egonet/nuke")
@_login_required
def api_egonet_nuke():
    """Nuclear option: Delete everything."""
    payload = request.get_json()
    if not payload or payload.get("confirmation") != "I UNDERSTAND THIS IS PERMANENT":
        return jsonify({"status": "error", "message": "Invalid confirmation"}), 400
        
    service = _require_service()
    
    def run_nuke(app_context_service):
        # We need a fresh DeletionManager or use service's capabilities
        # Creating a DeletionManager requires auth.
        # service.auth is available.
        dm = DeletionManager(app_context_service.auth)
        dm.nuke_all_content()
        
    # Run in background thread because it takes a long time
    thread = threading.Thread(target=run_nuke, args=(service,))
    thread.start()
    
    return jsonify({"status": "success", "message": "Nuclear deletion started in background. Check back later."})


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5050))
    app.run(debug=True, host="0.0.0.0", port=port)
