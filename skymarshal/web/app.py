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
            # Check if this is an EventSource request
            if request.headers.get('Accept') == 'text/event-stream':
                # Return proper EventSource error response
                response = Response(
                    f"data: {json.dumps({'status': 'error', 'error': 'Authentication required'})}\n\n",
                    mimetype='text/event-stream'
                )
                response.headers['Cache-Control'] = 'no-cache'
                response.headers['Connection'] = 'keep-alive'
                return response
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_auth_manager():
    """Get the current user's auth manager"""
    session_id = session.get('session_id')
    if session_id and session_id in auth_storage:
        return auth_storage[session_id]
    return None

def get_car_quick_stats(car_path):
    """Get quick statistics from a CAR file without full processing"""
    try:
        from atproto_core.car import CAR
        from skymarshal.models import ContentType
        
        stats = {
            'posts': 0,
            'replies': 0,
            'likes': 0, 
            'reposts': 0,
            'other': 0,
            'total': 0
        }
        
        debug_info = {
            'file_size': 0,
            'total_blocks': 0,
            'collections_found': set(),
            'sample_records': []
        }
        
        # Get file size for debugging
        import os
        debug_info['file_size'] = os.path.getsize(car_path)
        
        # Read the CAR file and count record types properly
        with open(car_path, 'rb') as f:
            car = CAR.from_bytes(f.read())
            debug_info['total_blocks'] = len(car.blocks)
            
            for cid, block_data in car.blocks.items():
                try:
                    # Decode the block using the same method as DataManager
                    if hasattr(block_data, 'data'):
                        # If it's already decoded
                        record = block_data.data
                    else:
                        # Try to decode CBOR
                        from skymarshal.data_manager import cbor_decode
                        if cbor_decode:
                            record = cbor_decode(block_data)
                        else:
                            continue
                    
                    # Check if this is a commit record with operations
                    if isinstance(record, dict) and 'ops' in record:
                        for op in record.get('ops', []):
                            if 'path' in op and 'cid' in op:
                                path = op['path']
                                
                                # Extract collection from path (e.g., "app.bsky.feed.post/abc123")
                                if '/' in path:
                                    collection = path.split('/')[0]
                                    debug_info['collections_found'].add(collection)
                                    
                                    if collection == 'app.bsky.feed.post':
                                        # This could be a post or reply - we'll categorize as posts for now
                                        # In full processing, we'd check the record content for reply field
                                        stats['posts'] += 1
                                    elif collection == 'app.bsky.feed.like':
                                        stats['likes'] += 1
                                    elif collection == 'app.bsky.feed.repost':
                                        stats['reposts'] += 1
                                    else:
                                        stats['other'] += 1
                                    
                                    stats['total'] += 1
                    
                    # Store sample for debugging (first 3 records)
                    if len(debug_info['sample_records']) < 3:
                        debug_info['sample_records'].append({
                            'type': type(record).__name__,
                            'keys': list(record.keys()) if isinstance(record, dict) else 'not_dict',
                            'has_ops': 'ops' in record if isinstance(record, dict) else False
                        })
                        
                except Exception as decode_error:
                    # Skip records that can't be decoded
                    continue
        
        # Add debug info to stats for troubleshooting
        stats['debug'] = debug_info
        
        # Log debug info for troubleshooting
        print(f"CAR Stats Debug - File: {car_path}")
        print(f"File size: {debug_info['file_size']} bytes")
        print(f"Total blocks: {debug_info['total_blocks']}")
        print(f"Collections found: {debug_info['collections_found']}")
        print(f"Sample records: {debug_info['sample_records']}")
        print(f"Final stats: posts={stats['posts']}, likes={stats['likes']}, reposts={stats['reposts']}")
        
        return stats
        
    except Exception as e:
        print(f"Error parsing CAR file {car_path}: {e}")
        import traceback
        traceback.print_exc()
        
        # Return basic file info if CAR parsing fails
        import os
        file_size = os.path.getsize(car_path)
        return {
            'posts': '?',
            'replies': '?',
            'likes': '?',
            'reposts': '?', 
            'total': f'{file_size // 1024}KB',
            'error': str(e)
        }

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

@app.route('/user-profile')
@login_required
def user_profile():
    """Get user profile information including avatar"""
    auth_manager = get_auth_manager()
    if not auth_manager or not auth_manager.client:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        handle = session['user_handle']
        profile = auth_manager.client.get_profile(handle)
        
        return jsonify({
            'success': True,
            'profile': {
                'handle': profile.handle,
                'displayName': profile.display_name,
                'description': profile.description,
                'avatar': profile.avatar,
                'banner': profile.banner,
                'followersCount': profile.followers_count,
                'followsCount': profile.follows_count,
                'postsCount': profile.posts_count,
                'createdAt': profile.created_at.isoformat() if profile.created_at else None
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/bluesky-facts')
@login_required
def bluesky_facts():
    """Get interesting Bluesky statistics and facts"""
    auth_manager = get_auth_manager()
    if not auth_manager or not auth_manager.client:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    facts = []
    
    try:
        handle = session['user_handle']
        
        # Get user's profile for their stats
        try:
            profile = auth_manager.client.get_profile(handle)
            
            # Get actual user content counts from CAR data if available
            # For now, use profile counts but we could enhance this
            facts.append({
                'icon': '📝',
                'title': 'Your Posts',
                'value': f'{profile.posts_count:,}',
                'description': 'posts you\'ve shared'
            })
            
            facts.append({
                'icon': '👥',
                'title': 'Your Followers',
                'value': f'{profile.followers_count:,}',
                'description': 'people following you'
            })
            
            facts.append({
                'icon': '👤',
                'title': 'Following',
                'value': f'{profile.follows_count:,}',
                'description': 'accounts you follow'
            })
            
            # Account age with more context
            if profile.created_at:
                from datetime import datetime
                account_age = (datetime.now(profile.created_at.tzinfo) - profile.created_at).days
                
                if account_age < 30:
                    description = 'days on Bluesky'
                elif account_age < 365:
                    months = account_age // 30
                    description = f'~{months} months on Bluesky'
                else:
                    years = account_age // 365
                    description = f'~{years} year{"s" if years > 1 else ""} on Bluesky'
                
                facts.append({
                    'icon': '📅',
                    'title': 'Member Since',
                    'value': f'{account_age}',
                    'description': description
                })
        except:
            pass
        
        # Platform milestones and interesting stats
        platform_facts = [
            {
                'icon': '🚀',
                'title': 'Bluesky Users',
                'value': '20M+',
                'description': 'registered accounts'
            },
            {
                'icon': '📈',
                'title': 'Growth Milestone',
                'value': '1M',
                'description': 'users joined in one day (Nov 2024)'
            },
            {
                'icon': '🌍',
                'title': 'Global Reach',
                'value': '190+',
                'description': 'countries represented'
            },
            {
                'icon': '💬',
                'title': 'Daily Posts',
                'value': '3M+',
                'description': 'posts shared every day'
            },
            {
                'icon': '⚡',
                'title': 'Launch Year',
                'value': '2024',
                'description': 'public launch milestone'
            },
            {
                'icon': '🔓',
                'title': 'Open Beta',
                'value': 'Feb 2024',
                'description': 'removed invite-only requirement'
            },
            {
                'icon': '📱',
                'title': 'Mobile Users',
                'value': '80%+',
                'description': 'access via mobile apps'
            },
            {
                'icon': '🌐',
                'title': 'Languages',
                'value': '50+',
                'description': 'languages used on platform'
            }
        ]
        
        # Add random platform facts
        import random
        facts.extend(random.sample(platform_facts, min(4, len(platform_facts))))
        
        return jsonify({
            'success': True,
            'facts': facts
        })
        
    except Exception as e:
        # Return some basic facts even if API calls fail
        fallback_facts = [
            {
                'icon': '🦋',
                'title': 'Welcome',
                'value': 'Bluesky',
                'description': 'You\'re using the AT Protocol social network'
            },
            {
                'icon': '🚀',
                'title': 'Processing',
                'value': 'Data',
                'description': 'Analyzing your Bluesky content'
            }
        ]
        
        return jsonify({
            'success': True,
            'facts': fallback_facts
        })

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
                settings_file = Path.home() / ".car_inspector_settings.json"
                settings_manager = SettingsManager(settings_file)
                settings = settings_manager.settings
                
                data_manager = DataManager(
                    auth_manager=auth_manager,
                    settings=settings,
                    skymarshal_dir=skymarshal_dir,
                    backups_dir=backups_dir,
                    json_dir=json_dir
                )
                
                yield f"data: {json.dumps({'status': 'starting', 'message': 'Connecting to Bluesky...'})}\n\n"
                
                import time
                time.sleep(0.5)  # Small delay to show progress step
                
                yield f"data: {json.dumps({'status': 'downloading', 'message': 'Downloading your archive...'})}\n\n"
                
                # Download CAR file using the actual method
                # Ensure we get a fresh download by using timestamped filename
                car_path = data_manager.create_timestamped_backup(handle)
                
                if car_path:
                    session['car_path'] = str(car_path)
                    print(f"Downloaded fresh CAR file: {car_path}")
                    
                    yield f"data: {json.dumps({'status': 'processing', 'message': 'Processing CAR file...'})}\n\n"
                    time.sleep(0.3)  # Small delay to show progress step
                    
                    # Get quick stats from CAR file
                    yield f"data: {json.dumps({'status': 'analyzing', 'message': 'Analyzing content...'})}\n\n"
                    time.sleep(0.3)  # Small delay to show progress step
                    
                    try:
                        # Quick analysis of CAR file contents
                        stats = get_car_quick_stats(car_path)
                        yield f"data: {json.dumps({'status': 'completed', 'car_path': str(car_path), 'stats': stats})}\n\n"
                    except Exception as e:
                        # If stats fail, still complete successfully
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
            settings_file = Path.home() / ".car_inspector_settings.json"
            settings_manager = SettingsManager(settings_file)
            settings = settings_manager.settings
            
            data_manager = DataManager(
                auth_manager=auth_manager or AuthManager(),
                settings=settings,
                skymarshal_dir=skymarshal_dir,
                backups_dir=backups_dir,
                json_dir=json_dir
            )
            
            yield f"data: {json.dumps({'status': 'processing', 'message': 'Starting data processing...', 'progress': 5})}\n\n"
            
            # Convert content types to category set
            categories = set(content_types)
            
            yield f"data: {json.dumps({'status': 'processing', 'message': f'Processing {len(categories)} content types: {", ".join(categories)}', 'progress': 10})}\n\n"
            
            # Process CAR file using import_backup_replace method
            yield f"data: {json.dumps({'status': 'processing', 'message': 'Reading CAR file structure...', 'progress': 20})}\n\n"
            
            json_path = data_manager.import_backup_replace(
                Path(car_path), 
                handle=handle, 
                categories=categories
            )
            
            yield f"data: {json.dumps({'status': 'processing', 'message': 'CAR file processed successfully!', 'progress': 60})}\n\n"
            
            if json_path:
                yield f"data: {json.dumps({'status': 'processing', 'message': 'Loading processed data...', 'progress': 65})}\n\n"
                
                # Load the processed data to get item count
                items = data_manager.load_exported_data(json_path)
                
                yield f"data: {json.dumps({'status': 'processing', 'message': f'Loaded {len(items)} total items', 'progress': 70})}\n\n"
                
                # Apply limits if specified (by re-processing with limits)
                yield f"data: {json.dumps({'status': 'processing', 'message': 'Applying content filters and limits...', 'progress': 75})}\n\n"
                
                filtered_items = []
                for i, content_type in enumerate(content_types):
                    limit = limits.get(content_type, 0)
                    
                    yield f"data: {json.dumps({'status': 'filtering', 'message': f'Processing {content_type}...', 'type': content_type})}\n\n"
                    
                    if content_type == 'posts':
                        type_items = [item for item in items if item.content_type == ContentType.POST]
                    elif content_type == 'likes':
                        type_items = [item for item in items if item.content_type == ContentType.LIKE]
                    elif content_type == 'reposts':
                        type_items = [item for item in items if item.content_type == ContentType.REPOST]
                    else:
                        continue
                    
                    original_count = len(type_items)
                    if limit > 0:
                        type_items = type_items[:limit]
                        yield f"data: {json.dumps({'status': 'filtering', 'message': f'Limited {content_type} from {original_count} to {len(type_items)} items', 'type': content_type, 'count': len(type_items), 'original_count': original_count})}\n\n"
                    else:
                        yield f"data: {json.dumps({'status': 'filtering', 'message': f'Using all {len(type_items)} {content_type}', 'type': content_type, 'count': len(type_items)})}\n\n"
                    
                    filtered_items.extend(type_items)
                    
                    # Update progress based on processing step
                    progress = 75 + (i + 1) * (10 / len(content_types))
                    yield f"data: {json.dumps({'status': 'processing', 'progress': int(progress)})}\n\n"
                
                # If limits were applied, save the filtered data
                if any(limits.values()):
                    yield f"data: {json.dumps({'status': 'processing', 'message': 'Saving filtered data...', 'progress': 85})}\n\n"
                    
                    # Create a new JSON file with filtered data
                    import tempfile
                    import json as json_lib
                    
                    yield f"data: {json.dumps({'status': 'processing', 'message': 'Preparing export data...', 'progress': 87})}\n\n"
                    
                    export_data = []
                    for i, item in enumerate(filtered_items):
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
                        
                        # Update progress during export preparation
                        if i % 100 == 0 and i > 0:
                            progress = 87 + (i / len(filtered_items)) * 8
                            yield f"data: {json.dumps({'status': 'processing', 'message': f'Prepared {i}/{len(filtered_items)} items...', 'progress': int(progress)})}\n\n"
                    
                    yield f"data: {json.dumps({'status': 'processing', 'message': 'Writing data to file...', 'progress': 95})}\n\n"
                    
                    # Save filtered data
                    export_dir = Path.home() / '.skymarshal' / 'json'
                    export_dir.mkdir(parents=True, exist_ok=True)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filtered_path = export_dir / f"{handle}_web_filtered_{timestamp}.json"
                    
                    with open(filtered_path, 'w') as f:
                        json_lib.dump(export_data, f, indent=2, default=str)
                    
                    yield f"data: {json.dumps({'status': 'processing', 'message': f'Saved filtered data to {filtered_path.name}', 'progress': 98})}\n\n"
                    
                    json_path = filtered_path
                    items = filtered_items
                else:
                    yield f"data: {json.dumps({'status': 'processing', 'message': 'Using all processed data (no limits applied)', 'progress': 95})}\n\n"
                    items = filtered_items
                
                session['json_path'] = str(json_path)
                session['total_items'] = len(items)
                
                yield f"data: {json.dumps({'status': 'finalizing', 'message': 'Processing complete! Redirecting to dashboard...', 'progress': 100})}\n\n"
                
                # Small delay to show completion message
                time.sleep(0.5)
                
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
    settings_file = Path.home() / ".car_inspector_settings.json"
    settings_manager = SettingsManager(settings_file)
    settings = settings_manager.settings
    
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
    settings_file = Path.home() / ".car_inspector_settings.json"
    settings_manager = SettingsManager(settings_file)
    settings = settings_manager.settings
    
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
        settings_file = Path.home() / ".car_inspector_settings.json"
        settings_manager = SettingsManager(settings_file)
        settings = settings_manager.settings
        
        deletion_manager = DeletionManager(auth_manager=auth_manager, settings=settings)
        
        # Create mock content items for deletion
        json_path = session.get('json_path')
        
        # Set up required directories
        skymarshal_dir = Path.home() / '.skymarshal'
        backups_dir = skymarshal_dir / 'cars'
        json_dir = skymarshal_dir / 'json'
        
        # Create default settings
        settings_file = Path.home() / ".car_inspector_settings.json"
        settings_manager = SettingsManager(settings_file)
        settings = settings_manager.settings
        
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