#!/bin/bash
# Skymarshal Web App Startup Script

echo "🚀 Starting Skymarshal Web Application"
echo "======================================="

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    
    echo "📚 Installing dependencies..."
    source venv/bin/activate
    pip install flask atproto rich
else
    echo "✅ Virtual environment found"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Start the web application
echo "🌐 Starting Flask server..."
echo "📍 Access the application at: http://localhost:5000"
echo "🔐 Use your Bluesky credentials to login"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

python webapp.py