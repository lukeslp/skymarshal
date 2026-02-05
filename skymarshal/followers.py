"""
Skymarshal Followers Manager

File Purpose: Manage follower ranking and analysis
Primary Functions/Classes: FollowerManager
Inputs and Outputs (I/O): Bluesky API for follower data

This module provides functionality to fetch, rank, and analyze followers.
It uses ThreadPoolExecutor for concurrent profile fetching to ensure performance.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional
import time

from rich.progress import SpinnerColumn, TextColumn
from .models import console, safe_progress
from .auth import AuthenticationError

class FollowerManager:
    """Manages follower ranking and analysis."""

    def __init__(self, auth_manager, settings_manager):
        self.auth = auth_manager
        self.settings = settings_manager

    def get_followers(self, actor_did: str, limit: int = None) -> List[Dict]:
        """Retrieve followers for a given actor using pagination."""
        followers = []
        cursor = None
        
        # Batch size for getFollowers is usually 100
        batch_size = 100

        with safe_progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
            console=console,
        ) as progress:
            task = progress.add_task("Fetching followers...", total=None)
            
            while True:
                if limit and len(followers) >= limit:
                    break
                
                try:
                    # Using the atproto SDK client
                    # We might need to access the rawXRPC client or use the high-level methods
                    # self.auth.client.app.bsky.graph.get_followers (if available)
                    
                    # Fallback to direct xrpc if methods differ in version
                    params = {
                        "actor": actor_did,
                        "limit": min(batch_size, limit - len(followers)) if limit else batch_size
                    }
                    if cursor:
                        params["cursor"] = cursor

                    # Calling the SDK method
                    resp = self.auth.client.app.bsky.graph.get_followers(params)
                    
                    batch = getattr(resp, "followers", [])
                    if not batch:
                        break
                        
                    followers.extend(batch)
                    progress.update(task, description=f"Fetching followers... ({len(followers)})")
                    
                    cursor = getattr(resp, "cursor", None)
                    if not cursor:
                        break
                        
                except Exception as e:
                    console.print(f"[yellow]Error fetching followers: {e}[/]")
                    break

        return followers[:limit] if limit else followers

    def get_profiles_batch(self, dids: List[str]) -> List[Dict]:
        """Fetch profiles for a list of DIDs in parallel batches."""
        if not dids:
            return []

        all_profiles = []
        batch_size = 25 # API limit
        batches = [dids[i : i + batch_size] for i in range(0, len(dids), batch_size)]
        
        # We can use parallelism here if needed, though get_profiles takes a list
        # so mostly we just need to batch the calls.
        # However, making multiple network requests in parallel speeds this up.
        
        def fetch_batch(batch_dids):
            try:
                resp = self.auth.client.app.bsky.actor.get_profiles({"actors": batch_dids})
                return getattr(resp, "profiles", [])
            except Exception as e:
                # console.print(f"[yellow]Warning: Profile batch fetch failed: {e}[/]")
                return []

        with safe_progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
            console=console,
        ) as progress:
            task = progress.add_task("Fetching detailed profiles...", total=len(batches))
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(fetch_batch, batch): batch for batch in batches}
                
                for future in as_completed(futures):
                    result = future.result()
                    all_profiles.extend(result)
                    progress.advance(task)

        return all_profiles

    def rank_followers(self, target_did: str, limit: int = None) -> List[Dict]:
        """Rank followers by follower count (descending)."""
        console.print(f"[dim]Step 1: Fetching followers list...[/]")
        followers_raw = self.get_followers(target_did, limit)
        
        if not followers_raw:
            return []
            
        follower_dids = [getattr(f, "did") for f in followers_raw if hasattr(f, "did")]
        
        console.print(f"[dim]Step 2: Fetching details for {len(follower_dids)} profiles...[/]")
        profiles = self.get_profiles_batch(follower_dids)
        
        # Convert to a convenient dict structure
        ranked_data = []
        for p in profiles:
            followers_count = getattr(p, "followers_count", 0) or 0
            following_count = getattr(p, "follows_count", 0) or 0
            
            # Helper for ratio
            ratio = followers_count / following_count if following_count > 0 else 0
            
            ranked_data.append({
                "handle": getattr(p, "handle", "unknown"),
                "display_name": getattr(p, "display_name", ""),
                "did": getattr(p, "did", ""),
                "followers_count": followers_count,
                "following_count": following_count,
                "posts_count": getattr(p, "posts_count", 0) or 0,
                "description": getattr(p, "description", ""),
                "avatar": getattr(p, "avatar", ""),
                "ratio": ratio
            })
            
        # Sort by follower count descending
        ranked_data.sort(key=lambda x: x["followers_count"], reverse=True)
        return ranked_data

    def analyze_quality(self, ranked_data: List[Dict], top_n: int = 20) -> List[Dict]:
        """Identify high-quality (selective) followers."""
        # Filter for active accounts (some threshold)
        active = [d for d in ranked_data if d["following_count"] > 0 and d["followers_count"] > 5]
        
        # Sort by following count (ascending) - selective followers
        active.sort(key=lambda x: x["following_count"])
        return active[:top_n]
