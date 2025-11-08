#!/usr/bin/env python3
"""
Startup script for Skymarshal Lite Web Interface
"""

import os
import sys

# Add the correct path to find skymarshal modules
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Import and run the Flask app
from lite_app import app


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


if __name__ == '__main__':
    port = 5050  # Litemarshal web interface port (lite version)
    # Only honor Lite-specific toggles to avoid inheriting global Flask debug env
    debug_mode = _env_flag('SKYMARSHAL_LITE_DEBUG')
    use_reloader = debug_mode and _env_flag('SKYMARSHAL_LITE_RELOAD')

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
