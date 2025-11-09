#!/usr/bin/env python3
"""
Bluesky Follower Ranker - CLI Script
====================================

Purpose: Ranks a Bluesky user's followers from most followed to least followed,
         with optional bot detection and quality analysis
Author: Lucas "Luke" Steuber
Created: 2025-01-27

This script efficiently retrieves follower data using batched API calls to 
the Bluesky AT Protocol API and exports a ranked list to a text file.

Features:
- Standard follower ranking by follower count
- Bot indicator analysis (low follower/following ratio)
- Quality follower analysis (selective following behavior)
- Smart caching system for fast subsequent runs

Usage: python bluesky_follower_ranker.py [options]
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

class BlueskyFollowerRanker:
    """
    Efficiently ranks Bluesky followers by their follower count using batch API calls.
    
    Features:
    - Smart caching system (SQLite database) - eliminates redundant API calls
    - Batch processing (25 profiles per request - API confirmed limit)
    - Optimized rate limiting (respects 3000 req/5min limit)
    - Unlimited follower analysis (no artificial caps)
    - Persistent profile database shared across all runs
    - Progress tracking for long-running operations
    - Bot indicator analysis (low follower/following ratios)
    - Quality follower analysis (selective following behavior)
    - Comprehensive error handling
    - Export to formatted text file with multiple analyses
    """
    
    def __init__(self, username: str, password: str, db_path: str = "bluesky_profiles.db"):
        self.username = username
        self.password = password
        self.base_url = "https://public.api.bsky.app"
        self.session = None
        self.access_token = None
        self.batch_size = 25  # API limit is actually 25 profiles per batch (confirmed by error testing)
        self.followers_batch_size = 100  # API max for getFollowers is 100 per request
        self.rate_limit_delay = 0.05  # Reduced delay - API has generous limits (3000 per 5 min)
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """
        Initialize SQLite database for caching profile data.
        
        Creates tables for storing profile information to avoid redundant API calls.
        """
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
        """
        Retrieve cached profiles from database.
        
        Args:
            dids (List[str]): List of DIDs to look up
            
        Returns:
            Dict[str, Dict]: Dictionary mapping DID to profile data for cached profiles
        """
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
        """
        Store profiles in database cache.
        
        Args:
            profiles (List[Dict]): List of profile dictionaries to cache
        """
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
        """
        Get statistics about the profile cache.
        
        Returns:
            Dict[str, int]: Statistics about cached profiles
        """
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
        """
        Authenticate with Bluesky AT Protocol using provided credentials.
        
        Returns:
            bool: True if authentication successful, False otherwise
        """
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
    
    async def get_followers(self, actor_did: str, limit: int = None) -> List[Dict]:
        """
        Retrieve followers for a given actor using paginated requests.
        
        Args:
            actor_did (str): The DID of the actor whose followers to retrieve
            limit (int): Maximum number of followers to retrieve (None for unlimited)
            
        Returns:
            List[Dict]: List of follower data dictionaries
        """
        followers = []
        cursor = None
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
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
                                
                            print(f"📥 Retrieved {len(followers)} followers so far...")
                            await asyncio.sleep(self.rate_limit_delay)
                            
                        else:
                            error_text = await response.text()
                            print(f"❌ Error retrieving followers: {response.status} - {error_text}")
                            break
                            
                except Exception as e:
                    print(f"❌ Error during followers retrieval: {str(e)}")
                    break
        
        print(f"✅ Retrieved {len(followers)} total followers")
        return followers if limit is None else followers[:limit]
    
    async def get_profiles_batch(self, actor_dids: List[str]) -> List[Dict]:
        """
        Efficiently retrieve multiple profiles using cache-first approach.
        
        Args:
            actor_dids (List[str]): List of actor DIDs to retrieve profiles for
            
        Returns:
            List[Dict]: List of profile data dictionaries
        """
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
    
    async def rank_followers(self, target_username: str, max_followers: int = None) -> List[Dict]:
        """
        Main function to rank followers by their follower count.
        
        Args:
            target_username (str): Username/handle to analyze followers for
            max_followers (int): Maximum number of followers to analyze (None for unlimited)
            
        Returns:
            List[Dict]: Ranked list of followers with their stats
        """
        limit_text = f"up to {max_followers:,}" if max_followers else "all"
        print(f"🔍 Starting follower analysis for @{target_username} ({limit_text} followers)")
        
        # Get target user's profile to get their DID
        url = f"{self.base_url}/xrpc/app.bsky.actor.getProfile"
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=headers, params={'actor': target_username}) as response:
                    if response.status == 200:
                        profile_data = await response.json()
                        target_did = profile_data.get('did')
                        print(f"✅ Found target user: {profile_data.get('displayName', target_username)}")
                    else:
                        print(f"❌ Could not find user: {target_username}")
                        return []
            except Exception as e:
                print(f"❌ Error finding target user: {str(e)}")
                return []
        
        # Get followers
        followers = await self.get_followers(target_did, max_followers)
        if not followers:
            print("❌ No followers found or error retrieving followers")
            return []
        
        # Extract DIDs for batch processing
        follower_dids = [follower.get('did') for follower in followers if follower.get('did')]
        
        print(f"📊 Processing {len(follower_dids)} followers in batches of {self.batch_size}...")
        
        # Process followers in batches to get detailed profiles
        ranked_followers = []
        
        for i in range(0, len(follower_dids), self.batch_size):
            batch_dids = follower_dids[i:i + self.batch_size]
            batch_profiles = await self.get_profiles_batch(batch_dids)
            
            for profile in batch_profiles:
                follower_data = {
                    'handle': profile.get('handle', 'unknown'),
                    'display_name': profile.get('displayName', ''),
                    'did': profile.get('did', ''),
                    'followers_count': profile.get('followersCount', 0),
                    'following_count': profile.get('followsCount', 0),
                    'posts_count': profile.get('postsCount', 0),
                    'description': profile.get('description', '')[:100] + '...' if profile.get('description', '') else ''
                }
                ranked_followers.append(follower_data)
            
            print(f"⏳ Processed {min(i + self.batch_size, len(follower_dids))}/{len(follower_dids)} followers")
            
            # Rate limiting
            if i + self.batch_size < len(follower_dids):
                await asyncio.sleep(self.rate_limit_delay)
        
        # Sort by follower count (descending)
        ranked_followers.sort(key=lambda x: x['followers_count'], reverse=True)
        
        print(f"✅ Successfully ranked {len(ranked_followers)} followers!")
        return ranked_followers
    
    def analyze_bot_indicators(self, followers: List[Dict], top_n: int = 20) -> List[Dict]:
        """
        Identify potential bot accounts based on followers-to-following ratio.
        
        Bots typically follow many accounts but have few followers themselves.
        
        Args:
            followers (List[Dict]): List of follower data
            top_n (int): Number of top suspects to return
            
        Returns:
            List[Dict]: Followers sorted by bot likelihood (lowest ratio first)
        """
        bot_suspects = []
        
        for follower in followers:
            followers_count = follower.get('followers_count', 0)
            following_count = follower.get('following_count', 0)
            
            # Skip accounts with no data or very new accounts
            if following_count == 0 or followers_count == 0:
                continue
                
            # Calculate ratio (lower = more bot-like)
            ratio = followers_count / following_count
            
            # Add additional bot indicators
            bot_score = {
                'handle': follower.get('handle', 'unknown'),
                'display_name': follower.get('display_name', ''),
                'followers_count': followers_count,
                'following_count': following_count,
                'posts_count': follower.get('posts_count', 0),
                'ratio': ratio,
                'description': follower.get('description', '')[:100] + '...' if follower.get('description', '') else 'No bio'
            }
            
            bot_suspects.append(bot_score)
        
        # Sort by ratio (ascending - lowest ratios first)
        bot_suspects.sort(key=lambda x: x['ratio'])
        
        print(f"🤖 Analyzed {len(bot_suspects)} followers for bot indicators")
        return bot_suspects[:top_n]
    
    def analyze_quality_followers(self, followers: List[Dict], top_n: int = 20) -> List[Dict]:
        """
        Identify high-quality followers based on selective following behavior.
        
        Quality followers typically follow fewer accounts, indicating selectivity.
        
        Args:
            followers (List[Dict]): List of follower data
            top_n (int): Number of top quality followers to return
            
        Returns:
            List[Dict]: Followers sorted by quality (fewest following first)
        """
        quality_followers = []
        
        for follower in followers:
            followers_count = follower.get('followers_count', 0)
            following_count = follower.get('following_count', 0)
            posts_count = follower.get('posts_count', 0)
            
            # Skip accounts that look inactive or fake
            if following_count == 0 or followers_count < 5:
                continue
                
            quality_score = {
                'handle': follower.get('handle', 'unknown'),
                'display_name': follower.get('display_name', ''),
                'followers_count': followers_count,
                'following_count': following_count,
                'posts_count': posts_count,
                'ratio': followers_count / following_count if following_count > 0 else 0,
                'description': follower.get('description', '')[:100] + '...' if follower.get('description', '') else 'No bio'
            }
            
            quality_followers.append(quality_score)
        
        # Sort by following_count (ascending - fewest following first)
        quality_followers.sort(key=lambda x: x['following_count'])
        
        print(f"⭐ Analyzed {len(quality_followers)} followers for quality indicators")
        return quality_followers[:top_n]
    
    def export_to_file(self, ranked_followers: List[Dict], target_username: str, filename: Optional[str] = None, 
                       bot_analysis: List[Dict] = None, quality_analysis: List[Dict] = None):
        """
        Export ranked followers to a formatted text file.
        
        Args:
            ranked_followers (List[Dict]): Ranked list of followers
            target_username (str): Target username for context
            filename (Optional[str]): Custom filename, auto-generated if None
            bot_analysis (List[Dict]): Optional bot indicator analysis results
            quality_analysis (List[Dict]): Optional quality follower analysis results
        """
        # Create reports directory if it doesn't exist
        reports_dir = "bluesky_reports"
        os.makedirs(reports_dir, exist_ok=True)
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"bluesky_followers_ranked_{target_username}_{timestamp}.txt"
        
        # Ensure filename is in the reports directory
        if not filename.startswith(reports_dir):
            filename = os.path.join(reports_dir, os.path.basename(filename))
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                # Header
                f.write("=" * 80 + "\n")
                f.write(f"BLUESKY FOLLOWER RANKING REPORT\n")
                f.write(f"Target User: @{target_username}\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total Followers Analyzed: {len(ranked_followers)}\n")
                f.write("=" * 80 + "\n\n")
                
                # Quick Summary Section
                if ranked_followers:
                    total_followers = sum(f['followers_count'] for f in ranked_followers)
                    avg_followers = total_followers / len(ranked_followers)
                    
                    # Calculate ratios for summary
                    followers_with_ratios = []
                    for f in ranked_followers:
                        if f['following_count'] > 0:
                            ratio = f['followers_count'] / f['following_count']
                            followers_with_ratios.append({**f, 'ratio': ratio})
                    
                    f.write("QUICK SUMMARY\n")
                    f.write("-" * 40 + "\n")
                    f.write(f"Most Followed: @{ranked_followers[0]['handle']} ({ranked_followers[0]['followers_count']:,} followers)\n")
                    f.write(f"Average Followers: {avg_followers:,.0f}\n")
                    f.write(f"Total Combined Followers: {total_followers:,}\n")
                    
                    if followers_with_ratios:
                        best_ratio = max(followers_with_ratios, key=lambda x: x['ratio'])
                        worst_ratio = min(followers_with_ratios, key=lambda x: x['ratio'])
                        f.write(f"Best Ratio: @{best_ratio['handle']} ({best_ratio['ratio']:.2f})\n")
                        f.write(f"Worst Ratio: @{worst_ratio['handle']} ({worst_ratio['ratio']:.3f})\n")
                    
                    if bot_analysis:
                        f.write(f"Bot Analysis: {len(bot_analysis)} potential bots identified\n")
                    if quality_analysis:
                        f.write(f"Quality Analysis: {len(quality_analysis)} selective followers identified\n")
                    
                    f.write("\n" + "=" * 80 + "\n\n")
                
                # Rankings
                for i, follower in enumerate(ranked_followers, 1):
                    f.write(f"#{i:3d} | @{follower['handle']}\n")
                    if follower['display_name']:
                        f.write(f"      Name: {follower['display_name']}\n")
                    f.write(f"      Followers: {follower['followers_count']:,}\n")
                    f.write(f"      Following: {follower['following_count']:,}\n")
                    f.write(f"      Posts: {follower['posts_count']:,}\n")
                    if follower['description']:
                        f.write(f"      Bio: {follower['description']}\n")
                    f.write("-" * 60 + "\n")
                
                # Bot Analysis Section
                if bot_analysis:
                    f.write("\n" + "=" * 80 + "\n")
                    f.write("POTENTIAL BOT INDICATORS\n")
                    f.write("=" * 80 + "\n")
                    f.write("Followers with low followers-to-following ratios (potential bots)\n")
                    f.write("Lower ratios indicate accounts that follow many but are followed by few\n\n")
                    
                    for i, bot in enumerate(bot_analysis, 1):
                        f.write(f"#{i:2d} | @{bot['handle']}\n")
                        if bot['display_name']:
                            f.write(f"      Name: {bot['display_name']}\n")
                        f.write(f"      Followers: {bot['followers_count']:,}\n")
                        f.write(f"      Following: {bot['following_count']:,}\n")
                        f.write(f"      Ratio: {bot['ratio']:.3f} (followers/following)\n")
                        f.write(f"      Posts: {bot['posts_count']:,}\n")
                        if bot['description'] and bot['description'] != 'No bio':
                            f.write(f"      Bio: {bot['description']}\n")
                        f.write("-" * 60 + "\n")
                
                # Quality Analysis Section
                if quality_analysis:
                    f.write("\n" + "=" * 80 + "\n")
                    f.write("HIGH-QUALITY FOLLOWERS\n")
                    f.write("=" * 80 + "\n")
                    f.write("Followers who follow very few accounts (selective/engaged followers)\n")
                    f.write("These users are typically more discerning about who they follow\n\n")
                    
                    for i, quality in enumerate(quality_analysis, 1):
                        f.write(f"#{i:2d} | @{quality['handle']}\n")
                        if quality['display_name']:
                            f.write(f"      Name: {quality['display_name']}\n")
                        f.write(f"      Followers: {quality['followers_count']:,}\n")
                        f.write(f"      Following: {quality['following_count']:,} (selective!)\n")
                        f.write(f"      Ratio: {quality['ratio']:.2f}\n")
                        f.write(f"      Posts: {quality['posts_count']:,}\n")
                        if quality['description'] and quality['description'] != 'No bio':
                            f.write(f"      Bio: {quality['description']}\n")
                        f.write("-" * 60 + "\n")

                # Summary statistics
                f.write("\n" + "=" * 80 + "\n")
                f.write("SUMMARY STATISTICS\n")
                f.write("=" * 80 + "\n")
                
                if ranked_followers:
                    total_followers = sum(f['followers_count'] for f in ranked_followers)
                    avg_followers = total_followers / len(ranked_followers)
                    
                    f.write(f"Most Followed: @{ranked_followers[0]['handle']} ({ranked_followers[0]['followers_count']:,} followers)\n")
                    f.write(f"Average Followers: {avg_followers:,.0f}\n")
                    f.write(f"Total Combined Followers: {total_followers:,}\n")
                    
                    # Analysis summaries
                    if bot_analysis:
                        lowest_ratio = bot_analysis[0]['ratio'] if bot_analysis else 0
                        f.write(f"Most Suspicious Bot (lowest ratio): @{bot_analysis[0]['handle']} ({lowest_ratio:.3f})\n")
                    
                    if quality_analysis:
                        most_selective = quality_analysis[0]['following_count'] if quality_analysis else 0
                        f.write(f"Most Selective Follower: @{quality_analysis[0]['handle']} (follows {most_selective:,})\n")
                    
                    # Top 10 summary
                    f.write(f"\nTOP 10 MOST FOLLOWED:\n")
                    for i, follower in enumerate(ranked_followers[:10], 1):
                        f.write(f"{i:2d}. @{follower['handle']} - {follower['followers_count']:,} followers\n")
            
            print(f"✅ Exported ranking to: {filename}")
            
        except Exception as e:
            print(f"❌ Error exporting to file: {str(e)}")

async def main():
    """
    Main CLI function with argument parsing and execution flow.
    """
    parser = argparse.ArgumentParser(
        description="Rank Bluesky user's followers by their follower count",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python bluesky_follower_ranker.py --target lukesteuber.substack.com
  python bluesky_follower_ranker.py --target someuser.bsky.social --max-followers 5000
  python bluesky_follower_ranker.py --target user.bsky.social --output custom_ranking.txt
  python bluesky_follower_ranker.py --target bigaccount.bsky.social  # Process ALL followers
  python bluesky_follower_ranker.py --target user.bsky.social --database my_cache.db
  
  # Include bot analysis (low follower/following ratio)
  python bluesky_follower_ranker.py --target user.bsky.social --bot-analysis
  
  # Include quality analysis (selective followers)
  python bluesky_follower_ranker.py --target user.bsky.social --quality-analysis
  
  # Run all analyses with custom count
  python bluesky_follower_ranker.py --target user.bsky.social --bot-analysis --quality-analysis --analysis-count 30
        """
    )
    
    parser.add_argument(
        '--target', 
        type=str, 
        help='Target Bluesky username/handle to analyze followers for (default: authenticated user)',
        default=None
    )
    
    parser.add_argument(
        '--max-followers', 
        type=int, 
        default=None,
        help='Maximum number of followers to analyze (default: unlimited - will process all followers)'
    )
    
    parser.add_argument(
        '--output', 
        type=str, 
        help='Output filename (default: auto-generated with timestamp)',
        default=None
    )
    
    parser.add_argument(
        '--database', 
        type=str, 
        help='Database path for caching profiles (default: bluesky_profiles.db)',
        default="bluesky_profiles.db"
    )
    
    parser.add_argument(
        '--bot-analysis', 
        action='store_true',
        help='Include bot indicator analysis (low follower-to-following ratio)'
    )
    
    parser.add_argument(
        '--quality-analysis', 
        action='store_true',
        help='Include quality follower analysis (users who follow few accounts)'
    )
    
    parser.add_argument(
        '--analysis-count', 
        type=int, 
        default=20,
        help='Number of results to show in bot/quality analyses (default: 20)'
    )
    
    args = parser.parse_args()
    
    # Initialize the ranker with provided credentials
    username = "lukesteuber.substack.com"
    password = "Tr33b3@rd"
    
    ranker = BlueskyFollowerRanker(username, password, args.database)
    
    # Show cache statistics
    cache_stats = ranker.get_cache_stats()
    if cache_stats['total_profiles'] > 0:
        print(f"📊 Profile cache: {cache_stats['total_profiles']:,} profiles, {cache_stats['popular_profiles']:,} popular (>1K followers)")
    
    # Authenticate
    if not await ranker.authenticate():
        print("❌ Authentication failed. Please check your credentials.")
        sys.exit(1)
    
    # Use authenticated user as target if not specified
    target_username = args.target if args.target else username
    
    # Rank followers (handle None properly)
    max_followers = args.max_followers
    ranked_followers = await ranker.rank_followers(target_username, max_followers)
    
    if not ranked_followers:
        print("❌ No followers could be ranked. Exiting.")
        sys.exit(1)
    
    # Perform additional analyses if requested
    bot_analysis = None
    quality_analysis = None
    
    if args.bot_analysis:
        print(f"\n🤖 Running bot indicator analysis...")
        bot_analysis = ranker.analyze_bot_indicators(ranked_followers, args.analysis_count)
        
    if args.quality_analysis:
        print(f"\n⭐ Running quality follower analysis...")
        quality_analysis = ranker.analyze_quality_followers(ranked_followers, args.analysis_count)
    
    # Export results
    ranker.export_to_file(ranked_followers, target_username, args.output, bot_analysis, quality_analysis)
    
    print(f"\n🎉 Successfully ranked {len(ranked_followers)} followers!")
    
    # Show updated cache statistics
    final_cache_stats = ranker.get_cache_stats()
    print(f"📦 Profile cache now contains {final_cache_stats['total_profiles']:,} profiles")
    
    # Calculate ratios for console output
    followers_with_ratios = []
    for follower in ranked_followers:
        if follower['following_count'] > 0:
            ratio = follower['followers_count'] / follower['following_count']
            followers_with_ratios.append({**follower, 'ratio': ratio})
    
    print(f"\n📊 TOP 10 MOST FOLLOWED:")
    for i, follower in enumerate(ranked_followers[:10], 1):
        print(f"  {i:2d}. @{follower['handle']} - {follower['followers_count']:,} followers")
    
    if followers_with_ratios:
        # Sort by best ratios (highest followers/following)
        best_ratios = sorted(followers_with_ratios, key=lambda x: x['ratio'], reverse=True)[:10]
        print(f"\n⭐ TOP 10 BEST RATIOS (highest followers/following):")
        for i, follower in enumerate(best_ratios, 1):
            print(f"  {i:2d}. @{follower['handle']} - ratio: {follower['ratio']:.2f} ({follower['followers_count']:,}/{follower['following_count']:,})")
        
        # Sort by worst ratios (lowest followers/following) 
        worst_ratios = sorted(followers_with_ratios, key=lambda x: x['ratio'])[:10]
        print(f"\n🤖 TOP 10 WORST RATIOS (potential bots - lowest followers/following):")
        for i, follower in enumerate(worst_ratios, 1):
            print(f"  {i:2d}. @{follower['handle']} - ratio: {follower['ratio']:.3f} ({follower['followers_count']:,}/{follower['following_count']:,})")
    
    # Show analysis results if performed (keep existing for backwards compatibility)
    if bot_analysis:
        print(f"\n🔍 Bot Analysis: {len(bot_analysis)} potential bots identified")
        
    if quality_analysis:
        print(f"\n✨ Quality Analysis: {len(quality_analysis)} selective followers identified")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        sys.exit(1) 