#!/usr/bin/env python3
"""
Test engagement hydration with the same logic as the webapp
"""

import sys
import os
from pathlib import Path

# Add skymarshal to path
sys.path.insert(0, '.')

from atproto import Client
from skymarshal.models import ContentItem
import json

def test_engagement_hydration():
    # Test with our known working account
    handle = 'rufferto.bsky.social'
    app_password = '6zki-berj-fdco-k2l5'
    
    print(f"Testing engagement hydration for {handle}")
    
    # Create authenticated client
    client = Client()
    try:
        client.login(handle, app_password)
        print("✓ Authentication successful")
    except Exception as e:
        print(f"✗ Authentication failed: {e}")
        return
    
    # Get the user's posts
    try:
        posts_resp = client.get_author_feed(actor=handle, limit=5)
        
        if not posts_resp.feed:
            print("No posts found")
            return
            
        print(f"Found {len(posts_resp.feed)} posts")
        
        # Convert to ContentItem format like webapp does
        items = []
        for feed_item in posts_resp.feed:
            post = feed_item.post
            
            # Create ContentItem similar to how DataManager does it
            item = ContentItem(
                uri=post.uri,
                cid=post.cid,
                content_type="post",
                text=post.record.text if hasattr(post.record, 'text') else "",
                created_at=post.record.created_at if hasattr(post.record, 'created_at') else "",
                like_count=0,  # Start with 0 to test hydration
                repost_count=0,
                reply_count=0,
                engagement_score=0,
                raw_data={}
            )
            items.append(item)
            
        print(f"Created {len(items)} ContentItem objects")
        
        # Now test the hydration function from site_gpt5
        print("\n--- Testing hydration ---")
        
        # Test hydration on first item
        first_item = items[0]
        print(f"Before hydration: likes={first_item.like_count}, reposts={first_item.repost_count}, replies={first_item.reply_count}")
        
        # Manually hydrate this one item to test
        uri = first_item.uri
        print(f"Hydrating URI: {uri}")
        
        try:
            # Get likes
            likes_resp = client.get_likes(uri=uri, limit=100)
            likes_count = len(likes_resp.likes) if likes_resp.likes else 0
            
            # Get reposts  
            reposts_resp = client.get_reposted_by(uri=uri, limit=100)
            reposts_count = len(reposts_resp.reposted_by) if reposts_resp.reposted_by else 0
            
            # Get replies
            thread_resp = client.get_post_thread(uri=uri, depth=1)
            replies_count = 0
            if hasattr(thread_resp.thread, 'replies') and thread_resp.thread.replies:
                replies_count = len(thread_resp.thread.replies)
            
            # Update the item
            first_item.like_count = likes_count
            first_item.repost_count = reposts_count
            first_item.reply_count = replies_count
            first_item.update_engagement_score()
            
            print(f"After hydration: likes={first_item.like_count}, reposts={first_item.repost_count}, replies={first_item.reply_count}")
            print(f"Engagement score: {first_item.engagement_score}")
            
            # Test JSON serialization like webapp does
            print("\n--- Testing JSON serialization ---")
            
            item_dict = {
                'uri': first_item.uri,
                'cid': first_item.cid,
                'content_type': first_item.content_type,
                'text': first_item.text,
                'created_at': first_item.created_at,
                'like_count': first_item.like_count,
                'repost_count': first_item.repost_count,
                'reply_count': first_item.reply_count,
                'engagement_score': first_item.engagement_score,
                'raw_data': first_item.raw_data
            }
            
            # Save to test file
            test_file = Path.home() / '.skymarshal' / 'json' / 'test_hydration.json'
            test_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(test_file, 'w') as f:
                json.dump([item_dict], f, indent=2, default=str)
                
            print(f"✓ Saved test data to {test_file}")
            
            # Read it back to verify
            with open(test_file, 'r') as f:
                loaded_data = json.load(f)
                
            loaded_item = loaded_data[0]
            print(f"✓ Loaded back: likes={loaded_item['like_count']}, reposts={loaded_item['repost_count']}, replies={loaded_item['reply_count']}")
            
            if (loaded_item['like_count'] == first_item.like_count and 
                loaded_item['repost_count'] == first_item.repost_count and
                loaded_item['reply_count'] == first_item.reply_count):
                print("✓ Data persistence test PASSED")
            else:
                print("✗ Data persistence test FAILED")
                
        except Exception as e:
            print(f"✗ Hydration failed: {e}")
            import traceback
            traceback.print_exc()
        
    except Exception as e:
        print(f"✗ Failed to get posts: {e}")

if __name__ == "__main__":
    test_engagement_hydration()