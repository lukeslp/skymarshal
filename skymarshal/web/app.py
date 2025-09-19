#!/usr/bin/env python3
"""
Flask web interface for Skymarshal
"""

import os
import sys
import json
import asyncio
import math
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any
from functools import wraps

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, Response, stream_with_context, send_from_directory
import secrets
import threading
import queue
import time

# Add parent directory to path to import skymarshal modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from skymarshal.auth import AuthManager
from skymarshal.data_manager import DataManager
from skymarshal.search import SearchManager
from skymarshal.deletion import DeletionManager
from skymarshal.models import ContentType, SearchFilters, DeleteMode, UserSettings, console, calculate_engagement_score
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
            # Check if this is an AJAX request expecting JSON
            if (request.headers.get('Content-Type') == 'application/json' or 
                'application/json' in request.headers.get('Accept', '') or
                request.method == 'POST' and request.is_json):
                return jsonify({'success': False, 'error': 'Authentication required'}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_auth_manager():
    """Get the current user's auth manager"""
    session_id = session.get('session_id')
    if session_id and session_id in auth_storage:
        return auth_storage[session_id]
    return None

def get_json_path():
    """Get the current user's JSON data path with fallback logic"""
    json_path = session.get('json_path')
    session_id = session.get('session_id')
    
    # Try to get json_path from progress_data if not in session
    if not json_path and session_id and session_id in progress_data:
        json_path = progress_data[session_id].get('json_path')
        if json_path:
            # Restore to session for future use
            session['json_path'] = json_path
            session.modified = True
    
    # Fallback: look for recent JSON files for this user
    if not json_path:
        try:
            handle = session.get('user_handle')
            if not handle:
                return None
                
            json_dir = Path.home() / '.skymarshal' / 'json'
            if json_dir.exists():
                # Look for JSON files matching the user's handle
                patterns = [
                    f"{handle}_*.json",
                    f"*{handle.split('.')[0]}*.json",
                    "*.json"  # Any JSON file as last resort
                ]
                
                json_files = []
                for pattern in patterns:
                    found_files = list(json_dir.glob(pattern))
                    json_files.extend(found_files)
                    if found_files:
                        break
                
                if json_files:
                    # Use the most recent JSON file
                    latest_json = max(json_files, key=lambda p: p.stat().st_mtime)
                    json_path = str(latest_json)
                    session['json_path'] = json_path
                    session.modified = True
        except Exception as e:
            pass
    
    return json_path

def format_bytes(bytes_val):
    """Format bytes as human readable string"""
    if bytes_val == 0:
        return '0 B'
    size_names = ['B', 'KB', 'MB', 'GB']
    i = int(math.floor(math.log(bytes_val) / math.log(1024)))
    p = math.pow(1024, i)
    s = round(bytes_val / p, 2)
    return f'{s} {size_names[i]}'

def get_car_quick_stats(car_path):
    """Get quick statistics from a CAR file without full processing"""
    try:
        from atproto_core.car import CAR
        from skymarshal.data_manager import cbor_decode
        
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
            'decoded_blocks': 0,
            'record_types': set(),
            'sample_records': []
        }
        
        # Get file size for debugging
        import os
        debug_info['file_size'] = os.path.getsize(car_path)
        
        if cbor_decode is None:
            print("WARNING: No CBOR decoder available, cannot parse CAR file contents")
            return {
                'posts': '?',
                'replies': '?',
                'likes': '?',
                'reposts': '?', 
                'total': f'{debug_info["file_size"] // 1024}KB',
                'error': 'No CBOR decoder available'
            }
        
        # Read the CAR file and decode blocks like DataManager does
        with open(car_path, 'rb') as f:
            car = CAR.from_bytes(f.read())
            debug_info['total_blocks'] = len(car.blocks)
            
            # Decode all blocks first (like DataManager._decode_car_blocks)
            decoded = {}
            
            # Handle different CAR block access patterns
            if isinstance(car.blocks, dict):
                # car.blocks is a dict mapping CID -> block data
                blocks_iter = car.blocks.items()
            else:
                # car.blocks might be another iterator
                blocks_iter = car.blocks
            
            for item in blocks_iter:
                try:
                    # Handle different iterator types
                    if isinstance(item, tuple) and len(item) == 2:
                        cid, block = item
                    elif hasattr(item, "cid") and hasattr(item, "data"):
                        cid, block = item.cid, item.data
                    elif hasattr(item, "cid") and hasattr(item, "bytes"):
                        cid, block = item.cid, item.bytes
                    else:
                        continue
                    
                    # Handle different block data formats
                    if isinstance(block, dict):
                        decoded[str(cid)] = block
                    elif isinstance(block, (bytes, bytearray)):
                        decoded[str(cid)] = cbor_decode(block)
                    else:
                        if hasattr(block, "bytes"):
                            decoded[str(cid)] = cbor_decode(block.bytes)
                        elif hasattr(block, "data"):
                            decoded[str(cid)] = cbor_decode(block.data)
                        else:
                            continue
                    
                    debug_info['decoded_blocks'] += 1
                        
                except Exception as decode_error:
                    # Skip records that can't be decoded
                    continue
            
            # Now count records by type (like DataManager._process_backup_records)
            for cid, obj in decoded.items():
                try:
                    if not isinstance(obj, dict):
                        continue

                    rtype = obj.get("$type")
                    if not rtype:
                        continue
                        
                    debug_info['record_types'].add(rtype)
                    
                    # Store sample for debugging (first 3 records)
                    if len(debug_info['sample_records']) < 3:
                        debug_info['sample_records'].append({
                            'type': rtype,
                            'has_text': 'text' in obj,
                            'has_reply': 'reply' in obj,
                            'text_preview': obj.get('text', '')[:50] if obj.get('text') else ''
                        })

                    if rtype == "app.bsky.feed.post":
                        is_reply = bool(obj.get("reply"))
                        if is_reply:
                            stats['replies'] += 1
                        else:
                            stats['posts'] += 1
                        stats['total'] += 1
                    elif rtype == "app.bsky.feed.like":
                        stats['likes'] += 1
                        stats['total'] += 1
                    elif rtype == "app.bsky.feed.repost":
                        stats['reposts'] += 1
                        stats['total'] += 1
                    else:
                        stats['other'] += 1
                        
                except Exception as record_error:
                    # Skip records that can't be processed
                    continue
        
        # Store in session for use in facts
        session['car_stats'] = {
            'posts': stats['posts'],
            'replies': stats['replies'], 
            'likes': stats['likes'],
            'reposts': stats['reposts'],
            'total': stats['total']
        }
        
        # Add debug info to stats for troubleshooting
        stats['debug'] = debug_info
        
        # Log debug info for troubleshooting
        print(f"CAR Stats Debug - File: {car_path}")
        print(f"File size: {debug_info['file_size']} bytes")
        print(f"Total blocks: {debug_info['total_blocks']}")
        print(f"Decoded blocks: {debug_info['decoded_blocks']}")
        print(f"Record types found: {debug_info['record_types']}")
        print(f"Sample records: {debug_info['sample_records']}")
        print(f"Final stats: posts={stats['posts']}, replies={stats['replies']}, likes={stats['likes']}, reposts={stats['reposts']}, total={stats['total']}")
        
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
        
        # Check if password looks like a regular password (not an app password)
        def is_likely_regular_password(pwd):
            # App passwords are typically 19 characters with hyphens (xxxx-xxxx-xxxx-xxxx)
            # Regular passwords are usually different patterns
            if len(pwd) == 19 and pwd.count('-') == 3:
                # Likely an app password format
                parts = pwd.split('-')
                return not (len(parts) == 4 and all(len(part) == 4 for part in parts))
            elif len(pwd) < 15 or ' ' in pwd or any(c.isupper() for c in pwd):
                # Likely a regular password (too short, has spaces, or mixed case)
                return True
            return False
        
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
                # Check if it looks like they used their regular password
                if is_likely_regular_password(password):
                    return jsonify({
                        'success': False, 
                        'error': 'That appears to be your regular password. Please use an app password from Bluesky settings instead. If you know what you\'re doing, try again.',
                        'suggestion': 'app_password'
                    }), 401
                else:
                    return jsonify({'success': False, 'error': 'Invalid app password. Please check your credentials.'}), 401
        except Exception as e:
            error_msg = str(e).lower()
            if 'invalid' in error_msg or 'unauthorized' in error_msg:
                if is_likely_regular_password(password):
                    return jsonify({
                        'success': False, 
                        'error': 'Authentication failed. This looks like your regular password - please use an app password from Bluesky settings.',
                        'suggestion': 'app_password'
                    }), 401
                else:
                    return jsonify({'success': False, 'error': 'Invalid app password. Please check your credentials.'}), 401
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
        
        # Check if client is authenticated
        if not auth_manager.is_authenticated():
            return jsonify({'success': False, 'error': 'Session expired'}), 401
            
        print(f"DEBUG: Fetching profile for handle: {handle}")
        
        # Try multiple methods to get profile data
        profile_data = None
        method_used = None
        
        # Method 1: Try the app.bsky.actor.getProfile method
        try:
            print("DEBUG: Trying app.bsky.actor.get_profile method...")
            response = auth_manager.client.app.bsky.actor.get_profile({'actor': handle})
            if hasattr(response, 'value'):
                profile_data = response.value
                method_used = 'app.bsky.actor.get_profile'
                print(f"DEBUG: Method 1 succeeded with data type: {type(profile_data)}")
        except Exception as e:
            print(f"DEBUG: Method 1 failed: {e}")
        
        # Method 2: Try the legacy get_profile method
        if not profile_data:
            try:
                print("DEBUG: Trying legacy get_profile method...")
                profile_data = auth_manager.client.get_profile(handle)
                method_used = 'get_profile'
                print(f"DEBUG: Method 2 succeeded with data type: {type(profile_data)}")
            except Exception as e:
                print(f"DEBUG: Method 2 failed: {e}")
        
        if not profile_data:
            raise Exception("All profile fetch methods failed")
        
        # Extract data with flexible attribute access
        def get_attr(obj, *names):
            for name in names:
                value = getattr(obj, name, None)
                if value is not None:
                    return value
            return None
        
        handle_val = get_attr(profile_data, 'handle') or handle
        display_name_val = get_attr(profile_data, 'display_name', 'displayName') or ''
        description_val = get_attr(profile_data, 'description') or ''
        avatar_val = get_attr(profile_data, 'avatar') or '/static/images/default-avatar.svg'
        banner_val = get_attr(profile_data, 'banner') or ''
        followers_val = get_attr(profile_data, 'followers_count', 'followersCount') or 0
        follows_val = get_attr(profile_data, 'follows_count', 'followsCount') or 0
        posts_val = get_attr(profile_data, 'posts_count', 'postsCount') or 0
        created_val = get_attr(profile_data, 'created_at', 'createdAt')
        
        print(f"DEBUG: Extracted data - handle: {handle_val}, displayName: '{display_name_val}', avatar: {avatar_val}")
        print(f"DEBUG: Method used: {method_used}")
        
        return jsonify({
            'success': True,
            'method_used': method_used,
            'profile': {
                'handle': handle_val,
                'displayName': display_name_val,
                'description': description_val,
                'avatar': avatar_val,
                'banner': banner_val,
                'followersCount': followers_val,
                'followsCount': follows_val,
                'postsCount': posts_val,
                'createdAt': created_val.isoformat() if created_val and hasattr(created_val, 'isoformat') else None
            }
        })
    except Exception as e:
        print(f"ERROR: Failed to get profile for {session.get('user_handle', 'unknown')}: {e}")
        # Return fallback data if profile fetch fails
        return jsonify({
            'success': True,
            'profile': {
                'handle': session.get('user_handle', 'unknown'),
                'displayName': '',
                'description': '',
                'avatar': '/static/images/default-avatar.svg',
                'banner': '',
                'followersCount': 0,
                'followsCount': 0,
                'postsCount': 0,
                'createdAt': None
            },
            'error': f'Profile fetch failed: {str(e)}'
        })

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
            # Use the correct AT Protocol method
            from atproto import models
            try:
                profile_response = auth_manager.client.app.bsky.actor.get_profile(
                    models.AppBskyActorGetProfile.Params(actor=handle)
                )
                profile = profile_response.value
            except Exception:
                # Fallback to simpler method
                profile = auth_manager.client.get_profile(handle)
            
            # Use CAR stats if available, otherwise fall back to profile
            car_stats = session.get('car_stats', {})
            
            if car_stats:
                # Use actual counts from CAR data
                facts.append({
                    'icon': '📝',
                    'title': 'Your Posts',
                    'value': f'{car_stats.get("posts", 0):,}',
                    'description': 'posts in your archive'
                })
                
                facts.append({
                    'icon': '❤️',
                    'title': 'Your Likes',
                    'value': f'{car_stats.get("likes", 0):,}',
                    'description': 'posts you\'ve liked'
                })
                
                facts.append({
                    'icon': '🔄',
                    'title': 'Your Reposts',
                    'value': f'{car_stats.get("reposts", 0):,}',
                    'description': 'posts you\'ve shared'
                })
                
                if car_stats.get("replies", 0) > 0:
                    facts.append({
                        'icon': '💬',
                        'title': 'Your Replies',
                        'value': f'{car_stats.get("replies", 0):,}',
                        'description': 'replies you\'ve made'
                    })
            else:
                # Fall back to profile counts
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
                
                yield f"data: {json.dumps({'status': 'downloading', 'message': 'Importing your repository...'})}\n\n"
                
                # Track download progress
                progress_messages = []
                
                def progress_callback(downloaded_bytes, total_bytes):
                    if total_bytes and total_bytes > 0:
                        progress = int((downloaded_bytes / total_bytes) * 70) + 25  # 25% to 95%
                        message = f'Downloaded {format_bytes(downloaded_bytes)} of {format_bytes(total_bytes)}...'
                        progress_messages.append({
                            'status': 'downloading', 
                            'message': message, 
                            'progress': progress, 
                            'downloaded': downloaded_bytes, 
                            'total': total_bytes
                        })
                    else:
                        # Fallback when size is unknown
                        message = f'Downloaded {format_bytes(downloaded_bytes)}...'
                        progress_messages.append({
                            'status': 'downloading', 
                            'message': message, 
                            'downloaded': downloaded_bytes
                        })
                
                # Create custom progress-aware backup method
                car_path = data_manager.create_timestamped_backup_with_progress(handle, progress_callback)
                
                # Send any progress updates that were collected
                for msg in progress_messages[-1:]:  # Send only the latest message to avoid flooding
                    yield f"data: {json.dumps(msg)}\n\n"
                
                if car_path:
                    # Store the car_path in multiple ways to ensure persistence
                    session_id = session.get('session_id')
                    
                    # Save to session
                    session['car_path'] = str(car_path)
                    session.permanent = True
                    session.modified = True
                    
                    # Also store in global progress_data as backup
                    if session_id:
                        if session_id not in progress_data:
                            progress_data[session_id] = {}
                        progress_data[session_id]['car_path'] = str(car_path)
                        progress_data[session_id]['handle'] = handle
                        progress_data[session_id]['timestamp'] = time.time()
                    
                    print(f"Downloaded fresh CAR file: {car_path}")
                    print(f"DEBUG: Saved car_path to session: {session.get('car_path')}")
                    print(f"DEBUG: Saved car_path to progress_data[{session_id}]: {progress_data.get(session_id, {}).get('car_path')}")
                    
                    # Force session save (mark as modified to ensure persistence)
                    try:
                        session.permanent = True
                        session.modified = True
                        print("DEBUG: Session marked as modified for persistence")
                    except Exception as save_error:
                        print(f"DEBUG: Session modification failed: {save_error}")
                    
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
    session_id = session.get('session_id')
    car_path = session.get('car_path')
    
    print(f"DEBUG: Processing for {handle}, car_path in session: {car_path}")
    print(f"DEBUG: Session keys: {list(session.keys())}")
    print(f"DEBUG: Session ID: {session_id}")
    print(f"DEBUG: Progress data keys: {list(progress_data.keys())}")
    
    # Try to get car_path from progress_data if not in session
    if not car_path and session_id and session_id in progress_data:
        car_path = progress_data[session_id].get('car_path')
        if car_path:
            print(f"DEBUG: Retrieved car_path from progress_data: {car_path}")
            # Restore to session for future use
            session['car_path'] = car_path
            session.modified = True
    
    print(f"DEBUG: Final car_path: {car_path}")
    
    if not car_path:
        # Check if there are any CAR files in the backup directory as fallback
        try:
            skymarshal_dir = Path.home() / '.skymarshal'
            backups_dir = skymarshal_dir / 'cars'
            print(f"DEBUG: Checking for CAR files in {backups_dir}")
            
            if backups_dir.exists():
                # Look for files matching different patterns
                patterns = [
                    f"{handle}_*.car",
                    f"*{handle.split('.')[0]}*.car",  # Handle without domain
                    "*.car"  # Any CAR file as last resort
                ]
                
                car_files = []
                for pattern in patterns:
                    found_files = list(backups_dir.glob(pattern))
                    print(f"DEBUG: Pattern '{pattern}' found {len(found_files)} files: {[f.name for f in found_files]}")
                    car_files.extend(found_files)
                    if found_files:
                        break  # Use first pattern that finds files
                
                if car_files:
                    # Use the most recent CAR file
                    latest_car = max(car_files, key=lambda p: p.stat().st_mtime)
                    session['car_path'] = str(latest_car)
                    car_path = str(latest_car)
                    print(f"DEBUG: Using fallback CAR file: {latest_car}")
                else:
                    print("DEBUG: No CAR files found in backup directory")
                    return jsonify({'success': False, 'error': 'No CAR file found. Please complete step 1 first.'}), 400
            else:
                print("DEBUG: Backup directory does not exist")
                return jsonify({'success': False, 'error': 'No CAR file found. Please complete step 1 first.'}), 400
        except Exception as e:
            print(f"DEBUG: Exception in fallback logic: {e}")
            return jsonify({'success': False, 'error': f'Error locating CAR file: {str(e)}'}), 400
    
    def generate():
        try:
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
            
            # Try to get existing auth manager
            auth_manager = get_auth_manager()
            if not auth_manager:
                # Create a new auth manager if none exists
                yield f"data: {json.dumps({'status': 'processing', 'message': 'Setting up authentication for engagement hydration...', 'progress': 3})}\n\n"
                
                from skymarshal.ui import UIManager
                ui_manager = UIManager(settings)
                auth_manager = AuthManager(ui_manager)
                
                # Store it in auth_storage for this session
                session_id = session.get('session_id')
                if session_id:
                    auth_storage[session_id] = auth_manager
            
            # Ensure authentication (this will try to resume saved session automatically)
            if not auth_manager.is_authenticated():
                yield f"data: {json.dumps({'status': 'processing', 'message': 'Checking authentication for engagement hydration...', 'progress': 4})}\n\n"
                
                try:
                    # Try to get handle from session for re-auth if needed
                    handle = session.get('user_handle')
                    if handle and hasattr(auth_manager, 'saved_session_file'):
                        # Try to load saved session
                        saved_session_path = auth_manager.saved_session_file
                        if saved_session_path.exists():
                            try:
                                with open(saved_session_path, 'r') as f:
                                    saved_data = json.load(f)
                                    if saved_data.get('handle') == handle:
                                        # Session file exists for this user
                                        yield f"data: {json.dumps({'status': 'processing', 'message': 'Found saved session, attempting to restore...', 'progress': 4})}\n\n"
                            except:
                                pass
                    
                    # This will automatically try to resume the saved session
                    if auth_manager.ensure_authentication():
                        yield f"data: {json.dumps({'status': 'processing', 'message': 'Authentication restored! Ready for engagement hydration.', 'progress': 5})}\n\n"
                    else:
                        yield f"data: {json.dumps({'status': 'processing', 'message': 'Proceeding without live engagement data (authentication unavailable)', 'progress': 5})}\n\n"
                        auth_manager = None  # Set to None so hydration is skipped
                except Exception as e:
                    print(f"DEBUG: Authentication restoration error: {e}")
                    yield f"data: {json.dumps({'status': 'processing', 'message': 'Will use cached engagement data from CAR file', 'progress': 5})}\n\n"
                    auth_manager = None  # Set to None so hydration is skipped
            
            data_manager = DataManager(
                auth_manager=auth_manager,
                settings=settings,
                skymarshal_dir=skymarshal_dir,
                backups_dir=backups_dir,
                json_dir=json_dir
            )
            
            yield f"data: {json.dumps({'status': 'processing', 'message': 'Starting data processing...', 'progress': 6})}\n\n"
            
            # Convert content types to category set
            categories = set(content_types)
            
            category_list = ", ".join(categories)
            yield f"data: {json.dumps({'status': 'processing', 'message': f'Processing {len(categories)} content types: {category_list}', 'progress': 10})}\n\n"
            
            # Process CAR file using import_backup_replace method
            yield f"data: {json.dumps({'status': 'processing', 'message': 'Reading CAR file structure...', 'progress': 20})}\n\n"
            
            json_path = data_manager.import_backup_replace(
                Path(car_path), 
                handle=handle, 
                categories=categories
            )
            
            yield f"data: {json.dumps({'status': 'processing', 'message': 'CAR file processed successfully!', 'progress': 60})}\n\n"
            
            if json_path:
                yield f"data: {json.dumps({'status': 'processing', 'message': 'Loading processed data...', 'progress': 62})}\n\n"
                
                # Load the processed data to get item count
                items = data_manager.load_exported_data(json_path)
                
                # Hydrate engagement data following stats.py pattern (lines 106-111)
                if auth_manager and auth_manager.is_authenticated():
                    yield f"data: {json.dumps({'status': 'processing', 'message': 'Hydrating engagement data...', 'progress': 65})}\n\n"
                    
                    try:
                        # Follow the exact working pattern from stats.py
                        yield f"data: {json.dumps({'status': 'processing', 'message': f'Updating engagement for {len(items)} items...', 'progress': 67})}\n\n"
                        
                        # Use the hydrate_items method exactly like in stats.py
                        data_manager.hydrate_items(items)
                        
                        yield f"data: {json.dumps({'status': 'processing', 'message': 'Engagement data updated successfully!', 'progress': 69})}\n\n"
                        
                        # Save the hydrated data back to JSON file
                        yield f"data: {json.dumps({'status': 'processing', 'message': 'Saving hydrated data...', 'progress': 70})}\n\n"
                        
                        # Export the hydrated items to ensure persistence
                        export_data = []
                        for item in items:
                            export_data.append({
                                'uri': item.uri,
                                'cid': item.cid,
                                'content_type': item.content_type,
                                'text': item.text,
                                'created_at': item.created_at,
                                'like_count': item.like_count,
                                'repost_count': item.repost_count,
                                'reply_count': item.reply_count,
                                'engagement_score': item.engagement_score,
                                'raw_data': item.raw_data
                            })
                        
                        # Overwrite the existing JSON with hydrated data
                        import json as json_lib
                        with open(json_path, 'w') as f:
                            json_lib.dump(export_data, f, indent=2, default=str)
                            
                    except Exception as e:
                        # Log the full error for debugging but show user-friendly message
                        print(f"ERROR: Hydration failed: {e}")
                        import traceback
                        traceback.print_exc()
                        
                        # Don't fail the whole process if hydration fails
                        yield f"data: {json.dumps({'status': 'processing', 'message': f'Warning: Could not update engagement data: {str(e)[:50]}...', 'progress': 69})}\n\n"
                        yield f"data: {json.dumps({'status': 'processing', 'message': 'Continuing with cached engagement data', 'progress': 70})}\n\n"
                else:
                    yield f"data: {json.dumps({'status': 'processing', 'message': 'Skipping engagement hydration (authentication required)', 'progress': 69})}\n\n"
                    yield f"data: {json.dumps({'status': 'processing', 'message': 'Using cached engagement data from CAR file', 'progress': 70})}\n\n"
                
                yield f"data: {json.dumps({'status': 'processing', 'message': f'Loaded {len(items)} total items', 'progress': 70})}\n\n"
                
                # Apply limits if specified (by re-processing with limits)
                yield f"data: {json.dumps({'status': 'processing', 'message': 'Applying content filters and limits...', 'progress': 75})}\n\n"
                
                filtered_items = []
                for i, content_type in enumerate(content_types):
                    limit = limits.get(content_type, 0)
                    
                    yield f"data: {json.dumps({'status': 'filtering', 'message': f'Processing {content_type}...', 'type': content_type})}\n\n"
                    
                    if content_type == 'posts':
                        type_items = [item for item in items if item.content_type == "post"]
                    elif content_type == 'likes':
                        type_items = [item for item in items if item.content_type == "like"]
                    elif content_type == 'reposts':
                        type_items = [item for item in items if item.content_type == "repost"]
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
                            'content_type': item.content_type,
                            'text': item.text,
                            'created_at': item.created_at,
                            'like_count': item.like_count,
                            'repost_count': item.repost_count,
                            'reply_count': item.reply_count,
                            'engagement_score': item.engagement_score,
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
                session.modified = True
                
                # Also store in progress_data as backup
                session_id = session.get('session_id')
                if session_id:
                    if session_id not in progress_data:
                        progress_data[session_id] = {}
                    progress_data[session_id]['json_path'] = str(json_path)
                    progress_data[session_id]['total_items'] = len(items)
                    print(f"DEBUG: Saved json_path to progress_data[{session_id}]: {progress_data[session_id]['json_path']}")
                
                # Clean up old progress_data and auth_storage entries (keep only last 10 sessions)
                if len(progress_data) > 10:
                    oldest_keys = sorted(progress_data.keys(), 
                                       key=lambda k: progress_data[k].get('timestamp', 0))[:len(progress_data)-10]
                    for old_key in oldest_keys:
                        progress_data.pop(old_key, None)
                        # Also cleanup corresponding auth_storage to prevent memory leak
                        auth_storage.pop(old_key, None)
                        print(f"DEBUG: Cleaned up old progress_data and auth_storage for session {old_key}")
                
                # Additional auth_storage cleanup - remove entries older than 24 hours
                current_time = time.time()
                expired_sessions = []
                for session_id, progress_info in progress_data.items():
                    session_timestamp = progress_info.get('timestamp', 0)
                    if current_time - session_timestamp > 86400:  # 24 hours
                        expired_sessions.append(session_id)
                
                for expired_session in expired_sessions:
                    progress_data.pop(expired_session, None)
                    auth_storage.pop(expired_session, None)
                    print(f"DEBUG: Cleaned up expired session {expired_session}")
                
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
    handle = session['user_handle']
    json_path = get_json_path()
    
    print(f"DEBUG: Dashboard access for {handle}")
    print(f"DEBUG: json_path resolved: {json_path}")
    
    if not json_path:
        print("DEBUG: No JSON path found, redirecting to setup")
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
    print(f"DEBUG: Attempting to load data from: {json_path}")
    print(f"DEBUG: File exists: {Path(json_path).exists()}")
    print(f"DEBUG: File size: {Path(json_path).stat().st_size if Path(json_path).exists() else 'N/A'}")
    
    try:
        items = data_manager.load_exported_data(Path(json_path))
        print(f"DEBUG: Successfully loaded {len(items)} items")
        if len(items) > 0:
            print(f"DEBUG: First item type: {items[0].content_type}")
            print(f"DEBUG: First item text: {items[0].text[:50] if items[0].text else 'No text'}...")
    except Exception as e:
        print(f"DEBUG: Error loading data: {e}")
        import traceback
        traceback.print_exc()
        items = []
    
    # Calculate statistics following stats.py pattern
    print(f"DEBUG: Calculating statistics for {len(items)} items")
    
    # Follow the pattern from stats.py:119-202 show_basic_stats
    total_items = len(items)
    posts = [item for item in items if item.content_type == 'post']
    replies = [item for item in items if item.content_type == 'reply']
    repost_items = [item for item in items if item.content_type == 'repost']
    like_items = [item for item in items if item.content_type == 'like']
    
    pr_items = posts + replies  # Posts and replies for engagement calculations
    
    # Compute totals only over posts/replies (like stats.py)
    total_likes = sum(int(it.like_count or 0) for it in pr_items)
    total_reposts = sum(int(it.repost_count or 0) for it in pr_items)
    total_replies_count = sum(int(it.reply_count or 0) for it in pr_items)
    total_engagement = sum(calculate_engagement_score(int(it.like_count or 0), int(it.repost_count or 0), int(it.reply_count or 0)) for it in pr_items)
    
    # Averages are per post/reply, not per total items
    avg_engagement = (total_engagement / len(pr_items)) if pr_items else 0
    avg_likes = (total_likes / len(pr_items)) if pr_items else 0
    dead_threads = [it for it in pr_items if it.like_count == 0 and it.repost_count == 0 and it.reply_count == 0]
    high_engagement = [it for it in pr_items if calculate_engagement_score(int(it.like_count or 0), int(it.repost_count or 0), int(it.reply_count or 0)) >= settings.high_engagement_threshold]
    
    # Likes-based categories (based on runtime avg like stats.py)
    avg_likes_runtime = avg_likes
    half = max(0.0, avg_likes_runtime * 0.5)
    one_half = max(1.0, avg_likes_runtime * 1.5)
    double = max(1.0, avg_likes_runtime * 2.0)
    cat_dead = [it for it in pr_items if (it.like_count or 0) == 0]
    cat_bomber = [it for it in pr_items if 0 < (it.like_count or 0) <= half]
    cat_mid = [it for it in pr_items if half < (it.like_count or 0) <= one_half]
    cat_banger = [it for it in pr_items if (it.like_count or 0) >= double]
    cat_viral = [it for it in pr_items if (it.like_count or 0) >= 2000]
    
    # Create stats structure for template
    stats = {
        'total_posts': len(posts),
        'total_replies': len(replies),
        'total_likes': len(like_items),  # This is the count of like actions
        'total_reposts': len(repost_items),  # This is the count of repost actions
        'total_items': total_items,
        'engagement_stats': {
            'total_likes_received': total_likes,  # Likes received on posts
            'total_reposts_received': total_reposts,  # Reposts received on posts  
            'total_replies_received': total_replies_count,  # Replies received on posts
            'total_engagement': int(total_engagement),
            'avg_engagement': round(avg_engagement, 1),
            'avg_likes': round(avg_likes, 1),
        },
        'categories': {
            'dead_threads': len(cat_dead),
            'bombers': len(cat_bomber),
            'mid': len(cat_mid),
            'bangers': len(cat_banger),
            'viral': len(cat_viral),
            'high_engagement': len(high_engagement)
        },
        'thresholds': {
            'half': round(half, 1),
            'one_half': round(one_half, 1),
            'double': round(double, 1),
            'high_engagement': settings.high_engagement_threshold
        }
    }
    
    print(f"DEBUG: Enhanced stats calculated: {stats}")
    
    return render_template('dashboard.html', 
                         handle=session['user_handle'],
                         stats=stats,
                         total_items=len(items))

@app.route('/search', methods=['POST'])
@login_required
def search():
    """Search and filter content"""
    data = request.get_json()
    json_path = get_json_path()
    
    if not json_path:
        return jsonify({'success': False, 'error': 'No data loaded. Please complete setup first.'}), 400
    
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
    
    print(f"DEBUG: Search endpoint - json_path: {json_path}")
    print(f"DEBUG: Search endpoint - file exists: {Path(json_path).exists()}")
    
    try:
        items = data_manager.load_exported_data(Path(json_path))
        print(f"DEBUG: Search endpoint - loaded {len(items)} items")
    except Exception as e:
        print(f"DEBUG: Search endpoint - error loading data: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'Failed to load data: {str(e)}'}), 500
    
    # Map content types from web form to SearchFilters format
    content_types = data.get('content_types', [])
    if len(content_types) == 1:
        content_type_str = content_types[0]
        if content_type_str == 'post':
            content_type = ContentType.POSTS
        elif content_type_str == 'like':
            content_type = ContentType.LIKES
        elif content_type_str == 'repost':
            content_type = ContentType.REPOSTS
        else:
            content_type = ContentType.ALL
    else:
        content_type = ContentType.ALL  # Multiple types or none selected
    
    # Create search filters
    keyword = data.get('keyword')
    keywords = [keyword] if keyword else None
    
    filters = SearchFilters(
        keywords=keywords,
        content_type=content_type,
        start_date=data.get('start_date'),
        end_date=data.get('end_date'),
        min_engagement=data.get('min_engagement') or 0,
        max_engagement=data.get('max_engagement') or 999999
    )
    
    # Search
    search_manager = SearchManager(auth_manager=auth_manager or AuthManager(), settings=settings)
    results = search_manager.search_content_with_filters(items, filters)
    
    # Convert results for JSON serialization
    serialized_results = []
    for item in results[:100]:  # Limit to 100 for performance
        # Handle content_type - ensure consistent string representation
        content_type_value = item.content_type
        if hasattr(content_type_value, 'value'):
            content_type_value = content_type_value.value
        elif not isinstance(content_type_value, str):
            content_type_value = str(content_type_value)
        
        serialized_results.append({
            'uri': item.uri,
            'content_type': content_type_value,
            'text': item.text[:200] + '...' if len(item.text) > 200 else item.text,
            'created_at': item.created_at.isoformat() if hasattr(item.created_at, 'isoformat') else str(item.created_at),
            'likes': item.like_count,
            'reposts': item.repost_count,
            'replies': item.reply_count,
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

@app.route('/debug-profile')
@login_required
def debug_profile():
    """Debug endpoint to test profile fetching"""
    auth_manager = get_auth_manager()
    if not auth_manager or not auth_manager.client:
        return jsonify({'error': 'Not authenticated'}), 401
    
    handle = session['user_handle']
    debug_info = {'handle': handle}
    
    try:
        # Test the client object
        debug_info['client_type'] = str(type(auth_manager.client))
        debug_info['client_authenticated'] = auth_manager.is_authenticated()
        
        # Test different methods
        try:
            from atproto import models
            profile_response = auth_manager.client.app.bsky.actor.get_profile(
                models.AppBskyActorGetProfile.Params(actor=handle)
            )
            profile = profile_response.value
            debug_info['at_protocol_method'] = {
                'success': True,
                'handle': getattr(profile, 'handle', None),
                'display_name': getattr(profile, 'display_name', None),
                'avatar': getattr(profile, 'avatar', None),
                'type': str(type(profile))
            }
        except Exception as e:
            debug_info['at_protocol_method'] = {'success': False, 'error': str(e)}
        
        try:
            profile = auth_manager.client.get_profile(handle)
            debug_info['simple_method'] = {
                'success': True,
                'handle': getattr(profile, 'handle', None),
                'display_name': getattr(profile, 'display_name', None),
                'avatar': getattr(profile, 'avatar', None),
                'type': str(type(profile)),
                'attributes': [attr for attr in dir(profile) if not attr.startswith('_')]
            }
        except Exception as e:
            debug_info['simple_method'] = {'success': False, 'error': str(e)}
        
        return jsonify(debug_info)
        
    except Exception as e:
        debug_info['error'] = str(e)
        return jsonify(debug_info), 500

@app.route('/firehose')
@login_required
def firehose():
    """Stream real-time Bluesky firehose data"""
    def generate():
        firehose_error = None
        try:
            # Import firehose client
            print("INFO: Starting firehose connection...")
            from atproto import FirehoseSubscribeReposClient, models, parse_subscribe_repos_message
            print("INFO: Firehose imports successful")
            
            # Create a queue to buffer messages
            message_queue = queue.Queue(maxsize=50)
            firehose_connected = False
            
            def on_message_handler(message):
                nonlocal firehose_connected
                try:
                    if not firehose_connected:
                        print("INFO: Firehose connection established, receiving messages")
                        firehose_connected = True
                    
                    commit = parse_subscribe_repos_message(message)
                    if not isinstance(commit, models.ComAtprotoSyncSubscribeRepos.Commit):
                        return
                    
                    # Parse CAR blocks if available
                    blocks_dict = {}
                    if hasattr(commit, 'blocks') and commit.blocks:
                        try:
                            from atproto import CAR
                            car = CAR.from_bytes(commit.blocks)
                            blocks_dict = car.blocks
                        except Exception as car_error:
                            print(f"ERROR: Parsing CAR blocks: {car_error}")
                    
                    # Process operations - ONLY posts and replies (comments)
                    for op in commit.ops:
                        if op.action == 'create' and 'app.bsky.feed.post' in op.path:
                            try:
                                # Extract post text from the record block
                                post_text = 'New post'
                                is_reply = False
                                
                                if op.cid in blocks_dict:
                                    record = blocks_dict[op.cid]
                                    if isinstance(record, dict):
                                        post_text = record.get('text', 'New post')[:80]  # Shorter for better display
                                        is_reply = 'reply' in record or record.get('reply') is not None
                                
                                # Only process posts and replies, skip other types
                                if is_reply:
                                    display_text = f"💬 {post_text}"
                                    content_type = 'reply'
                                else:
                                    display_text = post_text
                                    content_type = 'post'
                                
                                # Get a readable author identifier
                                author_did = commit.repo
                                if author_did.startswith('did:plc:'):
                                    # Try to get handle from the record if available
                                    author_display = author_did.replace('did:plc:', '')[:12] + '...'
                                else:
                                    author_display = author_did[:20]
                                
                                post_data = {
                                    'type': content_type,
                                    'author': author_display,
                                    'text': display_text,
                                    'timestamp': time.time()
                                }
                                
                                if not message_queue.full():
                                    message_queue.put(post_data)
                                else:
                                    # If queue is full, remove oldest and add new
                                    try:
                                        message_queue.get_nowait()
                                        message_queue.put(post_data)
                                    except queue.Empty:
                                        pass
                                        
                            except Exception as op_error:
                                print(f"ERROR: Processing post operation: {op_error}")
                        # Skip likes and reposts entirely - only process posts and replies
                except Exception as e:
                    print(f"ERROR: Processing firehose message: {e}")
            
            # Start firehose client in separate thread
            def start_firehose():
                nonlocal firehose_error
                try:
                    print("INFO: Creating FirehoseSubscribeReposClient...")
                    client = FirehoseSubscribeReposClient()
                    print("INFO: Starting firehose client...")
                    client.start(on_message_handler)
                except Exception as e:
                    firehose_error = str(e)
                    print(f"ERROR: Firehose client failed: {e}")
                    import traceback
                    traceback.print_exc()
            
            firehose_thread = threading.Thread(target=start_firehose, daemon=True)
            firehose_thread.start()
            
            # Give the firehose a moment to connect
            time.sleep(2)
            print(f"INFO: Firehose thread started, connected: {firehose_connected}")
            
            # Stream messages to client with minimal delay for real-time feel
            last_message_time = 0
            min_delay = 0.1  # Very minimal delay for real-time display
            messages_received = 0
            start_time = time.time()
            
            # Send initial status
            yield f"data: {json.dumps({'type': 'status', 'message': 'Connecting to live Bluesky posts and replies...', 'timestamp': time.time()})}\n\n"
            
            timeout_duration = 8  # 8 seconds timeout for initial connection
            
            while True:
                try:
                    current_time = time.time()
                    
                    # Check for timeout if no messages received
                    if messages_received == 0 and (current_time - start_time) > timeout_duration:
                        if firehose_error:
                            yield f"data: {json.dumps({'type': 'error', 'message': f'Firehose connection failed: {firehose_error}', 'timestamp': time.time()})}\n\n"
                        else:
                            yield f"data: {json.dumps({'type': 'status', 'message': 'Firehose connected but quiet - falling back to demo mode', 'timestamp': time.time()})}\n\n"
                        break
                    
                    if not message_queue.empty():
                        if current_time - last_message_time >= min_delay:
                            message = message_queue.get_nowait()
                            messages_received += 1
                            yield f"data: {json.dumps(message)}\n\n"
                            last_message_time = current_time
                        else:
                            time.sleep(0.05)  # Very short wait for real-time feel
                    else:
                        time.sleep(0.05)  # Check very frequently for real-time updates
                except queue.Empty:
                    time.sleep(0.05)
                except Exception as e:
                    print(f"ERROR: Streaming firehose data: {e}")
                    break
                    
        except Exception as e:
            print(f"ERROR: Firehose setup failed: {e}")
            import traceback
            traceback.print_exc()
            firehose_error = str(e)
            
        # Send error notification if we had issues
        if firehose_error:
            yield f"data: {json.dumps({'type': 'error', 'message': f'Firehose failed: {firehose_error}', 'timestamp': time.time()})}\n\n"
            
            # Fallback with mock data if firehose fails - ONLY posts and replies
            print("INFO: Using mock posts and replies for demo")
            yield f"data: {json.dumps({'type': 'status', 'message': '✨ Demo mode: showing sample posts while processing continues...', 'timestamp': time.time()})}\n\n"
        
        mock_messages = [
            {'type': 'post', 'author': 'alice.bsky.social', 'text': 'Hello Bluesky! 🌅', 'timestamp': time.time()},
            {'type': 'reply', 'author': 'bob.bsky.social', 'text': '💬 That sounds great!', 'timestamp': time.time()},
            {'type': 'post', 'author': 'charlie.bsky.social', 'text': 'Beautiful sunset today', 'timestamp': time.time()},
            {'type': 'post', 'author': 'photographer...', 'text': 'Just captured an amazing landscape 📸', 'timestamp': time.time()},
            {'type': 'reply', 'author': 'artist.bsky...', 'text': '💬 Amazing work! Love the composition', 'timestamp': time.time()},
            {'type': 'post', 'author': 'developer...', 'text': 'Working on a new project with AT Protocol', 'timestamp': time.time()},
            {'type': 'reply', 'author': 'tech.bsky...', 'text': '💬 What kind of project? Sounds interesting!', 'timestamp': time.time()},
            {'type': 'post', 'author': 'news.bsky.social', 'text': 'Breaking: New features coming to Bluesky!', 'timestamp': time.time()},
            {'type': 'post', 'author': 'music.bsky...', 'text': 'Just released a new track 🎵', 'timestamp': time.time()},
            {'type': 'reply', 'author': 'fan.bsky.social', 'text': '💬 Can\'t wait to listen!', 'timestamp': time.time()}
        ]
        
        for i in range(150):  # Stream for demo - more content
            import random
            message = random.choice(mock_messages)
            message['timestamp'] = time.time()
            yield f"data: {json.dumps(message)}\n\n"
            time.sleep(0.3)  # Faster rate to simulate real-time activity
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/download-backup')
@login_required
def download_backup():
    """Download the user's CAR file as a backup"""
    car_path = session.get('car_path')
    session_id = session.get('session_id')
    
    # Try to get car_path from progress_data if not in session
    if not car_path and session_id and session_id in progress_data:
        car_path = progress_data[session_id].get('car_path')
    
    if not car_path or not Path(car_path).exists():
        return jsonify({'error': 'Backup file not found'}), 404
    
    try:
        car_file = Path(car_path)
        handle = session['user_handle']
        
        # Create a user-friendly filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        download_filename = f"bluesky_backup_{handle}_{timestamp}.car"
        
        return send_from_directory(
            car_file.parent,
            car_file.name,
            as_attachment=True,
            download_name=download_filename,
            mimetype='application/octet-stream'
        )
    except Exception as e:
        return jsonify({'error': f'Download failed: {str(e)}'}), 500

@app.route('/debug-session')
@login_required
def debug_session():
    """Debug endpoint to check session data"""
    json_path = get_json_path()
    
    debug_info = {
        'user_handle': session.get('user_handle'),
        'json_path': session.get('json_path'),
        'resolved_json_path': json_path,
        'session_id': session.get('session_id'),
        'total_items': session.get('total_items'),
        'progress_data': progress_data.get(session.get('session_id'), {}) if session.get('session_id') else {}
    }
    
    # Try to load data if path exists
    if json_path:
        try:
            from skymarshal.data_manager import DataManager
            from skymarshal.auth import AuthManager
            from skymarshal.settings import SettingsManager
            
            auth_manager = get_auth_manager()
            settings_file = Path.home() / ".car_inspector_settings.json"
            settings_manager = SettingsManager(settings_file)
            settings = settings_manager.settings
            
            skymarshal_dir = Path.home() / '.skymarshal'
            backups_dir = skymarshal_dir / 'cars'
            json_dir = skymarshal_dir / 'json'
            
            data_manager = DataManager(
                auth_manager=auth_manager or AuthManager(),
                settings=settings,
                skymarshal_dir=skymarshal_dir,
                backups_dir=backups_dir,
                json_dir=json_dir
            )
            
            items = data_manager.load_exported_data(Path(json_path))
            debug_info['data_load_success'] = True
            debug_info['items_count'] = len(items)
            debug_info['file_exists'] = Path(json_path).exists()
            debug_info['file_size'] = Path(json_path).stat().st_size if Path(json_path).exists() else 0
            
            if len(items) > 0:
                debug_info['sample_item'] = {
                    'type': items[0].content_type,
                    'text': items[0].text[:100] if items[0].text else None,
                    'likes': items[0].like_count,
                    'reposts': items[0].repost_count,
                    'replies': items[0].reply_count
                }
        except Exception as e:
            debug_info['data_load_error'] = str(e)
            debug_info['file_exists'] = Path(json_path).exists() if json_path else False
    
    return jsonify(debug_info)

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)