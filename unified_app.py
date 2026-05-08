"""Entry point for the Skymarshal unified Flask + SocketIO backend.

Usage:
    python unified_app.py                    # Development (port 5090)
    python unified_app.py --port 5050        # Production port
    gunicorn -k eventlet -w 1 unified_app:app  # Production with gunicorn

This replaces the Express server that previously backed the React unified app.
It exposes:
  - REST API endpoints (/api/auth, /api/content, /api/search, etc.)
  - Socket.IO events for real-time features (firehose, network jobs)
  - Health endpoint at /health
"""

from __future__ import annotations

import argparse
import os

from skymarshal.api import create_app, socketio

app = create_app()


def main():
    parser = argparse.ArgumentParser(description="Skymarshal unified backend")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 5090)))
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--debug", action="store_true", default=False)
    args = parser.parse_args()

    print(f"Starting Skymarshal unified backend on {args.host}:{args.port}")
    # allow_unsafe_werkzeug only when --debug is on (dev). Production should
    # use `gunicorn -k eventlet -w 1 unified_app:app`; Werkzeug's safety lock
    # is the right error to hit if someone runs this without --debug in prod.
    socketio.run(
        app,
        host=args.host,
        port=args.port,
        debug=args.debug,
        allow_unsafe_werkzeug=args.debug,
    )


if __name__ == "__main__":
    main()
