#!/usr/bin/env python3
"""
XAI BlueSky Tool

A comprehensive CLI tool for interacting with the BlueSky API:
- Fetch and display user profiles
- Get a user's posts and perform "vibe checks"
- View follower and following lists
- Search for posts and users
- Analyze engagement metrics

Required:
- The 'requests' package (install via pip if needed)
- The 'openai' package for XAI API access
- Valid internet connectivity
- BlueSky account credentials for authentication
"""

#  ____  _            ____  _              _____           _ 
# | __ )| |_   _  ___/ ___|| | ___   _    |_   _|__   ___ | |
# |  _ \| | | | |/ _ \___ \| |/ / | | |     | |/ _ \ / _ \| |
# | |_) | | |_| |  __/___) |   <| |_| |     | | (_) | (_) | |
# |____/|_|\__,_|\___|____/|_|\_\\__, |     |_|\___/ \___/|_|
#                               |___/                        
#
# Available Tools:
# ┌────────────────┬────────────────────────────────────────────────┐
# │ User Profiles  │ View profile information and stats             │
# │ User Posts     │ Fetch recent posts from any user               │
# │ Vibe Check     │ AI analysis of user's tone and content         │
# │ Followers      │ View and analyze follower lists                │
# │ Following      │ View and analyze following lists               │
# │ Search         │ Search posts and users on BlueSky              │
# │ Analytics      │ Behavior analysis and engagement metrics       │
# └────────────────┴────────────────────────────────────────────────┘

import requests
import getpass
import re
import base64
import os
import json
import argparse
import textwrap
import sys
import time
import csv
import concurrent.futures
import shutil
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from openai import OpenAI
from rich.console import Console
from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn, SpinnerColumn, TimeRemainingColumn
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.style import Style
from rich.markdown import Markdown

# Initialize rich console
console = Console()

# Hard-coded XAI API key (DO NOT expose in production code)
API_KEY = "xai-8zAk5VIaL3Vxpu3fO3r2aiWqqeVAZ173X04VK2R1m425uYpWOIOQJM3puq1Q38xJ2sHfbq3mX4PBxJXC"

# Hard-coded BlueSky credentials
# BSKY_IDENTIFIER = "accesscounts.bsky.social"
# BSKY_PASSWORD = "B!vH%TscF9W8ZAn@4sRh"
BSKY_IDENTIFIER = "lukesteuber.com"
BSKY_PASSWORD = "G@nym3de"

# BlueSky API endpoints
BSKY_AUTH_ENDPOINT = "https://bsky.social/xrpc/com.atproto.server.createSession"
BSKY_FEED_ENDPOINT = "https://bsky.social/xrpc/app.bsky.feed.getAuthorFeed"
BSKY_PROFILE_ENDPOINT = "https://bsky.social/xrpc/app.bsky.actor.getProfile"
BSKY_PROFILES_ENDPOINT = "https://bsky.social/xrpc/app.bsky.actor.getProfiles"
BSKY_FOLLOWERS_ENDPOINT = "https://bsky.social/xrpc/app.bsky.graph.getFollowers"
BSKY_FOLLOWS_ENDPOINT = "https://bsky.social/xrpc/app.bsky.graph.getFollows"
BSKY_POST_THREAD_ENDPOINT = "https://bsky.social/xrpc/app.bsky.feed.getPostThread"
BSKY_SEARCH_POSTS_ENDPOINT = "https://bsky.social/xrpc/app.bsky.feed.searchPosts"
BSKY_SEARCH_ACTORS_ENDPOINT = "https://bsky.social/xrpc/app.bsky.actor.searchActors"
BSKY_LIKES_ENDPOINT = "https://bsky.social/xrpc/app.bsky.feed.getLikes"

# Initialize OpenAI client for XAI
client = OpenAI(
    api_key=API_KEY,
    base_url="https://api.x.ai/v1",
)

# For generating alt text
ALT_PROMPT = "Describe this image in detail for accessibility purposes."

# Cache directories
CACHE_DIR = os.path.expanduser("~/.xai/bsky_cache")
PROFILES_CACHE_DIR = os.path.join(CACHE_DIR, "profiles")
POSTS_CACHE_DIR = os.path.join(CACHE_DIR, "posts")
FOLLOWERS_CACHE_DIR = os.path.join(CACHE_DIR, "followers")
FOLLOWING_CACHE_DIR = os.path.join(CACHE_DIR, "following")


class BlueSkyAPI:
    def __init__(self):
        self.xai_api_key = API_KEY
        self.xai_client = client
        self.bsky_auth_token = None
        self.bsky_headers = None
        self.bsky_did = None
        self.current_user_handle = None
        
        # Ensure cache directories exist
        os.makedirs(CACHE_DIR, exist_ok=True)
        os.makedirs(PROFILES_CACHE_DIR, exist_ok=True)
        os.makedirs(POSTS_CACHE_DIR, exist_ok=True)
        os.makedirs(FOLLOWERS_CACHE_DIR, exist_ok=True)
        os.makedirs(FOLLOWING_CACHE_DIR, exist_ok=True)
    
    def authenticate_bsky(self, identifier: str = BSKY_IDENTIFIER, password: str = BSKY_PASSWORD) -> bool:
        """
        Authenticates with the BlueSky API using the provided credentials.
        Sets the auth token for subsequent API calls.
        
        By default, uses the hard-coded credentials.
        """
        auth_payload = {
            "identifier": identifier,
            "password": password
        }
        
        try:
            response = requests.post(BSKY_AUTH_ENDPOINT, json=auth_payload)
            response.raise_for_status()
            auth_data = response.json()
            self.bsky_auth_token = auth_data.get("accessJwt")
            if not self.bsky_auth_token:
                raise ValueError("Authentication succeeded but no access token was returned")
            
            # Also save did for future API calls if needed
            self.bsky_did = auth_data.get("did")
            self.current_user_handle = auth_data.get("handle")
            
            self.bsky_headers = {
                "Authorization": f"Bearer {self.bsky_auth_token}",
                "Content-Type": "application/json"
            }
            return True
        except Exception as e:
            raise RuntimeError(f"BlueSky authentication failed: {e}")
    
    def format_handle(self, handle: str) -> str:
        """
        Formats a handle for use with the BlueSky API.
        """
        # Remove @ prefix if present
        if handle.startswith("@"):
            handle = handle[1:]
            
        # Add .bsky.social suffix if not present and no other domain is specified
        if "." not in handle:
            handle = f"{handle}.bsky.social"
            
        return handle
    
    def get_profile(self, handle: str, use_cache: bool = True, cache_max_age_hours: int = 336) -> dict:
        """
        Fetches the profile information for a given handle using the getProfile endpoint.
        
        Args:
            handle: The BlueSky handle
            use_cache: Whether to use cached profile data if available
            cache_max_age_hours: Maximum age of cache in hours (default: 336 hours / 14 days)
            
        Returns:
            Profile information as a dict
        """
        if not self.bsky_headers:
            raise RuntimeError("Not authenticated with BlueSky. Call authenticate_bsky() first.")
        
        # Check cache first if requested
        if use_cache:
            cached_profile = self.get_cached_profile(handle, cache_max_age_hours)
            if cached_profile:
                console.print(f"[cyan]Using cached profile for @{handle}[/cyan]")
                return cached_profile
            
        # Format the handle properly for the API
        handle = self.format_handle(handle)
        
        params = {
            "actor": handle
        }
        
        try:
            response = requests.get(BSKY_PROFILE_ENDPOINT, params=params, headers=self.bsky_headers)
            response.raise_for_status()
            profile_data = response.json()
            
            # Cache the profile data
            self.cache_profile(handle, profile_data)
            
            return profile_data
        except Exception as e:
            raise RuntimeError(f"Error fetching BlueSky profile: {e}")
    
    def get_detailed_profiles(self, users: List[dict], use_cache: bool = True, cache_max_age_hours: int = 336) -> List[dict]:
        """
        Fetch detailed profile information for a list of users using individual getProfile calls.
        
        Args:
            users: List of user objects with at least a 'did' or 'handle' field
            use_cache: Whether to use cached profile data when available
            cache_max_age_hours: Maximum age of cache in hours (default: 336 hours / 14 days)
            
        Returns:
            List of detailed profile objects
        """
        if not self.bsky_headers:
            raise RuntimeError("Not authenticated with BlueSky. Call authenticate_bsky() first.")
            
        detailed_profiles = []
        total_users = len(users)
        
        console.print(f"[cyan]Fetching detailed profiles for {total_users} users...[/cyan]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Fetching detailed profiles...", total=total_users)
            
            for i, user in enumerate(users):
                # Get the user identifier (handle or DID)
                actor = None
                if user.get('handle'):
                    actor = user.get('handle')
                elif user.get('did'):
                    actor = user.get('did')
                
                if not actor:
                    progress.update(task, advance=1)
                    console.print(f"[yellow]Warning: No handle or DID found for user: {user}[/yellow]")
                    continue
                
                try:
                    # Fetch profile using getProfile endpoint
                    profile = self.get_profile(actor, use_cache=use_cache, cache_max_age_hours=cache_max_age_hours)
                    detailed_profiles.append(profile)
                    
                    # Update progress
                    progress.update(task, advance=1, description=f"Fetched {i+1}/{total_users} profiles")
                    
                    # Small delay to avoid rate limiting
                    time.sleep(0.5)
                except Exception as e:
                    console.print(f"[yellow]Warning: Error fetching profile for {actor}: {e}[/yellow]")
                    progress.update(task, advance=1)
                    continue
        
        console.print(f"[green]Successfully fetched {len(detailed_profiles)} out of {total_users} profiles[/green]")
        return detailed_profiles
    
    def get_bsky_posts(self, handle: str, limit: int = 100, cursor: str = None) -> dict:
        """
        Fetches posts for the given BlueSky handle with pagination support.
        
        Args:
            handle: The BlueSky handle to fetch posts for
            limit: Number of posts to fetch (maximum per request is 100)
            cursor: Optional cursor for pagination
            
        Returns:
            The API response as a dict
        """
        if not self.bsky_headers:
            raise RuntimeError("Not authenticated with BlueSky. Call authenticate_bsky() first.")
            
        # Format the handle properly for the API
        handle = self.format_handle(handle)
        
        # Ensure limit doesn't exceed API maximum
        page_limit = min(limit, 100)
        
        params = {
            "actor": handle,
            "limit": page_limit
        }
        
        if cursor:
            params["cursor"] = cursor
            
        try:
            response = requests.get(BSKY_FEED_ENDPOINT, params=params, headers=self.bsky_headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise RuntimeError(f"Error fetching BlueSky posts: {e}")
    
    def get_all_posts(self, handle: str, max_posts: int = 100, 
                      start_date: datetime = None, end_date: datetime = None,
                      show_progress: bool = True) -> List[dict]:
        """
        Fetches multiple pages of posts for a user, handling pagination and date filtering.
        
        Args:
            handle: The BlueSky handle to fetch posts for
            max_posts: Maximum number of posts to fetch (0 for all)
            start_date: Optional start date for filtering posts
            end_date: Optional end date for filtering posts
            show_progress: Whether to show a progress bar
            
        Returns:
            List of posts
        """
        if not self.bsky_headers:
            raise RuntimeError("Not authenticated with BlueSky. Call authenticate_bsky() first.")
        handle = self.format_handle(handle)
        if start_date and start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        if end_date and end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)
        all_posts = []
        cursor = None
        progress = None
        task_id = None
        if show_progress:
            progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console
            )
            progress.start()
            task_id = progress.add_task(f"Fetching posts for @{handle}...", total=None)
        try:
            while True:
                # If max_posts is 0, fetch all available posts (up to API limits)
                if max_posts > 0:
                    page_size = min(100, max_posts - len(all_posts))
                    if page_size <= 0:
                        break
                else:
                    page_size = 100
                posts_data = self.get_bsky_posts(handle, limit=page_size, cursor=cursor)
                posts = posts_data.get("feed", [])
                if not posts:
                    break
                for item in posts:
                    post = item.get("post", {})
                    record = post.get("record", {})
                    post_date = None
                    if "createdAt" in record:
                        try:
                            post_date = datetime.fromisoformat(record["createdAt"].replace("Z", "+00:00"))
                        except:
                            pass
                    if post_date:
                        if start_date and post_date < start_date:
                            continue
                        if end_date and post_date > end_date:
                            continue
                    all_posts.append(item)
                    if max_posts > 0 and len(all_posts) >= max_posts:
                        break
                if max_posts > 0 and len(all_posts) >= max_posts:
                    all_posts = all_posts[:max_posts]
                    break
                cursor = posts_data.get("cursor")
                if not cursor:
                    break
                time.sleep(0.2)
        finally:
            if progress:
                progress.stop()
        self.cache_posts(handle, all_posts)
        return all_posts
    
    def cache_posts(self, handle: str, posts: List[dict]) -> None:
        """
        Cache posts for a user.
        
        Args:
            handle: The BlueSky handle
            posts: List of posts to cache
        """
        # Normalize handle for filename
        handle = self.format_handle(handle).replace('.', '_')
        
        # Use the current authenticated user's directory if available
        if self.current_user_handle:
            user_cache_dir = os.path.join(POSTS_CACHE_DIR, self.current_user_handle.replace('.', '_'))
            os.makedirs(user_cache_dir, exist_ok=True)
            cache_file = os.path.join(user_cache_dir, f"{handle}_posts.json")
        else:
            cache_file = os.path.join(POSTS_CACHE_DIR, f"{handle}_posts.json")
        
        # Load existing cache if it exists
        existing_posts = []
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    existing_posts = json.load(f)
            except Exception as e:
                console.print(f"[yellow]Warning: Could not load existing cache: {e}[/yellow]")
        
        # Create a set of post URIs to avoid duplicates
        existing_uris = set()
        for post in existing_posts:
            post_view = post.get("post", {})
            uri = post_view.get("uri", "")
            if uri:
                existing_uris.add(uri)
        
        # Add new posts that aren't already in the cache
        new_posts_added = 0
        for post in posts:
            post_view = post.get("post", {})
            uri = post_view.get("uri", "")
            if uri and uri not in existing_uris:
                existing_posts.append(post)
                existing_uris.add(uri)
                new_posts_added += 1
        
        # Save the updated cache
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(existing_posts, f)
            console.print(f"[green]Added {new_posts_added} new posts to cache for @{handle}[/green]")
        except Exception as e:
            console.print(f"[red]Error saving cache: {e}[/red]")
    
    def get_cached_posts(self, handle: str) -> List[dict]:
        """
        Get cached posts for a user.
        
        Args:
            handle: The BlueSky handle
            
        Returns:
            List of cached posts or empty list if no cache exists
        """
        # Normalize handle for filename
        handle = self.format_handle(handle).replace('.', '_')
        
        # Check in current user's directory first if available
        if self.current_user_handle:
            user_cache_dir = os.path.join(POSTS_CACHE_DIR, self.current_user_handle.replace('.', '_'))
            cache_file = os.path.join(user_cache_dir, f"{handle}_posts.json")
            
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception as e:
                    console.print(f"[yellow]Warning: Could not load user-specific cache: {e}[/yellow]")
        
        # Fall back to general cache
        cache_file = os.path.join(POSTS_CACHE_DIR, f"{handle}_posts.json")
            
        if not os.path.exists(cache_file):
            return []
            
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not load cache: {e}[/yellow]")
            return []
    
    def clear_cache(self, handle: str = None) -> bool:
        """
        Clear cached data for a specific user or all users.
        
        Args:
            handle: The BlueSky handle to clear cache for, or None to clear all cache
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if handle:
                # Clear cache for a specific user
                handle = self.format_handle(handle).replace('.', '_')
                
                # Clear posts cache
                post_cache_file = os.path.join(POSTS_CACHE_DIR, f"{handle}_posts.json")
                if os.path.exists(post_cache_file):
                    os.remove(post_cache_file)
                
                # Clear user-specific posts cache if current user is set
                if self.current_user_handle:
                    user_posts_dir = os.path.join(POSTS_CACHE_DIR, self.current_user_handle.replace('.', '_'))
                    user_post_cache_file = os.path.join(user_posts_dir, f"{handle}_posts.json")
                    if os.path.exists(user_post_cache_file):
                        os.remove(user_post_cache_file)
                
                # Clear profile cache
                profile_cache_file = os.path.join(PROFILES_CACHE_DIR, f"{handle}_profile.json")
                if os.path.exists(profile_cache_file):
                    os.remove(profile_cache_file)
                
                # Clear followers cache
                followers_cache_file = os.path.join(FOLLOWERS_CACHE_DIR, f"{handle}_followers.json")
                if os.path.exists(followers_cache_file):
                    os.remove(followers_cache_file)
                
                # Clear user-specific followers cache if current user is set
                if self.current_user_handle:
                    user_followers_dir = os.path.join(FOLLOWERS_CACHE_DIR, self.current_user_handle.replace('.', '_'))
                    user_followers_cache_file = os.path.join(user_followers_dir, f"{handle}_followers.json")
                    if os.path.exists(user_followers_cache_file):
                        os.remove(user_followers_cache_file)
                
                # Clear following cache
                following_cache_file = os.path.join(FOLLOWING_CACHE_DIR, f"{handle}_following.json")
                if os.path.exists(following_cache_file):
                    os.remove(following_cache_file)
                
                # Clear user-specific following cache if current user is set
                if self.current_user_handle:
                    user_following_dir = os.path.join(FOLLOWING_CACHE_DIR, self.current_user_handle.replace('.', '_'))
                    user_following_cache_file = os.path.join(user_following_dir, f"{handle}_following.json")
                    if os.path.exists(user_following_cache_file):
                        os.remove(user_following_cache_file)
                
                console.print(f"[green]Cleared cache for @{handle}[/green]")
            else:
                # Clear all cache
                for cache_dir in [POSTS_CACHE_DIR, PROFILES_CACHE_DIR, FOLLOWERS_CACHE_DIR, FOLLOWING_CACHE_DIR]:
                    if os.path.exists(cache_dir):
                        shutil.rmtree(cache_dir)
                        os.makedirs(cache_dir, exist_ok=True)
                
                console.print("[green]Cleared all cache[/green]")
            return True
        except Exception as e:
            console.print(f"[red]Error clearing cache: {e}[/red]")
            return False
    
    def sort_posts(self, posts: List[dict], sort_by: str = "date", reverse: bool = True) -> List[dict]:
        """
        Sort posts by the specified criteria.
        
        Args:
            posts: List of posts to sort
            sort_by: Criteria to sort by (date, likes, replies)
            reverse: Whether to sort in descending order
            
        Returns:
            Sorted list of posts
        """
        def get_sort_key(post):
            post_view = post.get("post", {})
            record = post_view.get("record", {})
            
            if sort_by == "date":
                # Sort by date
                if "createdAt" in record:
                    try:
                        return datetime.fromisoformat(record["createdAt"].replace("Z", "+00:00"))
                    except:
                        return datetime.min
                return datetime.min
            
            elif sort_by == "likes":
                # Sort by like count
                return post_view.get("likeCount", 0)
                
            elif sort_by == "replies":
                # Sort by reply count
                return post_view.get("replyCount", 0)
                
            else:
                # Default to date
                if "createdAt" in record:
                    try:
                        return datetime.fromisoformat(record["createdAt"].replace("Z", "+00:00"))
                    except:
                        return datetime.min
                return datetime.min
        
        return sorted(posts, key=get_sort_key, reverse=reverse)
    
    def get_post_content(self, posts_data: dict) -> str:
        """
        Extracts post text from the full API response.
        Returns a concatenated string of all post texts.
        """
        # Extract posts from feed
        posts = posts_data.get("feed", []) if "feed" in posts_data else posts_data
        combined_text = ""
        
        for item in posts:
            # Extract text from the post record
            post_view = item.get("post", {})
            record = post_view.get("record", {})
            text = record.get("text", "")
            if text:
                combined_text += text + "\n"
                
        if not combined_text.strip():
            raise ValueError("No post texts were found in the response.")
        return combined_text.strip()

    def export_to_markdown(self, handle: str, data: dict, data_type: str, output_file: str = None) -> str:
        """
        Export data to markdown format.
        
        Args:
            handle: The BlueSky handle
            data: The data to export (posts, profile, etc.)
            data_type: Type of data being exported (posts, profile, followers, following)
            output_file: Optional output file path
            
        Returns:
            Markdown formatted text
        """
        formatted_handle = self.format_handle(handle)
        markdown_text = f"# BlueSky Data for @{formatted_handle}\n\n"
        
        if data_type == "posts":
            # Export posts
            markdown_text += "## Posts\n\n"
            sorted_posts = self.sort_posts(data, sort_by="date", reverse=True)
            
            for post in sorted_posts:
                post_view = post.get("post", {})
                record = post_view.get("record", {})
                text = record.get("text", "")
                
                # Get post date
                post_date = "Unknown date"
                if "createdAt" in record:
                    try:
                        dt = datetime.fromisoformat(record["createdAt"].replace("Z", "+00:00"))
                        post_date = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                    except:
                        pass
                
                # Get like and reply counts
                like_count = post_view.get("likeCount", 0)
                reply_count = post_view.get("replyCount", 0)
                
                markdown_text += f"### {post_date}\n\n"
                markdown_text += f"{text}\n\n"
                markdown_text += f"*Likes: {like_count} | Replies: {reply_count}*\n\n"
                markdown_text += "---\n\n"
                
        elif data_type == "profile":
            # Export profile data
            markdown_text += "## Profile Information\n\n"
            
            # Basic profile info
            display_name = data.get("displayName", "Unknown")
            description = data.get("description", "")
            
            markdown_text += f"**Display Name:** {display_name}\n\n"
            if description:
                markdown_text += f"**Description:** {description}\n\n"
                
            # Stats
            posts_count = data.get("postsCount", 0)
            followers_count = data.get("followersCount", 0)
            follows_count = data.get("followsCount", 0)
            
            markdown_text += "### Stats\n\n"
            markdown_text += f"- **Posts:** {posts_count:,}\n"
            markdown_text += f"- **Followers:** {followers_count:,}\n"
            markdown_text += f"- **Following:** {follows_count:,}\n\n"
            
        elif data_type == "followers" or data_type == "following":
            # Export followers or following
            title = "Followers" if data_type == "followers" else "Following"
            markdown_text += f"## {title}\n\n"
            
            for user in data:
                display_name = user.get("displayName", "Unknown")
                user_handle = user.get("handle", "unknown")
                description = user.get("description", "")
                
                markdown_text += f"### @{user_handle} ({display_name})\n\n"
                if description:
                    markdown_text += f"{description}\n\n"
                
                followers_count = user.get("followersCount", 0)
                follows_count = user.get("followingCount", 0)
                
                markdown_text += f"*Followers: {followers_count:,} | Following: {follows_count:,}*\n\n"
                markdown_text += "---\n\n"
        
        # Save to file if output_file is provided
        if output_file:
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(markdown_text)
                console.print(f"[green]Successfully exported data to {output_file}[/green]")
            except Exception as e:
                console.print(f"[red]Error exporting data: {e}[/red]")
        
        return markdown_text
    
    def get_followers(self, handle: str, limit: int = 50) -> dict:
        """
        Fetches the followers of a BlueSky handle.
        """
        if not self.bsky_headers:
            raise RuntimeError("Not authenticated with BlueSky. Call authenticate_bsky() first.")
            
        # Format the handle properly for the API
        handle = self.format_handle(handle)
        
        params = {
            "actor": handle,
            "limit": limit
        }
        
        try:
            response = requests.get(BSKY_FOLLOWERS_ENDPOINT, params=params, headers=self.bsky_headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise RuntimeError(f"Error fetching BlueSky followers: {e}")
    
    def get_follows(self, handle: str, limit: int = 50) -> dict:
        """
        Fetches the accounts a BlueSky handle is following.
        """
        if not self.bsky_headers:
            raise RuntimeError("Not authenticated with BlueSky. Call authenticate_bsky() first.")
            
        # Format the handle properly for the API
        handle = self.format_handle(handle)
        
        params = {
            "actor": handle,
            "limit": limit
        }
        
        try:
            response = requests.get(BSKY_FOLLOWS_ENDPOINT, params=params, headers=self.bsky_headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise RuntimeError(f"Error fetching BlueSky follows: {e}")
    
    def get_post_thread(self, uri: str) -> dict:
        """
        Fetches a post thread by its URI.
        """
        if not self.bsky_headers:
            raise RuntimeError("Not authenticated with BlueSky. Call authenticate_bsky() first.")
            
        params = {
            "uri": uri
        }
        
        try:
            response = requests.get(BSKY_POST_THREAD_ENDPOINT, params=params, headers=self.bsky_headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise RuntimeError(f"Error fetching BlueSky post thread: {e}")
            
    def search_posts(self, query: str, limit: int = 20) -> dict:
        """
        Searches for posts containing the query term.
        """
        if not self.bsky_headers:
            raise RuntimeError("Not authenticated with BlueSky. Call authenticate_bsky() first.")
            
        params = {
            "q": query,
            "limit": limit
        }
        
        try:
            response = requests.get(BSKY_SEARCH_POSTS_ENDPOINT, params=params, headers=self.bsky_headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise RuntimeError(f"Error searching BlueSky posts: {e}")
    
    def search_users(self, query: str, limit: int = 20) -> dict:
        """
        Searches for users matching the query term.
        """
        if not self.bsky_headers:
            raise RuntimeError("Not authenticated with BlueSky. Call authenticate_bsky() first.")
            
        params = {
            "q": query,
            "limit": limit
        }
        
        try:
            response = requests.get(BSKY_SEARCH_ACTORS_ENDPOINT, params=params, headers=self.bsky_headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise RuntimeError(f"Error searching BlueSky users: {e}")
    
    def get_post_likes(self, uri: str, limit: int = 50) -> dict:
        """
        Gets likes for a specific post.
        """
        if not self.bsky_headers:
            raise RuntimeError("Not authenticated with BlueSky. Call authenticate_bsky() first.")
            
        params = {
            "uri": uri,
            "limit": limit
        }
        
        try:
            response = requests.get(BSKY_LIKES_ENDPOINT, params=params, headers=self.bsky_headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise RuntimeError(f"Error fetching likes for post: {e}")
    
    def vibe_check(self, text: str) -> str:
        """
        Analyzes the posts to provide a "vibe check" of the user using the XAI API.
        """
        try:
            completion = self.xai_client.chat.completions.create(
                model="grok-3",
                messages=[
                    {"role": "system", "content": "You are an insightful social media analyst who performs comprehensive 'vibe checks' on BlueSky users. Your analysis should thoroughly examine the user's recent moods, interests, and overall tone in their posts. Provide detailed observations about their communication style, recurring themes, and whether they generally present as friendly and positive or negative and confrontational. Include specific examples from their posts to support your assessment."},
                    {"role": "user", "content": f"Find context or source on this image. Then please perform a detailed vibe check on the following BlueSky posts. Analyze the user's recent moods, interests, and overall commentary. Provide a comprehensive assessment of their communication style and whether they come across as friendly/positive or negative/confrontational. Support your analysis with specific examples:\n\n{text}"}
                ],
                temperature=0.3,
            )
            
            analysis = completion.choices[0].message.content.strip()
            return analysis
        except Exception as e:
            raise RuntimeError(f"Error performing vibe check: {e}")
    
    def summarize_text(self, text: str) -> str:
        """
        Summarizes the provided text using the XAI API via OpenAI client.
        """
        try:
            prompt = f"Please summarize the following BlueSky posts concisely, capturing key themes and topics:\n\n{text}"
            
            completion = self.xai_client.chat.completions.create(
                model="grok-3",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that summarizes text."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
            )
            
            summary = completion.choices[0].message.content.strip()
            return summary
        except Exception as e:
            raise RuntimeError(f"Error summarizing text: {e}")
    
    def generate_alt_text(self, image_path):
        """
        Call the OpenAI API with the image (as a base64-encoded string) and the alt text prompt.
        Returns the generated alt text (string) if successful; otherwise, returns None.
        """
        try:
            with open(image_path, "rb") as img_file:
                img_data = img_file.read()
            encoded = base64.b64encode(img_data).decode("utf-8")
            ext = os.path.splitext(image_path)[1].lower()
            if ext in [".jpg", ".jpeg"]:
                mime = "jpeg"
            elif ext == ".png":
                mime = "png"
            elif ext == ".gif":
                mime = "gif"
            elif ext == ".bmp":
                mime = "bmp"
            elif ext == ".tiff":
                mime = "tiff"
            else:
                mime = "jpeg"
            image_str = f"data:image/{mime};base64,{encoded}"
        except Exception as e:
            print("Error encoding image for alt text generation:", e)
            return None

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_str,
                            "detail": "high"
                        }
                    },
                    {
                        "type": "text",
                        "text": ALT_PROMPT
                    }
                ]
            }
        ]
        try:
            completion = self.xai_client.chat.completions.create(
                model="grok-3",
                messages=messages,
                temperature=0.01,
            )
            generated_text = completion.choices[0].message.content.strip()
            return generated_text
        except Exception as e:
            print(f"Error generating alt text for {image_path}: {e}")
            return None
    
    def get_all_followers(self, handle: str, max_results: int = 1000, concurrency: int = 3, 
                         batch_size: int = 100, use_cache: bool = True, 
                         max_cache_age_hours: int = 336, fetch_detailed: bool = True) -> List[dict]:
        """
        Fetches all followers of a BlueSky handle, handling pagination and respecting max_results exactly.
        Avoids re-fetching already cached users and continues efficiently from the last fetch.
        """
        if not self.bsky_headers:
            raise RuntimeError("Not authenticated with BlueSky. Call authenticate_bsky() first.")
            
        # Ensure handle is correctly formatted
        handle = self.format_handle(handle)
        
        # Check if max_results is 0 (meaning get all available)
        all_available = (max_results == 0)
        
        # Load cached followers if available and valid
        cached_followers = []
        if use_cache:
            cached_followers = self.get_cached_followers(handle, max_cache_age_hours) or []
            
        # If we have enough cached followers and max_results > 0, return them
        if not all_available and cached_followers and len(cached_followers) >= max_results:
            console.print(f"[green]Using {max_results} cached followers for @{handle}[/green]")
            return cached_followers[:max_results]
            
        # Start with existing cached followers
        all_followers = cached_followers.copy() if cached_followers else []
        seen_dids = set(f.get('did') for f in all_followers if f.get('did'))
        
        # Determine how many more followers we need to fetch
        remaining = max_results - len(all_followers) if not all_available else float('inf')
        if remaining <= 0:
            return all_followers[:max_results]
            
        cursor = None
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task_total = max_results if not all_available else None
            task = progress.add_task(
                f"Fetching followers for @{handle}...", 
                total=task_total, 
                completed=len(all_followers) if not all_available else 0
            )
            
            try:
                # Continue fetching until we have enough or we've fetched all available
                while (all_available or remaining > 0):
                    # Limit parameter should be the smaller of batch_size or remaining
                    limit = min(batch_size, remaining) if not all_available else batch_size
                    
                    params = {"actor": handle, "limit": limit}
                    if cursor:
                        params["cursor"] = cursor
                        
                    response = requests.get(BSKY_FOLLOWERS_ENDPOINT, params=params, headers=self.bsky_headers)
                    response.raise_for_status()
                    page_data = response.json()
                    page_followers = page_data.get("followers", [])
                    
                    # If no more followers are returned, we're done
                    if not page_followers:
                        break
                        
                    # Only add followers we haven't seen before
                    new_followers = [f for f in page_followers if f.get('did') not in seen_dids]
                    
                    # Add new followers to our collection
                    all_followers.extend(new_followers)
                    
                    # Update seen DIDs
                    for f in new_followers:
                        if f.get('did'):
                            seen_dids.add(f.get('did'))
                            
                    # Update progress
                    description = f"Fetched {len(all_followers)}/{max_results if not all_available else '?'} followers..."
                    progress.update(task, 
                                   advance=len(new_followers) if not all_available else 0, 
                                   description=description)
                    
                    # Update remaining count
                    remaining = max_results - len(all_followers) if not all_available else float('inf')
                    
                    # Get cursor for next page
                    cursor = page_data.get("cursor")
                    
                    # If no more pages or we have enough, exit loop
                    if not cursor or remaining <= 0:
                        break
                        
                    # Respect rate limits
                    time.sleep(0.5)
                    
            except KeyboardInterrupt:
                console.print("[yellow]\nFollower fetching interrupted. Returning what we have so far.[/yellow]")
            except Exception as e:
                console.print(f"[yellow]Error fetching followers: {e}[/yellow]")
                
        # Cache what we found
        if all_followers:
            self.cache_followers(handle, all_followers)
            
        # Fetch detailed profiles if requested
        if fetch_detailed and all_followers:
            console.print(f"[cyan]Fetching detailed profiles for {len(all_followers)} followers...[/cyan]")
            try:
                detailed_followers = self.get_detailed_profiles(all_followers)
                self.cache_followers(handle, detailed_followers)
                followers_to_return = detailed_followers
            except KeyboardInterrupt:
                console.print("[yellow]\nDetailed profile fetching interrupted. Returning basic profiles.[/yellow]")
                followers_to_return = all_followers
            except Exception as e:
                console.print(f"[yellow]Error fetching detailed profiles: {e}. Returning basic profiles.[/yellow]")
                followers_to_return = all_followers
        else:
            followers_to_return = all_followers
            
        # Return exactly max_results followers (or all if max_results is 0)
        return followers_to_return[:max_results] if not all_available else followers_to_return

    def get_all_follows(self, handle: str, max_results: int = 1000, concurrency: int = 3, 
                         batch_size: int = 100, use_cache: bool = True, 
                         max_cache_age_hours: int = 336, fetch_detailed: bool = True) -> List[dict]:
        """
        Fetches all accounts a BlueSky handle is following, handling pagination and respecting max_results exactly.
        Avoids re-fetching already cached users and continues efficiently from the last fetch.
        """
        if not self.bsky_headers:
            raise RuntimeError("Not authenticated with BlueSky. Call authenticate_bsky() first.")
            
        # Ensure handle is correctly formatted
        handle = self.format_handle(handle)
        
        # Check if max_results is 0 (meaning get all available)
        all_available = (max_results == 0)
        
        # Load cached following if available and valid
        cached_following = []
        if use_cache:
            cached_following = self.get_cached_following(handle, max_cache_age_hours) or []
            
        # If we have enough cached following and max_results > 0, return them
        if not all_available and cached_following and len(cached_following) >= max_results:
            console.print(f"[green]Using {max_results} cached following for @{handle}[/green]")
            return cached_following[:max_results]
            
        # Start with existing cached following
        all_follows = cached_following.copy() if cached_following else []
        seen_dids = set(f.get('did') for f in all_follows if f.get('did'))
        
        # Determine how many more follows we need to fetch
        remaining = max_results - len(all_follows) if not all_available else float('inf')
        if remaining <= 0:
            return all_follows[:max_results]
            
        cursor = None
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task_total = max_results if not all_available else None
            task = progress.add_task(
                f"Fetching following for @{handle}...", 
                total=task_total, 
                completed=len(all_follows) if not all_available else 0
            )
            
            try:
                # Continue fetching until we have enough or we've fetched all available
                while (all_available or remaining > 0):
                    # Limit parameter should be the smaller of batch_size or remaining
                    limit = min(batch_size, remaining) if not all_available else batch_size
                    
                    params = {"actor": handle, "limit": limit}
                    if cursor:
                        params["cursor"] = cursor
                        
                    response = requests.get(BSKY_FOLLOWS_ENDPOINT, params=params, headers=self.bsky_headers)
                    response.raise_for_status()
                    page_data = response.json()
                    page_follows = page_data.get("follows", [])
                    
                    # If no more follows are returned, we're done
                    if not page_follows:
                        break
                        
                    # Only add follows we haven't seen before
                    new_follows = [f for f in page_follows if f.get('did') not in seen_dids]
                    
                    # Add new follows to our collection
                    all_follows.extend(new_follows)
                    
                    # Update seen DIDs
                    for f in new_follows:
                        if f.get('did'):
                            seen_dids.add(f.get('did'))
                            
                    # Update progress
                    description = f"Fetched {len(all_follows)}/{max_results if not all_available else '?'} following..."
                    progress.update(task, 
                                   advance=len(new_follows) if not all_available else 0, 
                                   description=description)
                    
                    # Update remaining count
                    remaining = max_results - len(all_follows) if not all_available else float('inf')
                    
                    # Get cursor for next page
                    cursor = page_data.get("cursor")
                    
                    # If no more pages or we have enough, exit loop
                    if not cursor or remaining <= 0:
                        break
                        
                    # Respect rate limits
                    time.sleep(0.5)
                    
            except KeyboardInterrupt:
                console.print("[yellow]\nFollowing fetching interrupted. Returning what we have so far.[/yellow]")
            except Exception as e:
                console.print(f"[yellow]Error fetching following: {e}[/yellow]")
                
        # Cache what we found
        if all_follows:
            self.cache_following(handle, all_follows)
            
        # Fetch detailed profiles if requested
        if fetch_detailed and all_follows:
            console.print(f"[cyan]Fetching detailed profiles for {len(all_follows)} following...[/cyan]")
            try:
                detailed_follows = self.get_detailed_profiles(all_follows)
                self.cache_following(handle, detailed_follows)
                follows_to_return = detailed_follows
            except KeyboardInterrupt:
                console.print("[yellow]\nDetailed profile fetching interrupted. Returning basic profiles.[/yellow]")
                follows_to_return = all_follows
            except Exception as e:
                console.print(f"[yellow]Error fetching detailed profiles: {e}. Returning basic profiles.[/yellow]")
                follows_to_return = all_follows
        else:
            follows_to_return = all_follows
            
        # Return exactly max_results follows (or all if max_results is 0)
        return follows_to_return[:max_results] if not all_available else follows_to_return

    def save_user_list_to_csv(self, users: List[dict], filename: str) -> bool:
        """
        Saves a list of users to a CSV file.
        
        Args:
            users: List of user objects
            filename: Path to save the CSV file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                # Define the fields to export
                fieldnames = ['handle', 'displayName', 'did', 'description', 'followerCount', 'followingCount']
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for user in users:
                    # Extract the relevant fields
                    writer.writerow({
                        'handle': user.get('handle', ''),
                        'displayName': user.get('displayName', ''),
                        'did': user.get('did', ''),
                        'description': user.get('description', ''),
                        'followerCount': user.get('followerCount', 0),
                        'followingCount': user.get('followingCount', 0)
                    })
                    
            return True
        except Exception as e:
            print(f"Error saving users to CSV: {e}")
            return False

    def cache_profile(self, handle: str, profile: dict) -> None:
        """
        Cache a user profile globally.
        
        Args:
            handle: The BlueSky handle
            profile: Profile data to cache
        """
        # Normalize handle for filename
        handle = self.format_handle(handle).replace('.', '_')
        cache_file = os.path.join(PROFILES_CACHE_DIR, f"{handle}_profile.json")
        
        # Add timestamp for cache freshness tracking
        profile_with_timestamp = {
            "timestamp": datetime.now().isoformat(),
            "profile": profile
        }
        
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(profile_with_timestamp, f)
            console.print(f"[green]Cached profile for @{handle}[/green]")
        except Exception as e:
            console.print(f"[red]Error caching profile: {e}[/red]")
    
    def get_cached_profile(self, handle: str, max_age_hours: int = 336) -> Optional[dict]:
        """
        Get a cached profile if it exists and is not too old.
        
        Args:
            handle: The BlueSky handle
            max_age_hours: Maximum age of cache in hours (default: 336 hours / 14 days)
            
        Returns:
            Cached profile or None if no valid cache exists
        """
        # Normalize handle for filename
        handle = self.format_handle(handle).replace('.', '_')
        cache_file = os.path.join(PROFILES_CACHE_DIR, f"{handle}_profile.json")
        
        if not os.path.exists(cache_file):
            return None
            
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
                
            # Check if cache is too old
            timestamp = datetime.fromisoformat(cached_data.get("timestamp", ""))
            age = datetime.now() - timestamp
            if age.total_seconds() > max_age_hours * 3600:
                console.print(f"[yellow]Cached profile for @{handle} is too old ({age.total_seconds()/86400:.1f} days)[/yellow]")
                return None
                
            return cached_data.get("profile")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not load cached profile: {e}[/yellow]")
            return None

    def cache_followers(self, handle: str, followers: List[dict]) -> None:
        """
        Cache followers for a user.
        
        Args:
            handle: The BlueSky handle
            followers: List of followers to cache
        """
        # Normalize handle for filename
        handle = self.format_handle(handle).replace('.', '_')
        
        # Use the current authenticated user's directory if available
        if self.current_user_handle:
            user_cache_dir = os.path.join(FOLLOWERS_CACHE_DIR, self.current_user_handle.replace('.', '_'))
            os.makedirs(user_cache_dir, exist_ok=True)
            cache_file = os.path.join(user_cache_dir, f"{handle}_followers.json")
        else:
            cache_file = os.path.join(FOLLOWERS_CACHE_DIR, f"{handle}_followers.json")
        
        # First, load existing data to preserve history
        history = []
        try:
            if os.path.exists(cache_file):
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    history = cached_data.get("history", [])
        except Exception as e:
            console.print(f"[yellow]Warning: Could not load existing follower history: {e}[/yellow]")
        
        # Add current followers to history with timestamp
        follower_entry = {
            "timestamp": datetime.now().isoformat(),
            "count": len(followers),
            # Store only DIDs or handles to save space
            "followers": [f.get('did', f.get('handle', '')) for f in followers if f.get('did') or f.get('handle')]
        }
        
        # Keep only the last 5 history entries to manage cache size
        history.append(follower_entry)
        if len(history) > 5:
            history = history[-5:]
        
        # Add timestamp for cache freshness tracking
        followers_with_timestamp = {
            "timestamp": datetime.now().isoformat(),
            "followers": followers,
            "history": history
        }
        
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(followers_with_timestamp, f)
            console.print(f"[green]Cached {len(followers)} followers for @{handle}[/green]")
        except Exception as e:
            console.print(f"[red]Error caching followers: {e}[/red]")

    def get_cached_followers(self, handle: str, max_age_hours: int = 336) -> Optional[List[dict]]:
        """
        Get cached followers if they exist and are not too old.
        
        Args:
            handle: The BlueSky handle
            max_age_hours: Maximum age of cache in hours (default: 336 hours / 14 days)
            
        Returns:
            List of cached followers or None if no valid cache exists
        """
        # Normalize handle for filename
        handle = self.format_handle(handle).replace('.', '_')
        
        # Check in current user's directory first if available
        if self.current_user_handle:
            user_cache_dir = os.path.join(FOLLOWERS_CACHE_DIR, self.current_user_handle.replace('.', '_'))
            cache_file = os.path.join(user_cache_dir, f"{handle}_followers.json")
            
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        cached_data = json.load(f)
                        
                    # Check if cache is too old
                    timestamp = datetime.fromisoformat(cached_data.get("timestamp", ""))
                    age = datetime.now() - timestamp
                    if age.total_seconds() <= max_age_hours * 3600:
                        return cached_data.get("followers", [])
                except Exception as e:
                    console.print(f"[yellow]Warning: Could not load user-specific followers cache: {e}[/yellow]")
        
        # Fall back to general cache
        cache_file = os.path.join(FOLLOWERS_CACHE_DIR, f"{handle}_followers.json")
            
        if not os.path.exists(cache_file):
            return None
            
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
                
            # Check if cache is too old
            timestamp = datetime.fromisoformat(cached_data.get("timestamp", ""))
            age = datetime.now() - timestamp
            if age.total_seconds() > max_age_hours * 3600:
                console.print(f"[yellow]Cached followers for @{handle} are too old ({age.total_seconds()/86400:.1f} days)[/yellow]")
                return None
                
            return cached_data.get("followers", [])
        except Exception as e:
            console.print(f"[yellow]Warning: Could not load followers cache: {e}[/yellow]")
            return None

    def get_follower_changes(self, handle: str) -> dict:
        """
        Compare current and previous follower lists to identify unfollows.
        
        Args:
            handle: The BlueSky handle
            
        Returns:
            Dict containing lists of new followers and unfollowers
        """
        # Normalize handle for filename
        handle = self.format_handle(handle).replace('.', '_')
        
        # Get cache path
        cache_file = None
        if self.current_user_handle:
            user_cache_dir = os.path.join(FOLLOWERS_CACHE_DIR, self.current_user_handle.replace('.', '_'))
            potential_file = os.path.join(user_cache_dir, f"{handle}_followers.json")
            if os.path.exists(potential_file):
                cache_file = potential_file
        
        if not cache_file:
            potential_file = os.path.join(FOLLOWERS_CACHE_DIR, f"{handle}_followers.json")
            if os.path.exists(potential_file):
                cache_file = potential_file
        
        if not cache_file or not os.path.exists(cache_file):
            return {"error": "No cached follower data found"}
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
                
            history = cached_data.get("history", [])
            
            # Need at least 2 history entries to compare
            if len(history) < 2:
                return {"error": "Not enough history to compare changes", "history_count": len(history)}
            
            # Get current and previous follower lists
            current = history[-1]
            previous = history[-2]
            
            # Convert lists to sets for comparison
            current_followers = set(current.get("followers", []))
            previous_followers = set(previous.get("followers", []))
            
            # Find new followers and unfollowers
            new_followers = current_followers - previous_followers
            unfollowers = previous_followers - current_followers
            
            # Get detailed profile info for the changes if available
            detailed_changes = {
                "current_timestamp": current.get("timestamp"),
                "previous_timestamp": previous.get("timestamp"),
                "new_followers": list(new_followers),
                "unfollowers": list(unfollowers),
                "new_count": len(new_followers),
                "unfollower_count": len(unfollowers)
            }
            
            return detailed_changes
            
        except Exception as e:
            return {"error": f"Error analyzing follower changes: {str(e)}"}
            
    def get_detailed_follower_changes(self, handle: str) -> dict:
        """
        Get detailed profile information for followers who have followed or unfollowed.
        
        Args:
            handle: The BlueSky handle
            
        Returns:
            Dict containing detailed profiles of new followers and unfollowers
        """
        # First get the basic changes
        changes = self.get_follower_changes(handle)
        
        if "error" in changes:
            return changes
            
        # Try to get detailed profile information for each change
        new_follower_profiles = []
        unfollower_profiles = []
        
        try:
            # Fetch detailed profiles for new followers if there are any
            if changes["new_followers"]:
                console.print(f"[cyan]Fetching profiles for {len(changes['new_followers'])} new followers...[/cyan]")
                for follower_id in changes["new_followers"]:
                    try:
                        profile = self.get_profile(follower_id)
                        new_follower_profiles.append(profile)
                    except Exception as e:
                        console.print(f"[yellow]Could not fetch profile for {follower_id}: {e}[/yellow]")
                        # Add minimal info so we still track the ID
                        new_follower_profiles.append({"did": follower_id, "error": str(e)})
            
            # Fetch detailed profiles for unfollowers if there are any
            if changes["unfollowers"]:
                console.print(f"[cyan]Fetching profiles for {len(changes['unfollowers'])} unfollowers...[/cyan]")
                for follower_id in changes["unfollowers"]:
                    try:
                        profile = self.get_profile(follower_id)
                        unfollower_profiles.append(profile)
                    except Exception as e:
                        console.print(f"[yellow]Could not fetch profile for {follower_id}: {e}[/yellow]")
                        # Add minimal info so we still track the ID
                        unfollower_profiles.append({"did": follower_id, "error": str(e)})
                        
            # Create a detailed result with profile data
            detailed_results = {
                "current_timestamp": changes["current_timestamp"],
                "previous_timestamp": changes["previous_timestamp"],
                "new_followers": new_follower_profiles,
                "unfollowers": unfollower_profiles,
                "new_count": len(new_follower_profiles),
                "unfollower_count": len(unfollower_profiles)
            }
            
            return detailed_results
        except Exception as e:
            return {"error": f"Error getting detailed follower changes: {str(e)}"}
    
    def cache_following(self, handle: str, following: List[dict]) -> None:
        """
        Cache following for a user.
        
        Args:
            handle: The BlueSky handle
            following: List of accounts followed to cache
        """
        # Normalize handle for filename
        handle = self.format_handle(handle).replace('.', '_')
        
        # Use the current authenticated user's directory if available
        if self.current_user_handle:
            user_cache_dir = os.path.join(FOLLOWING_CACHE_DIR, self.current_user_handle.replace('.', '_'))
            os.makedirs(user_cache_dir, exist_ok=True)
            cache_file = os.path.join(user_cache_dir, f"{handle}_following.json")
        else:
            cache_file = os.path.join(FOLLOWING_CACHE_DIR, f"{handle}_following.json")
        
        # Add timestamp for cache freshness tracking
        following_with_timestamp = {
            "timestamp": datetime.now().isoformat(),
            "following": following
        }
        
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(following_with_timestamp, f)
            console.print(f"[green]Cached {len(following)} following accounts for @{handle}[/green]")
        except Exception as e:
            console.print(f"[red]Error caching following: {e}[/red]")
    
    def get_cached_following(self, handle: str, max_age_hours: int = 336) -> Optional[List[dict]]:
        """
        Get cached following if they exist and are not too old.
        
        Args:
            handle: The BlueSky handle
            max_age_hours: Maximum age of cache in hours (default: 336 hours / 14 days)
            
        Returns:
            List of cached following or None if no valid cache exists
        """
        # Normalize handle for filename
        handle = self.format_handle(handle).replace('.', '_')
        
        # Check in current user's directory first if available
        if self.current_user_handle:
            user_cache_dir = os.path.join(FOLLOWING_CACHE_DIR, self.current_user_handle.replace('.', '_'))
            cache_file = os.path.join(user_cache_dir, f"{handle}_following.json")
            
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        cached_data = json.load(f)
                        
                    # Check if cache is too old
                    timestamp = datetime.fromisoformat(cached_data.get("timestamp", ""))
                    age = datetime.now() - timestamp
                    if age.total_seconds() <= max_age_hours * 3600:
                        return cached_data.get("following", [])
                except Exception as e:
                    console.print(f"[yellow]Warning: Could not load user-specific following cache: {e}[/yellow]")
        
        # Fall back to general cache
        cache_file = os.path.join(FOLLOWING_CACHE_DIR, f"{handle}_following.json")
            
        if not os.path.exists(cache_file):
            return None
            
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
                
            # Check if cache is too old
            timestamp = datetime.fromisoformat(cached_data.get("timestamp", ""))
            age = datetime.now() - timestamp
            if age.total_seconds() > max_age_hours * 3600:
                console.print(f"[yellow]Cached following for @{handle} are too old ({age.total_seconds()/86400:.1f} days)[/yellow]")
                return None
                
            return cached_data.get("following", [])
        except Exception as e:
            console.print(f"[yellow]Warning: Could not load following cache: {e}[/yellow]")
            return None

    def analyze_comment_behavior(self, posts_text, limit=500):
        """
        Analyze user's comments to determine if they're exhibiting troll behavior
        
        Args:
            posts_text (str): The concatenated text of posts/comments
            limit (int): Maximum number of comments to analyze
            
        Returns:
            dict: Analysis including verdict and reasoning
        """
        if not posts_text:
            raise RuntimeError("No posts found to analyze")
            
        system_prompt = """You are an objective evaluator of online behavior. 
        Review the following comments or posts from a user and determine if they 
        are exhibiting troll or antagonistic behavior. Look for:
        
        1. Personal attacks or insults
        2. Inflammatory language designed to provoke
        3. Bad faith arguments
        4. Consistent negativity or hostility
        5. Disregard for community norms
        
        Provide a clear YES or NO verdict if they are "being an asshole" based on this content.
        Follow this with a brief explanation of your reasoning with specific examples.
        """
        
        user_prompt = f"Here are the recent posts/comments from a user (limited to {limit}). Analyze them for troll or antagonistic behavior:\n\n{posts_text}"
        
        # Call to OpenAI API
        try:
            response = self.xai_client.chat.completions.create(
                model="grok-3",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )
            result = response.choices[0].message.content.strip()
            
            # Extract verdict
            verdict = "YES" if "YES" in result.split("\n")[0].upper() else "NO"
            
            return {
                "verdict": verdict,
                "analysis": result
            }
        except Exception as e:
            raise RuntimeError(f"Failed to analyze behavior: {str(e)}")

    def send_to_api(self, data, endpoint, api_key=None):
        """
        Send data to an external API endpoint
        
        Args:
            data (dict): The data to send
            endpoint (str): The API endpoint URL
            api_key (str, optional): API key for authentication
            
        Returns:
            dict: API response
        """
        headers = {
            "Content-Type": "application/json"
        }
        
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
            
        try:
            response = requests.post(
                endpoint,
                headers=headers,
                json=data,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise RuntimeError(f"Failed to send data to API: {str(e)}")

    def export_all(self, handle: str, export_dir: str = ".") -> None:
        """
        Export all data related to a handle to JSON files.
        
        Parameters:
            handle (str): BlueSky handle to export data for
            export_dir (str): Directory to save exports (default: current directory)
        """
        os.makedirs(export_dir, exist_ok=True)
        
        # Export profile
        profile = self.get_profile(handle)
        profile_path = os.path.join(export_dir, f"{handle}_profile.json")
        with open(profile_path, "w") as f:
            json.dump(profile, f, indent=2)
        console.print(f"[green]✓[/green] Exported profile to {profile_path}")
        
        # Export posts
        posts = self.get_all_posts(handle)
        posts_path = os.path.join(export_dir, f"{handle}_posts.json")
        with open(posts_path, "w") as f:
            json.dump(posts, f, indent=2)
        console.print(f"[green]✓[/green] Exported {len(posts)} posts to {posts_path}")
        
        # Export followers
        followers = self.get_all_followers(handle)
        followers_path = os.path.join(export_dir, f"{handle}_followers.json")
        with open(followers_path, "w") as f:
            json.dump(followers, f, indent=2)
        console.print(f"[green]✓[/green] Exported {len(followers)} followers to {followers_path}")
        
        # Export following
        following = self.get_all_follows(handle)
        following_path = os.path.join(export_dir, f"{handle}_following.json")
        with open(following_path, "w") as f:
            json.dump(following, f, indent=2)
        console.print(f"[green]✓[/green] Exported {len(following)} following to {following_path}")
        
        console.print(f"\n[bold green]All data exported to {export_dir}[/bold green]")

    def analyze_post_engagement(self, posts: List[dict]) -> dict:
        """
        Analyze engagement metrics for posts.
        
        Args:
            posts: List of posts to analyze
            
        Returns:
            Dictionary with engagement metrics and analysis
        """
        if not posts:
            return {"error": "No posts to analyze"}
            
        total_posts = len(posts)
        total_likes = 0
        total_replies = 0
        total_reposts = 0
        
        posts_with_likes = []
        posts_with_replies = []
        posts_with_reposts = []
        
        # Collect engagement data
        for post in posts:
            post_view = post.get("post", {})
            likes = post_view.get("likeCount", 0)
            replies = post_view.get("replyCount", 0)
            reposts = post_view.get("repostCount", 0)
            
            total_likes += likes
            total_replies += replies
            total_reposts += reposts
            
            # Store post data for later analysis
            post_data = {
                "post": post_view,
                "likes": likes,
                "replies": replies,
                "reposts": reposts,
                "engagement": likes + replies + reposts
            }
            
            # Add post date if available
            record = post_view.get("record", {})
            if "createdAt" in record:
                try:
                    post_data["created_at"] = datetime.fromisoformat(record["createdAt"].replace("Z", "+00:00"))
                except:
                    pass
            
            # Track posts with engagement
            if likes > 0:
                posts_with_likes.append(post_data)
            if replies > 0:
                posts_with_replies.append(post_data)
            if reposts > 0:
                posts_with_reposts.append(post_data)
        
        # Calculate averages
        avg_likes = total_likes / total_posts if total_posts > 0 else 0
        avg_replies = total_replies / total_posts if total_posts > 0 else 0
        avg_reposts = total_reposts / total_posts if total_posts > 0 else 0
        avg_engagement = (total_likes + total_replies + total_reposts) / total_posts if total_posts > 0 else 0
        
        # Sort posts by engagement
        sorted_by_engagement = sorted([p for p in posts_with_likes + posts_with_replies + posts_with_reposts 
                                      if p.get("engagement", 0) > 0],
                                     key=lambda x: x.get("engagement", 0), 
                                     reverse=True)
        
        # Remove duplicates from sorted list
        seen_uris = set()
        unique_sorted = []
        for post in sorted_by_engagement:
            post_view = post.get("post", {})
            uri = post_view.get("uri", "")
            if uri and uri not in seen_uris:
                seen_uris.add(uri)
                unique_sorted.append(post)
        
        # Calculate engagement rates
        like_rate = len(posts_with_likes) / total_posts if total_posts > 0 else 0
        reply_rate = len(posts_with_replies) / total_posts if total_posts > 0 else 0
        repost_rate = len(posts_with_reposts) / total_posts if total_posts > 0 else 0
        
        # Get top performing posts
        top_posts = unique_sorted[:5] if unique_sorted else []
        
        # Compile analytics
        analytics = {
            "total_posts": total_posts,
            "total_likes": total_likes,
            "total_replies": total_replies,
            "total_reposts": total_reposts,
            "total_engagement": total_likes + total_replies + total_reposts,
            "avg_likes_per_post": avg_likes,
            "avg_replies_per_post": avg_replies,
            "avg_reposts_per_post": avg_reposts,
            "avg_engagement_per_post": avg_engagement,
            "posts_with_likes_pct": like_rate * 100,
            "posts_with_replies_pct": reply_rate * 100,
            "posts_with_reposts_pct": repost_rate * 100,
            "top_performing_posts": top_posts
        }
        
        return analytics
        
    def analyze_posting_time_patterns(self, posts: List[dict]) -> dict:
        """
        Analyze posting time patterns to identify optimal posting times.
        
        Args:
            posts: List of posts to analyze
            
        Returns:
            Dictionary with posting time analytics
        """
        if not posts:
            return {"error": "No posts to analyze"}
            
        # Initialize counters
        day_counts = {i: 0 for i in range(7)}  # 0 = Monday, 6 = Sunday
        hour_counts = {i: 0 for i in range(24)}
        
        day_engagement = {i: [] for i in range(7)}
        hour_engagement = {i: [] for i in range(24)}
        
        # Track posts with timestamp
        posts_with_timestamp = []
        
        # Collect posting time data
        for post in posts:
            post_view = post.get("post", {})
            record = post_view.get("record", {})
            
            if "createdAt" in record:
                try:
                    dt = datetime.fromisoformat(record["createdAt"].replace("Z", "+00:00"))
                    
                    # Get day and hour
                    day = dt.weekday()  # 0 = Monday, 6 = Sunday
                    hour = dt.hour
                    
                    # Count posts by day and hour
                    day_counts[day] += 1
                    hour_counts[hour] += 1
                    
                    # Track engagement by day and hour
                    engagement = post_view.get("likeCount", 0) + post_view.get("replyCount", 0) + post_view.get("repostCount", 0)
                    day_engagement[day].append(engagement)
                    hour_engagement[hour].append(engagement)
                    
                    # Store post with timestamp for further analysis
                    posts_with_timestamp.append({
                        "post": post_view,
                        "timestamp": dt,
                        "day": day,
                        "hour": hour,
                        "engagement": engagement
                    })
                except:
                    pass
        
        # Calculate average engagement by day and hour
        avg_day_engagement = {}
        for day, engagements in day_engagement.items():
            if engagements:
                avg_day_engagement[day] = sum(engagements) / len(engagements)
            else:
                avg_day_engagement[day] = 0
                
        avg_hour_engagement = {}
        for hour, engagements in hour_engagement.items():
            if engagements:
                avg_hour_engagement[hour] = sum(engagements) / len(engagements)
            else:
                avg_hour_engagement[hour] = 0
        
        # Find optimal posting times
        best_days = sorted(avg_day_engagement.keys(), key=lambda x: avg_day_engagement[x], reverse=True)
        best_hours = sorted(avg_hour_engagement.keys(), key=lambda x: avg_hour_engagement[x], reverse=True)
        
        # Day names for better readability
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        
        # Format hour with AM/PM
        def format_hour(h):
            if h == 0:
                return "12 AM"
            elif h < 12:
                return f"{h} AM"
            elif h == 12:
                return "12 PM"
            else:
                return f"{h-12} PM"
        
        # Compile time analysis
        time_analysis = {
            "total_posts_with_timestamp": len(posts_with_timestamp),
            "posting_frequency_by_day": {day_names[day]: count for day, count in day_counts.items()},
            "posting_frequency_by_hour": {format_hour(hour): count for hour, count in hour_counts.items()},
            "avg_engagement_by_day": {day_names[day]: avg_day_engagement[day] for day in range(7)},
            "avg_engagement_by_hour": {format_hour(hour): avg_hour_engagement[hour] for hour in range(24)},
            "best_days_by_engagement": [day_names[day] for day in best_days[:3]],
            "best_hours_by_engagement": [format_hour(hour) for hour in best_hours[:5]],
            "optimal_posting_times": []
        }
        
        # Generate recommended optimal posting times
        for day in best_days[:2]:  # Top 2 days
            for hour in best_hours[:3]:  # Top 3 hours
                time_analysis["optimal_posting_times"].append({
                    "day": day_names[day],
                    "hour": format_hour(hour),
                    "avg_engagement": avg_hour_engagement[hour] * avg_day_engagement[day] / (sum(avg_day_engagement.values())/7) if sum(avg_day_engagement.values()) > 0 else 0
                })
        
        # Sort optimal times by expected engagement
        time_analysis["optimal_posting_times"] = sorted(
            time_analysis["optimal_posting_times"],
            key=lambda x: x["avg_engagement"],
            reverse=True
        )
        
        return time_analysis

    def batch_analyze_users(self, handles: List[str], analysis_type: str = "engagement", max_posts: int = 100) -> dict:
        """
        Perform batch analysis on multiple users.
        
        Args:
            handles: List of user handles to analyze
            analysis_type: Type of analysis to perform (engagement, posting_time, vibe, summary)
            max_posts: Maximum number of posts to analyze per user
            
        Returns:
            Dictionary with analysis results for each user
        """
        if not self.bsky_headers:
            raise RuntimeError("Not authenticated with BlueSky. Call authenticate_bsky() first.")
        
        results = {}
        processed = 0
        errored = 0
        
        # Create progress bar for overall progress
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=console
        ) as progress:
            overall_task = progress.add_task(f"[cyan]Analyzing {len(handles)} users...[/cyan]", total=len(handles))
            
            for handle in handles:
                try:
                    formatted_handle = self.format_handle(handle)
                    progress.update(overall_task, description=f"[cyan]Analyzing @{formatted_handle} ({processed+1}/{len(handles)})[/cyan]")
                    
                    # Fetch posts for this user
                    posts = self.get_all_posts(formatted_handle, max_posts=max_posts, show_progress=False)
                    
                    if not posts:
                        results[formatted_handle] = {"error": "No posts found"}
                        continue
                    
                    # Perform requested analysis
                    if analysis_type == "engagement":
                        results[formatted_handle] = self.analyze_post_engagement(posts)
                    elif analysis_type == "posting_time":
                        results[formatted_handle] = self.analyze_posting_time_patterns(posts)
                    elif analysis_type == "vibe":
                        posts_text = self.get_post_content(posts)
                        results[formatted_handle] = {"vibe_check": self.vibe_check(posts_text)}
                    elif analysis_type == "summary":
                        posts_text = self.get_post_content(posts)
                        results[formatted_handle] = {"summary": self.summarize_text(posts_text)}
                    else:
                        results[formatted_handle] = {"error": f"Unknown analysis type: {analysis_type}"}
                    
                    processed += 1
                    
                    # Update progress
                    progress.update(overall_task, advance=1)
                    
                    # Add small delay to avoid rate limiting
                    time.sleep(0.5)
                    
                except Exception as e:
                    results[formatted_handle] = {"error": str(e)}
                    errored += 1
                    progress.update(overall_task, advance=1)
        
        # Add summary stats
        summary = {
            "total_users": len(handles),
            "successful_analyses": processed - errored,
            "failed_analyses": errored,
            "analysis_type": analysis_type
        }
        
        return {"results": results, "summary": summary}

    def compare_users(self, handles: List[str], max_posts: int = 100) -> dict:
        """
        Compare engagement metrics between multiple users.
        
        Args:
            handles: List of user handles to compare
            max_posts: Maximum number of posts to analyze per user
            
        Returns:
            Dictionary with comparison results
        """
        if not self.bsky_headers:
            raise RuntimeError("Not authenticated with BlueSky. Call authenticate_bsky() first.")
        
        # Use batch analyze to get engagement metrics for all users
        batch_results = self.batch_analyze_users(handles, analysis_type="engagement", max_posts=max_posts)
        
        # Extract results
        results = batch_results.get("results", {})
        
        # Compile comparison metrics
        comparison = {
            "total_posts": {},
            "avg_likes_per_post": {},
            "avg_replies_per_post": {},
            "avg_reposts_per_post": {},
            "avg_engagement_per_post": {},
            "total_engagement": {}
        }
        
        # Build metrics for each user
        for handle, data in results.items():
            if "error" in data:
                continue
                
            comparison["total_posts"][handle] = data.get("total_posts", 0)
            comparison["avg_likes_per_post"][handle] = data.get("avg_likes_per_post", 0)
            comparison["avg_replies_per_post"][handle] = data.get("avg_replies_per_post", 0)
            comparison["avg_reposts_per_post"][handle] = data.get("avg_reposts_per_post", 0)
            comparison["avg_engagement_per_post"][handle] = data.get("avg_engagement_per_post", 0)
            comparison["total_engagement"][handle] = data.get("total_engagement", 0)
        
        # Find the "winner" for each metric
        winners = {}
        
        for metric, values in comparison.items():
            if values:
                max_handle = max(values.items(), key=lambda x: x[1])[0]
                winners[metric] = max_handle
        
        return {
            "metrics": comparison,
            "winners": winners,
            "details": results
        }

    # For progress bar enhancements
    class TimeRemainingColumn(TaskProgressColumn):
        """Renders estimated time remaining."""
        def render(self, task) -> Text:
            if task.finished:
                return Text("0:00:00", style="green")
            if task.total is None or task.completed == 0:
                return Text("-:--:--", style="cyan")
            seconds_remaining = (task.total - task.completed) / task.speed if task.speed else 0
            remaining = timedelta(seconds=int(seconds_remaining))
            return Text(str(remaining), style="cyan")

    def analyze_follower_ratios(self, handle: str, max_users: int = 100, min_following: int = 20) -> dict:
        """
        Analyze follower-to-following ratios for a user's followers and followed accounts.
        
        Args:
            handle: The BlueSky handle to analyze
            max_users: Maximum number of users to analyze
            min_following: Minimum following count for ratio calculation (to avoid division by small numbers)
            
        Returns:
            Dictionary with best and worst ratio users
        """
        # Get followers
        followers = self.get_all_followers(handle, max_results=max_users, fetch_detailed=True)
        
        # Get following
        following = self.get_all_follows(handle, max_results=max_users, fetch_detailed=True)
        
        # Calculate ratios for followers
        follower_ratios = []
        for user in followers:
            followers_count = user.get("followersCount", 0)
            following_count = user.get("followsCount", 0)
            
            if following_count >= min_following:
                ratio = followers_count / following_count if following_count > 0 else 0
                follower_ratios.append({
                    "handle": user.get("handle", "unknown"),
                    "display_name": user.get("displayName", "Unknown"),
                    "followers": followers_count,
                    "following": following_count,
                    "ratio": ratio
                })
                
        # Calculate ratios for following
        following_ratios = []
        for user in following:
            followers_count = user.get("followersCount", 0)
            following_count = user.get("followsCount", 0)
            
            if following_count >= min_following:
                ratio = followers_count / following_count if following_count > 0 else 0
                following_ratios.append({
                    "handle": user.get("handle", "unknown"),
                    "display_name": user.get("displayName", "Unknown"),
                    "followers": followers_count,
                    "following": following_count,
                    "ratio": ratio
                })
        
        # Sort ratios
        best_follower_ratios = sorted(follower_ratios, key=lambda x: x["ratio"], reverse=True)
        worst_follower_ratios = sorted(follower_ratios, key=lambda x: x["ratio"])
        
        best_following_ratios = sorted(following_ratios, key=lambda x: x["ratio"], reverse=True)
        worst_following_ratios = sorted(following_ratios, key=lambda x: x["ratio"])
        
        return {
            "best_follower_ratios": best_follower_ratios[:10] if best_follower_ratios else [],
            "worst_follower_ratios": worst_follower_ratios[:10] if worst_follower_ratios else [],
            "best_following_ratios": best_following_ratios[:10] if best_following_ratios else [],
            "worst_following_ratios": worst_following_ratios[:10] if worst_following_ratios else [],
            "stats": {
                "total_followers_analyzed": len(followers),
                "followers_with_ratio_calculated": len(follower_ratios),
                "total_following_analyzed": len(following),
                "following_with_ratio_calculated": len(following_ratios)
            }
        }
    
    def find_missing_cached_profiles(self, handle: str, profile_type: str = "followers", max_cache_age_hours: int = 336) -> List[str]:
        """
        Find followers or following accounts that are not cached or have stale cache, up to the full set.
        """
        if profile_type not in ["followers", "following"]:
            raise ValueError("Profile type must be 'followers' or 'following'")
        formatted_handle = self.format_handle(handle)
        # Get the full list of followers/following (all, not just 100)
        if profile_type == "followers":
            users = self.get_all_followers(formatted_handle, max_results=0, fetch_detailed=False, use_cache=True)
        else:
            users = self.get_all_follows(formatted_handle, max_results=0, fetch_detailed=False, use_cache=True)
        handles = [user.get("handle") for user in users if user.get("handle")]
        missing_handles = []
        for user_handle in handles:
            cache_file = os.path.join(PROFILES_CACHE_DIR, f"{user_handle.replace('.', '_')}_profile.json")
            if not os.path.exists(cache_file):
                missing_handles.append(user_handle)
                continue
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                timestamp = datetime.fromisoformat(cached_data.get("timestamp", ""))
                age = datetime.now() - timestamp
                if age.total_seconds() > max_cache_age_hours * 3600:
                    missing_handles.append(user_handle)
            except:
                missing_handles.append(user_handle)
        return missing_handles
    
    def update_missing_profiles(self, handles: List[str], 
                               batch_size: int = 10,
                               show_progress: bool = True) -> dict:
        """
        Update missing profile cache for a list of handles, using individual getProfile calls.
        """
        if not handles:
            return {"success": True, "updated": 0, "failed": 0, "total": 0}
        updated = 0
        failed = 0
        progress = None
        task_id = None
        try:
            if show_progress:
                progress = Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TaskProgressColumn(),
                    console=console
                )
                progress.start()
                task_id = progress.add_task(f"[cyan]Updating profile cache for {len(handles)} handles...", total=len(handles))
            
            # Use individual getProfile calls instead of batch
            for i, handle in enumerate(handles):
                try:
                    # Always use getProfile for consistent behavior
                    profile = self.get_profile(handle, use_cache=False)
                    if profile:
                        updated += 1
                    else:
                        failed += 1
                    
                    if progress and task_id is not None:
                        progress.update(task_id, advance=1, description=f"[cyan]Updated {updated}/{len(handles)} profiles...")
                except Exception as e:
                    failed += 1
                    if progress and task_id is not None:
                        progress.update(task_id, advance=1, description=f"[cyan]Updated {updated}/{len(handles)} profiles (failed: {failed})...")
            
            return {"success": True, "updated": updated, "failed": failed, "total": len(handles)}
        finally:
            if progress:
                progress.stop()

    def get_last_post_times(self, handles: list, max_age_hours: int = 336, max_posts: int = 1) -> dict:
        """
        For each handle in the list, get the timestamp of their most recent post (from cache if possible).
        Returns a dict: {handle: datetime or None}
        """
        last_times = {}
        for handle in handles:
            posts = self.get_cached_posts(handle)
            if not posts:
                # Fetch latest post if not cached
                try:
                    posts = self.get_all_posts(handle, max_posts=max_posts, show_progress=False)
                except Exception:
                    posts = []
            latest_time = None
            for post in posts:
                post_view = post.get("post", {})
                record = post_view.get("record", {})
                if "createdAt" in record:
                    try:
                        dt = datetime.fromisoformat(record["createdAt"].replace("Z", "+00:00"))
                        if not latest_time or dt > latest_time:
                            latest_time = dt
                    except Exception:
                        continue
            last_times[handle] = latest_time
        return last_times


class XaiBskySummarizer(BlueSkyAPI):
    """Legacy class name for backward compatibility"""
    pass


class CLIFormatter:
    """Helper class for formatting CLI output"""
    
    @staticmethod
    def print_header(text: str):
        """Print a header with a border"""
        console.print(Panel(
            Text(text, justify="center"),
            style="bold cyan",
            border_style="cyan"
        ))
    
    @staticmethod
    def print_section(title: str):
        """Print a section title"""
        console.print(Panel(
            Text(f"## {title}", style="bold"),
            style="blue",
            border_style="blue"
        ))
    
    @staticmethod
    def format_post(post: dict, include_date: bool = True) -> Text:
        """Format a single post nicely for display"""
        record = post.get("record", {})
        text = record.get("text", "")
        author = post.get("author", {})
        display_name = author.get("displayName", "Unknown")
        handle = author.get("handle", "unknown")
        
        created_at = ""
        if include_date and "createdAt" in record:
            try:
                dt = datetime.fromisoformat(record["createdAt"].replace("Z", "+00:00"))
                created_at = f" • {dt.strftime('%Y-%m-%d %H:%M:%S UTC')}"
            except:
                pass
        
        wrapper = textwrap.TextWrapper(width=min(os.get_terminal_size().columns - 4, 96), 
                                     subsequent_indent="    ")
        wrapped_text = wrapper.fill(text)
        
        result = Text()
        result.append(f"@{handle}", style="cyan bold")
        result.append(f" ({display_name})", style="blue")
        result.append(created_at, style="dim")
        result.append(f"\n{wrapped_text}\n")
        return result
    
    @staticmethod
    def format_profile(profile: dict) -> Text:
        """Format profile information for display"""
        result = Text()
        result.append("Handle: ", style="cyan")
        result.append(f"@{profile.get('handle', 'unknown')}\n", style="cyan bold")
        result.append("Display Name: ", style="cyan")
        result.append(f"{profile.get('displayName', 'Unknown')}\n", style="white bold")
        
        if "description" in profile:
            result.append("\nDescription: ", style="cyan")
            result.append(f"{profile.get('description', '')}\n", style="white")
        
        if "postsCount" in profile:
            result.append("\nPosts: ", style="cyan")
            result.append(f"{profile.get('postsCount', 0):,}\n", style="white bold")
        
        if "followersCount" in profile:
            result.append("Followers: ", style="cyan")
            result.append(f"{profile.get('followersCount', 0):,}\n", style="white bold")
        
        if "followsCount" in profile:
            result.append("Following: ", style="cyan")
            result.append(f"{profile.get('followsCount', 0):,}\n", style="white bold")
        
        if "indexedAt" in profile:
            try:
                dt = datetime.fromisoformat(profile["indexedAt"].replace("Z", "+00:00"))
                result.append("Last Indexed: ", style="cyan")
                result.append(f"{dt.strftime('%Y-%m-%d %H:%M:%S UTC')}\n", style="dim")
            except:
                pass
        
        return result
    
    @staticmethod
    def format_user_list(users: List[dict]) -> Table:
        """Format a list of users for display"""
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Handle", style="cyan")
        table.add_column("Display Name", style="white")
        table.add_column("Followers", justify="right", style="green")
        table.add_column("Following", justify="right", style="blue")
        
        for user in users:
            table.add_row(
                f"@{user.get('handle', 'unknown')}",
                user.get('displayName', 'Unknown'),
                f"{user.get('followersCount', 0):,}",
                f"{user.get('followingCount', 0):,}"
            )
        return table


def run_cli():
    """
    Run the CLI interface for the XAI BlueSky tools
    """
    parser = argparse.ArgumentParser(description="XAI BlueSky Tools")
    
    # Set up subparsers for commands
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Profile command
    profile_parser = subparsers.add_parser("profile", help="Get profile information for a BlueSky user")
    profile_parser.add_argument("handle", help="BlueSky handle (e.g., @username)")
    profile_parser.add_argument("--api", help="Send results to API endpoint")
    profile_parser.add_argument("--api-key", help="API key for authentication")
    
    # Posts command
    posts_parser = subparsers.add_parser("posts", help="Get recent posts from a BlueSky user")
    posts_parser.add_argument("handle", help="BlueSky handle (e.g., @username)")
    posts_parser.add_argument("--limit", type=int, default=10, help="Number of posts to retrieve (default: 10)")
    posts_parser.add_argument("--since", help="Start date (YYYY-MM-DD)")
    posts_parser.add_argument("--until", help="End date (YYYY-MM-DD)")
    posts_parser.add_argument("--sort", choices=["date", "likes", "replies"], default="date", 
                             help="Sort criteria (default: date)")
    posts_parser.add_argument("--asc", action="store_true", help="Sort in ascending order (default: descending)")
    posts_parser.add_argument("--use-cache", action="store_true", help="Use cached posts if available")
    posts_parser.add_argument("--api", help="Send results to API endpoint")
    posts_parser.add_argument("--api-key", help="API key for authentication")
    
    # Summary command
    summary_parser = subparsers.add_parser("summary", help="Get a summary of recent posts from a BlueSky user")
    summary_parser.add_argument("handle", help="BlueSky handle (e.g., @username)")
    summary_parser.add_argument("--limit", type=int, default=100, help="Number of posts to analyze (default: 100)")
    summary_parser.add_argument("--since", help="Start date (YYYY-MM-DD)")
    summary_parser.add_argument("--until", help="End date (YYYY-MM-DD)")
    summary_parser.add_argument("--use-cache", action="store_true", help="Use cached posts if available")
    summary_parser.add_argument("--api", help="Send results to API endpoint")
    summary_parser.add_argument("--api-key", help="API key for authentication")
    
    # Vibe check command
    vibe_parser = subparsers.add_parser("vibe", help="Get a vibe check for a BlueSky user")
    vibe_parser.add_argument("handle", help="BlueSky handle (e.g., @username)")
    vibe_parser.add_argument("--limit", type=int, default=100, help="Number of posts to analyze (default: 100)")
    vibe_parser.add_argument("--since", help="Start date (YYYY-MM-DD)")
    vibe_parser.add_argument("--until", help="End date (YYYY-MM-DD)")
    vibe_parser.add_argument("--use-cache", action="store_true", help="Use cached posts if available")
    vibe_parser.add_argument("--api", help="Send results to API endpoint")
    vibe_parser.add_argument("--api-key", help="API key for authentication")
    
    # Followers command
    followers_parser = subparsers.add_parser("followers", help="Get followers for a BlueSky user")
    followers_parser.add_argument("handle", help="BlueSky handle (e.g., @username)")
    followers_parser.add_argument("--limit", type=int, default=100, help="Number of followers to retrieve (default: 100)")
    followers_parser.add_argument("--api", help="Send results to API endpoint")
    followers_parser.add_argument("--api-key", help="API key for authentication")
    
    # Following command
    following_parser = subparsers.add_parser("following", help="Get accounts a BlueSky user is following")
    following_parser.add_argument("handle", help="BlueSky handle (e.g., @username)")
    following_parser.add_argument("--limit", type=int, default=100, help="Number of following accounts to retrieve (default: 100)")
    following_parser.add_argument("--api", help="Send results to API endpoint")
    following_parser.add_argument("--api-key", help="API key for authentication")
    
    # Batch follower collection command
    batch_followers_parser = subparsers.add_parser("batch-followers", help="Collect all followers for a BlueSky user")
    batch_followers_parser.add_argument("handle", help="BlueSky handle (e.g., @username)")
    batch_followers_parser.add_argument("output", help="Output CSV file path")
    batch_followers_parser.add_argument("--max", type=int, default=0, help="Maximum number of followers to collect (0 for all)")
    batch_followers_parser.add_argument("--concurrency", type=int, default=5, help="Number of concurrent requests (default: 5)")
    batch_followers_parser.add_argument("--batch-size", type=int, default=100, help="Batch size for API requests (default: 100)")
    batch_followers_parser.add_argument("--api", help="Send results to API endpoint")
    batch_followers_parser.add_argument("--api-key", help="API key for authentication")
    
    # Batch following collection command
    batch_following_parser = subparsers.add_parser("batch-following", help="Collect all accounts a BlueSky user is following")
    batch_following_parser.add_argument("handle", help="BlueSky handle (e.g., @username)")
    batch_following_parser.add_argument("output", help="Output CSV file path")
    batch_following_parser.add_argument("--max", type=int, default=0, help="Maximum number of accounts to collect (0 for all)")
    batch_following_parser.add_argument("--concurrency", type=int, default=5, help="Number of concurrent requests (default: 5)")
    batch_following_parser.add_argument("--batch-size", type=int, default=100, help="Batch size for API requests (default: 100)")
    batch_following_parser.add_argument("--api", help="Send results to API endpoint")
    batch_following_parser.add_argument("--api-key", help="API key for authentication")
    
    # Search posts command
    search_posts_parser = subparsers.add_parser("search-posts", help="Search BlueSky posts")
    search_posts_parser.add_argument("query", help="Search query")
    search_posts_parser.add_argument("--limit", type=int, default=20, help="Maximum number of results (default: 20)")
    search_posts_parser.add_argument("--api", help="Send results to API endpoint")
    search_posts_parser.add_argument("--api-key", help="API key for authentication")
    
    # Search users command
    search_users_parser = subparsers.add_parser("search-users", help="Search BlueSky users")
    search_users_parser.add_argument("query", help="Search query")
    search_users_parser.add_argument("--limit", type=int, default=20, help="Maximum number of results (default: 20)")
    search_users_parser.add_argument("--api", help="Send results to API endpoint")
    search_users_parser.add_argument("--api-key", help="API key for authentication")
    
    # Am I Being An Asshole command
    aita_parser = subparsers.add_parser("am-i-being-an-asshole", help="Analyze comment behavior for trolling")
    aita_parser.add_argument("handle", help="BlueSky handle (e.g., @username)")
    aita_parser.add_argument("--limit", type=int, default=500, help="Number of comments to analyze (default: 500)")
    aita_parser.add_argument("--api", help="Send results to API endpoint")
    aita_parser.add_argument("--api-key", help="API key for authentication")
    
    # Interactive stats command
    stats_parser = subparsers.add_parser("stats", help="Interactive statistics and analysis for a BlueSky user")
    stats_parser.add_argument("handle", help="BlueSky handle (e.g., @username)")
    
    # Analytics command
    analytics_parser = subparsers.add_parser("analytics", help="Get detailed engagement analytics for a BlueSky user")
    analytics_parser.add_argument("handle", help="BlueSky handle (e.g., @username)")
    analytics_parser.add_argument("--limit", type=int, default=100, help="Number of posts to analyze (default: 100)")
    analytics_parser.add_argument("--since", help="Start date (YYYY-MM-DD)")
    analytics_parser.add_argument("--until", help="End date (YYYY-MM-DD)")
    analytics_parser.add_argument("--use-cache", action="store_true", help="Use cached posts if available")
    analytics_parser.add_argument("--export", help="Export results to file (CSV or JSON)")
    
    # Posting time analysis command
    posting_time_parser = subparsers.add_parser("posting-time", help="Analyze optimal posting times for a BlueSky user")
    posting_time_parser.add_argument("handle", help="BlueSky handle (e.g., @username)")
    posting_time_parser.add_argument("--limit", type=int, default=200, help="Number of posts to analyze (default: 200)")
    posting_time_parser.add_argument("--since", help="Start date (YYYY-MM-DD)")
    posting_time_parser.add_argument("--until", help="End date (YYYY-MM-DD)")
    posting_time_parser.add_argument("--use-cache", action="store_true", help="Use cached posts if available")
    posting_time_parser.add_argument("--export", help="Export results to file (CSV or JSON)")
    
    # Batch analysis command
    batch_parser = subparsers.add_parser("batch", help="Perform batch analysis on multiple BlueSky users")
    batch_parser.add_argument("handles", help="File with list of handles, one per line")
    batch_parser.add_argument("--type", choices=["engagement", "posting_time", "vibe", "summary"], 
                             default="engagement", help="Type of analysis to perform (default: engagement)")
    batch_parser.add_argument("--limit", type=int, default=100, help="Posts to analyze per user (default: 100)")
    batch_parser.add_argument("--export", help="Export results to file (JSON)")
    
    # Compare users command
    compare_parser = subparsers.add_parser("compare", help="Compare engagement metrics between multiple BlueSky users")
    compare_parser.add_argument("handles", nargs="+", help="BlueSky handles to compare (e.g., @user1 @user2)")
    compare_parser.add_argument("--limit", type=int, default=100, help="Posts to analyze per user (default: 100)")
    compare_parser.add_argument("--export", help="Export results to file (CSV or JSON)")
    
    # Follower ratios command
    ratios_parser = subparsers.add_parser("follower-ratios", help="Analyze follower-to-following ratios")
    ratios_parser.add_argument("handle", help="BlueSky handle (e.g., @username)")
    ratios_parser.add_argument("--max", type=int, default=100, help="Maximum number of users to analyze (default: 100)")
    ratios_parser.add_argument("--min-following", type=int, default=20, help="Minimum following count for ratio calculation (default: 20)")
    ratios_parser.add_argument("--export", help="Export results to file (JSON)")
    
    # Manage data command and subcommands
    manage_parser = subparsers.add_parser("manage-data", help="Manage cached data and profiles")
    manage_subparsers = manage_parser.add_subparsers(dest="manage_command", help="Data management commands")
    
    # Clear cache subcommand
    clear_cache_parser = manage_subparsers.add_parser("clear-cache", help="Clear cached data")
    clear_cache_parser.add_argument("--handle", help="Clear cache for specific handle (default: all)")
    
    # Export data subcommand
    export_parser = manage_subparsers.add_parser("export", help="Export data to markdown")
    export_parser.add_argument("handle", help="BlueSky handle (e.g., @username)")
    export_parser.add_argument("--output-dir", help="Output directory (default: auto-generated)")
    
    # Pull missing followers subcommand
    missing_followers_parser = manage_subparsers.add_parser("pull-missing-followers", help="Pull missing or stale follower profiles")
    missing_followers_parser.add_argument("handle", help="BlueSky handle (e.g., @username)")
    missing_followers_parser.add_argument("--max-age", type=int, default=336, help="Max cache age in hours (default: 336, 14 days)")
    missing_followers_parser.add_argument("--batch-size", type=int, default=10, help="Batch size for API requests (default: 10)")
    
    # Pull missing following subcommand
    missing_following_parser = manage_subparsers.add_parser("pull-missing-following", help="Pull missing or stale following profiles")
    missing_following_parser.add_argument("handle", help="BlueSky handle (e.g., @username)")
    missing_following_parser.add_argument("--max-age", type=int, default=336, help="Max cache age in hours (default: 336, 14 days)")
    missing_following_parser.add_argument("--batch-size", type=int, default=10, help="Batch size for API requests (default: 10)")
    
    args = parser.parse_args()
    
    # Default to help if no command provided
    if not args.command:
        parser.print_help()
        sys.exit(1)
        
    console = Console()
    
    try:
        # Initialize the BlueSky API client
        bsky = XaiBskySummarizer()
        
        # Authenticate, if possible
        try:
            if os.path.exists(os.path.expanduser("~/.xai/bsky_credentials.json")):
                bsky.authenticate_bsky()
        except Exception as auth_error:
            console.print(f"[yellow]Warning: Could not authenticate: {auth_error}[/yellow]")
            
        formatter = CLIFormatter()
        
        # Function to handle API sending if needed
        def send_to_api_if_needed(data):
            if hasattr(args, 'api') and args.api:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console
                ) as progress:
                    progress.add_task(description="Sending to API...", total=None)
                    api_response = bsky.send_to_api(
                        data,
                        args.api,
                        api_key=args.api_key if hasattr(args, 'api_key') else None
                    )
                console.print("[green]Successfully sent data to API[/green]")
                return api_response
            return None
        
        # Helper function to parse date arguments
        def parse_date_arg(date_str):
            if not date_str:
                return None
                
            try:
                return datetime.fromisoformat(date_str)
            except ValueError:
                try:
                    return datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    console.print(f"[red]Error: Invalid date format '{date_str}'. Expected format: YYYY-MM-DD[/red]")
                    sys.exit(1)
        
        if args.command == "profile":
            formatter.print_header(f"Profile for @{args.handle}")
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                progress.add_task(description="Fetching profile...", total=None)
                profile = bsky.get_profile(args.handle)
            console.print(formatter.format_profile(profile))
            send_to_api_if_needed(profile)
            
        elif args.command == "posts":
            formatter.print_header(f"Recent Posts from @{args.handle}")
            
            # Parse date arguments
            start_date = parse_date_arg(args.since) if hasattr(args, 'since') else None
            end_date = parse_date_arg(args.until) if hasattr(args, 'until') else None
            
            # Handle date range description for output
            date_range_desc = ""
            if start_date and end_date:
                date_range_desc = f" from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
            elif start_date:
                date_range_desc = f" since {start_date.strftime('%Y-%m-%d')}"
            elif end_date:
                date_range_desc = f" until {end_date.strftime('%Y-%m-%d')}"
            
            # Get posts
            posts = []
            if hasattr(args, 'use_cache') and args.use_cache:
                # Try to use cached posts first
                posts = bsky.get_cached_posts(args.handle)
                console.print(f"[cyan]Using {len(posts)} cached posts for @{args.handle}[/cyan]")
                
                # If date filtering is applied, filter the cached posts
                if start_date or end_date:
                    filtered_posts = []
                    for post in posts:
                        post_view = post.get("post", {})
                        record = post_view.get("record", {})
                        
                        if "createdAt" in record:
                            try:
                                post_date = datetime.fromisoformat(record["createdAt"].replace("Z", "+00:00"))
                                if start_date and post_date < start_date:
                                    continue
                                if end_date and post_date > end_date:
                                    continue
                                filtered_posts.append(post)
                            except:
                                pass
                    posts = filtered_posts
                    console.print(f"[cyan]Filtered to {len(posts)} posts{date_range_desc}[/cyan]")
            
            # If no cached posts or not using cache, fetch posts
            if not posts:
                console.print(f"[cyan]Fetching posts for @{args.handle}{date_range_desc}...[/cyan]")
                posts = bsky.get_all_posts(
                    args.handle,
                    max_posts=args.limit,
                    start_date=start_date,
                    end_date=end_date
                )
            
            # Sort posts
            if hasattr(args, 'sort'):
                sort_by = args.sort
                reverse = not args.asc if hasattr(args, 'asc') else True
                
                sort_dir = "ascending" if not reverse else "descending"
                console.print(f"[cyan]Sorting posts by {sort_by} in {sort_dir} order...[/cyan]")
                
                posts = bsky.sort_posts(posts, sort_by=sort_by, reverse=reverse)
            
            # Display posts
            for post in posts[:args.limit]:
                post_view = post.get("post", {})
                console.print(formatter.format_post(post_view))
                console.print("─" * min(os.get_terminal_size().columns, 100))
                
            send_to_api_if_needed({"handle": args.handle, "posts": posts[:args.limit]})
            
        elif args.command == "summary":
            formatter.print_header(f"Summary of @{args.handle}'s Recent Posts")
            
            # Parse date arguments
            start_date = parse_date_arg(args.since) if hasattr(args, 'since') else None
            end_date = parse_date_arg(args.until) if hasattr(args, 'until') else None
            
            # Get posts
            posts = []
            if hasattr(args, 'use_cache') and args.use_cache:
                posts = bsky.get_cached_posts(args.handle)
                console.print(f"[cyan]Using {len(posts)} cached posts for @{args.handle}[/cyan]")
                
                # Apply date filtering if needed
                if start_date or end_date:
                    filtered_posts = []
                    for post in posts:
                        post_view = post.get("post", {})
                        record = post_view.get("record", {})
                        
                        if "createdAt" in record:
                            try:
                                post_date = datetime.fromisoformat(record["createdAt"].replace("Z", "+00:00"))
                                if start_date and post_date < start_date:
                                    continue
                                if end_date and post_date > end_date:
                                    continue
                                filtered_posts.append(post)
                            except:
                                pass
                    posts = filtered_posts
            
            if not posts:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TaskProgressColumn(),
                    console=console
                ) as progress:
                    task1 = progress.add_task("Fetching posts...", total=100)
                    posts = bsky.get_all_posts(
                        args.handle,
                        max_posts=args.limit,
                        start_date=start_date,
                        end_date=end_date
                    )
                    progress.update(task1, advance=75)
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console
            ) as progress:
                progress.add_task(description="Generating summary...", total=None)
                posts_text = bsky.get_post_content(posts)
                summary = bsky.summarize_text(posts_text)
            
            console.print(Panel(summary, title="Summary", border_style="green"))
            send_to_api_if_needed({"handle": args.handle, "summary": summary})
            
        elif args.command == "vibe":
            formatter.print_header(f"Vibe Check for @{args.handle}")
            
            # Parse date arguments
            start_date = parse_date_arg(args.since) if hasattr(args, 'since') else None
            end_date = parse_date_arg(args.until) if hasattr(args, 'until') else None
            
            # Get posts
            posts = []
            if hasattr(args, 'use_cache') and args.use_cache:
                posts = bsky.get_cached_posts(args.handle)
                console.print(f"[cyan]Using {len(posts)} cached posts for @{args.handle}[/cyan]")
                
                # Apply date filtering if needed
                if start_date or end_date:
                    filtered_posts = []
                    for post in posts:
                        post_view = post.get("post", {})
                        record = post_view.get("record", {})
                        
                        if "createdAt" in record:
                            try:
                                post_date = datetime.fromisoformat(record["createdAt"].replace("Z", "+00:00"))
                                if start_date and post_date < start_date:
                                    continue
                                if end_date and post_date > end_date:
                                    continue
                                filtered_posts.append(post)
                            except:
                                pass
                    posts = filtered_posts
            
            if not posts:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TaskProgressColumn(),
                    console=console
                ) as progress:
                    task1 = progress.add_task("Fetching posts...", total=100)
                    posts = bsky.get_all_posts(
                        args.handle,
                        max_posts=args.limit,
                        start_date=start_date,
                        end_date=end_date
                    )
                    progress.update(task1, advance=50)
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console
            ) as progress:
                progress.add_task(description="Analyzing vibes...", total=None)
                posts_text = bsky.get_post_content(posts)
                vibe = bsky.vibe_check(posts_text)
            
            console.print(Panel(vibe, title="Vibe Check Results", border_style="magenta"))
            send_to_api_if_needed({"handle": args.handle, "vibe_check": vibe})
            
        elif args.command == "followers":
            formatter.print_header(f"Followers of @{args.handle}")
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                progress.add_task(description="Fetching followers...", total=None)
                followers_data = bsky.get_followers(args.handle, limit=args.limit)
            
            followers = followers_data.get("followers", [])
            console.print(formatter.format_user_list(followers))
            send_to_api_if_needed(followers_data)
            
        elif args.command == "following":
            formatter.print_header(f"Accounts @{args.handle} is Following")
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                progress.add_task(description="Fetching following...", total=None)
                following_data = bsky.get_follows(args.handle, limit=args.limit)
            
            follows = following_data.get("follows", [])
            console.print(formatter.format_user_list(follows))
            send_to_api_if_needed(following_data)
            
        elif args.command == "batch-followers":
            formatter.print_header(f"Batch Collecting Followers for @{args.handle}")
            console.print("[yellow]This may take a while depending on the number of followers...[/yellow]")
            
            max_display = "all" if args.max == 0 else args.max
            console.print(f"Collecting up to [cyan]{max_display}[/cyan] followers with [cyan]{args.concurrency}[/cyan] concurrent requests...")
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console
            ) as progress:
                task1 = progress.add_task("Collecting followers...", total=None)
                start_time = time.time()
                followers = bsky.get_all_followers(
                    args.handle, 
                    max_results=args.max,
                    concurrency=args.concurrency,
                    batch_size=args.batch_size
                )
                end_time = time.time()
            
            console.print(f"[green]Collected[/green] [cyan]{len(followers):,}[/cyan] [green]followers in[/green] [cyan]{end_time - start_time:.2f}[/cyan] [green]seconds.[/green]")
            
            # Save to CSV
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                progress.add_task(description=f"Saving followers to {args.output}...", total=None)
                if bsky.save_user_list_to_csv(followers, args.output):
                    console.print(f"[green]Successfully saved[/green] [cyan]{len(followers):,}[/cyan] [green]followers to[/green] [cyan]{args.output}[/cyan]")
                else:
                    console.print(f"[red]Failed to save followers to {args.output}[/red]")
                    
            send_to_api_if_needed({"handle": args.handle, "followers": followers})
            
        elif args.command == "batch-following":
            formatter.print_header(f"Batch Collecting Following for @{args.handle}")
            console.print("[yellow]This may take a while depending on the number of accounts...[/yellow]")
            
            max_display = "all" if args.max == 0 else args.max
            console.print(f"Collecting up to [cyan]{max_display}[/cyan] accounts with [cyan]{args.concurrency}[/cyan] concurrent requests...")
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console
            ) as progress:
                task1 = progress.add_task("Collecting following...", total=None)
                start_time = time.time()
                follows = bsky.get_all_follows(
                    args.handle, 
                    max_results=args.max,
                    concurrency=args.concurrency,
                    batch_size=args.batch_size
                )
                end_time = time.time()
            
            console.print(f"[green]Collected[/green] [cyan]{len(follows):,}[/cyan] [green]accounts in[/green] [cyan]{end_time - start_time:.2f}[/cyan] [green]seconds.[/green]")
            
            # Save to CSV
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                progress.add_task(description=f"Saving accounts to {args.output}...", total=None)
                if bsky.save_user_list_to_csv(follows, args.output):
                    console.print(f"[green]Successfully saved[/green] [cyan]{len(follows):,}[/cyan] [green]accounts to[/green] [cyan]{args.output}[/cyan]")
                else:
                    console.print(f"[red]Failed to save accounts to {args.output}[/red]")
                    
            send_to_api_if_needed({"handle": args.handle, "following": follows})
            
        elif args.command == "search-posts":
            formatter.print_header(f"Search Results for Posts: '{args.query}'")
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                progress.add_task(description="Searching posts...", total=None)
                search_results = bsky.search_posts(args.query, limit=args.limit)
            
            for post in search_results.get("posts", [])[:args.limit]:
                console.print(formatter.format_post(post))
                console.print("─" * min(os.get_terminal_size().columns, 100))
                
            send_to_api_if_needed(search_results)
                
        elif args.command == "search-users":
            formatter.print_header(f"Search Results for Users: '{args.query}'")
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                progress.add_task(description="Searching users...", total=None)
                search_results = bsky.search_users(args.query, limit=args.limit)
            
            users = search_results.get("actors", [])
            console.print(formatter.format_user_list(users))
            
            send_to_api_if_needed(search_results)
            
        elif args.command == "am-i-being-an-asshole":
            formatter.print_header(f"Behavior Analysis for @{args.handle}")
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console
            ) as progress:
                task1 = progress.add_task("Fetching posts...", total=100)
                posts = bsky.get_all_posts(args.handle, max_posts=args.limit)
                progress.update(task1, advance=60)
                
                progress.update(task1, description="Analyzing behavior...")
                posts_text = bsky.get_post_content(posts)
                analysis = bsky.analyze_comment_behavior(posts_text, limit=args.limit)
                progress.update(task1, advance=40)
            
            verdict = analysis["verdict"]
            verdict_color = "red" if verdict == "YES" else "green"
            
            console.print(f"\n[bold {verdict_color}]Verdict: {verdict}[/bold {verdict_color}]")
            console.print(Panel(analysis["analysis"], title="Behavior Analysis", border_style=verdict_color))
            
            send_to_api_if_needed({"handle": args.handle, "behavior_analysis": analysis})
            
        elif args.command == "stats":
            formatter.print_header(f"Interactive Statistics for @{args.handle}")
            
            # Get user profile
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                progress.add_task(description="Fetching profile...", total=None)
                profile = bsky.get_profile(args.handle)
            
            console.print(formatter.format_profile(profile))
            
            # Interactive mode
            while True:
                # Display menu options
                formatter.print_section("Analysis Options")
                console.print("[1] Fetch Posts")
                console.print("[2] View Most Liked Posts")
                console.print("[3] View Most Replied Posts")
                console.print("[4] View Posts by Date Range")
                console.print("[5] Generate Vibe Check")
                console.print("[6] Generate Summary")
                console.print("[7] Quit")
                
                # Get user choice
                choice = IntPrompt.ask("Select an option", choices=["1", "2", "3", "4", "5", "6", "7"])
                
                if choice == 1:
                    # Ask how many posts to fetch
                    num_posts = IntPrompt.ask("How many posts to fetch?", default=100)
                    
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        BarColumn(),
                        TaskProgressColumn(),
                        console=console
                    ) as progress:
                        task1 = progress.add_task(f"Fetching {num_posts} posts...", total=None)
                        posts = bsky.get_all_posts(args.handle, max_posts=num_posts)
                    
                    console.print(f"[green]Successfully fetched [cyan]{len(posts)}[/cyan] posts for @{args.handle}[/green]")
                    
                elif choice == 2:
                    # Check if we have cached posts
                    posts = bsky.get_cached_posts(args.handle)
                    
                    if not posts:
                        # If no cached posts, ask how many to fetch
                        num_posts = IntPrompt.ask("No cached posts found. How many posts to fetch?", default=100)
                        
                        with Progress(
                            SpinnerColumn(),
                            TextColumn("[progress.description]{task.description}"),
                            BarColumn(),
                            TaskProgressColumn(),
                            console=console
                        ) as progress:
                            task1 = progress.add_task(f"Fetching {num_posts} posts...", total=None)
                            posts = bsky.get_all_posts(args.handle, max_posts=num_posts)
                    
                    # Sort by likes
                    sorted_posts = bsky.sort_posts(posts, sort_by="likes", reverse=True)
                    
                    # Display top 10 posts by likes
                    formatter.print_section("Most Liked Posts")
                    for i, post in enumerate(sorted_posts[:10], 1):
                        post_view = post.get("post", {})
                        like_count = post_view.get("likeCount", 0)
                        console.print(f"[cyan]#{i} - {like_count} likes[/cyan]")
                        console.print(formatter.format_post(post_view))
                        console.print("─" * min(os.get_terminal_size().columns, 100))
                    
                elif choice == 3:
                    # Check if we have cached posts
                    posts = bsky.get_cached_posts(args.handle)
                    
                    if not posts:
                        # If no cached posts, ask how many to fetch
                        num_posts = IntPrompt.ask("No cached posts found. How many posts to fetch?", default=100)
                        
                        with Progress(
                            SpinnerColumn(),
                            TextColumn("[progress.description]{task.description}"),
                            BarColumn(),
                            TaskProgressColumn(),
                            console=console
                        ) as progress:
                            task1 = progress.add_task(f"Fetching {num_posts} posts...", total=None)
                            posts = bsky.get_all_posts(args.handle, max_posts=num_posts)
                    
                    # Sort by replies
                    sorted_posts = bsky.sort_posts(posts, sort_by="replies", reverse=True)
                    
                    # Display top 10 posts by replies
                    formatter.print_section("Most Replied Posts")
                    for i, post in enumerate(sorted_posts[:10], 1):
                        post_view = post.get("post", {})
                        reply_count = post_view.get("replyCount", 0)
                        console.print(f"[cyan]#{i} - {reply_count} replies[/cyan]")
                        console.print(formatter.format_post(post_view))
                        console.print("─" * min(os.get_terminal_size().columns, 100))
                    
                elif choice == 4:
                    # Ask for date range
                    start_date_str = Prompt.ask("Start date (YYYY-MM-DD or leave empty)", default="")
                    end_date_str = Prompt.ask("End date (YYYY-MM-DD or leave empty)", default="")
                    
                    start_date = parse_date_arg(start_date_str) if start_date_str else None
                    end_date = parse_date_arg(end_date_str) if end_date_str else None
                    
                    # Ask how many posts to fetch
                    num_posts = IntPrompt.ask("How many posts to fetch? (0 for all)", default=100)
                    
                    # Get posts within date range
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        BarColumn(),
                        TaskProgressColumn(),
                        console=console
                    ) as progress:
                        task1 = progress.add_task("Fetching posts...", total=None)
                        posts = bsky.get_all_posts(
                            args.handle,
                            max_posts=num_posts,
                            start_date=start_date,
                            end_date=end_date
                        )
                    
                    # Display posts
                    date_range_desc = ""
                    if start_date and end_date:
                        date_range_desc = f"from {start_date_str} to {end_date_str}"
                    elif start_date:
                        date_range_desc = f"since {start_date_str}"
                    elif end_date:
                        date_range_desc = f"until {end_date_str}"
                    
                    formatter.print_section(f"Posts {date_range_desc}")
                    
                    if not posts:
                        console.print("[yellow]No posts found in this date range.[/yellow]")
                    else:
                        for post in posts[:10]:  # Show only first 10 posts
                            post_view = post.get("post", {})
                            console.print(formatter.format_post(post_view))
                            console.print("─" * min(os.get_terminal_size().columns, 100))
                        
                        if len(posts) > 10:
                            console.print(f"[cyan]...and {len(posts) - 10} more posts[/cyan]")
                    
                elif choice == 5:
                    # Check if we have cached posts
                    posts = bsky.get_cached_posts(args.handle)
                    
                    if not posts:
                        # If no cached posts, ask how many to fetch
                        num_posts = IntPrompt.ask("No cached posts found. How many posts to fetch?", default=100)
                        
                        with Progress(
                            SpinnerColumn(),
                            TextColumn("[progress.description]{task.description}"),
                            BarColumn(),
                            TaskProgressColumn(),
                            console=console
                        ) as progress:
                            task1 = progress.add_task(f"Fetching {num_posts} posts...", total=None)
                            posts = bsky.get_all_posts(args.handle, max_posts=num_posts)
                    
                    # Generate vibe check
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        console=console
                    ) as progress:
                        progress.add_task(description="Analyzing vibes...", total=None)
                        posts_text = bsky.get_post_content(posts)
                        vibe = bsky.vibe_check(posts_text)
                    
                    console.print(Panel(vibe, title="Vibe Check Results", border_style="magenta"))
                    
                elif choice == 6:
                    # Check if we have cached posts
                    posts = bsky.get_cached_posts(args.handle)
                    
                    if not posts:
                        # If no cached posts, ask how many to fetch
                        num_posts = IntPrompt.ask("No cached posts found. How many posts to fetch?", default=100)
                        
                        with Progress(
                            SpinnerColumn(),
                            TextColumn("[progress.description]{task.description}"),
                            BarColumn(),
                            TaskProgressColumn(),
                            console=console
                        ) as progress:
                            task1 = progress.add_task(f"Fetching {num_posts} posts...", total=None)
                            posts = bsky.get_all_posts(args.handle, max_posts=num_posts)
                    
                    # Generate summary
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        console=console
                    ) as progress:
                        progress.add_task(description="Generating summary...", total=None)
                        posts_text = bsky.get_post_content(posts)
                        summary = bsky.summarize_text(posts_text)
                    
                    console.print(Panel(summary, title="Summary", border_style="green"))
                    
                elif choice == 7:
                    # Exit
                    console.print("[cyan]Goodbye![/cyan]")
                    return  # Using return instead of break
            
        elif args.command == "analytics":
            formatter.print_header(f"Engagement Analytics for @{args.handle}")
            
            # Parse date arguments
            start_date = parse_date_arg(args.since) if hasattr(args, 'since') else None
            end_date = parse_date_arg(args.until) if hasattr(args, 'until') else None
            
            # Handle date range description for output
            date_range_desc = ""
            if start_date and end_date:
                date_range_desc = f" from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
            elif start_date:
                date_range_desc = f" since {start_date.strftime('%Y-%m-%d')}"
            elif end_date:
                date_range_desc = f" until {end_date.strftime('%Y-%m-%d')}"
            
            # Get posts
            posts = []
            if hasattr(args, 'use_cache') and args.use_cache:
                posts = bsky.get_cached_posts(args.handle)
                if posts:
                    console.print(f"[cyan]Using {len(posts)} cached posts for @{args.handle}[/cyan]")
                    
                    # Apply date filtering if needed
                    if start_date or end_date:
                        filtered_posts = []
                        for post in posts:
                            post_view = post.get("post", {})
                            record = post_view.get("record", {})
                            
                            if "createdAt" in record:
                                try:
                                    post_date = datetime.fromisoformat(record["createdAt"].replace("Z", "+00:00"))
                                    if start_date and post_date < start_date:
                                        continue
                                    if end_date and post_date > end_date:
                                        continue
                                    filtered_posts.append(post)
                                except:
                                    pass
                        posts = filtered_posts
                        console.print(f"[cyan]Filtered to {len(posts)} posts{date_range_desc}[/cyan]")
            
            if not posts:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TaskProgressColumn(),
                    TimeRemainingColumn(),
                    console=console
                ) as progress:
                    task = progress.add_task(f"[cyan]Fetching posts for @{args.handle}{date_range_desc}...[/cyan]", total=None)
                    posts = bsky.get_all_posts(
                        args.handle,
                        max_posts=args.limit,
                        start_date=start_date,
                        end_date=end_date
                    )
                    progress.update(task, completed=1)
            
            # Analyze engagement
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console
            ) as progress:
                task = progress.add_task(f"[cyan]Analyzing engagement for {len(posts)} posts...[/cyan]", total=None)
                analytics = bsky.analyze_post_engagement(posts)
                progress.update(task, completed=1)
            
            # Display analytics results
            console.print("\n[bold cyan]Engagement Analytics[/bold cyan]")
            console.print(f"[green]Total Posts:[/green] {analytics['total_posts']:,}")
            console.print(f"[green]Total Engagement:[/green] {analytics['total_engagement']:,} interactions")
            
            # Create table for average metrics
            table = Table(title="Engagement Metrics", show_header=True, header_style="bold cyan")
            table.add_column("Metric", style="cyan")
            table.add_column("Average Per Post", style="green", justify="right")
            table.add_column("Total", style="blue", justify="right")
            table.add_column("Posts With (%)", style="magenta", justify="right")
            
            table.add_row(
                "Likes",
                f"{analytics['avg_likes_per_post']:.2f}",
                f"{analytics['total_likes']:,}",
                f"{analytics['posts_with_likes_pct']:.1f}%"
            )
            table.add_row(
                "Replies",
                f"{analytics['avg_replies_per_post']:.2f}",
                f"{analytics['total_replies']:,}",
                f"{analytics['posts_with_replies_pct']:.1f}%"
            )
            table.add_row(
                "Reposts",
                f"{analytics['avg_reposts_per_post']:.2f}",
                f"{analytics['total_reposts']:,}",
                f"{analytics['posts_with_reposts_pct']:.1f}%"
            )
            table.add_row(
                "Total Engagement",
                f"{analytics['avg_engagement_per_post']:.2f}",
                f"{analytics['total_engagement']:,}",
                ""
            )
            
            console.print(table)
            
            # Display top performing posts
            console.print("\n[bold cyan]Top Performing Posts[/bold cyan]")
            for i, post_data in enumerate(analytics['top_performing_posts'], 1):
                console.print(f"[bold cyan]#{i} - {post_data['engagement']} total engagement[/bold cyan]")
                console.print(f"  [green]Likes:[/green] {post_data['likes']} | [blue]Replies:[/blue] {post_data['replies']} | [magenta]Reposts:[/magenta] {post_data['reposts']}")
                post_view = post_data.get('post', {})
                record = post_view.get('record', {})
                text = record.get('text', '')
                console.print(f"  {text[:100]}{'...' if len(text) > 100 else ''}")
                console.print("")
            
            # Export if requested
            if hasattr(args, 'export') and args.export:
                export_path = args.export
                try:
                    if export_path.endswith('.json'):
                        with open(export_path, 'w', encoding='utf-8') as f:
                            json.dump(analytics, f, indent=2)
                    elif export_path.endswith('.csv'):
                        with open(export_path, 'w', newline='', encoding='utf-8') as f:
                            writer = csv.writer(f)
                            writer.writerow(['Metric', 'Value'])
                            for key, value in analytics.items():
                                if key != 'top_performing_posts':
                                    writer.writerow([key, value])
                    else:
                        export_path += '.json'
                        with open(export_path, 'w', encoding='utf-8') as f:
                            json.dump(analytics, f, indent=2)
                            
                    console.print(f"[green]Analytics exported to {export_path}[/green]")
                except Exception as e:
                    console.print(f"[red]Error exporting analytics: {e}[/red]")
            
            send_to_api_if_needed(analytics)
            
        elif args.command == "posting-time":
            formatter.print_header(f"Posting Time Analysis for @{args.handle}")
            
            # Parse date arguments
            start_date = parse_date_arg(args.since) if hasattr(args, 'since') else None
            end_date = parse_date_arg(args.until) if hasattr(args, 'until') else None
            
            # Handle date range description for output
            date_range_desc = ""
            if start_date and end_date:
                date_range_desc = f" from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
            elif start_date:
                date_range_desc = f" since {start_date.strftime('%Y-%m-%d')}"
            elif end_date:
                date_range_desc = f" until {end_date.strftime('%Y-%m-%d')}"
            
            # Get posts
            posts = []
            if hasattr(args, 'use_cache') and args.use_cache:
                posts = bsky.get_cached_posts(args.handle)
                if posts:
                    console.print(f"[cyan]Using {len(posts)} cached posts for @{args.handle}[/cyan]")
                    
                    # Apply date filtering if needed
                    if start_date or end_date:
                        filtered_posts = []
                        for post in posts:
                            post_view = post.get("post", {})
                            record = post_view.get("record", {})
                            
                            if "createdAt" in record:
                                try:
                                    post_date = datetime.fromisoformat(record["createdAt"].replace("Z", "+00:00"))
                                    if start_date and post_date < start_date:
                                        continue
                                    if end_date and post_date > end_date:
                                        continue
                                    filtered_posts.append(post)
                                except:
                                    pass
                        posts = filtered_posts
                        console.print(f"[cyan]Filtered to {len(posts)} posts{date_range_desc}[/cyan]")
            
            if not posts:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TaskProgressColumn(),
                    TimeRemainingColumn(),
                    console=console
                ) as progress:
                    task = progress.add_task(f"[cyan]Fetching posts for @{args.handle}{date_range_desc}...[/cyan]", total=None)
                    posts = bsky.get_all_posts(
                        args.handle,
                        max_posts=args.limit,
                        start_date=start_date,
                        end_date=end_date
                    )
                    progress.update(task, completed=1)
            
            # Analyze posting times
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console
            ) as progress:
                task = progress.add_task(f"[cyan]Analyzing posting times for {len(posts)} posts...[/cyan]", total=None)
                time_analysis = bsky.analyze_posting_time_patterns(posts)
                progress.update(task, completed=1)
            
            if "error" in time_analysis:
                console.print(f"[red]Error: {time_analysis['error']}[/red]")
                return
            
            # Display time analysis results
            console.print(f"\n[bold cyan]Posting Time Analysis for @{args.handle}[/bold cyan]")
            console.print(f"[green]Posts Analyzed:[/green] {time_analysis['total_posts_with_timestamp']:,}")
            
            # Display posting frequency by day
            console.print("\n[bold cyan]Posting Frequency by Day[/bold cyan]")
            day_table = Table(show_header=True, header_style="bold cyan")
            day_table.add_column("Day", style="cyan")
            day_table.add_column("Posts", style="green", justify="right")
            day_table.add_column("Avg Engagement", style="magenta", justify="right")
            
            for day, count in time_analysis["posting_frequency_by_day"].items():
                day_table.add_row(
                    day,
                    str(count),
                    f"{time_analysis['avg_engagement_by_day'][day]:.2f}"
                )
            
            console.print(day_table)
            
            # Display posting frequency by hour
            console.print("\n[bold cyan]Posting Frequency by Hour[/bold cyan]")
            
            # Create a more compact hour display with bars
            hour_data = []
            for hour in sorted(time_analysis["posting_frequency_by_hour"].keys(), 
                              key=lambda h: int(h.split()[0]) + (0 if h.endswith('AM') or h == '12 PM' else 12) - (12 if h == '12 AM' else 0)):
                count = time_analysis["posting_frequency_by_hour"][hour]
                engagement = time_analysis["avg_engagement_by_hour"][hour]
                hour_data.append((hour, count, engagement))
            
            # Find max count for scaling
            max_count = max(c for _, c, _ in hour_data) if hour_data else 1
            
            hour_table = Table(show_header=True, header_style="bold cyan", width=min(os.get_terminal_size().columns - 4, 80))
            hour_table.add_column("Hour", style="cyan", width=10)
            hour_table.add_column("Count", style="green", justify="right", width=6)
            hour_table.add_column("Histogram", width=40)
            hour_table.add_column("Engagement", style="magenta", justify="right", width=10)
            
            for hour, count, engagement in hour_data:
                bar_length = int((count / max_count) * 40)
                bar = "█" * bar_length
                hour_table.add_row(
                    hour,
                    str(count),
                    Text(bar, style="green"),
                    f"{engagement:.2f}"
                )
            
            console.print(hour_table)
            
            # Display optimal posting times
            console.print("\n[bold cyan]Recommended Posting Times[/bold cyan]")
            console.print("[yellow]Based on historical engagement patterns:[/yellow]")
            
            for i, time_slot in enumerate(time_analysis["optimal_posting_times"][:5], 1):
                console.print(f"{i}. [bold green]{time_slot['day']} at {time_slot['hour']}[/bold green] - Expected engagement: {time_slot['avg_engagement']:.2f}")
            
            console.print("\n[bold cyan]Best Days by Engagement[/bold cyan]")
            for day in time_analysis["best_days_by_engagement"]:
                console.print(f"[green]{day}[/green] - {time_analysis['avg_engagement_by_day'][day]:.2f} avg engagement")
            
            console.print("\n[bold cyan]Best Hours by Engagement[/bold cyan]")
            for hour in time_analysis["best_hours_by_engagement"]:
                console.print(f"[green]{hour}[/green] - {time_analysis['avg_engagement_by_hour'][hour]:.2f} avg engagement")
            
            # Export if requested
            if hasattr(args, 'export') and args.export:
                export_path = args.export
                try:
                    if export_path.endswith('.json'):
                        with open(export_path, 'w', encoding='utf-8') as f:
                            json.dump(time_analysis, f, indent=2)
                    elif export_path.endswith('.csv'):
                        with open(export_path, 'w', newline='', encoding='utf-8') as f:
                            writer = csv.writer(f)
                            writer.writerow(['Day', 'Posts', 'Avg Engagement'])
                            for day in time_analysis["posting_frequency_by_day"].keys():
                                writer.writerow([
                                    day, 
                                    time_analysis["posting_frequency_by_day"][day],
                                    time_analysis["avg_engagement_by_day"][day]
                                ])
                            
                            writer.writerow([])
                            writer.writerow(['Hour', 'Posts', 'Avg Engagement'])
                            for hour in sorted(time_analysis["posting_frequency_by_hour"].keys()):
                                writer.writerow([
                                    hour, 
                                    time_analysis["posting_frequency_by_hour"][hour],
                                    time_analysis["avg_engagement_by_hour"][hour]
                                ])
                    else:
                        export_path += '.json'
                        with open(export_path, 'w', encoding='utf-8') as f:
                            json.dump(time_analysis, f, indent=2)
                            
                    console.print(f"[green]Time analysis exported to {export_path}[/green]")
                except Exception as e:
                    console.print(f"[red]Error exporting time analysis: {e}[/red]")
                send_to_api_if_needed(time_analysis)
                    
            elif analytics_choice == 5:
                # Back to analytics menu
                pass  # Remove continue
                    
            elif choice == 5:
                # Settings & Data menu
                console.print("\n[bold cyan]Settings & Data Options[/bold cyan]")
                console.print("[1] Clear Cache")
                console.print("[2] Change User") 
                console.print("[3] Manage Data")
                console.print("[4] Back to Main Menu")
                
                settings_choice = IntPrompt.ask("Select an option", choices=["1", "2", "3", "4"])
                
                if settings_choice == 1:
                    # Clear cache
                    console.print("\n[bold cyan]Clear Cache[/bold cyan]")
                    console.print("[1] Clear cache for this user")
                    console.print("[2] Clear all cache")
                    console.print("[3] Back")
                    
                    clear_choice = IntPrompt.ask("What would you like to clear?", choices=["1", "2", "3"])
                    
                    if clear_choice == 1:
                        if Confirm.ask(f"Are you sure you want to clear cache for @{handle}?"):
                            summarizer.clear_cache(handle)
                    elif clear_choice == 2:
                        if Confirm.ask("Are you sure you want to clear all cache?"):
                            summarizer.clear_cache()
                    elif clear_choice == 3:
                        pass  # was continue
                
                elif settings_choice == 2:
                    # Change user to analyze
                    new_handle = Prompt.ask("Enter BlueSky handle to analyze (e.g., @username)")
                    handle = new_handle
                    console.print(f"[green]Now analyzing: @{handle}[/green]")
                
                elif settings_choice == 3:
                    # Manage data submenu
                    console.print("\n[bold cyan]Manage Data Options[/bold cyan]")
                    console.print("[1] Export All Data")
                    console.print("[2] Pull Missing Followers")
                    console.print("[3] Pull Missing Following")
                    console.print("[4] Back")
                    
                    manage_choice = IntPrompt.ask("Select an option", choices=["1", "2", "3", "4"])
                    
                    if manage_choice == 1:
                        # Export all data
                        output_dir = Prompt.ask("Output directory (leave empty for default)")
                        summarizer.export_all(handle, output_dir if output_dir else None)
                    
                    elif manage_choice == 2:
                        # Pull missing followers
                        console.print(f"[cyan]Pulling missing or stale follower profiles for @{handle}[/cyan]")
                        
                        # Configure options
                        max_age = IntPrompt.ask("Maximum cache age in hours (default: 336, 14 days)", default=336)
                        batch_size = IntPrompt.ask("Batch size for updates", default=10)
                        
                        # Fetch missing followers
                        missing_handles = summarizer.find_missing_cached_profiles(handle, profile_type="followers", max_cache_age_hours=max_age)
                        if missing_handles:
                            console.print(f"[yellow]Found {len(missing_handles)} missing followers:[/yellow]")
                            for i, handle in enumerate(missing_handles[:10], 1):
                                console.print(f"  {i}. {handle}")
                            
                            if len(missing_handles) > 10:
                                console.print(f"  ...and {len(missing_handles)-10} more")
                            
                            if Confirm.ask("Would you like to update these profiles?"):
                                with Progress(
                                    SpinnerColumn(),
                                    TextColumn("[progress.description]{task.description}"),
                                    BarColumn(),
                                    TaskProgressColumn(),
                                    TimeRemainingColumn(),
                                    console=console
                                ) as progress:
                                    task = progress.add_task("Updating profiles...", total=None)
                                    update_stats = summarizer.update_missing_profiles(missing_handles, batch_size=batch_size)
                                    progress.update(task, completed=1)
                                    
                                    if update_stats['success']:
                                        console.print(f"[green]Successfully updated {update_stats['updated']} profiles and found {update_stats['failed']} failures.[/green]")
                                    else:
                                        console.print(f"[red]Failed to update profiles: {update_stats['failed']} profiles failed to update.[/red]")
                        else:
                            console.print("[green]No missing or stale follower profiles found.[/green]")
                    
                    elif manage_choice == 3:
                        # Pull missing following
                        console.print(f"[cyan]Pulling missing or stale following profiles for @{handle}[/cyan]")
                        # Configure options
                        max_age = IntPrompt.ask("Maximum cache age in hours (default: 336, 14 days)", default=336)
                        batch_size = IntPrompt.ask("Batch size for updates", default=10)
                        
                        # Fetch missing following
                        missing_handles = summarizer.find_missing_cached_profiles(handle, profile_type="following", max_cache_age_hours=max_age)
                        if missing_handles:
                            console.print(f"[yellow]Found {len(missing_handles)} missing following:[/yellow]")
                            for i, handle in enumerate(missing_handles[:10], 1):
                                console.print(f"  {i}. {handle}")
                            
                            if len(missing_handles) > 10:
                                console.print(f"  ...and {len(missing_handles)-10} more")
                            
                            if Confirm.ask("Would you like to update these profiles?"):
                                with Progress(
                                    SpinnerColumn(),
                                    TextColumn("[progress.description]{task.description}"),
                                    BarColumn(),
                                    TaskProgressColumn(),
                                    TimeRemainingColumn(),
                                    console=console
                                ) as progress:
                                    task = progress.add_task("Updating profiles...", total=None)
                                    update_stats = summarizer.update_missing_profiles(missing_handles, batch_size=batch_size)
                                    progress.update(task, completed=1)
                                    
                                    if update_stats['success']:
                                        console.print(f"[green]Successfully updated {update_stats['updated']} profiles and found {update_stats['failed']} failures.[/green]")
                                    else:
                                        console.print(f"[red]Failed to update profiles: {update_stats['failed']} profiles failed to update.[/red]")
                        else:
                            console.print("[green]No missing or stale following profiles found.[/green]")
                    
                    elif manage_choice == 4:
                        # Back to settings menu
                        pass  # Remove continue
                
                elif settings_choice == 4:
                    # Back to main menu
                    pass  # Remove continue
                    
            elif choice == 6:
                # Exit
                console.print("[green]Goodbye![/green]")
                return  # Using return instead of break
            
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}", style="red")
        if hasattr(e, 'traceback'):
            console.print(e.traceback)

# Call main() when this script is run directly
def main():
    """
    Main entry point for the XAI BlueSky Tools
    Ensures the CLI is launched when the script is run directly
    """
    run_cli()

if __name__ == "__main__":
    main()