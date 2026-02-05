#!/usr/bin/env python3
"""
Startup script for Skymarshal Lite Web Interface
"""

import os
import sys

# Add the correct path to find skymarshal modules
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
# Add the parent of the skymarshal package (two levels up from web/)
skymarshal_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, skymarshal_root)

# Import and run the Flask app
from lite_app import app


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


if __name__ == '__main__':
    # Allow port to be configured via environment variable
    port = int(os.getenv('SKYMARSHAL_PORT', '5050'))
    debug_mode = os.getenv('SKYMARSHAL_DEBUG', 'False').lower() == 'true'
    use_reloader = os.getenv('FLASK_RELOADER', 'False').lower() == 'true'

    print("🚀 Starting Skymarshal Web Interface...")
    print(f"📍 Interface will be available at: http://localhost:{port}")
    print(f"🔧 Debug mode: {'enabled' if debug_mode else 'disabled'}")
    print(f"♻️  Auto-reloader: {'enabled' if use_reloader else 'disabled'}")
    print("🔒 Login with your Bluesky credentials to get started")
    print("\n" + "="*50)

    try:
        app.run(debug=debug_mode, host='0.0.0.0', port=port, use_reloader=use_reloader)
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down Skymarshal Web Interface...")
    except Exception as e:
        print(f"\n❌ Error starting interface: {e}")
        print("💡 Make sure all dependencies are installed and try again")
