#!/usr/bin/env python3
"""
Bluesky Following Cleaner - Bot/Spam Account Cleanup Tool
=========================================================

Purpose: Analyzes accounts YOU follow to identify potential bots/spam accounts
         based on follower-to-following ratios and provides interactive unfollowing.
Author: Lucas "Luke" Steuber
Created: 2025-01-27

This tool helps you clean up your following list by identifying accounts with
suspicious follower-to-following ratios that may be bots or spam accounts.

Features:
- Analyzes accounts YOU are following (not your followers)
- Identifies accounts with poor follower-to-following ratios
- Interactive unfollowing with individual review or bulk options
- Smart caching system for fast subsequent runs
- Safety measures to prevent accidental mass unfollowing

Usage: python bluesky_cleaner.py --username your.username --password your_password
"""

import asyncio
import argparse
import json
import sys
import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional
import aiohttp
import time
import re

class BlueskyFollowingCleaner:
    """
    Analyzes accounts you follow to identify potential bots/spam for cleanup.
    
    Features:
    - Smart caching system (SQLite database) - eliminates redundant API calls
    - Batch processing (25 profiles per request - API confirmed limit)
    - Optimized rate limiting (respects 3000 req/5min limit)
    - Interactive unfollowing with safety measures
    - Persistent profile database shared across all runs
    - Progress tracking for long-running operations
    - Comprehensive error handling
    """
    
    def __init__(self, username: str, password: str, db_path: str = "bluesky_profiles.db"):
        self.username = username
        self.password = password
        self.base_url = "https://public.api.bsky.app"
        self.session = None
        self.access_token = None
        self.did = None
        self.batch_size = 25  # API limit is actually 25 profiles per batch
        self.following_batch_size = 100  # API max for getFollows is 100 per request
        self.rate_limit_delay = 0.05  # Reduced delay - API has generous limits
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
            
            # Create index for faster lookups
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_profiles_handle ON profiles(handle)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_profiles_followers ON profiles(followers_count DESC)")
            
            conn.commit()
            conn.close()
            print(f"📦 Database initialized: {self.db_path}")
            
        except Exception as e:
            print(f"❌ Database initialization error: {str(e)}")
    
    def get_cached_profiles(self, dids: List[str]) -> Dict[str, Dict]:
        """Retrieve cached profiles from database."""
        if not dids:
            return {}
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Query for cached profiles
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
            print(f"❌ Error retrieving cached profiles: {str(e)}")
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
            print(f"💾 Cached {len(profiles)} profiles to database")
            
        except Exception as e:
            print(f"❌ Error caching profiles: {str(e)}")
    
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
            print(f"❌ Error getting cache stats: {str(e)}")
            return {'total_profiles': 0, 'popular_profiles': 0, 'max_followers': 0}
        
    async def authenticate(self) -> bool:
        """Authenticate with Bluesky AT Protocol using provided credentials."""
        auth_url = "https://bsky.social/xrpc/com.atproto.server.createSession"
        
        async with aiohttp.ClientSession() as session:
            try:
                auth_data = {
                    "identifier": self.username,
                    "password": self.password
                }
                
                async with session.post(auth_url, json=auth_data) as response:
                    if response.status == 200:
                        auth_result = await response.json()
                        self.access_token = auth_result.get('accessJwt')
                        self.did = auth_result.get('did')
                        print(f"✅ Successfully authenticated as {self.username}")
                        return True
                    else:
                        error_text = await response.text()
                        print(f"❌ Authentication failed: {response.status} - {error_text}")
                        return False
                        
            except Exception as e:
                print(f"❌ Authentication error: {str(e)}")
                return False
    
    async def get_following(self, actor_did: str, limit: int = None) -> List[Dict]:
        """
        Retrieve accounts that a given actor follows using paginated requests.
        
        Args:
            actor_did (str): The DID of the actor whose following to retrieve
            limit (int): Maximum number of following to retrieve (None for unlimited)
            
        Returns:
            List[Dict]: List of following data dictionaries
        """
        following = []
        cursor = None
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
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
                                
                            print(f"📥 Retrieved {len(following)} accounts you follow so far...")
                            await asyncio.sleep(self.rate_limit_delay)
                            
                        else:
                            error_text = await response.text()
                            print(f"❌ Error retrieving following: {response.status} - {error_text}")
                            break
                            
                except Exception as e:
                    print(f"❌ Error during following retrieval: {str(e)}")
                    break
        
        print(f"✅ Retrieved {len(following)} total accounts you follow")
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
            print(f"🔄 Found {len(cached_dids)} profiles in cache, fetching {len(uncached_dids)} from API")
        
        # Fetch uncached profiles from API
        if uncached_dids:
            url = f"{self.base_url}/xrpc/app.bsky.actor.getProfiles"
            headers = {
                'Authorization': f'Bearer {self.access_token}',
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
                            print(f"❌ Error retrieving profiles batch: {response.status} - {error_text}")
                            
                except Exception as e:
                    print(f"❌ Error during batch profile retrieval: {str(e)}")
        
        return all_profiles
    
    async def analyze_following_for_cleanup(self, max_following: int = None) -> List[Dict]:
        """
        Main function to analyze accounts you follow for potential cleanup.
        
        Args:
            max_following (int): Maximum number of following accounts to analyze (None for unlimited)
            
        Returns:
            List[Dict]: List of suspicious accounts with their stats
        """
        limit_text = f"up to {max_following:,}" if max_following else "all"
        print(f"🧹 Starting cleanup analysis for accounts you follow ({limit_text} accounts)")
        
        # Get accounts you follow
        following = await self.get_following(self.did, max_following)
        if not following:
            print("❌ No following accounts found or error retrieving following")
            return []
        
        # Extract DIDs for batch processing
        following_dids = [account.get('did') for account in following if account.get('did')]
        
        print(f"📊 Processing {len(following_dids)} accounts you follow in batches of {self.batch_size}...")
        
        # Process following in batches to get detailed profiles
        analyzed_accounts = []
        
        for i in range(0, len(following_dids), self.batch_size):
            batch_dids = following_dids[i:i + self.batch_size]
            batch_profiles = await self.get_profiles_batch(batch_dids)
            
            for profile in batch_profiles:
                followers_count = profile.get('followersCount', 0)
                following_count = profile.get('followsCount', 0)
                
                # Calculate ratio (lower = more suspicious)
                ratio = followers_count / following_count if following_count > 0 else 0
                
                account_data = {
                    'handle': profile.get('handle', 'unknown'),
                    'display_name': profile.get('displayName', ''),
                    'did': profile.get('did', ''),
                    'followers_count': followers_count,
                    'following_count': following_count,
                    'posts_count': profile.get('postsCount', 0),
                    'ratio': ratio,
                    'description': profile.get('description', '')[:100] + '...' if profile.get('description', '') else 'No bio'
                }
                analyzed_accounts.append(account_data)
            
            print(f"⏳ Processed {min(i + self.batch_size, len(following_dids))}/{len(following_dids)} accounts")
            
            # Rate limiting
            if i + self.batch_size < len(following_dids):
                await asyncio.sleep(self.rate_limit_delay)
        
        # Sort by ratio (ascending - worst ratios first)
        analyzed_accounts.sort(key=lambda x: x['ratio'])
        
        print(f"✅ Successfully analyzed {len(analyzed_accounts)} accounts you follow!")
        return analyzed_accounts
    
    async def get_follow_record_uri(self, target_did: str) -> tuple:
        """Find the follow record URI and rkey for a given target DID, paginating through all records if needed."""
        url = f"{self.base_url}/xrpc/com.atproto.repo.listRecords"
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        params = {
            "repo": self.did,
            "collection": "app.bsky.graph.follow",
            "limit": 1000
        }
        cursor = None
        print(f"🔍 Searching for follow record for DID: {target_did}")
        async with aiohttp.ClientSession() as session:
            while True:
                if cursor:
                    params["cursor"] = cursor
                else:
                    params.pop("cursor", None)
                try:
                    async with session.get(url, headers=headers, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            records = data.get("records", [])
                            for record in records:
                                value = record.get("value", {})
                                if value.get("subject") == target_did:
                                    uri = record.get("uri")
                                    rkey = record.get("rkey")
                                    print(f"✅ Found follow record for {target_did}: rkey={rkey}")
                                    return uri, rkey
                            cursor = data.get("cursor")
                            if not cursor or not records:
                                print(f"⚠️  Reached end of follow records, record not found for {target_did}")
                                break
                        else:
                            error_text = await response.text()
                            print(f"❌ Error finding follow record for {target_did}: {response.status} - {error_text}")
                            break
                except Exception as e:
                    print(f"❌ Exception while finding follow record for {target_did}: {str(e)}")
                    break
        return None, None
    
    async def unfollow_account(self, target_did: str, handle: str) -> bool:
        """Unfollow a single account using the AT Protocol deleteRecord API."""
        # Find the follow record
        uri, rkey = await self.get_follow_record_uri(target_did)
        if not rkey:
            print(f"  ❌ Could not find follow record for @{handle}. You may not be following them.")
            return False
        
        url = f"{self.base_url}/xrpc/com.atproto.repo.deleteRecord"
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        payload = {
            "repo": self.did,
            "collection": "app.bsky.graph.follow",
            "rkey": rkey
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        print(f"  ✅ Unfollowed @{handle}")
                        return True
                    else:
                        error_text = await response.text()
                        print(f"  ❌ Failed to unfollow @{handle}: {response.status} - {error_text}")
                        return False
            except Exception as e:
                print(f"  ❌ Error unfollowing @{handle}: {str(e)}")
                return False
    
    async def cleanup_following_interactive(self, suspicious_accounts: List[Dict]):
        """Interactive cleanup functionality for suspicious accounts you follow."""
        if not suspicious_accounts:
            print("🎉 No suspicious accounts found in your following list!")
            return

        print(f"\n🧹 FOLLOWING CLEANUP ASSISTANT")
        print("=" * 60)
        print(f"Found {len(suspicious_accounts)} accounts with poor follower ratios (potential bots/spam).")
        print("These are accounts YOU are following that may be bots or inactive accounts.")
        print("\nOptions:")
        print("  1. Review each account individually (recommended)")
        print("  2. Unfollow ALL suspicious accounts in bulk")
        print("  3. Cancel (do nothing)")
        
        while True:
            choice = input("\nEnter your choice (1/2/3): ").strip()
            if choice in ["1", "2", "3"]:
                break
            print("Please enter 1, 2, or 3.")
        
        if choice == "3":
            print("Cleanup operation cancelled.")
            return
        
        successful_unfollows = 0
        failed_unfollows = 0
        
        if choice == "1":
            # Individual review mode
            print(f"\n📋 INDIVIDUAL REVIEW MODE")
            print("=" * 40)
            print("You'll be shown each suspicious account and can choose whether to unfollow.")
            print("Press Ctrl+C at any time to stop.\n")
            
            for i, account in enumerate(suspicious_accounts, 1):
                try:
                    handle = account.get('handle', 'unknown')
                    display_name = account.get('display_name', '')
                    followers_count = account.get('followers_count', 0)
                    following_count = account.get('following_count', 0)
                    ratio = account.get('ratio', 0)
                    description = account.get('description', 'No bio')
                    
                    print(f"\n[{i}/{len(suspicious_accounts)}] @{handle}")
                    if display_name:
                        print(f"  Name: {display_name}")
                    print(f"  Followers: {followers_count:,}")
                    print(f"  Following: {following_count:,}")
                    print(f"  Ratio: {ratio:.3f} (suspicious: < 0.1)")
                    if description and description != 'No bio':
                        print(f"  Bio: {description}")
                    
                    while True:
                        action = input("  Action: [u]nfollow / [s]kip / [q]uit: ").strip().lower()
                        if action in ['u', 's', 'q']:
                            break
                        print("  Please enter 'u' to unfollow, 's' to skip, or 'q' to quit.")
                    
                    if action == 'q':
                        print("Review stopped by user.")
                        break
                    elif action == 'u':
                        did = account.get('did')
                        if did:
                            success = await self.unfollow_account(did, handle)
                            if success:
                                successful_unfollows += 1
                            else:
                                failed_unfollows += 1
                        else:
                            print(f"  ❌ No DID found for @{handle}")
                            failed_unfollows += 1
                    else:
                        print(f"  ⏭️  Skipped @{handle}")
                        
                except KeyboardInterrupt:
                    print("\n\n⚠️  Review interrupted by user.")
                    break
                except Exception as e:
                    print(f"  ❌ Error processing @{handle}: {str(e)}")
                    failed_unfollows += 1
        
        elif choice == "2":
            # Bulk unfollow mode
            print(f"\n⚠️  BULK UNFOLLOW MODE")
            print("=" * 40)
            print(f"You are about to unfollow ALL {len(suspicious_accounts)} suspicious accounts.")
            print("This action cannot be undone easily!")
            
            confirm = input(f"\nAre you sure you want to unfollow all {len(suspicious_accounts)} accounts? [yes/no]: ").strip().lower()
            if confirm not in ['yes', 'y']:
                print("Bulk unfollow cancelled.")
                return
            
            print(f"\n🔄 Unfollowing {len(suspicious_accounts)} accounts...")
            
            for i, account in enumerate(suspicious_accounts, 1):
                handle = account.get('handle', 'unknown')
                did = account.get('did')
                
                print(f"[{i}/{len(suspicious_accounts)}] Processing @{handle}...")
                
                if did:
                    success = await self.unfollow_account(did, handle)
                    if success:
                        successful_unfollows += 1
                    else:
                        failed_unfollows += 1
                else:
                    print(f"  ❌ No DID found for @{handle}")
                    failed_unfollows += 1
                
                # Small delay to avoid rate limiting
                await asyncio.sleep(0.1)
        
        # Summary
        print(f"\n📊 CLEANUP SUMMARY")
        print("=" * 30)
        print(f"✅ Successfully unfollowed: {successful_unfollows}")
        print(f"❌ Failed to unfollow: {failed_unfollows}")
        print(f"📱 Total processed: {successful_unfollows + failed_unfollows}")
        
        if successful_unfollows > 0:
            print(f"\n🎉 You've cleaned up {successful_unfollows} problematic accounts from your following list!")
    
    async def cleanup_by_ratio_interactive(self, analyzed_accounts: List[Dict], custom_threshold: float):
        """Interactive cleanup functionality based on custom ratio thresholds."""
        # Filter accounts by custom threshold
        ratio_accounts = [acc for acc in analyzed_accounts if acc['ratio'] < custom_threshold]
        
        if not ratio_accounts:
            print(f"🎉 No accounts found with ratio below {custom_threshold}!")
            return

        print(f"\n📊 RATIO-BASED CLEANUP ASSISTANT")
        print("=" * 60)
        print(f"Found {len(ratio_accounts)} accounts with follower ratio below {custom_threshold}.")
        print("These accounts follow many but have relatively few followers themselves.")
        print("\nRatio Categories:")
        
        # Show ratio distribution
        very_low = [acc for acc in ratio_accounts if acc['ratio'] < 0.01]
        low = [acc for acc in ratio_accounts if 0.01 <= acc['ratio'] < 0.05]
        moderate = [acc for acc in ratio_accounts if 0.05 <= acc['ratio'] < custom_threshold]
        
        print(f"  • Very Low (< 0.01): {len(very_low)} accounts")
        print(f"  • Low (0.01 - 0.05): {len(low)} accounts") 
        print(f"  • Moderate (0.05 - {custom_threshold}): {len(moderate)} accounts")
        
        print("\nCleanup Options:")
        print("  1. Review each account individually")
        print("  2. Unfollow by ratio category")
        print("  3. Unfollow ALL accounts below threshold in bulk")
        print("  4. Cancel (do nothing)")
        
        while True:
            choice = input("\nEnter your choice (1/2/3/4): ").strip()
            if choice in ["1", "2", "3", "4"]:
                break
            print("Please enter 1, 2, 3, or 4.")
        
        if choice == "4":
            print("Ratio-based cleanup cancelled.")
            return
        
        accounts_to_process = []
        
        if choice == "1":
            # Individual review mode - use all ratio accounts
            accounts_to_process = ratio_accounts
            await self._process_accounts_individually(accounts_to_process, "ratio-based")
            
        elif choice == "2":
            # Category-based selection
            print(f"\nSelect ratio category to unfollow:")
            print(f"  1. Very Low only (< 0.01): {len(very_low)} accounts")
            print(f"  2. Low and below (< 0.05): {len(very_low + low)} accounts")
            print(f"  3. All below threshold (< {custom_threshold}): {len(ratio_accounts)} accounts")
            print(f"  4. Cancel")
            
            while True:
                cat_choice = input("\nEnter category choice (1/2/3/4): ").strip()
                if cat_choice in ["1", "2", "3", "4"]:
                    break
                print("Please enter 1, 2, 3, or 4.")
            
            if cat_choice == "4":
                print("Category selection cancelled.")
                return
            elif cat_choice == "1":
                accounts_to_process = very_low
            elif cat_choice == "2":
                accounts_to_process = very_low + low
            elif cat_choice == "3":
                accounts_to_process = ratio_accounts
            
            if accounts_to_process:
                await self._process_accounts_bulk(accounts_to_process, f"ratio category")
            
        elif choice == "3":
            # Bulk unfollow all
            accounts_to_process = ratio_accounts
            await self._process_accounts_bulk(accounts_to_process, f"ratio below {custom_threshold}")
    
    async def _process_accounts_individually(self, accounts: List[Dict], mode_name: str):
        """Process accounts individually with user review."""
        successful_unfollows = 0
        failed_unfollows = 0
        
        print(f"\n📋 INDIVIDUAL {mode_name.upper()} REVIEW")
        print("=" * 50)
        print("You'll be shown each account and can choose whether to unfollow.")
        print("Press Ctrl+C at any time to stop.\n")
        
        for i, account in enumerate(accounts, 1):
            try:
                handle = account.get('handle', 'unknown')
                display_name = account.get('display_name', '')
                followers_count = account.get('followers_count', 0)
                following_count = account.get('following_count', 0)
                ratio = account.get('ratio', 0)
                posts_count = account.get('posts_count', 0)
                description = account.get('description', 'No bio')
                
                print(f"\n[{i}/{len(accounts)}] @{handle}")
                if display_name:
                    print(f"  Name: {display_name}")
                print(f"  Followers: {followers_count:,}")
                print(f"  Following: {following_count:,}")
                print(f"  Posts: {posts_count:,}")
                print(f"  Ratio: {ratio:.3f}")
                
                # Add ratio interpretation
                if ratio < 0.01:
                    print("  📊 Very poor ratio - likely bot/spam")
                elif ratio < 0.05:
                    print("  📊 Poor ratio - possibly inactive")
                elif ratio < 0.1:
                    print("  📊 Below average ratio")
                else:
                    print("  📊 Moderate ratio")
                
                if description and description != 'No bio':
                    print(f"  Bio: {description}")
                
                while True:
                    action = input("  Action: [u]nfollow / [s]kip / [q]uit: ").strip().lower()
                    if action in ['u', 's', 'q']:
                        break
                    print("  Please enter 'u' to unfollow, 's' to skip, or 'q' to quit.")
                
                if action == 'q':
                    print("Review stopped by user.")
                    break
                elif action == 'u':
                    did = account.get('did')
                    if did:
                        success = await self.unfollow_account(did, handle)
                        if success:
                            successful_unfollows += 1
                        else:
                            failed_unfollows += 1
                    else:
                        print(f"  ❌ No DID found for @{handle}")
                        failed_unfollows += 1
                else:
                    print(f"  ⏭️  Skipped @{handle}")
                    
            except KeyboardInterrupt:
                print("\n\n⚠️  Review interrupted by user.")
                break
            except Exception as e:
                print(f"  ❌ Error processing @{handle}: {str(e)}")
                failed_unfollows += 1
        
        self._print_cleanup_summary(successful_unfollows, failed_unfollows, mode_name)
    
    async def _process_accounts_bulk(self, accounts: List[Dict], mode_name: str):
        """Process accounts in bulk with confirmation."""
        print(f"\n⚠️  BULK UNFOLLOW MODE - {mode_name.upper()}")
        print("=" * 50)
        print(f"You are about to unfollow ALL {len(accounts)} accounts in {mode_name}.")
        print("This action cannot be undone easily!")
        
        # Show sample of accounts to be unfollowed
        print(f"\nSample accounts to be unfollowed:")
        for i, account in enumerate(accounts[:5], 1):
            print(f"  {i}. @{account['handle']} (ratio: {account['ratio']:.3f})")
        if len(accounts) > 5:
            print(f"  ... and {len(accounts) - 5} more")
        
        confirm = input(f"\nAre you sure you want to unfollow all {len(accounts)} accounts? [yes/no]: ").strip().lower()
        if confirm not in ['yes', 'y']:
            print("Bulk unfollow cancelled.")
            return
        
        successful_unfollows = 0
        failed_unfollows = 0
        
        print(f"\n🔄 Unfollowing {len(accounts)} accounts...")
        
        for i, account in enumerate(accounts, 1):
            handle = account.get('handle', 'unknown')
            did = account.get('did')
            ratio = account.get('ratio', 0)
            
            print(f"[{i}/{len(accounts)}] Processing @{handle} (ratio: {ratio:.3f})...")
            
            if did:
                success = await self.unfollow_account(did, handle)
                if success:
                    successful_unfollows += 1
                else:
                    failed_unfollows += 1
            else:
                print(f"  ❌ No DID found for @{handle}")
                failed_unfollows += 1
            
            # Small delay to avoid rate limiting
            await asyncio.sleep(0.1)
        
        self._print_cleanup_summary(successful_unfollows, failed_unfollows, mode_name)
    
    def _print_cleanup_summary(self, successful: int, failed: int, mode_name: str):
        """Print cleanup summary statistics."""
        print(f"\n📊 {mode_name.upper()} CLEANUP SUMMARY")
        print("=" * 40)
        print(f"✅ Successfully unfollowed: {successful}")
        print(f"❌ Failed to unfollow: {failed}")
        print(f"📱 Total processed: {successful + failed}")
        
        if successful > 0:
            print(f"\n🎉 You've cleaned up {successful} accounts from your following list using {mode_name} cleanup!")

    async def clean_bottom_n(self, analyzed_accounts: List[Dict], n: int = 50):
        """
        Offer to unfollow the bottom N users by ratio, excluding bots/mods, with interactive or batch review.
        """
        # Exclude obvious bots/mods by handle pattern
        def is_user(account):
            handle = account.get('handle', '').lower()
            # Exclude if handle contains 'bot', 'mod', 'admin', or similar
            return not re.search(r'(bot|mod|admin|system|service)', handle)

        user_accounts = [acc for acc in analyzed_accounts if is_user(acc)]
        user_accounts.sort(key=lambda x: x['ratio'])
        bottom_n = user_accounts[:n]

        if not bottom_n:
            print(f"No user accounts found to clean.")
            return

        print(f"\n🧹 CLEANUP: Bottom {n} users by follower ratio (excluding bots/mods)")
        print("=" * 60)
        for i, acc in enumerate(bottom_n, 1):
            print(f"{i:2d}. @{acc['handle']} - ratio: {acc['ratio']:.3f} ({acc['followers_count']:,}/{acc['following_count']:,})")

        print("\nOptions:")
        print("  1. Review each account individually")
        print("  2. Unfollow ALL {n} accounts in bulk")
        print("  3. Cancel (do nothing)")

        while True:
            choice = input("\nEnter your choice (1/2/3): ").strip()
            if choice in ["1", "2", "3"]:
                break
            print("Please enter 1, 2, or 3.")

        if choice == "3":
            print("Cleanup operation cancelled.")
            return
        elif choice == "1":
            await self._process_accounts_individually(bottom_n, f"bottom {n} ratio")
        elif choice == "2":
            await self._process_accounts_bulk(bottom_n, f"bottom {n} ratio")

async def main():
    """Main CLI function with argument parsing and execution flow."""
    parser = argparse.ArgumentParser(
        description="Clean up your Bluesky following list by identifying and unfollowing bot/spam accounts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic bot cleanup with default threshold (0.1)
  python bluesky_cleaner.py --username your.username --password your_password
  
  # Analyze only first 1000 accounts you follow
  python bluesky_cleaner.py --username your.username --password your_password --max-following 1000
  
  # Use stricter bot detection threshold
  python bluesky_cleaner.py --username your.username --password your_password --threshold 0.05
  
  # Ratio-based cleanup - review all accounts with ratio below 0.2
  python bluesky_cleaner.py --username your.username --password your_password --ratio-cleanup 0.2
  
  # Show ratio distribution in your following list
  python bluesky_cleaner.py --username your.username --password your_password --show-ratio-stats
  
  # Combine ratio stats with ratio cleanup
  python bluesky_cleaner.py --username your.username --password your_password --show-ratio-stats --ratio-cleanup 0.15
        """
    )
    
    parser.add_argument(
        '--username', 
        type=str, 
        required=True,
        help='Your Bluesky username/handle'
    )
    
    parser.add_argument(
        '--password', 
        type=str, 
        required=True,
        help='Your Bluesky password'
    )
    
    parser.add_argument(
        '--max-following', 
        type=int, 
        default=None,
        help='Maximum number of following accounts to analyze (default: unlimited - will process all)'
    )
    
    parser.add_argument(
        '--database', 
        type=str, 
        help='Database path for caching profiles (default: bluesky_profiles.db)',
        default="bluesky_profiles.db"
    )
    
    parser.add_argument(
        '--threshold', 
        type=float, 
        default=0.1,
        help='Follower ratio threshold for suspicious accounts (default: 0.1)'
    )
    
    parser.add_argument(
        '--ratio-cleanup', 
        type=float, 
        help='Enable ratio-based cleanup with custom threshold (e.g., 0.2 for accounts with ratio < 0.2)'
    )
    
    parser.add_argument(
        '--show-ratio-stats', 
        action='store_true',
        help='Show distribution of follower ratios in your following list'
    )
    
    parser.add_argument(
        '--clean',
        nargs='?',
        const=50,
        type=int,
        help='Review and optionally unfollow the bottom N users you follow by ratio (default: 50)'
    )
    
    args = parser.parse_args()
    
    # Initialize the cleaner
    cleaner = BlueskyFollowingCleaner(args.username, args.password, args.database)
    
    # Show cache statistics
    cache_stats = cleaner.get_cache_stats()
    if cache_stats['total_profiles'] > 0:
        print(f"📊 Profile cache: {cache_stats['total_profiles']:,} profiles, {cache_stats['popular_profiles']:,} popular (>1K followers)")
    
    # Authenticate
    if not await cleaner.authenticate():
        print("❌ Authentication failed. Please check your credentials.")
        sys.exit(1)
    
    # Analyze following for cleanup
    analyzed_accounts = await cleaner.analyze_following_for_cleanup(args.max_following)
    
    if not analyzed_accounts:
        print("❌ No accounts to analyze. Exiting.")
        sys.exit(1)
    
    # Show ratio statistics if requested
    if args.show_ratio_stats:
        print(f"\n📊 FOLLOWER RATIO DISTRIBUTION")
        print("=" * 50)
        
        # Calculate ratio distribution
        very_low = [acc for acc in analyzed_accounts if acc['ratio'] < 0.01]
        low = [acc for acc in analyzed_accounts if 0.01 <= acc['ratio'] < 0.05]
        moderate = [acc for acc in analyzed_accounts if 0.05 <= acc['ratio'] < 0.1]
        good = [acc for acc in analyzed_accounts if 0.1 <= acc['ratio'] < 0.5]
        excellent = [acc for acc in analyzed_accounts if acc['ratio'] >= 0.5]
        
        print(f"Very Low (< 0.01): {len(very_low):,} accounts ({(len(very_low) / len(analyzed_accounts) * 100):.1f}%)")
        print(f"Low (0.01 - 0.05): {len(low):,} accounts ({(len(low) / len(analyzed_accounts) * 100):.1f}%)")
        print(f"Moderate (0.05 - 0.1): {len(moderate):,} accounts ({(len(moderate) / len(analyzed_accounts) * 100):.1f}%)")
        print(f"Good (0.1 - 0.5): {len(good):,} accounts ({(len(good) / len(analyzed_accounts) * 100):.1f}%)")
        print(f"Excellent (≥ 0.5): {len(excellent):,} accounts ({(len(excellent) / len(analyzed_accounts) * 100):.1f}%)")
        
        # Show some examples from each category
        if very_low:
            print(f"\nExamples of Very Low ratio accounts:")
            for i, account in enumerate(very_low[:3], 1):
                print(f"  {i}. @{account['handle']} - ratio: {account['ratio']:.4f}")
    
    # Filter suspicious accounts based on threshold
    suspicious_accounts = [acc for acc in analyzed_accounts if acc['ratio'] < args.threshold]
    
    print(f"\n📊 ANALYSIS RESULTS")
    print("=" * 40)
    print(f"Total accounts analyzed: {len(analyzed_accounts):,}")
    print(f"Suspicious accounts (ratio < {args.threshold}): {len(suspicious_accounts):,}")
    print(f"Percentage suspicious: {(len(suspicious_accounts) / len(analyzed_accounts) * 100):.1f}%")
    
    if suspicious_accounts:
        print(f"\n🔍 TOP 10 MOST SUSPICIOUS ACCOUNTS:")
        for i, account in enumerate(suspicious_accounts[:10], 1):
            print(f"  {i:2d}. @{account['handle']} - ratio: {account['ratio']:.3f} ({account['followers_count']:,}/{account['following_count']:,})")
    
    # Determine cleanup mode
    cleanup_performed = False
    
    if args.ratio_cleanup:
        # Custom ratio-based cleanup
        print(f"\n🎯 RATIO-BASED CLEANUP MODE")
        print(f"Threshold: {args.ratio_cleanup}")
        await cleaner.cleanup_by_ratio_interactive(analyzed_accounts, args.ratio_cleanup)
        cleanup_performed = True
        
    elif suspicious_accounts:
        # Standard bot detection cleanup
        print(f"\n🤖 BOT DETECTION CLEANUP MODE")
        print(f"Threshold: {args.threshold}")
        await cleaner.cleanup_following_interactive(suspicious_accounts)
        cleanup_performed = True
    
    if args.clean:
        print(f"\n🧹 CLEANUP MODE: Bottom {args.clean} users by ratio")
        await cleaner.clean_bottom_n(analyzed_accounts, args.clean)
        cleanup_performed = True
    
    if not cleanup_performed:
        if args.ratio_cleanup and not [acc for acc in analyzed_accounts if acc['ratio'] < args.ratio_cleanup]:
            print(f"\n🎉 Great news! No accounts found with ratio below {args.ratio_cleanup}.")
        elif not suspicious_accounts:
            print(f"\n🎉 Great news! No suspicious accounts found in your following list.")
            print("Your following list appears to be clean of obvious bots/spam accounts.")
        
        # Suggest ratio cleanup if no suspicious accounts but there are low-ratio accounts
        if not suspicious_accounts and not args.ratio_cleanup:
            low_ratio_accounts = [acc for acc in analyzed_accounts if acc['ratio'] < 0.2]
            if low_ratio_accounts:
                print(f"\n💡 TIP: Found {len(low_ratio_accounts)} accounts with low ratios (< 0.2).")
                print("    Consider using --ratio-cleanup 0.2 to review these accounts.")
    
    # Show updated cache statistics
    final_cache_stats = cleaner.get_cache_stats()
    print(f"\n📦 Profile cache now contains {final_cache_stats['total_profiles']:,} profiles")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        sys.exit(1) 