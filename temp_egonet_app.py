import os
import sys
import logging
import json
import threading
import time
from pathlib import Path
from flask import Flask, render_template, jsonify, request, send_file, Response
import dotenv
import requests

# Add skymarshal to path
SKYMARSHAL_PATH = "/home/coolhand/servers/skymarshal"
if SKYMARSHAL_PATH not in sys.path:
    sys.path.append(SKYMARSHAL_PATH)

try:
    from skymarshal.auth import AuthManager
    from skymarshal.data_manager import DataManager
    from skymarshal.deletion import DeletionManager
    from skymarshal.models import UserSettings
    from skymarshal.ui import UIManager # Needed for auth, but we'll mock interaction
except ImportError as e:
    print(f"Error importing skymarshal modules: {e}")
    sys.exit(1)

# Load environment variables
dotenv.load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
BSKY_HANDLE = os.getenv("BSKY_IDENTIFIER")
BSKY_PASSWORD = os.getenv("BSKY_PASSWORD")

# Directories
APP_DIR = Path("/home/coolhand/html/bluesky/egonet-manager")
BACKUP_DIR = APP_DIR / "backups"
BACKUP_DIR.mkdir(exist_ok=True)

# Headless UI Mock for AuthManager
class HeadlessUI:
    def print(self, *args, **kwargs): pass
    def status(self, *args, **kwargs): return self
    def __enter__(self): return self
    def __exit__(self, *args): pass

# Initialize Managers
settings = UserSettings()
ui = HeadlessUI()
auth = AuthManager(ui)
# Authenticate on startup
if BSKY_HANDLE and BSKY_PASSWORD:
    if auth.authenticate_client(BSKY_HANDLE, BSKY_PASSWORD):
        logger.info(f"Authenticated as {auth.current_handle}")
    else:
        logger.error("Failed to authenticate with env vars")

data_manager = DataManager(auth, settings, APP_DIR, BACKUP_DIR, APP_DIR / "json")
deletion_manager = DeletionManager(auth, settings)

@app.route('/')
def index():
    return render_template('index.html', handle=auth.current_handle)

# --- Graph Logic (Adapted from bsky_ego_network.py) ---

def api_get(endpoint: str, params: dict) -> dict:
    base = "https://public.api.bsky.app/xrpc"
    try:
        resp = requests.get(f"{base}/{endpoint}", params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"API Error {endpoint}: {e}")
        return {}

def fetch_all(endpoint: str, actor: str, key: str, limit=200):
    results = []
    cursor = None
    while True:
        params = {"actor": actor, "limit": 100}
        if cursor: params["cursor"] = cursor
        
        data = api_get(endpoint, params)
        items = data.get(key, [])
        results.extend(items)
        
        cursor = data.get("cursor")
        if not cursor or len(results) >= limit:
            break
        time.sleep(0.1)
    return results

@app.route('/api/network')
def get_network():
    if not auth.current_handle:
        return jsonify({"error": "Not authenticated"}), 401

    try:
        # Resolve self
        profile = api_get("app.bsky.actor.getProfile", {"actor": auth.current_handle})
        if not profile:
             return jsonify({"error": "Could not resolve profile"}), 500
        
        me_did = profile["did"]
        
        logger.info("Fetching graph data...")
        # Get nodes
        followers = fetch_all("app.bsky.graph.getFollowers", me_did, "followers", limit=100) # Limit for speed
        follows = fetch_all("app.bsky.graph.getFollows", me_did, "follows", limit=100)
        
        nodes = {}
        links = []
        
        # Add Me
        nodes[me_did] = {"id": me_did, "group": 1, "handle": profile.get("handle")}
        
        ego_dids = {me_did}
        
        # Add Followers
        for f in followers:
            did = f["did"]
            ego_dids.add(did)
            nodes[did] = {"id": did, "group": 2, "handle": f["handle"]}
            links.append({"source": did, "target": me_did, "value": 1})
            
        # Add Follows
        for f in follows:
            did = f["did"]
            ego_dids.add(did)
            if did not in nodes:
                nodes[did] = {"id": did, "group": 3, "handle": f["handle"]}
            links.append({"source": me_did, "target": did, "value": 1})
            
        # Optional: Interconnections (expensive, maybe skip for lite version)
        # For a truly "lite" manager, simple ego graph is often enough.
        # User requested "Powerful data management features", but Viz is "EgoNet Visualizer"
        
        return jsonify({
            "nodes": list(nodes.values()),
            "links": links
        })
        
    except Exception as e:
        logger.error(f"Graph error: {e}")
        return jsonify({"error": str(e)}), 500

# --- Management Endpoints ---

@app.route('/api/backup', methods=['POST'])
def backup_repo():
    if not auth.current_handle:
        return jsonify({"error": "Not authenticated"}), 401
        
    try:
        # Initial implementation: Trigger CAR download
        # Logic from DataManager.download_car
        logger.info(f"Starting backup for {auth.current_handle}")
        path = data_manager.download_car(auth.current_handle)
        
        if path:
            return jsonify({
                "status": "success", 
                "message": f"Backup saved: {path.name}",
                "path": str(path)
            })
        else:
             return jsonify({"status": "error", "message": "Download failed"}), 500
             
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/nuke', methods=['POST'])
def nuke_repo():
    data = request.json
    confirmation = data.get('confirmation')
    
    if confirmation != "I UNDERSTAND THIS IS PERMANENT":
        return jsonify({"error": "Invalid confirmation phrase"}), 400
        
    if not auth.current_handle:
        return jsonify({"error": "Not authenticated"}), 401

    def run_nuke():
        # Running in background thread to avoid timeout
        logger.warning(f"STARTING NUCLEAR DELETE FOR {auth.current_handle}")
        try:
             # Using deletion manager directly
             # We delete collections one by one
             collections = [
                 "app.bsky.feed.post",
                 "app.bsky.feed.like",
                 "app.bsky.feed.repost"
             ]
             for col in collections:
                 logger.info(f"Deleting {col}...")
                 deletion_manager.bulk_remove_by_collection(col, dry_run=False)
             logger.info("Nuclear delete complete.")
        except Exception as e:
            logger.error(f"Nuke failed: {e}")

    thread = threading.Thread(target=run_nuke)
    thread.start()
    
    return jsonify({
        "status": "success", 
        "message": "Nuclear deletion started in background. Check logs for progress."
    })

@app.route('/api/verify_empty', methods=['GET'])
def verify_empty():
    # Helper to check if repo is actually empty
    if not auth.current_handle:
        return jsonify({"error": "Not authenticated"}), 401
        
    # Check counts
    profile = api_get("app.bsky.actor.getProfile", {"actor": auth.current_handle})
    if profile:
        return jsonify({
            "posts": profile.get("postsCount", 0),
            "handle": profile.get("handle")
        })
    return jsonify({"error": "Check failed"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005, debug=True)
