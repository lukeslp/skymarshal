#!/usr/bin/env bash
# Start the Skymarshal unified Flask + SocketIO backend.
#
# Usage:
#   ./start.sh              # Production (port 5050)
#   PORT=5090 ./start.sh    # Development

set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# Activate virtual environment
if [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
elif [ -f venv/bin/activate ]; then
    source venv/bin/activate
fi

# Default to production port
PORT="${PORT:-5050}"

export PYTHONPATH="${DIR}:${PYTHONPATH:-}"

echo "Starting Skymarshal unified backend on port ${PORT}..."
exec python unified_app.py --port "$PORT" --host 0.0.0.0
