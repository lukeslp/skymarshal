"""
Follower Analyzer Module

This module provides comprehensive follower analysis capabilities for Bluesky accounts.
It integrates functionality from the standalone bluesky_follower_ranker.py tool.

Features:
- Follower ranking by follower count
- Bot detection analysis (follower/following ratios)
- Quality follower analysis (selective following behavior)
- Smart caching system for performance
- Batch processing with rate limiting
"""

import asyncio
import json
import sqlite3
import time
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import aiohttp
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from ..models import console


class FollowerAnalyzer:
    """
    Analyzes Bluesky followers with ranking, bot detection, and quality analysis.
    
    This class provides comprehensive follower analysis capabilities including:
    - Ranking followers by follower count
    - Detecting potential bot accounts
    - Analyzing follower quality based on following patterns
    - Smart caching for performance optimization
    """
    
    def __init__(self, auth_manager, db_path: str = None):
        """
        Initialize the FollowerAnalyzer.
        
        Args:
            auth_manager: Authenticated Bluesky client manager
            db_path: Optional custom database path
        """
        self.auth_manager = auth_manager
        self.client = auth_manager.client
        self.base_url = "https://public.api.bsky.app"
        self.batch_size = 25  # API limit for profile batches
        self.followers_batch_size = 100  # API max for getFollowers
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
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get statistics about the profile cache."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM profiles")
            total_profiles = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM profiles WHERE followers_count > 1000")
            popular_profiles = cursor.fetchone()[0]
            
            cursor.execute("SELECT MAX(followers_count) FROM profiles")
            max_followers = cursor.fetchone()[0] or 0
            
            conn.close()
            
            return {
                'total_profiles': total_profiles,
                'popular_profiles': popular_profiles,
                'max_followers': max_followers
            }
            
        except Exception as e:
            console.print(f"[red]❌ Error getting cache stats: {str(e)}[/red]")
            return {'total_profiles': 0, 'popular_profiles': 0, 'max_followers': 0}
    
    async def get_followers(self, actor_did: str, limit: int = None) -> List[Dict]:
        """Retrieve followers for a given actor using paginated requests."""
        followers = []
        cursor = None
        
        headers = {
            'Authorization': f'Bearer {self.auth_manager.access_token}',
            'Content-Type': 'application/json'
        }
        
        async with aiohttp.ClientSession() as session:
            while limit is None or len(followers) < limit:
                url = f"{self.base_url}/xrpc/app.bsky.graph.getFollowers"
                params = {
                    'actor': actor_did,
                    'limit': self.followers_batch_size if limit is None else min(self.followers_batch_size, limit - len(followers))
                }
                
                if cursor:
                    params['cursor'] = cursor
                    
                try:
                    async with session.get(url, headers=headers, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            batch_followers = data.get('followers', [])
                            followers.extend(batch_followers)
                            
                            cursor = data.get('cursor')
                            if not cursor or not batch_followers:
                                break
                                
                            await asyncio.sleep(self.rate_limit_delay)
                            
                        else:
                            error_text = await response.text()
                            console.print(f"[red]❌ Error retrieving followers: {response.status} - {error_text}[/red]")
                            break
                            
                except Exception as e:
                    console.print(f"[red]❌ Error during followers retrieval: {str(e)}[/red]")
                    break
        
        return followers if limit is None else followers[:limit]
    
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
    
    async def rank_followers(self, target_username: str, max_followers: int = None) -> List[Dict]:
        """
        Rank followers by their follower count with comprehensive analysis.
        
        Args:
            target_username: Username to analyze followers for
            max_followers: Maximum number of followers to analyze (None for all)
            
        Returns:
            List[Dict]: Ranked list of follower profiles with analysis
        """
        console.print(f"[blue]🔍 Starting follower analysis for @{target_username}[/blue]")
        
        # Get target user's DID
        try:
            target_profile = await self.client.get_profile(target_username)
            target_did = target_profile.did
        except Exception as e:
            console.print(f"[red]❌ Error getting target profile: {str(e)}[/red]")
            return []
        
        # Get followers
        console.print(f"[blue]📥 Retrieving followers...[/blue]")
        followers = await self.get_followers(target_did, max_followers)
        
        if not followers:
            console.print("[yellow]⚠️ No followers found[/yellow]")
            return []
        
        # Extract DIDs for profile lookup
        follower_dids = [follower['did'] for follower in followers]
        
        # Get detailed profiles
        console.print(f"[blue]👥 Fetching detailed profiles for {len(follower_dids)} followers...[/blue]")
        profiles = await self.get_profiles_batch(follower_dids)
        
        # Create mapping for quick lookup
        profile_map = {profile['did']: profile for profile in profiles}
        
        # Rank followers by follower count
        ranked_followers = []
        for follower in followers:
            did = follower['did']
            if did in profile_map:
                profile = profile_map[did]
                ranked_followers.append({
                    'did': did,
                    'handle': profile.get('handle', ''),
                    'displayName': profile.get('displayName', ''),
                    'description': profile.get('description', ''),
                    'followersCount': profile.get('followersCount', 0),
                    'followsCount': profile.get('followsCount', 0),
                    'postsCount': profile.get('postsCount', 0),
                    'avatar': profile.get('avatar', ''),
                    'indexedAt': follower.get('indexedAt', ''),
                    'raw_data': profile.get('raw_data', '')
                })
        
        # Sort by follower count (descending)
        ranked_followers.sort(key=lambda x: x['followersCount'], reverse=True)
        
        console.print(f"[green]✅ Analysis complete! Ranked {len(ranked_followers)} followers[/green]")
        return ranked_followers
    
    def analyze_bot_indicators(self, followers: List[Dict], top_n: int = 20) -> List[Dict]:
        """
        Analyze followers for potential bot indicators.
        
        Args:
            followers: List of follower profiles
            top_n: Number of top followers to analyze
            
        Returns:
            List[Dict]: Followers with bot analysis scores
        """
        console.print(f"[blue]🤖 Analyzing bot indicators for top {top_n} followers...[/blue]")
        
        bot_analysis = []
        for follower in followers[:top_n]:
            followers_count = follower.get('followersCount', 0)
            follows_count = follower.get('followsCount', 0)
            
            # Calculate bot score (0-1, higher = more likely bot)
            if follows_count == 0:
                bot_score = 0.0  # Can't calculate ratio
            else:
                ratio = followers_count / follows_count
                # Bot score based on ratio (very low ratios indicate bots)
                if ratio < 0.1:
                    bot_score = 0.9
                elif ratio < 0.2:
                    bot_score = 0.7
                elif ratio < 0.5:
                    bot_score = 0.5
                elif ratio < 1.0:
                    bot_score = 0.3
                else:
                    bot_score = 0.1
            
            follower['bot_score'] = bot_score
            follower['bot_ratio'] = ratio if follows_count > 0 else None
            bot_analysis.append(follower)
        
        # Sort by bot score (descending)
        bot_analysis.sort(key=lambda x: x['bot_score'], reverse=True)
        
        return bot_analysis
    
    def analyze_quality_followers(self, followers: List[Dict], top_n: int = 20) -> List[Dict]:
        """
        Analyze followers for quality indicators (selective following behavior).
        
        Args:
            followers: List of follower profiles
            top_n: Number of top followers to analyze
            
        Returns:
            List[Dict]: Followers with quality analysis scores
        """
        console.print(f"[blue]⭐ Analyzing quality indicators for top {top_n} followers...[/blue]")
        
        quality_analysis = []
        for follower in followers[:top_n]:
            followers_count = follower.get('followersCount', 0)
            follows_count = follower.get('followsCount', 0)
            posts_count = follower.get('postsCount', 0)
            
            # Calculate quality score (0-1, higher = better quality)
            quality_score = 0.0
            
            # Factor 1: Follower/following ratio (selective following)
            if follows_count > 0:
                ratio = followers_count / follows_count
                if ratio > 2.0:
                    quality_score += 0.4
                elif ratio > 1.0:
                    quality_score += 0.3
                elif ratio > 0.5:
                    quality_score += 0.2
                else:
                    quality_score += 0.1
            
            # Factor 2: Post activity (active users)
            if posts_count > 100:
                quality_score += 0.3
            elif posts_count > 50:
                quality_score += 0.2
            elif posts_count > 10:
                quality_score += 0.1
            
            # Factor 3: Follower count (influence)
            if followers_count > 10000:
                quality_score += 0.3
            elif followers_count > 1000:
                quality_score += 0.2
            elif followers_count > 100:
                quality_score += 0.1
            
            follower['quality_score'] = quality_score
            follower['quality_ratio'] = ratio if follows_count > 0 else None
            quality_analysis.append(follower)
        
        # Sort by quality score (descending)
        quality_analysis.sort(key=lambda x: x['quality_score'], reverse=True)
        
        return quality_analysis
    
    def display_analysis_results(self, ranked_followers: List[Dict], bot_analysis: List[Dict] = None, quality_analysis: List[Dict] = None):
        """Display analysis results in a formatted table."""
        
        # Main ranking table
        table = Table(title="Follower Ranking Analysis", show_header=True, header_style="bold magenta")
        table.add_column("Rank", style="dim", width=6)
        table.add_column("Handle", style="cyan", width=20)
        table.add_column("Display Name", style="white", width=25)
        table.add_column("Followers", justify="right", style="green", width=10)
        table.add_column("Following", justify="right", style="blue", width=10)
        table.add_column("Posts", justify="right", style="yellow", width=8)
        table.add_column("Ratio", justify="right", style="magenta", width=8)
        
        for i, follower in enumerate(ranked_followers[:20], 1):
            follows_count = follower.get('followsCount', 0)
            ratio = follower.get('followersCount', 0) / follows_count if follows_count > 0 else 0
            
            table.add_row(
                str(i),
                follower.get('handle', ''),
                follower.get('displayName', '')[:24],
                str(follower.get('followersCount', 0)),
                str(follows_count),
                str(follower.get('postsCount', 0)),
                f"{ratio:.2f}"
            )
        
        console.print(table)
        
        # Bot analysis table
        if bot_analysis:
            bot_table = Table(title="Bot Analysis (Top 10)", show_header=True, header_style="bold red")
            bot_table.add_column("Handle", style="cyan", width=20)
            bot_table.add_column("Bot Score", justify="right", style="red", width=10)
            bot_table.add_column("Ratio", justify="right", style="magenta", width=8)
            bot_table.add_column("Followers", justify="right", style="green", width=10)
            
            for follower in bot_analysis[:10]:
                bot_table.add_row(
                    follower.get('handle', ''),
                    f"{follower.get('bot_score', 0):.2f}",
                    f"{follower.get('bot_ratio', 0):.2f}" if follower.get('bot_ratio') else "N/A",
                    str(follower.get('followersCount', 0))
                )
            
            console.print(bot_table)
        
        # Quality analysis table
        if quality_analysis:
            quality_table = Table(title="Quality Analysis (Top 10)", show_header=True, header_style="bold green")
            quality_table.add_column("Handle", style="cyan", width=20)
            quality_table.add_column("Quality Score", justify="right", style="green", width=12)
            quality_table.add_column("Ratio", justify="right", style="magenta", width=8)
            quality_table.add_column("Posts", justify="right", style="yellow", width=8)
            
            for follower in quality_analysis[:10]:
                quality_table.add_row(
                    follower.get('handle', ''),
                    f"{follower.get('quality_score', 0):.2f}",
                    f"{follower.get('quality_ratio', 0):.2f}" if follower.get('quality_ratio') else "N/A",
                    str(follower.get('postsCount', 0))
                )
            
            console.print(quality_table)
    
    async def run_complete_analysis(self, target_username: str, max_followers: int = None) -> Dict:
        """
        Run complete follower analysis including ranking, bot detection, and quality analysis.
        
        Args:
            target_username: Username to analyze
            max_followers: Maximum number of followers to analyze
            
        Returns:
            Dict: Complete analysis results
        """
        console.print(f"[bold blue]🚀 Starting complete follower analysis for @{target_username}[/bold blue]")
        
        # Get ranked followers
        ranked_followers = await self.rank_followers(target_username, max_followers)
        
        if not ranked_followers:
            return {'error': 'No followers found'}
        
        # Run bot analysis
        bot_analysis = self.analyze_bot_indicators(ranked_followers)
        
        # Run quality analysis
        quality_analysis = self.analyze_quality_followers(ranked_followers)
        
        # Display results
        self.display_analysis_results(ranked_followers, bot_analysis, quality_analysis)
        
        # Return complete results
        return {
            'target_username': target_username,
            'total_followers': len(ranked_followers),
            'ranked_followers': ranked_followers,
            'bot_analysis': bot_analysis,
            'quality_analysis': quality_analysis,
            'cache_stats': self.get_cache_stats()
        }