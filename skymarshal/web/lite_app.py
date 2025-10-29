"""Lightweight Flask interface for essential Skymarshal workflows."""

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

app.wsgi_app = PrefixMiddleware(app.wsgi_app, prefix='/skymarshal')

app.config['SESSION_COOKIE_PATH'] = '/skymarshal'
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

_services: Dict[str, ContentService] = {}
_prefer_car_for_lite = _env_flag("SKYMARSHAL_LITE_USE_CAR")


@app.route("/")
def index():
    if session.get("session_id") in _services:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


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
                error="Handle and app password are required.",
            )

        # Check if using regular password
        used_regular_password = _is_likely_regular_password(password)

        service = ContentService(prefer_car_backup=_prefer_car_for_lite)
        if not service.login(handle, password):
            error_msg = "Authentication failed. Confirm the app password."
            if used_regular_password:
                error_msg = "Authentication failed. You appear to be using your regular password. Please use an app password from Bluesky settings for better security."
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
            session["password_warning"] = "⚠️ Warning: You appear to be using your regular Bluesky password. For security, we recommend using an app password from Settings > Privacy & Security > App Passwords."

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

    # Try to load data if not already loaded
    try:
        items = service.ensure_content_loaded(
            categories=["posts", "likes", "reposts"],
            limit=5000,  # Reasonable limit for search/delete workflow
        )

        # Hydrate engagement data (likes, reposts, replies) from Bluesky API
        # This is essential for accurate counts - without it, CAR files show zeros
        try:
            service.data_manager.hydrate_items(items)
        except Exception as hydrate_error:
            # Non-fatal: continue with cached/zero engagement data
            current_app.logger.warning(f"Could not hydrate engagement: {hydrate_error}")

        summary = service.summarize()
    except RuntimeError as exc:
        # Failed to load data - show error message
        summary = {"posts": 0, "likes": 0, "reposts": 0, "replies": 0, "total": 0}
        error_msg = f"Failed to load data: {str(exc)}"
        return render_template("lite_dashboard.html", summary=summary, handle=handle, error=error_msg)

    return render_template("lite_dashboard.html", summary=summary, handle=handle)


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
            limit=5000,  # Reasonable limit for search/delete workflow
        )

        # Hydrate engagement data for accurate counts
        try:
            service.data_manager.hydrate_items(items)
        except Exception as hydrate_error:
            # Non-fatal: continue with cached/zero engagement data
            current_app.logger.warning(f"Could not hydrate engagement: {hydrate_error}")

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
        min_engagement=_get_int("min_engagement"),
        max_engagement=_get_int("max_engagement"),
        limit=_get_int("limit") or 250,
    )

    try:
        results, total = service.search(request_obj)
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


@app.post("/refresh")
def refresh():
    try:
        service = _require_service()
    except PermissionError:
        return jsonify({"success": False, "error": "Authentication required"}), 401

    try:
        items = service.ensure_content_loaded(
            categories=["posts", "likes", "reposts"],
            force_refresh=True,
            limit=5000,  # Reasonable limit for search/delete workflow
        )

        # Hydrate engagement data after refresh
        try:
            service.data_manager.hydrate_items(items)
        except Exception as hydrate_error:
            current_app.logger.warning(f"Could not hydrate engagement: {hydrate_error}")

    except RuntimeError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    summary = service.summarize()
    return jsonify({"success": True, "summary": summary})


@app.get("/export/csv")
def export_csv():
    """Export all loaded content as CSV file."""
    try:
        service = _require_service()
    except PermissionError:
        return redirect(url_for("login"))

    try:
        items = service.ensure_content_loaded(
            categories=["posts", "likes", "reposts"],
            limit=5000,
        )

        # Hydrate engagement data for accurate CSV export
        try:
            service.data_manager.hydrate_items(items)
        except Exception as hydrate_error:
            current_app.logger.warning(f"Could not hydrate engagement: {hydrate_error}")

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
    """Get analytics and insights for the current user's content."""
    try:
        service = _require_service()
    except PermissionError:
        return jsonify({"success": False, "error": "Authentication required"}), 401

    try:
        items = service.ensure_content_loaded(
            categories=["posts", "likes", "reposts"],
            limit=5000,
        )

        # Hydrate engagement data for accurate analytics
        try:
            service.data_manager.hydrate_items(items)
        except Exception as hydrate_error:
            current_app.logger.warning(f"Could not hydrate engagement: {hydrate_error}")

        # Generate comprehensive analytics
        insights = ContentAnalytics.generate_insights(items)

        return jsonify({"success": True, "analytics": insights})

    except RuntimeError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5051)
