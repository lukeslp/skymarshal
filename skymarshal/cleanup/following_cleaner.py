"""
Following Cleaner Module

This module provides following cleanup and bot detection capabilities for Bluesky accounts.
It integrates functionality from the standalone bluesky_cleaner.py tool.

Features:
- Analyzes accounts you follow for bot/spam indicators
- Identifies accounts with poor follower-to-following ratios
- Interactive unfollowing with safety measures
- Smart caching system for performance
- Batch processing with rate limiting
"""

import asyncio
import json
import sqlite3
import time
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any
import aiohttp

from ..models import console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Confirm, Prompt


class FollowingCleaner:
    """
    Analyzes and cleans up following lists by identifying potential bot/spam accounts.
    
    This class provides comprehensive following cleanup capabilities including:
    - Analysis of follower-to-following ratios
    - Bot detection and spam identification
    - Interactive unfollowing with safety measures
    - Smart caching for performance optimization
    """
    
    def __init__(self, auth_manager, db_path: str = None):
        """
        Initialize the FollowingCleaner.
        
        Args:
            auth_manager: Authenticated Bluesky client manager
            db_path: Optional custom database path
        """
        self.auth_manager = auth_manager
        self.client = auth_manager.client
        self.base_url = "https://public.api.bsky.app"
        self.batch_size = 25  # API limit for profile batches
        self.following_batch_size = 100  # API max for getFollows
        self.rate_limit_delay = 0.05  # Rate limiting delay
        
        # Use shared database if no custom path provided
        if db_path is None:
            from ..data_manager import DataManager
            data_manager = DataManager(auth_manager)
            self.db_path = data_manager.get_database_path()
        else:
            self.db_path = db_path
            
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database for caching profile data."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create profiles table with comprehensive profile data
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    did TEXT PRIMARY KEY,
                    handle TEXT,
                    display_name TEXT,
                    description TEXT,
                    followers_count INTEGER,
                    following_count INTEGER,
                    posts_count INTEGER,
                    avatar TEXT,
                    created_at TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    raw_data TEXT
                )
            """)
            
            # Create indexes for faster lookups
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_profiles_handle ON profiles(handle)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_profiles_followers ON profiles(followers_count DESC)")
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            console.print(f"[red]❌ Database initialization error: {str(e)}[/red]")
    
    def get_cached_profiles(self, dids: List[str]) -> Dict[str, Dict]:
        """Retrieve cached profiles from database."""
        if not dids:
            return {}
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            placeholders = ','.join(['?' for _ in dids])
            cursor.execute(f"""
                SELECT did, handle, display_name, description, followers_count, 
                       following_count, posts_count, avatar, raw_data
                FROM profiles 
                WHERE did IN ({placeholders})
            """, dids)
            
            cached_profiles = {}
            for row in cursor.fetchall():
                did, handle, display_name, description, followers_count, following_count, posts_count, avatar, raw_data = row
                cached_profiles[did] = {
                    'did': did,
                    'handle': handle,
                    'displayName': display_name,
                    'description': description,
                    'followersCount': followers_count,
                    'followsCount': following_count,
                    'postsCount': posts_count,
                    'avatar': avatar,
                    'raw_data': raw_data
                }
            
            conn.close()
            return cached_profiles
            
        except Exception as e:
            console.print(f"[red]❌ Error retrieving cached profiles: {str(e)}[/red]")
            return {}
    
    def cache_profiles(self, profiles: List[Dict]):
        """Store profiles in database cache."""
        if not profiles:
            return
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for profile in profiles:
                cursor.execute("""
                    INSERT OR REPLACE INTO profiles 
                    (did, handle, display_name, description, followers_count, 
                     following_count, posts_count, avatar, raw_data, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    profile.get('did', ''),
                    profile.get('handle', ''),
                    profile.get('displayName', ''),
                    profile.get('description', ''),
                    profile.get('followersCount', 0),
                    profile.get('followsCount', 0),
                    profile.get('postsCount', 0),
                    profile.get('avatar', ''),
                    json.dumps(profile)
                ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            console.print(f"[red]❌ Error caching profiles: {str(e)}[/red]")
    
    async def get_following(self, actor_did: str, limit: int = None) -> List[Dict]:
        """Retrieve following list for a given actor using paginated requests."""
        following = []
        cursor = None
        
        headers = {
            'Authorization': f'Bearer {self.auth_manager.access_token}',
            'Content-Type': 'application/json'
        }
        
        async with aiohttp.ClientSession() as session:
            while limit is None or len(following) < limit:
                url = f"{self.base_url}/xrpc/app.bsky.graph.getFollows"
                params = {
                    'actor': actor_did,
                    'limit': self.following_batch_size if limit is None else min(self.following_batch_size, limit - len(following))
                }
                
                if cursor:
                    params['cursor'] = cursor
                    
                try:
                    async with session.get(url, headers=headers, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            batch_following = data.get('follows', [])
                            following.extend(batch_following)
                            
                            cursor = data.get('cursor')
                            if not cursor or not batch_following:
                                break
                                
                            await asyncio.sleep(self.rate_limit_delay)
                            
                        else:
                            error_text = await response.text()
                            console.print(f"[red]❌ Error retrieving following: {response.status} - {error_text}[/red]")
                            break
                            
                except Exception as e:
                    console.print(f"[red]❌ Error during following retrieval: {str(e)}[/red]")
                    break
        
        return following if limit is None else following[:limit]
    
    async def get_profiles_batch(self, actor_dids: List[str]) -> List[Dict]:
        """Efficiently retrieve multiple profiles using cache-first approach."""
        if not actor_dids:
            return []
        
        # First, check cache for existing profiles
        cached_profiles = self.get_cached_profiles(actor_dids)
        cached_dids = set(cached_profiles.keys())
        uncached_dids = [did for did in actor_dids if did not in cached_dids]
        
        all_profiles = list(cached_profiles.values())
        
        if cached_dids:
            console.print(f"[blue]🔄 Found {len(cached_dids)} profiles in cache, fetching {len(uncached_dids)} from API[/blue]")
        
        # Fetch uncached profiles from API
        if uncached_dids:
            url = f"{self.base_url}/xrpc/app.bsky.actor.getProfiles"
            headers = {
                'Authorization': f'Bearer {self.auth_manager.access_token}',
                'Content-Type': 'application/json'
            }
            
            params = {'actors': uncached_dids}
            
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get(url, headers=headers, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            new_profiles = data.get('profiles', [])
                            
                            # Cache the newly fetched profiles
                            if new_profiles:
                                self.cache_profiles(new_profiles)
                            
                            all_profiles.extend(new_profiles)
                            
                        else:
                            error_text = await response.text()
                            console.print(f"[red]❌ Error retrieving profiles: {response.status} - {error_text}[/red]")
                            
                except Exception as e:
                    console.print(f"[red]❌ Error during profile retrieval: {str(e)}[/red]")
        
        return all_profiles
    
    def analyze_following_quality(self, following: List[Dict], profiles: List[Dict]) -> List[Dict]:
        """
        Analyze following list for potential bot/spam accounts.
        
        Args:
            following: List of following data
            profiles: List of detailed profile data
            
        Returns:
            List[Dict]: Following accounts with quality analysis
        """
        console.print(f"[blue]🔍 Analyzing {len(following)} following accounts for quality...[/blue]")
        
        # Create profile mapping
        profile_map = {profile['did']: profile for profile in profiles}
        
        analyzed_following = []
        for follow in following:
            did = follow['did']
            profile = profile_map.get(did, {})
            
            followers_count = profile.get('followersCount', 0)
            follows_count = profile.get('followsCount', 0)
            posts_count = profile.get('postsCount', 0)
            
            # Calculate quality metrics
            quality_score = 0.0
            bot_score = 0.0
            issues = []
            
            # Bot detection based on follower/following ratio
            if follows_count > 0:
                ratio = followers_count / follows_count
                if ratio < 0.1:
                    bot_score = 0.9
                    issues.append("Very low follower/following ratio")
                elif ratio < 0.2:
                    bot_score = 0.7
                    issues.append("Low follower/following ratio")
                elif ratio < 0.5:
                    bot_score = 0.5
                    issues.append("Moderate follower/following ratio")
                else:
                    bot_score = 0.1
            else:
                issues.append("No following data available")
            
            # Quality assessment
            if followers_count > 1000:
                quality_score += 0.3
            elif followers_count > 100:
                quality_score += 0.2
            elif followers_count > 10:
                quality_score += 0.1
            
            if posts_count > 100:
                quality_score += 0.3
            elif posts_count > 50:
                quality_score += 0.2
            elif posts_count > 10:
                quality_score += 0.1
            
            if follows_count > 0 and ratio > 1.0:
                quality_score += 0.2
            elif follows_count > 0 and ratio > 0.5:
                quality_score += 0.1
            
            # Check for suspicious patterns
            handle = profile.get('handle', '')
            if handle:
                if any(pattern in handle.lower() for pattern in ['bot', 'spam', 'fake', 'test']):
                    issues.append("Suspicious handle pattern")
                    bot_score = max(bot_score, 0.8)
                
                if len(handle) < 3:
                    issues.append("Very short handle")
                    bot_score = max(bot_score, 0.6)
            
            # Check description
            description = profile.get('description', '')
            if not description or len(description) < 10:
                issues.append("Missing or very short description")
                bot_score = max(bot_score, 0.4)
            
            # Create analysis result
            analysis = {
                'did': did,
                'handle': profile.get('handle', ''),
                'displayName': profile.get('displayName', ''),
                'description': description,
                'followersCount': followers_count,
                'followsCount': follows_count,
                'postsCount': posts_count,
                'avatar': profile.get('avatar', ''),
                'quality_score': quality_score,
                'bot_score': bot_score,
                'issues': issues,
                'ratio': ratio if follows_count > 0 else None,
                'indexedAt': follow.get('indexedAt', ''),
                'raw_data': profile.get('raw_data', '')
            }
            
            analyzed_following.append(analysis)
        
        # Sort by bot score (descending) and quality score (ascending)
        analyzed_following.sort(key=lambda x: (x['bot_score'], -x['quality_score']), reverse=True)
        
        return analyzed_following
    
    def display_analysis_results(self, analyzed_following: List[Dict], show_all: bool = False):
        """Display analysis results in a formatted table."""
        
        # Filter for problematic accounts if not showing all
        if not show_all:
            problematic = [acc for acc in analyzed_following if acc['bot_score'] > 0.5 or acc['quality_score'] < 0.3]
        else:
            problematic = analyzed_following
        
        if not problematic:
            console.print("[green]✅ No problematic accounts found in your following list![/green]")
            return
        
        # Create analysis table
        table = Table(title=f"Following Analysis - {len(problematic)} Problematic Accounts", 
                     show_header=True, header_style="bold red")
        table.add_column("Handle", style="cyan", width=20)
        table.add_column("Display Name", style="white", width=25)
        table.add_column("Followers", justify="right", style="green", width=10)
        table.add_column("Following", justify="right", style="blue", width=10)
        table.add_column("Posts", justify="right", style="yellow", width=8)
        table.add_column("Bot Score", justify="right", style="red", width=10)
        table.add_column("Quality", justify="right", style="magenta", width=8)
        table.add_column("Issues", style="dim", width=30)
        
        for account in problematic[:20]:  # Show top 20
            issues_text = ", ".join(account['issues'][:2])  # Show first 2 issues
            if len(account['issues']) > 2:
                issues_text += "..."
            
            table.add_row(
                account['handle'],
                account['displayName'][:24],
                str(account['followersCount']),
                str(account['followsCount']),
                str(account['postsCount']),
                f"{account['bot_score']:.2f}",
                f"{account['quality_score']:.2f}",
                issues_text
            )
        
        console.print(table)
        
        # Summary statistics
        high_bot_score = len([acc for acc in problematic if acc['bot_score'] > 0.7])
        low_quality = len([acc for acc in problematic if acc['quality_score'] < 0.3])
        
        summary_text = f"""
Analysis Summary:
- Total accounts analyzed: {len(analyzed_following)}
- Problematic accounts: {len(problematic)}
- High bot score (>0.7): {high_bot_score}
- Low quality (<0.3): {low_quality}
        """
        
        console.print(Panel(summary_text, title="Analysis Summary", border_style="yellow"))
    
    async def interactive_unfollow(self, analyzed_following: List[Dict]) -> Dict[str, Any]:
        """
        Interactive unfollowing process with safety measures.
        
        Args:
            analyzed_following: List of analyzed following accounts
            
        Returns:
            Dict: Unfollow results and statistics
        """
        console.print("[bold yellow]⚠️ Interactive Unfollowing Mode[/bold yellow]")
        console.print("This will help you unfollow accounts with safety measures.")
        
        # Filter for high-risk accounts
        high_risk = [acc for acc in analyzed_following if acc['bot_score'] > 0.7 or acc['quality_score'] < 0.2]
        
        if not high_risk:
            console.print("[green]✅ No high-risk accounts found for unfollowing![/green]")
            return {'unfollowed': 0, 'skipped': 0, 'errors': 0}
        
        console.print(f"[yellow]Found {len(high_risk)} high-risk accounts for review[/yellow]")
        
        # Safety confirmation
        if not Confirm.ask("Do you want to proceed with interactive unfollowing?"):
            console.print("[blue]Unfollowing cancelled by user[/blue]")
            return {'unfollowed': 0, 'skipped': 0, 'errors': 0}
        
        unfollowed = 0
        skipped = 0
        errors = 0
        
        # Process each high-risk account
        for i, account in enumerate(high_risk[:10], 1):  # Limit to 10 for safety
            console.print(f"\n[blue]Account {i}/{min(len(high_risk), 10)}: @{account['handle']}[/blue]")
            console.print(f"Bot Score: {account['bot_score']:.2f}, Quality: {account['quality_score']:.2f}")
            console.print(f"Issues: {', '.join(account['issues'])}")
            
            # Show account details
            if account['description']:
                console.print(f"Description: {account['description'][:100]}...")
            
            # Ask for confirmation
            action = Prompt.ask(
                "Action",
                choices=["unfollow", "skip", "quit"],
                default="skip"
            )
            
            if action == "quit":
                console.print("[blue]Unfollowing stopped by user[/blue]")
                break
            elif action == "skip":
                skipped += 1
                console.print("[yellow]Skipped[/yellow]")
                continue
            elif action == "unfollow":
                # Perform unfollow
                try:
                    await self.client.unfollow(account['did'])
                    unfollowed += 1
                    console.print("[green]✅ Unfollowed[/green]")
                    
                    # Rate limiting
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    errors += 1
                    console.print(f"[red]❌ Error unfollowing: {str(e)}[/red]")
        
        # Summary
        results = {
            'unfollowed': unfollowed,
            'skipped': skipped,
            'errors': errors,
            'total_reviewed': unfollowed + skipped + errors
        }
        
        console.print(f"\n[bold green]Unfollowing Complete![/bold green]")
        console.print(f"Unfollowed: {unfollowed}")
        console.print(f"Skipped: {skipped}")
        console.print(f"Errors: {errors}")
        
        return results
    
    async def run_complete_analysis(self, max_following: int = None, interactive: bool = False) -> Dict[str, Any]:
        """
        Run complete following analysis and optional cleanup.
        
        Args:
            max_following: Maximum number of following accounts to analyze
            interactive: Whether to run interactive unfollowing
            
        Returns:
            Dict: Complete analysis results
        """
        console.print(f"[bold blue]🚀 Starting following analysis[/bold blue]")
        
        # Get current user's DID
        try:
            profile = await self.client.get_profile()
            user_did = profile.did
        except Exception as e:
            console.print(f"[red]❌ Error getting user profile: {str(e)}[/red]")
            return {'error': 'Failed to get user profile'}
        
        # Get following list
        console.print(f"[blue]📥 Retrieving following list...[/blue]")
        following = await self.get_following(user_did, max_following)
        
        if not following:
            console.print("[yellow]⚠️ No following accounts found[/yellow]")
            return {'error': 'No following accounts found'}
        
        # Extract DIDs for profile lookup
        following_dids = [follow['did'] for follow in following]
        
        # Get detailed profiles
        console.print(f"[blue]👥 Fetching detailed profiles for {len(following_dids)} accounts...[/blue]")
        profiles = await self.get_profiles_batch(following_dids)
        
        # Analyze following quality
        analyzed_following = self.analyze_following_quality(following, profiles)
        
        # Display results
        self.display_analysis_results(analyzed_following)
        
        # Interactive unfollowing if requested
        unfollow_results = None
        if interactive:
            unfollow_results = await self.interactive_unfollow(analyzed_following)
        
        # Return complete results
        return {
            'total_following': len(following),
            'analyzed_following': analyzed_following,
            'high_risk_count': len([acc for acc in analyzed_following if acc['bot_score'] > 0.7]),
            'low_quality_count': len([acc for acc in analyzed_following if acc['quality_score'] < 0.3]),
            'unfollow_results': unfollow_results,
            'timestamp': datetime.now().isoformat()
        }