"""
Post Analyzer Module

This module provides comprehensive post analysis capabilities for Bluesky accounts.
It integrates functionality from the standalone pull_and_rank_posts.py tool.

Features:
- Parallelized post fetching with pagination
- Post ranking by engagement metrics
- Deduplication by post URI
- Smart caching system for performance
- Comprehensive engagement analysis
"""

import asyncio
import json
import sqlite3
import time
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import requests

from ..models import console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn


class PostAnalyzer:
    """
    Analyzes Bluesky posts with ranking, engagement metrics, and content analysis.
    
    This class provides comprehensive post analysis capabilities including:
    - Fetching all posts for a user with pagination
    - Ranking posts by engagement metrics (likes, replies, reposts)
    - Deduplication and caching for performance
    - Parallel processing for speed
    """
    
    def __init__(self, auth_manager, db_path: str = None):
        """
        Initialize the PostAnalyzer.
        
        Args:
            auth_manager: Authenticated Bluesky client manager
            db_path: Optional custom database path
        """
        self.auth_manager = auth_manager
        self.client = auth_manager.client
        self.base_url = "https://bsky.social"
        self.feed_endpoint = f"{self.base_url}/xrpc/app.bsky.feed.getAuthorFeed"
        self.profile_endpoint = f"{self.base_url}/xrpc/app.bsky.actor.getProfile"
        
        # Use shared database if no custom path provided
        if db_path is None:
            from ..data_manager import DataManager
            data_manager = DataManager(auth_manager)
            self.db_path = data_manager.get_database_path()
        else:
            self.db_path = db_path
            
        self.init_database()
        self.db_lock = threading.Lock()
    
    def init_database(self):
        """Initialize SQLite database for caching post and profile data."""
        try:
            conn = sqlite3.connect(self.db_path)
            
            # Optimize SQLite performance
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=10000")
            conn.execute("PRAGMA temp_store=MEMORY")
            
            with conn:
                # Create posts table with URI as primary key
                conn.execute('''
                CREATE TABLE IF NOT EXISTS posts (
                    uri TEXT PRIMARY KEY,
                    cid TEXT,
                    author_handle TEXT,
                    text TEXT,
                    created_at TEXT,
                    like_count INTEGER,
                    reply_count INTEGER,
                    repost_count INTEGER,
                    raw_data TEXT
                )''')
                
                # Create profiles table with DID as primary key
                conn.execute('''
                CREATE TABLE IF NOT EXISTS profiles (
                    did TEXT PRIMARY KEY,
                    handle TEXT,
                    display_name TEXT,
                    avatar TEXT,
                    description TEXT,
                    followers_count INTEGER,
                    follows_count INTEGER,
                    posts_count INTEGER,
                    raw_data TEXT
                )''')
                
                # Create indexes for performance
                conn.execute("CREATE INDEX IF NOT EXISTS idx_posts_author ON posts(author_handle)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_at)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_posts_likes ON posts(like_count DESC)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_profiles_handle ON profiles(handle)")
            
            conn.close()
            
        except Exception as e:
            console.print(f"[red]❌ Database initialization error: {str(e)}[/red]")
    
    def get_cached_posts(self, author_handle: str) -> List[Dict]:
        """Retrieve cached posts for an author."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT uri, cid, author_handle, text, created_at, 
                       like_count, reply_count, repost_count, raw_data
                FROM posts 
                WHERE author_handle = ?
                ORDER BY created_at DESC
            """, (author_handle,))
            
            posts = []
            for row in cursor.fetchall():
                uri, cid, author_handle, text, created_at, like_count, reply_count, repost_count, raw_data = row
                posts.append({
                    'uri': uri,
                    'cid': cid,
                    'author_handle': author_handle,
                    'text': text,
                    'created_at': created_at,
                    'like_count': like_count,
                    'reply_count': reply_count,
                    'repost_count': repost_count,
                    'raw_data': raw_data
                })
            
            conn.close()
            return posts
            
        except Exception as e:
            console.print(f"[red]❌ Error retrieving cached posts: {str(e)}[/red]")
            return []
    
    def cache_posts(self, posts: List[Dict]):
        """Store posts in database cache."""
        if not posts:
            return
            
        try:
            with self.db_lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                for post in posts:
                    cursor.execute("""
                        INSERT OR REPLACE INTO posts 
                        (uri, cid, author_handle, text, created_at, 
                         like_count, reply_count, repost_count, raw_data)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        post.get('uri', ''),
                        post.get('cid', ''),
                        post.get('author_handle', ''),
                        post.get('text', ''),
                        post.get('created_at', ''),
                        post.get('like_count', 0),
                        post.get('reply_count', 0),
                        post.get('repost_count', 0),
                        json.dumps(post)
                    ))
                
                conn.commit()
                conn.close()
                
        except Exception as e:
            console.print(f"[red]❌ Error caching posts: {str(e)}[/red]")
    
    def cache_profile(self, profile: Dict):
        """Store profile in database cache."""
        try:
            with self.db_lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO profiles 
                    (did, handle, display_name, avatar, description, 
                     followers_count, follows_count, posts_count, raw_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    profile.get('did', ''),
                    profile.get('handle', ''),
                    profile.get('displayName', ''),
                    profile.get('avatar', ''),
                    profile.get('description', ''),
                    profile.get('followersCount', 0),
                    profile.get('followsCount', 0),
                    profile.get('postsCount', 0),
                    json.dumps(profile)
                ))
                
                conn.commit()
                conn.close()
                
        except Exception as e:
            console.print(f"[red]❌ Error caching profile: {str(e)}[/red]")
    
    async def fetch_posts(self, author_handle: str, max_posts: int = None, resume: bool = False) -> List[Dict]:
        """
        Fetch all posts for a given author with pagination and caching.
        
        Args:
            author_handle: Handle of the author to fetch posts for
            max_posts: Maximum number of posts to fetch (None for all)
            resume: Whether to resume from cached posts
            
        Returns:
            List[Dict]: List of post data dictionaries
        """
        console.print(f"[blue]📥 Fetching posts for @{author_handle}...[/blue]")
        
        # Check cache first if resuming
        if resume:
            cached_posts = self.get_cached_posts(author_handle)
            if cached_posts:
                console.print(f"[green]✅ Found {len(cached_posts)} cached posts[/green]")
                if max_posts and len(cached_posts) >= max_posts:
                    return cached_posts[:max_posts]
        
        # Get author profile first
        try:
            profile = await self.client.get_profile(author_handle)
            self.cache_profile({
                'did': profile.did,
                'handle': profile.handle,
                'displayName': profile.display_name,
                'avatar': str(profile.avatar) if profile.avatar else '',
                'description': profile.description or '',
                'followersCount': profile.followers_count,
                'followsCount': profile.follows_count,
                'postsCount': profile.posts_count
            })
        except Exception as e:
            console.print(f"[red]❌ Error getting author profile: {str(e)}[/red]")
            return []
        
        # Fetch posts with pagination
        posts = []
        cursor = None
        batch_size = 100  # API limit per request
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Fetching posts...", total=None)
            
            while True:
                try:
                    # Prepare request parameters
                    params = {
                        'actor': author_handle,
                        'limit': batch_size
                    }
                    if cursor:
                        params['cursor'] = cursor
                    
                    # Make API request
                    response = await self.client.get_author_feed(
                        actor=author_handle,
                        limit=batch_size,
                        cursor=cursor
                    )
                    
                    if not response or not hasattr(response, 'feed'):
                        break
                    
                    batch_posts = response.feed
                    if not batch_posts:
                        break
                    
                    # Process posts
                    for post in batch_posts:
                        if hasattr(post, 'post'):
                            post_data = post.post
                            
                            # Extract engagement metrics
                            like_count = 0
                            reply_count = 0
                            repost_count = 0
                            
                            if hasattr(post_data, 'like_count'):
                                like_count = post_data.like_count
                            if hasattr(post_data, 'reply_count'):
                                reply_count = post_data.reply_count
                            if hasattr(post_data, 'repost_count'):
                                repost_count = post_data.repost_count
                            
                            # Create post dictionary
                            post_dict = {
                                'uri': str(post_data.uri),
                                'cid': str(post_data.cid),
                                'author_handle': author_handle,
                                'text': post_data.record.text if hasattr(post_data.record, 'text') else '',
                                'created_at': post_data.record.created_at if hasattr(post_data.record, 'created_at') else '',
                                'like_count': like_count,
                                'reply_count': reply_count,
                                'repost_count': repost_count,
                                'raw_data': json.dumps(post_data.dict())
                            }
                            
                            posts.append(post_dict)
                    
                    # Update progress
                    progress.update(task, description=f"Fetched {len(posts)} posts...")
                    
                    # Check if we have enough posts
                    if max_posts and len(posts) >= max_posts:
                        posts = posts[:max_posts]
                        break
                    
                    # Get next cursor
                    cursor = response.cursor
                    if not cursor:
                        break
                    
                    # Rate limiting
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    console.print(f"[red]❌ Error fetching posts: {str(e)}[/red]")
                    break
        
        # Cache the posts
        if posts:
            self.cache_posts(posts)
            console.print(f"[green]✅ Fetched and cached {len(posts)} posts[/green]")
        
        return posts
    
    def rank_posts_by_engagement(self, posts: List[Dict], metric: str = 'total') -> List[Dict]:
        """
        Rank posts by engagement metrics.
        
        Args:
            posts: List of post dictionaries
            metric: Engagement metric to use ('likes', 'replies', 'reposts', 'total')
            
        Returns:
            List[Dict]: Posts ranked by engagement
        """
        console.print(f"[blue]📊 Ranking posts by {metric} engagement...[/blue]")
        
        for post in posts:
            like_count = post.get('like_count', 0)
            reply_count = post.get('reply_count', 0)
            repost_count = post.get('repost_count', 0)
            
            # Calculate total engagement
            total_engagement = like_count + reply_count + repost_count
            
            # Calculate weighted engagement (likes = 1, replies = 2, reposts = 2.5)
            weighted_engagement = like_count + (reply_count * 2) + (repost_count * 2.5)
            
            post['total_engagement'] = total_engagement
            post['weighted_engagement'] = weighted_engagement
        
        # Sort by selected metric
        if metric == 'likes':
            posts.sort(key=lambda x: x.get('like_count', 0), reverse=True)
        elif metric == 'replies':
            posts.sort(key=lambda x: x.get('reply_count', 0), reverse=True)
        elif metric == 'reposts':
            posts.sort(key=lambda x: x.get('repost_count', 0), reverse=True)
        elif metric == 'total':
            posts.sort(key=lambda x: x.get('total_engagement', 0), reverse=True)
        elif metric == 'weighted':
            posts.sort(key=lambda x: x.get('weighted_engagement', 0), reverse=True)
        
        return posts
    
    def analyze_engagement_patterns(self, posts: List[Dict]) -> Dict:
        """
        Analyze engagement patterns across posts.
        
        Args:
            posts: List of post dictionaries
            
        Returns:
            Dict: Engagement analysis results
        """
        if not posts:
            return {}
        
        console.print(f"[blue]📈 Analyzing engagement patterns for {len(posts)} posts...[/blue]")
        
        # Calculate statistics
        total_likes = sum(post.get('like_count', 0) for post in posts)
        total_replies = sum(post.get('reply_count', 0) for post in posts)
        total_reposts = sum(post.get('repost_count', 0) for post in posts)
        total_engagement = total_likes + total_replies + total_reposts
        
        # Find top posts
        top_liked = max(posts, key=lambda x: x.get('like_count', 0))
        top_replied = max(posts, key=lambda x: x.get('reply_count', 0))
        top_reposted = max(posts, key=lambda x: x.get('repost_count', 0))
        top_engagement = max(posts, key=lambda x: x.get('total_engagement', 0))
        
        # Calculate averages
        avg_likes = total_likes / len(posts) if posts else 0
        avg_replies = total_replies / len(posts) if posts else 0
        avg_reposts = total_reposts / len(posts) if posts else 0
        avg_engagement = total_engagement / len(posts) if posts else 0
        
        return {
            'total_posts': len(posts),
            'total_likes': total_likes,
            'total_replies': total_replies,
            'total_reposts': total_reposts,
            'total_engagement': total_engagement,
            'avg_likes': avg_likes,
            'avg_replies': avg_replies,
            'avg_reposts': avg_reposts,
            'avg_engagement': avg_engagement,
            'top_liked': top_liked,
            'top_replied': top_replied,
            'top_reposted': top_reposted,
            'top_engagement': top_engagement
        }
    
    def display_ranking_results(self, ranked_posts: List[Dict], top_n: int = 20):
        """Display post ranking results in a formatted table."""
        
        table = Table(title=f"Top {top_n} Posts by Engagement", show_header=True, header_style="bold magenta")
        table.add_column("Rank", style="dim", width=6)
        table.add_column("Text", style="white", width=50)
        table.add_column("Likes", justify="right", style="green", width=8)
        table.add_column("Replies", justify="right", style="blue", width=8)
        table.add_column("Reposts", justify="right", style="yellow", width=8)
        table.add_column("Total", justify="right", style="magenta", width=8)
        table.add_column("Date", style="dim", width=12)
        
        for i, post in enumerate(ranked_posts[:top_n], 1):
            text = post.get('text', '')[:47] + '...' if len(post.get('text', '')) > 50 else post.get('text', '')
            created_at = post.get('created_at', '')[:10] if post.get('created_at') else ''
            
            table.add_row(
                str(i),
                text,
                str(post.get('like_count', 0)),
                str(post.get('reply_count', 0)),
                str(post.get('repost_count', 0)),
                str(post.get('total_engagement', 0)),
                created_at
            )
        
        console.print(table)
    
    def display_analysis_results(self, analysis: Dict):
        """Display engagement analysis results."""
        
        # Summary panel
        summary_text = f"""
Total Posts: {analysis.get('total_posts', 0)}
Total Likes: {analysis.get('total_likes', 0):,}
Total Replies: {analysis.get('total_replies', 0):,}
Total Reposts: {analysis.get('total_reposts', 0):,}
Total Engagement: {analysis.get('total_engagement', 0):,}

Average Likes: {analysis.get('avg_likes', 0):.1f}
Average Replies: {analysis.get('avg_replies', 0):.1f}
Average Reposts: {analysis.get('avg_reposts', 0):.1f}
Average Engagement: {analysis.get('avg_engagement', 0):.1f}
        """
        
        console.print(Panel(summary_text, title="Engagement Analysis Summary", border_style="green"))
        
        # Top posts table
        if analysis.get('top_liked') or analysis.get('top_engagement'):
            top_table = Table(title="Top Performing Posts", show_header=True, header_style="bold cyan")
            top_table.add_column("Metric", style="cyan", width=15)
            top_table.add_column("Text", style="white", width=40)
            top_table.add_column("Likes", justify="right", style="green", width=8)
            top_table.add_column("Replies", justify="right", style="blue", width=8)
            top_table.add_column("Reposts", justify="right", style="yellow", width=8)
            
            if analysis.get('top_liked'):
                post = analysis['top_liked']
                text = post.get('text', '')[:37] + '...' if len(post.get('text', '')) > 40 else post.get('text', '')
                top_table.add_row(
                    "Most Liked",
                    text,
                    str(post.get('like_count', 0)),
                    str(post.get('reply_count', 0)),
                    str(post.get('repost_count', 0))
                )
            
            if analysis.get('top_engagement'):
                post = analysis['top_engagement']
                text = post.get('text', '')[:37] + '...' if len(post.get('text', '')) > 40 else post.get('text', '')
                top_table.add_row(
                    "Most Engaged",
                    text,
                    str(post.get('like_count', 0)),
                    str(post.get('reply_count', 0)),
                    str(post.get('repost_count', 0))
                )
            
            console.print(top_table)
    
    async def run_complete_analysis(self, author_handle: str, max_posts: int = None, 
                                  resume: bool = False, metric: str = 'total') -> Dict:
        """
        Run complete post analysis including fetching, ranking, and engagement analysis.
        
        Args:
            author_handle: Handle of the author to analyze
            max_posts: Maximum number of posts to analyze
            resume: Whether to resume from cached posts
            metric: Engagement metric to use for ranking
            
        Returns:
            Dict: Complete analysis results
        """
        console.print(f"[bold blue]🚀 Starting complete post analysis for @{author_handle}[/bold blue]")
        
        # Fetch posts
        posts = await self.fetch_posts(author_handle, max_posts, resume)
        
        if not posts:
            return {'error': 'No posts found'}
        
        # Rank posts by engagement
        ranked_posts = self.rank_posts_by_engagement(posts, metric)
        
        # Analyze engagement patterns
        analysis = self.analyze_engagement_patterns(ranked_posts)
        
        # Display results
        self.display_ranking_results(ranked_posts)
        self.display_analysis_results(analysis)
        
        # Return complete results
        return {
            'author_handle': author_handle,
            'total_posts': len(posts),
            'ranked_posts': ranked_posts,
            'analysis': analysis,
            'metric_used': metric
        }