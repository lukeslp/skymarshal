"""Lightweight Flask interface for essential Skymarshal workflows."""

from __future__ import annotations

import os
import secrets
from functools import wraps
from typing import Callable, Dict

from flask import (
    Flask,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.middleware.proxy_fix import ProxyFix

from skymarshal.services import ContentService, SearchRequest


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

app.wsgi_app = PrefixMiddleware(app.wsgi_app, prefix='/litemarshal')

app.config['SESSION_COOKIE_PATH'] = '/litemarshal'
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

_services: Dict[str, ContentService] = {}
_prefer_car_for_lite = _env_flag("SKYMARSHAL_LITE_USE_CAR")


@app.route("/")
def lite_index():
    if session.get("lite_session_id") in _services:
        return redirect(url_for("lite_dashboard"))
    return redirect(url_for("lite_login"))


def _require_service() -> ContentService:
    session_id = session.get("lite_session_id")
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
            return redirect(url_for("lite_login"))
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


@app.route("/lite/login", methods=["GET", "POST"])
def lite_login():
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
        session["lite_session_id"] = session_id
        session["lite_user_handle"] = service.auth.current_handle
        session["used_regular_password"] = used_regular_password
        _services[session_id] = service

        # Store warning message if regular password was used
        if used_regular_password:
            session["password_warning"] = "⚠️ Warning: You appear to be using your regular Bluesky password. For security, we recommend using an app password from Settings > Privacy & Security > App Passwords."

        return redirect(url_for("lite_dashboard"))

    return render_template("lite_login.html")


@app.route("/lite/logout")
def lite_logout():
    session_id = session.get("lite_session_id")
    if session_id and session_id in _services:
        del _services[session_id]
    session.clear()
    return redirect(url_for("lite_login"))


@app.route("/lite")
@_login_required
def lite_dashboard():
    service = _require_service()
    handle = session.get("lite_user_handle")

    # Try to load data if not already loaded
    try:
        service.ensure_content_loaded(
            categories=["posts", "likes", "reposts"],
            limit=5000,  # Reasonable limit for search/delete workflow
        )
        summary = service.summarize()
    except RuntimeError as exc:
        # Failed to load data - show error message
        summary = {"posts": 0, "likes": 0, "reposts": 0, "total": 0}
        error_msg = f"Failed to load data: {str(exc)}"
        return render_template("lite_dashboard.html", summary=summary, handle=handle, error=error_msg)

    return render_template("lite_dashboard.html", summary=summary, handle=handle)


@app.get("/lite/health")
def lite_health():
    return jsonify({"status": "ok"})


@app.post("/lite/search")
def lite_search():
    try:
        service = _require_service()
    except PermissionError:
        return jsonify({"success": False, "error": "Authentication required"}), 401

    # Lazy-load data on first search (fast login, load only when needed)
    try:
        service.ensure_content_loaded(
            categories=["posts", "likes", "reposts"],
            limit=5000,  # Reasonable limit for search/delete workflow
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


@app.post("/lite/delete")
def lite_delete():
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


@app.post("/lite/refresh")
def lite_refresh():
    try:
        service = _require_service()
    except PermissionError:
        return jsonify({"success": False, "error": "Authentication required"}), 401

    try:
        service.ensure_content_loaded(
            categories=["posts", "likes", "reposts"],
            force_refresh=True,
            limit=5000,  # Reasonable limit for search/delete workflow
        )
    except RuntimeError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    summary = service.summarize()
    return jsonify({"success": True, "summary": summary})


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5050)
