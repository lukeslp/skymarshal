"""Minimal Flask application for Bluesky data analysis."""

from __future__ import annotations

import os
from typing import Optional, Tuple

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

try:  # Import when running via package (Flask) or as script
    from .services import (
        ProcessingError,
        UserDataResult,
        has_saved_session,
        logout_user,
        process_user_data,
    )
except ImportError:  # pragma: no cover - script fallback
    import sys
    from pathlib import Path

    current_dir = Path(__file__).resolve().parent
    sys.path.append(str(current_dir.parent))
    from site_codex.services import (
        ProcessingError,
        UserDataResult,
        has_saved_session,
        logout_user,
        process_user_data,
    )


def _process_submission(handle: str, password: str) -> Tuple[Optional[UserDataResult], Optional[str]]:
    """Execute the processing pipeline and capture errors."""
    try:
        result = process_user_data(handle, password)
        return result, None
    except ProcessingError as exc:
        return None, str(exc)



def create_app(config: Optional[dict] = None) -> Flask:
    """Application factory used by Flask CLI or gunicorn."""
    app = Flask(__name__, template_folder="templates", static_folder="static")

    secret = (
        config.get("SECRET_KEY")
        if config and config.get("SECRET_KEY")
        else os.environ.get("FLASK_SECRET_KEY")
        or os.environ.get("SECRET_KEY")
        or "skymarshal-demo-secret"
    )
    app.config["SECRET_KEY"] = secret

    if config:
        app.config.update(config)

    @app.route("/", methods=["GET", "POST"])
    def index():
        result = None
        session_available = has_saved_session()

        if request.method == "POST":
            handle = request.form.get("handle", "").strip()
            password = request.form.get("password", "")

            try:
                result, error = _process_submission(handle, password)
            except Exception as exc:  # pragma: no cover - defensive logging only
                flash("Unexpected error while processing data.", "error")
                app.logger.exception("Unhandled exception in process_user_data", exc_info=exc)
            else:
                if error:
                    flash(error, "error")
            session_available = has_saved_session()
        return render_template("index.html", result=result, session_available=session_available)

    @app.route("/process", methods=["POST"])
    def process_endpoint():
        payload = request.get_json(silent=True) or {}
        handle = (payload.get("handle") or "").strip()
        password = payload.get("password") or ""

        try:
            result, error = _process_submission(handle, password)
        except Exception as exc:  # pragma: no cover - defensive logging only
            app.logger.exception("Unhandled exception in process_user_data", exc_info=exc)
            return jsonify({"error": "Unexpected error while processing data."}), 500

        if error:
            return jsonify({"error": error}), 400
        if not result:
            return jsonify({"error": "Processing pipeline did not return a result."}), 500

        return jsonify(
            {
                "handle": result.handle,
                "car_path": str(result.car_path),
                "export_path": str(result.export_path),
                "statistics": result.statistics,
                "top_posts": result.top_posts,
            }
        )

    @app.route("/logout", methods=["POST"])
    def logout():
        had_session = logout_user()
        if had_session:
            flash("Bluesky session cleared.", "success")
        else:
            flash("No active session found to clear.", "info")
        return redirect(url_for("index"))

    return app


# Provide a default app instance for flask run
app = create_app()


if __name__ == "__main__":
    # Local development convenience: `python site_codex/app.py`
    port = int(os.environ.get("PORT", "5001"))
    app.run(host="0.0.0.0", port=port)
