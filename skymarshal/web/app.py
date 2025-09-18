#!/usr/bin/env python3
"""
Flask web interface for Skymarshal
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any
from functools import wraps

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, Response, stream_with_context, send_from_directory
import secrets

# Add parent directory to path to import skymarshal modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from skymarshal.auth import AuthManager
from skymarshal.data_manager import DataManager
from skymarshal.search import SearchManager
from skymarshal.deletion import DeletionManager
from skymarshal.models import ContentType, SearchFilters, DeleteMode, UserSettings, console
from skymarshal.settings import SettingsManager

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# Use simple server-side sessions without Flask-Session
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Global progress tracking and auth storage
progress_data = {}
auth_storage = {}  # Store auth managers by session ID

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_handle' not in session or 'session_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_auth_manager():
    """Get the current user's auth manager"""
    session_id = session.get('session_id')
    if session_id and session_id in auth_storage:
        return auth_storage[session_id]
    return None

@app.route('/')
def index():
    if 'user_handle' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        handle = data.get('handle')
        password = data.get('password')
        
        if not handle or not password:
            return jsonify({'success': False, 'error': 'Handle and password are required'}), 400
        
        auth_manager = AuthManager()
        
        # Normalize handle using AuthManager's method
        normalized_handle = auth_manager.normalize_handle(handle)
        
        try:
            if auth_manager.authenticate_client(normalized_handle, password):
                session_id = secrets.token_hex(16)
                session['user_handle'] = normalized_handle
                session['session_id'] = session_id
                auth_storage[session_id] = auth_manager
                return jsonify({'success': True, 'redirect': url_for('setup')})
            else:
                return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session_id = session.get('session_id')
    if session_id and session_id in auth_storage:
        del auth_storage[session_id]
    session.clear()
    return redirect(url_for('login'))

@app.route('/setup')
@login_required
def setup():
    return render_template('setup.html', handle=session['user_handle'])

@app.route('/download-car', methods=['GET'])
@login_required
def download_car():
    """Stream CAR file download progress"""
    try:
        handle = session['user_handle']
        
        def generate():
            try:
                auth_manager = get_auth_manager()
                if not auth_manager:
                    yield f"data: {json.dumps({'status': 'error', 'error': 'Not authenticated'})}\n\n"
                    return
                
                # Check if still authenticated
                if not auth_manager.is_authenticated():
                    yield f"data: {json.dumps({'status': 'error', 'error': 'Session expired, please login again'})}\n\n"
                    return
                
                # Create DataManager with the authenticated AuthManager
                # Set up required directories
                skymarshal_dir = Path.home() / '.skymarshal'
                backups_dir = skymarshal_dir / 'cars'
                json_dir = skymarshal_dir / 'json'
                
                # Create directories if they don't exist
                skymarshal_dir.mkdir(exist_ok=True)
                backups_dir.mkdir(exist_ok=True)
                json_dir.mkdir(exist_ok=True)
                
                # Create default settings
                settings_manager = SettingsManager()
                settings = settings_manager.get_settings()
                
                data_manager = DataManager(
                    auth_manager=auth_manager,
                    settings=settings,
                    skymarshal_dir=skymarshal_dir,
                    backups_dir=backups_dir,
                    json_dir=json_dir
                )
                
                yield f"data: {json.dumps({'status': 'starting', 'message': 'Initializing CAR download...'})}\n\n"
                
                # Download CAR file using the actual method
                car_path = data_manager.download_backup(handle)
                
                if car_path:
                    session['car_path'] = str(car_path)
                    yield f"data: {json.dumps({'status': 'completed', 'car_path': str(car_path)})}\n\n"
                else:
                    yield f"data: {json.dumps({'status': 'error', 'error': 'Failed to download CAR file'})}\n\n"
                
            except Exception as e:
                yield f"data: {json.dumps({'status': 'error', 'error': str(e)})}\n\n"
        
        response = Response(stream_with_context(generate()), mimetype='text/event-stream')
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['Connection'] = 'keep-alive'
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response
        
    except Exception as e:
        # Fallback to JSON response if streaming fails
        return jsonify({'status': 'error', 'error': f'Streaming setup failed: {str(e)}'}), 500

@app.route('/process-data', methods=['POST'])
@login_required
def process_data():
    """Process CAR file and extract data based on user selection"""
    data = request.get_json()
    content_types = data.get('content_types', ['posts'])
    limits = data.get('limits', {})
    
    handle = session['user_handle']
    car_path = session.get('car_path')
    
    if not car_path:
        return jsonify({'success': False, 'error': 'No CAR file found'}), 400
    
    def generate():
        try:
            auth_manager = get_auth_manager()
            
            # Set up required directories
            skymarshal_dir = Path.home() / '.skymarshal'
            backups_dir = skymarshal_dir / 'cars'
            json_dir = skymarshal_dir / 'json'
            
            # Create directories if they don't exist
            skymarshal_dir.mkdir(exist_ok=True)
            backups_dir.mkdir(exist_ok=True)
            json_dir.mkdir(exist_ok=True)
            
            # Create default settings
            settings_manager = SettingsManager()
            settings = settings_manager.get_settings()
            
            data_manager = DataManager(
                auth_manager=auth_manager or AuthManager(),
                settings=settings,
                skymarshal_dir=skymarshal_dir,
                backups_dir=backups_dir,
                json_dir=json_dir
            )
            
            yield f"data: {json.dumps({'status': 'processing', 'message': 'Processing CAR file...'})}\n\n"
            
            # Convert content types to category set
            categories = set(content_types)
            
            # Process CAR file using import_backup_replace method
            json_path = data_manager.import_backup_replace(
                Path(car_path), 
                handle=handle, 
                categories=categories
            )
            
            if json_path:
                # Load the processed data to get item count
                items = data_manager.load_exported_data(json_path)
                
                # Apply limits if specified (by re-processing with limits)
                filtered_items = []
                for content_type in content_types:
                    limit = limits.get(content_type, 0)
                    
                    if content_type == 'posts':
                        type_items = [item for item in items if item.content_type == ContentType.POST]
                    elif content_type == 'likes':
                        type_items = [item for item in items if item.content_type == ContentType.LIKE]
                    elif content_type == 'reposts':
                        type_items = [item for item in items if item.content_type == ContentType.REPOST]
                    else:
                        continue
                    
                    if limit > 0:
                        type_items = type_items[:limit]
                    
                    filtered_items.extend(type_items)
                    yield f"data: {json.dumps({'status': 'progress', 'type': content_type, 'count': len(type_items)})}\n\n"
                
                # If limits were applied, save the filtered data
                if any(limits.values()):
                    # Create a new JSON file with filtered data
                    import tempfile
                    import json as json_lib
                    
                    export_data = []
                    for item in filtered_items:
                        export_data.append({
                            'uri': item.uri,
                            'cid': item.cid,
                            'content_type': item.content_type.value,
                            'text': item.text,
                            'created_at': item.created_at.isoformat(),
                            'author_handle': item.author_handle,
                            'like_count': item.likes,
                            'repost_count': item.reposts,
                            'reply_count': item.replies,
                            'engagement_score': item.engagement_score,
                            'has_media': item.has_media,
                            'is_reply': item.is_reply,
                            'raw_data': item.raw_data
                        })
                    
                    # Save filtered data
                    export_dir = Path.home() / '.skymarshal' / 'json'
                    export_dir.mkdir(parents=True, exist_ok=True)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filtered_path = export_dir / f"{handle}_web_filtered_{timestamp}.json"
                    
                    with open(filtered_path, 'w') as f:
                        json_lib.dump(export_data, f, indent=2, default=str)
                    
                    json_path = filtered_path
                    items = filtered_items
                
                session['json_path'] = str(json_path)
                session['total_items'] = len(items)
                
                yield f"data: {json.dumps({'status': 'completed', 'total_items': len(items), 'redirect': url_for('dashboard')})}\n\n"
            else:
                yield f"data: {json.dumps({'status': 'error', 'error': 'Failed to process CAR file'})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'status': 'error', 'error': str(e)})}\n\n"
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard with overview cards and search interface"""
    json_path = session.get('json_path')
    if not json_path:
        return redirect(url_for('setup'))
    
    # Load data
    auth_manager = get_auth_manager()
    
    # Set up required directories
    skymarshal_dir = Path.home() / '.skymarshal'
    backups_dir = skymarshal_dir / 'cars'
    json_dir = skymarshal_dir / 'json'
    
    # Create default settings
    settings_manager = SettingsManager()
    settings = settings_manager.get_settings()
    
    data_manager = DataManager(
        auth_manager=auth_manager or AuthManager(),
        settings=settings,
        skymarshal_dir=skymarshal_dir,
        backups_dir=backups_dir,
        json_dir=json_dir
    )
    items = data_manager.load_exported_data(Path(json_path))
    
    # Calculate statistics
    search_manager = SearchManager(auth_manager=auth_manager or AuthManager(), settings=settings)
    stats = search_manager._calculate_statistics(items)
    
    return render_template('dashboard.html', 
                         handle=session['user_handle'],
                         stats=stats,
                         total_items=len(items))

@app.route('/search', methods=['POST'])
@login_required
def search():
    """Search and filter content"""
    data = request.get_json()
    json_path = session.get('json_path')
    
    if not json_path:
        return jsonify({'success': False, 'error': 'No data loaded'}), 400
    
    # Load data
    auth_manager = get_auth_manager()
    
    # Set up required directories
    skymarshal_dir = Path.home() / '.skymarshal'
    backups_dir = skymarshal_dir / 'cars'
    json_dir = skymarshal_dir / 'json'
    
    # Create default settings
    settings_manager = SettingsManager()
    settings = settings_manager.get_settings()
    
    data_manager = DataManager(
        auth_manager=auth_manager or AuthManager(),
        settings=settings,
        skymarshal_dir=skymarshal_dir,
        backups_dir=backups_dir,
        json_dir=json_dir
    )
    items = data_manager.load_exported_data(Path(json_path))
    
    # Create search filters
    filters = SearchFilters(
        keyword=data.get('keyword'),
        content_types=[ContentType(t) for t in data.get('content_types', [])],
        start_date=data.get('start_date'),
        end_date=data.get('end_date'),
        min_engagement=data.get('min_engagement'),
        max_engagement=data.get('max_engagement'),
        has_media=data.get('has_media'),
        is_reply=data.get('is_reply'),
        has_alt_text=data.get('has_alt_text')
    )
    
    # Search
    search_manager = SearchManager(auth_manager=auth_manager or AuthManager(), settings=settings)
    results = search_manager.search_content(items, filters)
    
    # Convert results for JSON serialization
    serialized_results = []
    for item in results[:100]:  # Limit to 100 for performance
        serialized_results.append({
            'uri': item.uri,
            'content_type': item.content_type.value,
            'text': item.text[:200] + '...' if len(item.text) > 200 else item.text,
            'created_at': item.created_at.isoformat(),
            'likes': item.likes,
            'reposts': item.reposts,
            'replies': item.replies,
            'engagement_score': item.engagement_score,
            'has_media': item.has_media
        })
    
    return jsonify({
        'success': True,
        'results': serialized_results,
        'total': len(results)
    })

@app.route('/delete', methods=['POST'])
@login_required
def delete():
    """Delete selected content"""
    data = request.get_json()
    uris = data.get('uris', [])
    
    if not uris:
        return jsonify({'success': False, 'error': 'No items selected'}), 400
    
    auth_manager = get_auth_manager()
    if not auth_manager or not auth_manager.client:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        # Create default settings for deletion manager
        settings_manager = SettingsManager()
        settings = settings_manager.get_settings()
        
        deletion_manager = DeletionManager(auth_manager=auth_manager, settings=settings)
        
        # Create mock content items for deletion
        json_path = session.get('json_path')
        
        # Set up required directories
        skymarshal_dir = Path.home() / '.skymarshal'
        backups_dir = skymarshal_dir / 'cars'
        json_dir = skymarshal_dir / 'json'
        
        # Create default settings
        settings_manager = SettingsManager()
        settings = settings_manager.get_settings()
        
        data_manager = DataManager(
            auth_manager=auth_manager or AuthManager(),
            settings=settings,
            skymarshal_dir=skymarshal_dir,
            backups_dir=backups_dir,
            json_dir=json_dir
        )
        all_items = data_manager.load_exported_data(Path(json_path))
        
        # Filter items to delete based on URIs
        items_to_delete = [item for item in all_items if item.uri in uris]
        
        if not items_to_delete:
            return jsonify({'success': False, 'error': 'No matching items found'}), 400
        
        # Delete items using the actual deletion manager
        deleted_count, failed_count = deletion_manager.delete_items_batch(
            items_to_delete, 
            DeleteMode.ALL_AT_ONCE
        )
        
        return jsonify({
            'success': True,
            'deleted': deleted_count,
            'failed': failed_count
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)