#!/usr/bin/env python3
"""
Skymarshal Web App - Simple Flask interface for Bluesky account analysis
Provides authentication, CAR download, and enriched statistics display
"""

import os
import sys
import json
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import asyncio
import traceback

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
    from werkzeug.serving import run_simple
except ImportError:
    print("❌ Flask not installed. Run: pip install flask")
    sys.exit(1)

try:
    from skymarshal.auth import AuthManager
    from skymarshal.data_manager import DataManager
    from skymarshal.ui import UIManager
    from skymarshal.models import UserSettings, ContentItem
except ImportError as e:
    print(f"❌ Failed to import Skymarshal modules: {e}")
    print("💡 Make sure you're running this from the skymarshal directory")
    sys.exit(1)

app = Flask(__name__)
app.secret_key = 'skymarshal-webapp-secret-key-change-in-production'

class SkymarshalWebApp:
    """Web interface for Skymarshal functionality."""
    
    def __init__(self):
        self.settings_file = Path.home() / '.car_inspector_settings.json'
        self.settings = self._load_settings()
        
        # Initialize directories
        self.skymarshal_dir = Path.home() / '.skymarshal'
        self.cars_dir = self.skymarshal_dir / 'cars'
        self.json_dir = self.skymarshal_dir / 'json'
        
        # Create directories if they don't exist
        self.cars_dir.mkdir(parents=True, exist_ok=True)
        self.json_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize managers
        self.ui_manager = UIManager(self.settings)
        self.auth_manager = AuthManager(self.ui_manager)
        self.data_manager = DataManager(
            self.auth_manager,
            self.settings,
            self.skymarshal_dir,
            self.cars_dir,
            self.json_dir
        )
    
    def _load_settings(self) -> UserSettings:
        """Load user settings from file."""
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r') as f:
                    settings_data = json.load(f)
                return UserSettings(**settings_data)
        except Exception:
            pass
        return UserSettings()
    
    def authenticate(self, handle: str, password: str) -> bool:
        """Authenticate user with Bluesky."""
        try:
            normalized_handle = self.auth_manager.normalize_handle(handle)
            success = self.auth_manager.authenticate_client(normalized_handle, password)
            if success:
                session['authenticated'] = True
                session['handle'] = self.auth_manager.current_handle
                session['did'] = self.auth_manager.current_did
            return success
        except Exception as e:
            print(f"Authentication error: {e}")
            return False
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return session.get('authenticated', False) and self.auth_manager.is_authenticated()
    
    def download_and_process_data(self) -> Dict[str, Any]:
        """Download CAR file and process data."""
        try:
            if not self.is_authenticated():
                return {'success': False, 'error': 'Not authenticated'}
            
            handle = session.get('handle')
            if not handle:
                return {'success': False, 'error': 'No handle in session'}
            
            # Download and process CAR file
            success = self.data_manager.download_and_process_car(handle)
            
            if not success:
                return {'success': False, 'error': 'Failed to download CAR file'}
            
            # Load the processed data
            files = self.data_manager.get_user_files(handle, 'json')
            if not files:
                return {'success': False, 'error': 'No data files found after processing'}
            
            # Get the most recent file
            latest_file = max(files, key=lambda x: x.stat().st_mtime)
            data = self.data_manager.load_json_data(latest_file)
            
            if not data:
                return {'success': False, 'error': 'Failed to load processed data'}
            
            # Enrich data with engagement information
            enriched_data = self._enrich_data_with_engagement(data)
            
            return {
                'success': True,
                'data': enriched_data,
                'file_path': str(latest_file),
                'total_items': len(enriched_data)
            }
            
        except Exception as e:
            return {'success': False, 'error': f'Processing error: {str(e)}'}
    
    def _enrich_data_with_engagement(self, data: list) -> list:
        """Enrich data with like/repost information and engagement scores."""
        enriched = []
        
        for item in data:
            # Calculate engagement score
            likes = item.get('likes', 0)
            reposts = item.get('reposts', 0)
            replies = item.get('replies', 0)
            
            # Weighted engagement score (same formula as in models.py)
            engagement_score = likes + (2 * reposts) + (2.5 * replies)
            
            # Add engagement metadata
            item['engagement_score'] = engagement_score
            item['total_interactions'] = likes + reposts + replies
            
            # Categorize engagement level
            if engagement_score == 0:
                item['engagement_level'] = 'dead'
            elif engagement_score <= 2:
                item['engagement_level'] = 'low'
            elif engagement_score <= 10:
                item['engagement_level'] = 'medium'
            elif engagement_score <= 50:
                item['engagement_level'] = 'high'
            else:
                item['engagement_level'] = 'viral'
            
            enriched.append(item)
        
        return enriched
    
    def calculate_statistics(self, data: list) -> Dict[str, Any]:
        """Calculate comprehensive statistics from enriched data."""
        if not data:
            return {}
        
        stats = {
            'total_items': len(data),
            'posts': 0,
            'likes': 0,
            'reposts': 0,
            'total_engagement': 0,
            'avg_engagement': 0,
            'engagement_rate': 0,
            'engagement_distribution': {
                'dead': 0,
                'low': 0,
                'medium': 0,
                'high': 0,
                'viral': 0
            },
            'top_posts': [],
            'recent_activity': {
                'last_7_days': 0,
                'last_30_days': 0,
                'last_90_days': 0
            },
            'content_quality': {
                'avg_text_length': 0,
                'posts_with_engagement': 0
            }
        }
        
        posts_with_engagement = []
        text_lengths = []
        total_engagement_sum = 0
        
        # Current time for recent activity calculation
        now = datetime.now()
        
        for item in data:
            content_type = item.get('type', 'unknown')
            
            if content_type == 'post':
                stats['posts'] += 1
                
                # Text analysis
                text = item.get('text', '')
                text_lengths.append(len(text))
                
                # Engagement analysis
                engagement_score = item.get('engagement_score', 0)
                total_interactions = item.get('total_interactions', 0)
                
                total_engagement_sum += engagement_score
                
                if total_interactions > 0:
                    posts_with_engagement.append(item)
                    stats['content_quality']['posts_with_engagement'] += 1
                
                # Engagement level distribution
                level = item.get('engagement_level', 'dead')
                if level in stats['engagement_distribution']:
                    stats['engagement_distribution'][level] += 1
                
                # Recent activity analysis
                try:
                    if 'created_at' in item:
                        created_at = datetime.fromisoformat(item['created_at'].replace('Z', '+00:00'))
                        days_ago = (now - created_at).days
                        
                        if days_ago <= 7:
                            stats['recent_activity']['last_7_days'] += 1
                        elif days_ago <= 30:
                            stats['recent_activity']['last_30_days'] += 1
                        elif days_ago <= 90:
                            stats['recent_activity']['last_90_days'] += 1
                except:
                    pass
                
            elif content_type == 'like':
                stats['likes'] += 1
            elif content_type == 'repost':
                stats['reposts'] += 1
        
        # Calculate averages and rates
        if stats['posts'] > 0:
            stats['avg_engagement'] = total_engagement_sum / stats['posts']
            stats['engagement_rate'] = (len(posts_with_engagement) / stats['posts']) * 100
            stats['content_quality']['avg_text_length'] = sum(text_lengths) / len(text_lengths) if text_lengths else 0
        
        # Top performing posts
        stats['top_posts'] = sorted(
            posts_with_engagement,
            key=lambda x: x.get('engagement_score', 0),
            reverse=True
        )[:10]
        
        stats['total_engagement'] = total_engagement_sum
        
        return stats

# Initialize the web app
webapp = SkymarshalWebApp()

@app.route('/')
def index():
    """Home page."""
    if webapp.is_authenticated():
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle authentication."""
    if request.method == 'POST':
        handle = request.form.get('handle', '').strip()
        password = request.form.get('password', '').strip()
        
        if not handle or not password:
            flash('Please provide both handle and password', 'error')
            return render_template('login.html')
        
        if webapp.authenticate(handle, password):
            flash(f'Successfully authenticated as @{session["handle"]}', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Authentication failed. Please check your credentials.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout user."""
    webapp.auth_manager.logout()
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    """Main dashboard."""
    if not webapp.is_authenticated():
        flash('Please login first', 'error')
        return redirect(url_for('login'))
    
    return render_template('dashboard.html', handle=session.get('handle'))

@app.route('/process', methods=['POST'])
def process_data():
    """Download and process user data."""
    if not webapp.is_authenticated():
        return jsonify({'success': False, 'error': 'Not authenticated'})
    
    try:
        result = webapp.download_and_process_data()
        
        if result['success']:
            # Calculate statistics
            stats = webapp.calculate_statistics(result['data'])
            result['statistics'] = stats
            
            # Store in session for display
            session['last_stats'] = stats
            session['data_processed'] = True
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Processing failed: {str(e)}'})

@app.route('/statistics')
def statistics():
    """Display statistics page."""
    if not webapp.is_authenticated():
        flash('Please login first', 'error')
        return redirect(url_for('login'))
    
    stats = session.get('last_stats')
    if not stats:
        flash('No data processed yet. Please download your data first.', 'warning')
        return redirect(url_for('dashboard'))
    
    return render_template('statistics.html', stats=stats, handle=session.get('handle'))

if __name__ == '__main__':
    # Create templates directory and basic templates
    templates_dir = Path(__file__).parent / 'templates'
    templates_dir.mkdir(exist_ok=True)
    
    print("🚀 Starting Skymarshal Web App")
    print("📍 Access at: http://localhost:5000")
    print("🔐 Authenticate with your Bluesky credentials")
    
    app.run(debug=True, host='0.0.0.0', port=5000)