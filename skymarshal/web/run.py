#!/usr/bin/env python3
"""
Startup script for Skymarshal Web Interface
"""

import os
import sys

# Add the correct path to find skymarshal modules
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Import and run the Flask app
from app import app

if __name__ == '__main__':
    port = 5001  # Use 5001 to avoid conflicts with AirPlay
    print("🚀 Starting Skymarshal Web Interface...")
    print(f"📍 Web interface will be available at: http://localhost:{port}")
    print("🔒 Login with your Bluesky credentials to get started")
    print("\n" + "="*50)
    
    try:
        app.run(debug=True, host='0.0.0.0', port=port)
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down Skymarshal Web Interface...")
    except Exception as e:
        print(f"\n❌ Error starting web interface: {e}")
        print("💡 Make sure all dependencies are installed and try again")