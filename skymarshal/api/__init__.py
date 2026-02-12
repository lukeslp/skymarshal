"""Flask API package for the Skymarshal unified Bluesky client.

Provides a Flask + Flask-SocketIO backend that wraps existing skymarshal
domain managers (AuthManager, ContentService, analytics, etc.) as a REST API.
The React frontend calls these endpoints for power-tool features while
standard Bluesky operations go client-side to bsky.social/xrpc.
"""

from __future__ import annotations

import logging
import os
import secrets
from datetime import timedelta
from pathlib import Path
from typing import Dict

from flask import Flask, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO

from skymarshal.services import ContentService

logger = logging.getLogger(__name__)

# Singleton SocketIO instance shared across blueprints
socketio = SocketIO()

# Per-session ContentService instances (keyed by session token)
_services: Dict[str, ContentService] = {}


def get_services() -> Dict[str, ContentService]:
    """Return the shared services dict."""
    return _services


def create_app(*, testing: bool = False) -> Flask:
    """Flask application factory.

    Creates and configures the Flask app with:
    - CORS for the React dev server
    - Flask-SocketIO for real-time events
    - All API blueprints registered under /api
    """
    app = Flask(__name__)
    app.secret_key = os.environ.get("SKYMARSHAL_SECRET_KEY", secrets.token_hex(32))
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    # CORS: allow the React dev server and production origins
    allowed_origins = [
        "http://localhost:5086",
        "http://localhost:5090",
        "https://dr.eamer.dev",
        "https://d.reamwalker.com",
        "https://d.reamwalk.com",
    ]
    CORS(app, origins=allowed_origins, supports_credentials=True)

    # Logging
    if not testing:
        logging.basicConfig(level=logging.INFO)

    # ---- Register blueprints ------------------------------------------------
    from skymarshal.api.auth import auth_bp
    from skymarshal.api.content import content_bp
    from skymarshal.api.analytics import analytics_bp
    from skymarshal.api.network import network_bp
    from skymarshal.api.profile import profile_bp
    from skymarshal.api.cleanup import cleanup_bp
    from skymarshal.api.firehose import firehose_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(content_bp, url_prefix="/api")
    app.register_blueprint(analytics_bp, url_prefix="/api/analytics")
    app.register_blueprint(network_bp, url_prefix="/api/network")
    app.register_blueprint(profile_bp, url_prefix="/api/profile")
    app.register_blueprint(cleanup_bp, url_prefix="/api/cleanup")
    app.register_blueprint(firehose_bp, url_prefix="/api/firehose")

    # ---- Health endpoint ----------------------------------------------------
    @app.route("/health")
    def health():
        return jsonify({"status": "ok", "service": "skymarshal-unified"})

    @app.route("/")
    def root():
        return jsonify({
            "service": "skymarshal-unified",
            "version": "2.0.0",
            "docs": "/health",
        })

    # ---- Initialize SocketIO ------------------------------------------------
    socketio.init_app(
        app,
        cors_allowed_origins=allowed_origins,
        async_mode="threading",
        logger=False,
        engineio_logger=False,
    )

    # Register SocketIO event handlers
    _register_socketio_events()

    return app


def _register_socketio_events() -> None:
    """Register Socket.IO event handlers for real-time features."""
    from flask_socketio import emit

    @socketio.on("connect")
    def handle_connect():
        logger.info("Client connected")
        emit("connected", {"status": "ok"})

    @socketio.on("disconnect")
    def handle_disconnect():
        logger.info("Client disconnected")
