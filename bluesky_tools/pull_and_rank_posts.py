#!/usr/bin/env python3
"""
BlueSky Post Fetcher and Analyzer (pull_and_rank_posts.py)

Banner:
- Efficiently pulls all posts for a given BlueSky user in batches, using parallel/concurrent requests
- Stores posts and user profiles in a local SQLite database, deduplicating by post URI
- Uses robust handle/DID normalization (never appends .bsky.social to DIDs)
- Upserts full profile data for all authors encountered
- Extracts and stores all engagement metrics (likes, replies, reposts) from all API response formats
- Lists the user's top N most liked posts (by their own authorship)
- Uses accessible, screen-reader friendly CLI output (Rich)
- Progress/status updates throughout, with x/x counts
- Robust error handling and diagnostics
- I/O: CLI arguments, BlueSky API, local SQLite DB, Rich console output

Features:
- Parallelized, paginated fetching for posts (concurrency for speed)
- Deduplication by post URI
- Batch upserts for posts and profiles
- WAL mode, PRAGMAs, and indexes for DB performance
- Accessible CLI output and error messages
- Comprehensive diagnostics for data structure analysis

Usage:
    python pull_and_rank_posts.py --handle <bsky_handle> [--db <db_path>] [--max <N>] [--resume] [--parallel <N>]

Requirements:
- requests
- rich

"""

import argparse
import os
import sys
import sqlite3
import json
import traceback
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Set
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
session = requests.Session()

# Allow this module to be imported
# Keep constants at module level
BSKY_AUTH_ENDPOINT = "https://bsky.social/xrpc/com.atproto.server.createSession"
BSKY_FEED_ENDPOINT = "https://bsky.social/xrpc/app.bsky.feed.getAuthorFeed"
BSKY_PROFILE_ENDPOINT = "https://bsky.social/xrpc/app.bsky.actor.getProfile"

# Initialize console once at module level
console = Console()

# Thread safety
db_lock = threading.Lock()

# Core API functionality
def authenticate_bsky(identifier: str, password: str) -> Dict[str, Any]:
    """Authenticate with BlueSky API and return auth headers."""
    payload = {"identifier": identifier, "password": password}
    try:
        resp = session.post(BSKY_AUTH_ENDPOINT, json=payload)
        resp.raise_for_status()
        data = resp.json()
        token = data.get("accessJwt")
        if not token:
            raise RuntimeError("No access token returned from BlueSky API.")
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        return {"token": token, "headers": headers, "did": data.get("did"), "handle": data.get("handle")}
    except Exception as e:
        raise RuntimeError(f"BlueSky authentication failed: {e}")

def format_handle(handle: str) -> str:
    """Format a handle to ensure it's valid for BlueSky API."""
    if not handle:
        raise ValueError("Handle cannot be empty.")
    if handle.startswith('did:'):
        return handle
    if handle.startswith('@'):
        handle = handle[1:]
    if '.' not in handle:
        handle = f"{handle}.bsky.social"
    return handle

# Database functionality
def init_db(db_path: str) -> sqlite3.Connection:
    """Initialize the database with necessary tables and indexes for performance."""
    # Convert to absolute path if it's not already
    if not os.path.isabs(db_path):
        db_path = os.path.abspath(db_path)
    
    # Ensure the directory exists
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    
    try:
        # Increase timeout to handle concurrent access
        conn = sqlite3.connect(db_path, timeout=60)
        
        # Optimize SQLite performance
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=10000")
        conn.execute("PRAGMA temp_store=MEMORY")
        
        with conn:
            # Create posts table with URI as primary key - include both naming conventions
            conn.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                uri TEXT PRIMARY KEY,
                cid TEXT,
                author_handle TEXT,
                text TEXT,
                created_at TEXT,
                like_count INTEGER,
                likeCount INTEGER,
                reply_count INTEGER,
                replyCount INTEGER,
                repost_count INTEGER,
                repostCount INTEGER,
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
            # Deduplicate: keep only the first rowid per did
            conn.execute('''
            DELETE FROM profiles
            WHERE rowid NOT IN (
                SELECT MIN(rowid) FROM profiles GROUP BY did
            )
            ''')
            
            # Create cursor state table to store last cursor for each user
            conn.execute('''
            CREATE TABLE IF NOT EXISTS cursor_state (
                handle TEXT PRIMARY KEY,
                cursor TEXT,
                last_updated TEXT
            )''')
            
            # Create index on author_handle for faster filtering
            conn.execute('CREATE INDEX IF NOT EXISTS idx_posts_author_handle ON posts(author_handle)')
            
            # Check existing columns and add any that are missing
            cur = conn.execute("PRAGMA table_info(posts)")
            columns = [row[1] for row in cur.fetchall()]
            
            # Helper function to safely add a column if it doesn't exist
            def add_column_if_not_exists(column_name, column_type="INTEGER"):
                if column_name not in columns:
                    try:
                        console.print(f"[yellow]Adding {column_name} column to posts table...[/yellow]")
                        conn.execute(f"ALTER TABLE posts ADD COLUMN {column_name} {column_type}")
                        return True
                    except sqlite3.OperationalError as e:
                        console.print(f"[yellow]Could not add {column_name} column: {e}[/yellow]")
                        return False
                return True
            
            # Ensure all required columns exist
            add_column_if_not_exists("like_count")
            add_column_if_not_exists("likeCount")
            add_column_if_not_exists("reply_count")
            add_column_if_not_exists("replyCount")
            add_column_if_not_exists("repost_count")
            add_column_if_not_exists("repostCount")
            
            # Synchronize values between column pairs if both exist
            if "like_count" in columns and "likeCount" in columns:
                try:
                    # Update like_count from likeCount where like_count is NULL
                    conn.execute("UPDATE posts SET like_count = likeCount WHERE like_count IS NULL AND likeCount IS NOT NULL")
                    # Update likeCount from like_count where likeCount is NULL
                    conn.execute("UPDATE posts SET likeCount = like_count WHERE likeCount IS NULL AND like_count IS NOT NULL")
                except sqlite3.OperationalError as e:
                    console.print(f"[yellow]Could not synchronize like count columns: {e}[/yellow]")
            
            if "reply_count" in columns and "replyCount" in columns:
                try:
                    conn.execute("UPDATE posts SET reply_count = replyCount WHERE reply_count IS NULL AND replyCount IS NOT NULL")
                    conn.execute("UPDATE posts SET replyCount = reply_count WHERE replyCount IS NULL AND reply_count IS NOT NULL")
                except sqlite3.OperationalError as e:
                    console.print(f"[yellow]Could not synchronize reply count columns: {e}[/yellow]")
            
            if "repost_count" in columns and "repostCount" in columns:
                try:
                    conn.execute("UPDATE posts SET repost_count = repostCount WHERE repost_count IS NULL AND repostCount IS NOT NULL")
                    conn.execute("UPDATE posts SET repostCount = repost_count WHERE repostCount IS NULL AND repost_count IS NOT NULL")
                except sqlite3.OperationalError as e:
                    console.print(f"[yellow]Could not synchronize repost count columns: {e}[/yellow]")
        
        # Run VACUUM in a separate transaction
        conn.isolation_level = None
        conn.execute("VACUUM")
        conn.isolation_level = ''
        
        console.print(f"[green]Database initialized successfully at {db_path}[/green]")
        return conn
    except sqlite3.Error as e:
        console.print(f"[red]SQLite error initializing database: {e}[/red]")
        console.print(f"[yellow]Database path: {db_path}[/yellow]")
        console.print(f"[yellow]Checking if directory is writable: {os.access(db_dir, os.W_OK)}[/yellow]")
        raise RuntimeError(f"Database initialization failed: {e}")
    except Exception as e:
        console.print(f"[red]Unexpected error initializing database: {e}[/red]")
        console.print(f"[yellow]Database path: {db_path}[/yellow]")
        raise RuntimeError(f"Database initialization failed: {e}")

def clean_user_data(conn: sqlite3.Connection, handle: str) -> int:
    """Clean out all posts for a specific user and any invalid data (e.g., future dates)."""
    now = datetime.now().strftime("%Y-%m-%d")
    with conn:
        # Delete future-dated posts first
        deleted_future = conn.execute("DELETE FROM posts WHERE created_at > ? || 'T'", (now,)).rowcount
        
        # Delete all posts for this user to start fresh
        deleted_user = conn.execute("DELETE FROM posts WHERE author_handle = ?", (handle,)).rowcount
        
        # Also remove the cursor state
        conn.execute("DELETE FROM cursor_state WHERE handle = ?", (handle,))
    
    total_deleted = deleted_future + deleted_user
    if deleted_future > 0:
        console.print(f"[yellow]Cleaned {deleted_future} invalid future-dated posts from the database.[/yellow]")
    if deleted_user > 0:
        console.print(f"[yellow]Removed {deleted_user} previous posts by @{handle} to start fresh.[/yellow]")
    return total_deleted

def get_last_cursor(conn: sqlite3.Connection, handle: str) -> Optional[str]:
    """Get the last cursor position for the given user."""
    cur = conn.execute("SELECT cursor FROM cursor_state WHERE handle = ?", (handle,))
    result = cur.fetchone()
    return result[0] if result else None

def save_cursor(conn: sqlite3.Connection, handle: str, cursor: str) -> None:
    """Save the current cursor position for the given user."""
    now = datetime.now().isoformat()
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO cursor_state (handle, cursor, last_updated) VALUES (?, ?, ?)",
            (handle, cursor, now)
        )

def upsert_profile(conn: sqlite3.Connection, profile: dict) -> None:
    """Upsert a profile into the database."""
    if not profile:
        return
    did = profile.get('did')
    handle = profile.get('handle')
    display_name = profile.get('displayName') or profile.get('display_name')
    avatar = profile.get('avatar')
    description = profile.get('description')
    followers_count = profile.get('followersCount', 0)
    follows_count = profile.get('followsCount', 0)
    posts_count = profile.get('postsCount', 0)
    raw_data = str(profile)
    if not did:
        return
    with conn:
        conn.execute('''
            INSERT OR REPLACE INTO profiles (did, handle, display_name, avatar, description, followers_count, follows_count, posts_count, raw_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (did, handle, display_name, avatar, description, followers_count, follows_count, posts_count, raw_data))

def prepare_posts_for_insert(posts: List[dict], author_handle: str, existing_uris: Set[str]) -> Tuple[List[tuple], Set[str]]:
    """
    Prepare posts for insertion, filtering out existing ones.
    Returns a tuple of (posts_to_insert, new_uris).
    """
    now = datetime.now()
    posts_to_insert = []
    new_uris = set()
    skipped_reposts = 0
    skipped_replies = 0
    skipped_future = 0
    skipped_other_authors = 0
    skipped_existing = 0
    skipped_no_uri = 0
    
    # Debug the first post structure
    if posts and len(posts) > 0:
        console.print(f"[dim]Post structure sample: {list(posts[0].keys())}[/dim]")
    
    for post in posts:
        # Skip reposts and pins—only include original posts by the user
        if post.get("reason") is not None:
            skipped_reposts += 1
            continue
        
        # Get the actual post content, which could be in different locations based on API version
        post_view = None
        if "post" in post:
            post_view = post.get("post", {})
        else:
            # If post is directly the post object
            post_view = post
            
        if not post_view:
            console.print(f"[yellow]Warning: Could not find post content in: {post.keys()}[/yellow]")
            continue
            
        uri = post_view.get("uri")
        
        # Skip if no URI
        if not uri:
            skipped_no_uri += 1
            continue
            
        # Skip if already in DB
        if uri in existing_uris:
            skipped_existing += 1
            continue
            
        cid = post_view.get("cid")
        record = post_view.get("record", {})
        
        # Skip replies—only include standalone posts
        if record.get("reply") is not None:
            skipped_replies += 1
            continue
            
        text = record.get("text", "")
        created_at = record.get("createdAt", "")
        
        # Skip future-dated posts (test data)
        if created_at:
            try:
                post_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                if post_date > now:
                    skipped_future += 1
                    continue
            except:
                pass
                
        # Extract like/reply/repost counts - handle different API response formats
        like_count = 0
        reply_count = 0
        repost_count = 0
        
        # Check for direct likeCount field
        if "likeCount" in post_view:
            like_count = post_view.get("likeCount", 0)
            # Debug output for the first few posts to verify like count extraction
            if like_count > 0:
                console.print(f"[dim]Found post with {like_count} likes[/dim]")
        
        # Check for metrics field (another possible format)
        elif "metrics" in post_view:
            metrics = post_view.get("metrics", {})
            like_count = metrics.get("likes", 0) or metrics.get("likeCount", 0)
        
        # Get reply and repost counts
        reply_count = post_view.get("replyCount", 0)
        repost_count = post_view.get("repostCount", 0)
        
        # Ensure we have integer values
        like_count = int(like_count) if like_count is not None else 0
        reply_count = int(reply_count) if reply_count is not None else 0
        repost_count = int(repost_count) if repost_count is not None else 0
        
        # Store raw data as JSON string for better parsing later
        try:
            raw_data = json.dumps(post_view)
        except:
            raw_data = str(post_view)
        
        # Verify this post was actually created by the target user (not a repost, quote, etc.)
        post_author = post_view.get("author", {}).get("handle", "")
        # Normalize handles for comparison
        post_author = format_handle(post_author) if post_author else ""
        normalized_author_handle = format_handle(author_handle) if author_handle else ""
        
        # Only insert the post if it's truly by the target user
        if post_author == normalized_author_handle:
            posts_to_insert.append((uri, cid, author_handle, text, created_at, like_count, reply_count, repost_count, raw_data))
            new_uris.add(uri)
        else:
            skipped_other_authors += 1
    
    # Print skipped stats if any
    total_skipped = skipped_reposts + skipped_replies + skipped_future + skipped_other_authors + skipped_existing + skipped_no_uri
    if total_skipped > 0:
        console.print(f"[dim]Filter stats: processed {len(posts)} posts, inserting {len(posts_to_insert)}[/dim]")
        console.print(f"[dim]Skipped: {skipped_reposts} reposts, {skipped_replies} replies, {skipped_future} future-dated, " +
                      f"{skipped_other_authors} by other authors, {skipped_existing} existing, {skipped_no_uri} with no URI[/dim]")
        
    return posts_to_insert, new_uris

def batch_process_posts(conn: sqlite3.Connection, posts: List[dict], author_handle: str, existing_uris: Set[str]) -> Tuple[int, Set[str]]:
    """
    Process a batch of posts efficiently and thread-safely:
    1. Filter out posts already in DB
    2. Extract profiles for upsert
    3. Prepare post data for insertion
    4. Insert all new posts in one transaction
    
    Returns (num_inserted, updated_uris_set)
    """
    if not posts:
        return 0, existing_uris
    
    # Create a thread-local copy of existing_uris to avoid race conditions
    local_existing_uris = set(existing_uris)
    
    # Extract profiles for upsert
    profiles = []
    for post in posts:
        post_view = post.get("post", post)
        author = post_view.get("author", {})
        if author:
            profiles.append(author)
    
    # Prepare posts for insertion
    posts_to_insert, new_uris = prepare_posts_for_insert(posts, author_handle, local_existing_uris)
    
    # Use lock to ensure thread safety during database operations
    with db_lock:
        # Create a transaction for all changes
        with conn:
            # Upsert all profiles
            for profile in profiles:
                upsert_profile(conn, profile)
                
            # Insert all new posts - use a schema that handles both column naming conventions
            if posts_to_insert:
                try:
                    # Get the actual column names from the database
                    cur = conn.execute("PRAGMA table_info(posts)")
                    columns = [row[1] for row in cur.fetchall()]
                    console.print(f"[dim]Available columns: {columns}[/dim]")
                    
                    # Check if both column types exist
                    has_like_count = "like_count" in columns
                    has_likeCount = "likeCount" in columns
                    has_reply_count = "reply_count" in columns
                    has_replyCount = "replyCount" in columns
                    has_repost_count = "repost_count" in columns
                    has_repostCount = "repostCount" in columns
                    
                    # Create a dynamic insert statement based on available columns
                    column_names = ["uri", "cid", "author_handle", "text", "created_at"]
                    values_placeholders = ["?", "?", "?", "?", "?"]
                    
                    if has_like_count:
                        column_names.append("like_count")
                        values_placeholders.append("?")
                    if has_likeCount:
                        column_names.append("likeCount")
                        values_placeholders.append("?")
                    if has_reply_count:
                        column_names.append("reply_count")
                        values_placeholders.append("?")
                    if has_replyCount:
                        column_names.append("replyCount")
                        values_placeholders.append("?")
                    if has_repost_count:
                        column_names.append("repost_count")
                        values_placeholders.append("?")
                    if has_repostCount:
                        column_names.append("repostCount")
                        values_placeholders.append("?")
                    
                    column_names.append("raw_data")
                    values_placeholders.append("?")
                    
                    # Construct the SQL statement
                    sql = f'''
                        INSERT OR IGNORE INTO posts (
                            {', '.join(column_names)}
                        )
                        VALUES ({', '.join(values_placeholders)})
                    '''
                    
                    # Prepare the data tuples for insertion
                    insert_data = []
                    for uri, cid, author_handle, text, created_at, like_count, reply_count, repost_count, raw_data in posts_to_insert:
                        values = [uri, cid, author_handle, text, created_at]
                        if has_like_count:
                            values.append(like_count)
                        if has_likeCount:
                            values.append(like_count)  # Use the same value for both columns
                        if has_reply_count:
                            values.append(reply_count)
                        if has_replyCount:
                            values.append(reply_count)  # Use the same value for both columns
                        if has_repost_count:
                            values.append(repost_count)
                        if has_repostCount:
                            values.append(repost_count)  # Use the same value for both columns
                        values.append(raw_data)
                        insert_data.append(tuple(values))
                    
                    # Execute the insert
                    conn.executemany(sql, insert_data)
                    
                except sqlite3.OperationalError as e:
                    console.print(f"[yellow]Error with dynamic column format: {e}[/yellow]")
                    console.print("[yellow]Trying minimal schema for insert...[/yellow]")
                    
                    # Last resort - just insert the basic fields
                    conn.executemany('''
                        INSERT OR IGNORE INTO posts (uri, cid, author_handle, text, created_at, raw_data)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', [(uri, cid, author_handle, text, created_at, raw_data) 
                          for uri, cid, author_handle, text, created_at, _, _, _, raw_data in posts_to_insert])
    
    # Return the number of posts inserted and the new URIs
    # Note: We don't update the global existing_uris set here to avoid race conditions
    # Each thread will work with its own local copy
    return len(posts_to_insert), new_uris

def fetch_profile(headers: dict, handle: str) -> Optional[dict]:
    """Fetch a user's profile with error handling."""
    try:
        params = {"actor": handle}
        resp = session.get(BSKY_PROFILE_ENDPOINT, params=params, headers=headers)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        console.print(f"[yellow]Warning: Could not fetch profile for post count: {e}[/yellow]")
        return None

def get_existing_post_uris(conn: sqlite3.Connection, author_handle: str) -> set:
    """Return a set of all post URIs for the given author already in the DB.
    Uses a prepared statement for efficiency."""
    cur = conn.execute("SELECT uri FROM posts WHERE author_handle = ?", (author_handle,))
    return set(row[0] for row in cur.fetchall())

def pull_all_posts(conn: sqlite3.Connection, headers: dict, handle: str, max_posts: int = 0, resume: bool = False, max_workers: int = 5, force_fetch: bool = False, initial_cursor: str = None) -> Tuple[int, int]:
    """
    Pull all posts for a user, with optimized parallel processing:
    1. Use cursor-based pagination with resume support
    2. Process batches in parallel with ThreadPoolExecutor (fetch only)
    3. Efficient DB operations with transactions (main thread only)
    4. Memory-efficient processing with batch inserts
    5. Progress tracking with x/x counts
    
    Args:
        conn: Database connection
        headers: API request headers
        handle: User handle
        max_posts: Maximum posts to pull (0 for all)
        resume: Whether to resume from last cursor
        max_workers: Number of parallel workers
        force_fetch: Force fetch posts directly without using cursor-based pagination
        initial_cursor: Start fetching from this cursor (overrides resume)
        
    Returns:
        Tuple of (total_added, total_posts)
    """
    # Get existing post URIs and fetch profile
    existing_uris = get_existing_post_uris(conn, handle)
    profile = fetch_profile(headers, handle)
    total_posts = profile.get('postsCount', 0) if profile else 0
    
    # Check how many posts we already have for this user
    cur = conn.execute("SELECT COUNT(*) FROM posts WHERE author_handle = ?", (handle,))
    existing_count = cur.fetchone()[0]
    
    # If we already have all posts, we can avoid fetching
    if existing_count >= total_posts and not force_fetch:
        console.print(f"[green]Already have all {existing_count} posts for @{handle}. Skipping fetch.[/green]")
        return 0, total_posts
        
    # If we're not starting from beginning, fetch only newer posts
    if existing_count > 0 and not force_fetch:
        # Get the most recent post date we have
        cur = conn.execute("SELECT MAX(created_at) FROM posts WHERE author_handle = ?", (handle,))
        last_post_date = cur.fetchone()[0]
        console.print(f"[cyan]Have {existing_count} posts, fetching only posts newer than {last_post_date}[/cyan]")
        
        # Could use this date to filter API requests if the API supports it
        # Otherwise will still need to fetch and filter
    
    # Initialize counters and state
    total_added = 0
    total_seen = 0
    batch_size = 100
    
    # Determine which cursor to use
    if initial_cursor:
        # Use the provided initial cursor (highest priority)
        cursor = initial_cursor
        console.print(f"[cyan]Using provided initial cursor: {cursor}[/cyan]")
    elif resume and not force_fetch:
        # Use the last saved cursor for resuming
        cursor = get_last_cursor(conn, handle)
        if cursor:
            console.print(f"[cyan]Resuming from last saved cursor position for @{handle}...[/cyan]")
    else:
        # Start from the beginning
        cursor = None
    
    # First, try a direct fetch to verify the API is working
    console.print("[cyan]Testing API access with a direct fetch...[/cyan]")
    try:
        # Try a direct fetch first to see if we get any posts
        test_data = fetch_posts_batch(headers, handle, limit=10, cursor=None)
        test_feed = test_data.get("feed", [])
        console.print(f"[cyan]Direct API test: received {len(test_feed)} posts in test batch[/cyan]")
        
        if not test_feed:
            console.print("[yellow]WARNING: Direct API test returned no posts. This may indicate an API issue.[/yellow]")
            console.print(f"[yellow]API response: {test_data}[/yellow]")
            
            # Try a different approach - check if the handle format is correct
            normalized_handle = format_handle(handle)
            if normalized_handle != handle:
                console.print(f"[yellow]Trying with normalized handle: {normalized_handle}[/yellow]")
                test_data = fetch_posts_batch(headers, normalized_handle, limit=10, cursor=None)
                test_feed = test_data.get("feed", [])
                console.print(f"[cyan]Normalized handle test: received {len(test_feed)} posts[/cyan]")
                
                if test_feed:
                    handle = normalized_handle
                    console.print(f"[green]Using normalized handle {handle} for fetching[/green]")
    except Exception as e:
        console.print(f"[red]Error in direct API test: {e}[/red]")
    
    # If force_fetch is enabled, try to directly fetch all posts without using cursor-based pagination
    if force_fetch:
        console.print("[cyan]Force fetch enabled: directly fetching posts...[/cyan]")
        try:
            # Calculate how many batches we need to fetch all posts
            if max_posts > 0:
                total_to_fetch = min(max_posts, total_posts)
            else:
                total_to_fetch = total_posts
                
            batch_count = (total_to_fetch + batch_size - 1) // batch_size  # Ceiling division
            
            with Progress(
                SpinnerColumn(),
                TextColumn("Fetching: {task.completed}/{task.total} batches | Added: {task.fields[added]} posts"),
                BarColumn(),
                TaskProgressColumn(),
                console=console
            ) as progress:
                task = progress.add_task(
                    f"Fetching posts for @{handle}...", 
                    total=batch_count, 
                    added=0
                )
                
                for i in range(batch_count):
                    # Calculate how many posts to fetch in this batch
                    current_batch_size = min(batch_size, total_to_fetch - (i * batch_size))
                    if current_batch_size <= 0:
                        break
                        
                    # Fetch batch with cursor from previous batch
                    data = fetch_posts_batch(headers, handle, limit=current_batch_size, cursor=cursor)
                    feed = data.get("feed", [])
                    cursor = data.get("cursor")
                    
                    if not feed:
                        console.print(f"[yellow]No posts returned in batch {i+1}/{batch_count}. Stopping.[/yellow]")
                        break
                    
                    # Process this batch
                    added, _ = batch_process_posts(conn, feed, handle, existing_uris)
                    total_added += added
                    total_seen += len(feed)
                    
                    # Update progress
                    progress.update(task, completed=i+1, added=total_added)
                    
                    # Save cursor for next batch
                    if cursor:
                        save_cursor(conn, handle, cursor)
                    else:
                        console.print(f"[yellow]No next cursor returned in batch {i+1}/{batch_count}. Stopping.[/yellow]")
                        break
        except Exception as e:
            console.print(f"[red]Error during force fetch: {e}[/red]")
            
        # Summary output for force fetch
        if total_seen == 0:
            console.print(f"[yellow]No posts were pulled for @{handle}. Check if the user has posts or if there was an API issue.[/yellow]")
        else:
            skipped = total_seen - total_added
            console.print(f"[green]Processed {total_seen} posts, added {total_added} new posts (skipped {skipped} duplicates or filtered posts).[/green]")
        
        return total_added, total_posts
    
    # Progress bar setup for parallel processing
    progress_description = "Processed: {task.completed}/{task.total} | Added: {task.fields[added]}"
    with Progress(
        SpinnerColumn(),
        TextColumn(progress_description),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        task = progress.add_task(
            f"Pulling posts for @{handle}...",
            total=total_posts if total_posts else None,
            added=0
        )
        batch_cursors = [cursor]  # Start with initial cursor
        while batch_cursors and (max_posts <= 0 or total_seen < max_posts):
            next_batch_cursors = []
            batch_results = []
            # Fetch batches in parallel, but do not use conn in threads
            def fetch_batch_for_thread(batch_cursor):
                try:
                    data = fetch_posts_batch(headers, handle, limit=batch_size, cursor=batch_cursor)
                    feed = data.get("feed", [])
                    next_cursor = data.get("cursor")
                    return feed, next_cursor
                except Exception as e:
                    console.print(f"[red]Error fetching batch: {e}[/red]")
                    return [], None
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_cursor = {
                    executor.submit(fetch_batch_for_thread, c): c for c in batch_cursors if c is not None
                }
                if not future_to_cursor and not total_seen:
                    future_to_cursor[executor.submit(fetch_batch_for_thread, None)] = None
                for future in as_completed(future_to_cursor):
                    cursor = future_to_cursor[future]
                    try:
                        feed, next_cursor = future.result()
                        batch_results.append((feed, next_cursor))
                    except Exception as e:
                        console.print(f"[red]Error processing batch with cursor {cursor}: {e}[/red]")
            # Now, in the main thread, process and insert posts
            for feed, next_cursor in batch_results:
                if not feed:
                    continue
                added, _ = batch_process_posts(conn, feed, handle, existing_uris)
                total_added += added
                total_seen += len(feed)
                progress.update(task, completed=total_seen, added=total_added)
                if next_cursor:
                    next_batch_cursors.append(next_cursor)
                    save_cursor(conn, handle, next_cursor)
            if max_posts > 0 and total_seen >= max_posts:
                console.print(f"[cyan]Reached max_posts limit ({max_posts}). Stopping pull.[/cyan]")
                break
            batch_cursors = next_batch_cursors
            if not batch_cursors:
                console.print("[yellow]No next cursors returned. All posts fetched.[/yellow]")
                break
        progress.update(task, completed=total_seen, added=total_added)
    
    # Summary output
    if total_seen == 0:
        console.print(f"[yellow]No posts were pulled for @{handle}. Check if the user has posts or if there was an API issue.[/yellow]")
    else:
        skipped = total_seen - total_added
        console.print(f"[green]Processed {total_seen} posts, added {total_added} new posts (skipped {skipped} duplicates or filtered posts).[/green]")
    
    return total_added, total_posts

def fetch_posts_batch(headers: dict, handle: str, limit: int = 100, cursor: Optional[str] = None) -> dict:
    """Fetch a batch of posts from the API with detailed error handling."""
    params = {"actor": handle, "limit": limit}
    if cursor:
        params["cursor"] = cursor
    
    try:
        console.print(f"[dim]Fetching batch for {handle} (cursor: {cursor or 'initial'})...[/dim]")
        resp = session.get(BSKY_FEED_ENDPOINT, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        
        # Check if the response has the expected structure
        if "feed" not in data:
            console.print(f"[yellow]Warning: API response missing 'feed' key. Response: {data}[/yellow]")
            return {"feed": [], "cursor": None}
        
        feed = data.get("feed", [])
        console.print(f"[dim]Received {len(feed)} posts in batch[/dim]")
        
        # Debug output for the first post to verify structure
        if feed and len(feed) > 0:
            first_post = feed[0]
            post_keys = list(first_post.keys())
            console.print(f"[dim]First post keys: {post_keys}[/dim]")
            
            # Check if post has expected structure
            post_view = first_post.get("post", {})
            if post_view:
                post_view_keys = list(post_view.keys())
                console.print(f"[dim]First post.post keys: {post_view_keys}[/dim]")
        
        return data
    except requests.exceptions.HTTPError as e:
        console.print(f"[red]HTTP Error fetching posts: {e}[/red]")
        if hasattr(e.response, 'text'):
            console.print(f"[red]Response text: {e.response.text}[/red]")
        return {"feed": [], "cursor": None}
    except Exception as e:
        console.print(f"[red]Error fetching posts: {e}[/red]")
        return {"feed": [], "cursor": None}

def get_top_liked_posts(conn: sqlite3.Connection, author_handle: str, top_n: int = 10) -> List[dict]:
    """Get the top N most liked posts created by the user themselves (not reposts)."""
    # First, check what columns actually exist
    cur = conn.execute("PRAGMA table_info(posts)")
    columns = [row[1] for row in cur.fetchall()]
    console.print(f"[dim]Available columns in posts table: {', '.join(columns)}[/dim]")
    
    # Find a column that might contain like counts
    like_columns = [col for col in columns if 'like' in col.lower()]
    
    if not like_columns:
        console.print("[yellow]Warning: No like count columns found in the database. Returning posts sorted by date.[/yellow]")
        # If no like columns exist, just return recent posts
        try:
            cur = conn.execute('''
                SELECT text, NULL as like_count, created_at, uri FROM posts
                WHERE author_handle = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (author_handle, top_n))
            return [dict(row) for row in map(lambda x: dict(zip([c[0] for c in cur.description], x)), cur.fetchall())]
        except sqlite3.OperationalError as e:
            console.print(f"[red]Error retrieving posts by date: {e}[/red]")
            return []
    
    # Try each like column until one works
    for like_col in like_columns:
        try:
            console.print(f"[dim]Trying to sort by '{like_col}'[/dim]")
            cur = conn.execute(f'''
                SELECT text, {like_col} as like_count, created_at, uri FROM posts
                WHERE author_handle = ?
                ORDER BY {like_col} DESC, created_at DESC
                LIMIT ?
            ''', (author_handle, top_n))
            result = [dict(row) for row in map(lambda x: dict(zip([c[0] for c in cur.description], x)), cur.fetchall())]
            if result:
                return result
        except sqlite3.OperationalError as e:
            console.print(f"[yellow]Error using column '{like_col}': {e}[/yellow]")
            continue
    
    # If we get here, we couldn't find any posts with working like count columns
    console.print("[yellow]Could not retrieve posts by like count. Falling back to date sorting.[/yellow]")
    try:
        cur = conn.execute('''
            SELECT text, NULL as like_count, created_at, uri FROM posts
            WHERE author_handle = ?
            ORDER BY created_at DESC
            LIMIT ?
        ''', (author_handle, top_n))
        return [dict(row) for row in map(lambda x: dict(zip([c[0] for c in cur.description], x)), cur.fetchall())]
    except sqlite3.OperationalError as e:
        console.print(f"[red]Error retrieving posts by date: {e}[/red]")
        return []

def fetch_and_cache_connections(db, headers, handle, force_refresh=False):
    """Fetch and cache followers and following for network analytics."""
    console.print(Panel(f"Fetching network connections for {handle}", border_style="cyan"))
    
    # First check if we already have cached connections
    cached_followers = db.get_cached_followers(handle)
    cached_following = db.get_cached_following(handle)
    
    if len(cached_followers) > 0 and len(cached_following) > 0 and not force_refresh:
        console.print(f"[green]Using {len(cached_followers)} cached followers and {len(cached_following)} cached following.[/green]")
        return
    
    # Set auth headers on DB class for API access
    db.headers = headers
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TextColumn("[cyan]{task.fields[count]}/{task.fields[total]}"),
        console=console
    ) as progress:
        # Setup progress tracking
        follower_task = progress.add_task(f"[cyan]Fetching followers for @{handle}...", total=None, count=0)
        following_task = progress.add_task(f"[cyan]Fetching following for @{handle}...", total=None, count=0)
        
        def follower_progress_callback(count, total):
            progress.update(follower_task, count=count, total=total)
            
        def following_progress_callback(count, total):
            progress.update(following_task, count=count, total=total)
        
        # Fetch followers with parallel optimization
        db.get_all_followers(handle, progress_callback=follower_progress_callback)
        progress.update(follower_task, completed=True)
        
        # Fetch following with parallel optimization
        db.get_all_following(handle, progress_callback=following_progress_callback)
        progress.update(following_task, completed=True)
    
    # Summary
    followers = db.get_cached_followers(handle)
    following = db.get_cached_following(handle)
    console.print(f"[green]Fetched and cached {len(followers)} followers and {len(following)} following for @{handle}.[/green]")

def analyze_connections(db, handle):
    """Analyze follower/following connections for insights."""
    console.print(Panel(f"Network Analysis for {handle}", border_style="magenta"))
    
    # Check if we have network data
    followers = db.get_cached_followers(handle)
    following = db.get_cached_following(handle)
    
    if len(followers) == 0 or len(following) == 0:
        console.print("[yellow]No network data available. Run fetch_connections first.[/yellow]")
        return
    
    # Get ratio analysis
    ratio = db.analyze_follower_ratio(handle)
    
    # Create a rich table for the ratio
    ratio_table = Table(title=f"Follower Ratio for @{handle}")
    ratio_table.add_column("Followers", justify="center")
    ratio_table.add_column("Following", justify="center")
    ratio_table.add_column("Ratio", justify="center")
    ratio_table.add_column("Category", justify="center")
    
    ratio_table.add_row(
        f"[cyan]{ratio['follower_count']}[/cyan]",
        f"[cyan]{ratio['following_count']}[/cyan]",
        f"[bold magenta]{ratio['ratio_display']}[/bold magenta]",
        f"[green]{ratio['category']}[/green]"
    )
    
    console.print(ratio_table)
    console.print(f"[dim]{ratio['description']}[/dim]")
    
    # Get network analysis
    network = db.analyze_network(handle)
    
    # Find mutual follows
    console.print(f"\n[bold]Mutual Follows:[/bold] [cyan]{network['mutual_count']}[/cyan] accounts you follow who also follow you")
    
    # Display top accounts by ratio
    if network['top_accounts']:
        console.print("\n[bold]Top Accounts by Follower Ratio:[/bold]")
        top_accts_table = Table()
        top_accts_table.add_column("Handle")
        top_accts_table.add_column("Followers", justify="right")
        top_accts_table.add_column("Following", justify="right")
        top_accts_table.add_column("Ratio", justify="right")
        top_accts_table.add_column("Category")
        
        for acct in network['top_accounts']:
            top_accts_table.add_row(
                f"@{acct['handle']}",
                str(acct['follower_count']),
                str(acct['following_count']),
                f"[bold]{acct['ratio_display']}[/bold]",
                acct['category']
            )
        
        console.print(top_accts_table)

def run_cli():
    """Main CLI entry point with error handling."""
    try:
        # Create default database directory
        bluevibes_dir = os.path.join(os.path.expanduser("~"), ".bluevibes")
        os.makedirs(bluevibes_dir, exist_ok=True)
        default_db_path = os.path.join(bluevibes_dir, "bluevibes.db")
        
        parser = argparse.ArgumentParser(description="BlueSky Post Puller & Analyzer")
        parser.add_argument("--handle", help="BlueSky handle to analyze")
        parser.add_argument("--pwd", help="BlueSky password")
        parser.add_argument("--db", default=".bluevibes.db", help="Database file path")
        parser.add_argument("--max", type=int, default=0, help="Maximum posts to fetch (0 for all)")
        parser.add_argument("--limit", type=int, default=25, help="Number of top posts to display")
        parser.add_argument("--clean", action="store_true", help="Clean out previous posts for this user")
        parser.add_argument("--force", action="store_true", help="Force fetch all posts even if cached")
        parser.add_argument("--stats", action="store_true", help="Show database stats")
        parser.add_argument("--no-analyze", action="store_true", help="Skip post analysis")
        parser.add_argument("--connections", action="store_true", help="Fetch followers/following")
        parser.add_argument("--network", action="store_true", help="Analyze network connections")
        parser.add_argument("--batch-size", type=int, default=100, help="Batch size for API requests")

        args = parser.parse_args()
        
        # Show stats if requested and exit
        if args.stats:
            with BlueVibesDB(args.db) as db:
                stats = db.get_db_stats()
                console.print(Panel(f"Database file: {args.db}", border_style="cyan"))
                console.print(f"Posts: [cyan]{stats['post_count']}[/cyan]")
                console.print(f"Profiles: [cyan]{stats['profile_count']}[/cyan]")
                console.print(f"Followers: [cyan]{stats['follower_count']}[/cyan]")
                console.print(f"Following: [cyan]{stats['following_count']}[/cyan]")
                console.print(f"Database size: [cyan]{stats['db_size_mb']:.2f} MB[/cyan]")
                if stats['last_updated']:
                    console.print(f"Last updated: [cyan]{stats['last_updated'].strftime('%Y-%m-%d %H:%M:%S')}[/cyan]")
            sys.exit(0)

        # If no handle is provided, prompt for it
        if not args.handle:
            args.handle = Prompt.ask("Enter your BlueSky handle")
        
        # Initialize database
        db = BlueVibesDB(args.db)
        
        # Authenticate with BlueSky
        headers = authenticate_with_bluesky(args)
        
        # Clean out previous posts if requested
        if args.clean:
            db.clean_user_data(args.handle)
        
        # Fetch connections if requested
        if args.connections:
            fetch_and_cache_connections(db, headers, args.handle, force_refresh=args.force)
        
        # Analyze network if requested
        if args.network:
            analyze_connections(db, args.handle)
        
        # If connections only, exit here
        if args.connections and not args.network and not args.clean and args.max == 0:
            db.conn.close()
            sys.exit(0)

        # Create fetcher with authentication headers
        fetcher = BlueSkyFetcher(headers, db)
        
        # Pull all posts from BlueSky API
        total_added, total_posts = fetcher.pull_all_posts(
            args.handle, 
            max_posts=args.max,
            force_fetch=args.force
        )
        
        # Skip analysis if requested
        if args.no_analyze:
            db.conn.close()
            sys.exit(0)
        
        # Calculate top posts by likes
        top_posts = db.get_top_liked_posts(args.handle, top_n=args.limit)
        
        # Get all posts for analysis
        all_posts = db.get_all_posts(args.handle)
        
        console.print(f"\n[bold blue]Top {len(top_posts)} posts by likes:[/bold blue]")
        
        # Display top posts
        for i, post in enumerate(top_posts):
            display_post(post, i + 1)
        
        # Get all post texts for analysis
        texts = db.extract_post_texts(all_posts)
        
        if texts:
            # Calculate word frequency
            show_word_frequency(texts)
        
        # Close database connection
        db.conn.close()
    except ImportError as e:
        console.print(f"[red]ERROR: Missing required dependencies: {e}[/red]")
        console.print("[yellow]Please install required packages: pip install requests rich[/yellow]")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[red]ERROR: An unexpected error occurred: {e}[/red]")
        if os.environ.get("DEBUG"):
            console.print("[dim]" + traceback.format_exc() + "[/dim]")
        sys.exit(1)

def main():
    """Entry point of the script."""
    run_cli()

if __name__ == "__main__":
    main() 