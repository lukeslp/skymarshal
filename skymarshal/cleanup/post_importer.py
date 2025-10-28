"""
Post Importer Module

This module provides post import and management capabilities for Bluesky accounts.
It integrates functionality from the standalone bluesky_post_import_cli.py tool.

Features:
- Import posts from Bluesky API
- Post deduplication and storage
- Batch processing for efficiency
- Progress tracking and error handling
"""

import asyncio
import json
import sqlite3
import time
from datetime import datetime
from typing import List, Dict, Optional, Set, Any, Tuple
import aiohttp

from ..models import console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn


class PostImporter:
    """
    Imports and manages Bluesky posts with deduplication and caching.
    
    This class provides post import capabilities including:
    - Importing posts from Bluesky API
    - Deduplication by post URI
    - Batch processing for efficiency
    - Progress tracking and error handling
    """
    
    def __init__(self, auth_manager, db_path: str = None):
        """
        Initialize the PostImporter.
        
        Args:
            auth_manager: Authenticated Bluesky client manager
            db_path: Optional custom database path
        """
        self.auth_manager = auth_manager
        self.client = auth_manager.client
        self.base_url = "https://bsky.social"
        
        # Use shared database if no custom path provided
        if db_path is None:
            from ..data_manager import DataManager
            data_manager = DataManager(auth_manager)
            self.db_path = data_manager.get_database_path()
        else:
            self.db_path = db_path
            
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database for storing imported posts."""
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
                    raw_data TEXT,
                    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
                
                # Create indexes for performance
                conn.execute("CREATE INDEX IF NOT EXISTS idx_posts_author ON posts(author_handle)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_at)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_posts_imported ON posts(imported_at)")
            
            conn.close()
            
        except Exception as e:
            console.print(f"[red]❌ Database initialization error: {str(e)}[/red]")
    
    def get_existing_uris(self, author_handle: str) -> Set[str]:
        """Get set of existing post URIs for an author."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT uri FROM posts WHERE author_handle = ?", (author_handle,))
            uris = {row[0] for row in cursor.fetchall()}
            
            conn.close()
            return uris
            
        except Exception as e:
            console.print(f"[red]❌ Error getting existing URIs: {str(e)}[/red]")
            return set()
    
    def store_posts(self, posts: List[Dict]) -> Tuple[int, int]:
        """
        Store posts in database with deduplication.
        
        Args:
            posts: List of post dictionaries to store
            
        Returns:
            Tuple[int, int]: (new_posts_count, existing_posts_count)
        """
        if not posts:
            return 0, 0
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            new_count = 0
            existing_count = 0
            
            for post in posts:
                uri = post.get('uri', '')
                if not uri:
                    continue
                
                # Check if post already exists
                cursor.execute("SELECT 1 FROM posts WHERE uri = ?", (uri,))
                if cursor.fetchone():
                    existing_count += 1
                    continue
                
                # Insert new post
                cursor.execute("""
                    INSERT INTO posts 
                    (uri, cid, author_handle, text, created_at, 
                     like_count, reply_count, repost_count, raw_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    uri,
                    post.get('cid', ''),
                    post.get('author_handle', ''),
                    post.get('text', ''),
                    post.get('created_at', ''),
                    post.get('like_count', 0),
                    post.get('reply_count', 0),
                    post.get('repost_count', 0),
                    json.dumps(post)
                ))
                
                new_count += 1
            
            conn.commit()
            conn.close()
            
            return new_count, existing_count
            
        except Exception as e:
            console.print(f"[red]❌ Error storing posts: {str(e)}[/red]")
            return 0, 0
    
    async def import_posts(self, author_handle: str, max_posts: int = 50, 
                          batch_size: int = 25) -> Dict[str, Any]:
        """
        Import posts for a given author with deduplication.
        
        Args:
            author_handle: Handle of the author to import posts for
            max_posts: Maximum number of posts to import
            batch_size: Batch size for API requests
            
        Returns:
            Dict: Import results and statistics
        """
        console.print(f"[blue]📥 Importing posts for @{author_handle}...[/blue]")
        
        # Get existing URIs to avoid duplicates
        existing_uris = self.get_existing_uris(author_handle)
        console.print(f"[blue]Found {len(existing_uris)} existing posts in database[/blue]")
        
        # Get author profile
        try:
            profile = await self.client.get_profile(author_handle)
            total_posts = profile.posts_count
            console.print(f"[blue]Author has {total_posts} total posts[/blue]")
        except Exception as e:
            console.print(f"[red]❌ Error getting author profile: {str(e)}[/red]")
            return {'error': 'Failed to get author profile'}
        
        # Import posts with pagination
        imported_posts = []
        cursor = None
        imported_count = 0
        skipped_count = 0
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Importing posts...", total=max_posts)
            
            while len(imported_posts) < max_posts:
                try:
                    # Calculate batch size for this request
                    remaining = max_posts - len(imported_posts)
                    current_batch_size = min(batch_size, remaining)
                    
                    # Make API request
                    response = await self.client.get_author_feed(
                        actor=author_handle,
                        limit=current_batch_size,
                        cursor=cursor
                    )
                    
                    if not response or not hasattr(response, 'feed'):
                        break
                    
                    batch_posts = response.feed
                    if not batch_posts:
                        break
                    
                    # Process posts
                    new_posts = []
                    for post in batch_posts:
                        if hasattr(post, 'post'):
                            post_data = post.post
                            uri = str(post_data.uri)
                            
                            # Skip if already exists
                            if uri in existing_uris:
                                skipped_count += 1
                                continue
                            
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
                                'uri': uri,
                                'cid': str(post_data.cid),
                                'author_handle': author_handle,
                                'text': post_data.record.text if hasattr(post_data.record, 'text') else '',
                                'created_at': post_data.record.created_at if hasattr(post_data.record, 'created_at') else '',
                                'like_count': like_count,
                                'reply_count': reply_count,
                                'repost_count': repost_count,
                                'raw_data': json.dumps(post_data.dict())
                            }
                            
                            new_posts.append(post_dict)
                            imported_posts.append(post_dict)
                    
                    # Store batch in database
                    if new_posts:
                        new_stored, existing_stored = self.store_posts(new_posts)
                        imported_count += new_stored
                        skipped_count += existing_stored
                    
                    # Update progress
                    progress.update(task, completed=len(imported_posts), 
                                  description=f"Imported {len(imported_posts)} posts...")
                    
                    # Check if we have enough posts
                    if len(imported_posts) >= max_posts:
                        break
                    
                    # Get next cursor
                    cursor = response.cursor
                    if not cursor:
                        break
                    
                    # Rate limiting
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    console.print(f"[red]❌ Error importing posts: {str(e)}[/red]")
                    break
        
        # Final results
        results = {
            'author_handle': author_handle,
            'total_posts_available': total_posts,
            'posts_imported': imported_count,
            'posts_skipped': skipped_count,
            'posts_processed': len(imported_posts),
            'import_timestamp': datetime.now().isoformat()
        }
        
        console.print(f"[green]✅ Import complete![/green]")
        console.print(f"Imported: {imported_count} new posts")
        console.print(f"Skipped: {skipped_count} existing posts")
        console.print(f"Total processed: {len(imported_posts)} posts")
        
        return results
    
    def get_import_stats(self, author_handle: str = None) -> Dict[str, Any]:
        """
        Get import statistics for posts.
        
        Args:
            author_handle: Optional specific author to get stats for
            
        Returns:
            Dict: Import statistics
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if author_handle:
                # Stats for specific author
                cursor.execute("SELECT COUNT(*) FROM posts WHERE author_handle = ?", (author_handle,))
                total_posts = cursor.fetchone()[0]
                
                cursor.execute("""
                    SELECT MIN(imported_at), MAX(imported_at) 
                    FROM posts WHERE author_handle = ?
                """, (author_handle,))
                result = cursor.fetchone()
                first_import = result[0] if result[0] else None
                last_import = result[1] if result[1] else None
                
                cursor.execute("""
                    SELECT SUM(like_count), SUM(reply_count), SUM(repost_count)
                    FROM posts WHERE author_handle = ?
                """, (author_handle,))
                result = cursor.fetchone()
                total_likes = result[0] or 0
                total_replies = result[1] or 0
                total_reposts = result[2] or 0
                
            else:
                # Global stats
                cursor.execute("SELECT COUNT(*) FROM posts")
                total_posts = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(DISTINCT author_handle) FROM posts")
                unique_authors = cursor.fetchone()[0]
                
                cursor.execute("SELECT MIN(imported_at), MAX(imported_at) FROM posts")
                result = cursor.fetchone()
                first_import = result[0] if result[0] else None
                last_import = result[1] if result[1] else None
                
                cursor.execute("SELECT SUM(like_count), SUM(reply_count), SUM(repost_count) FROM posts")
                result = cursor.fetchone()
                total_likes = result[0] or 0
                total_replies = result[1] or 0
                total_reposts = result[2] or 0
                
                unique_authors = unique_authors
            
            conn.close()
            
            return {
                'total_posts': total_posts,
                'unique_authors': unique_authors if not author_handle else 1,
                'first_import': first_import,
                'last_import': last_import,
                'total_likes': total_likes,
                'total_replies': total_replies,
                'total_reposts': total_reposts,
                'total_engagement': total_likes + total_replies + total_reposts
            }
            
        except Exception as e:
            console.print(f"[red]❌ Error getting import stats: {str(e)}[/red]")
            return {}
    
    def display_import_stats(self, stats: Dict[str, Any], author_handle: str = None):
        """Display import statistics in a formatted panel."""
        
        if not stats:
            console.print("[red]❌ No statistics available[/red]")
            return
        
        title = f"Import Statistics{' - ' + author_handle if author_handle else ''}"
        
        content = f"""
Total Posts: {stats.get('total_posts', 0):,}
Unique Authors: {stats.get('unique_authors', 0)}
First Import: {stats.get('first_import', 'N/A')}
Last Import: {stats.get('last_import', 'N/A')}

Engagement Totals:
- Likes: {stats.get('total_likes', 0):,}
- Replies: {stats.get('total_replies', 0):,}
- Reposts: {stats.get('total_reposts', 0):,}
- Total: {stats.get('total_engagement', 0):,}
        """
        
        console.print(Panel(content, title=title, border_style="blue"))
    
    async def run_complete_import(self, author_handle: str, max_posts: int = 50) -> Dict[str, Any]:
        """
        Run complete post import process.
        
        Args:
            author_handle: Handle of the author to import posts for
            max_posts: Maximum number of posts to import
            
        Returns:
            Dict: Complete import results
        """
        console.print(f"[bold blue]🚀 Starting complete post import for @{author_handle}[/bold blue]")
        
        # Import posts
        import_results = await self.import_posts(author_handle, max_posts)
        
        if 'error' in import_results:
            return import_results
        
        # Get updated statistics
        stats = self.get_import_stats(author_handle)
        
        # Display statistics
        self.display_import_stats(stats, author_handle)
        
        # Return complete results
        return {
            **import_results,
            'statistics': stats
        }