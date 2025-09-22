#!/usr/bin/env python3
"""
Test the site_gpt5 webapp engagement functionality
"""

import requests
import json
import time
from pathlib import Path

def test_site_gpt5_webapp():
    """Test the site_gpt5 webapp with our known working credentials"""
    
    # Test credentials
    handle = 'rufferto.bsky.social'
    app_password = '6zki-berj-fdco-k2l5'
    
    base_url = 'http://localhost:5003'
    
    print(f"Testing site_gpt5 webapp at {base_url}")
    
    # Create a session to maintain cookies
    session = requests.Session()
    
    try:
        # Test 1: Login
        print("\n1. Testing login...")
        login_data = {
            'handle': handle,
            'password': app_password
        }
        
        response = session.post(f'{base_url}/login', json=login_data)
        print(f"Login response: {response.status_code}")
        print(f"Login result: {response.json()}")
        
        if not response.json().get('success'):
            print("❌ Login failed")
            return
        
        print("✅ Login successful")
        
        # Test 2: Download CAR file
        print("\n2. Testing CAR download...")
        response = session.post(f'{base_url}/download')
        print(f"Download response: {response.status_code}")
        result = response.json()
        print(f"Download result: {result}")
        
        if not result.get('success'):
            print("❌ CAR download failed")
            return
            
        print("✅ CAR download successful")
        
        # Test 3: Process data
        print("\n3. Testing data processing...")
        response = session.post(f'{base_url}/process')
        print(f"Process response: {response.status_code}")
        result = response.json()
        print(f"Process result: {result}")
        
        if not result.get('success'):
            print("❌ Data processing failed")
            return
            
        print("✅ Data processing successful")
        
        # Check if engagement data was found
        stats = result.get('stats', {})
        engagement = stats.get('engagement', {})
        
        print(f"\n📊 Engagement Stats:")
        print(f"  Likes received: {engagement.get('likes_received', 0)}")
        print(f"  Reposts received: {engagement.get('reposts_received', 0)}")
        print(f"  Replies received: {engagement.get('replies_received', 0)}")
        print(f"  Quotes received: {engagement.get('quotes_received', 0)}")
        print(f"  Total engagement: {engagement.get('total_engagement', 0)}")
        
        if (engagement.get('likes_received', 0) > 0 or 
            engagement.get('replies_received', 0) > 0):
            print("✅ Engagement data found!")
        else:
            print("❌ No engagement data found")
            
        # Test 4: Refresh engagement
        print("\n4. Testing engagement refresh...")
        response = session.post(f'{base_url}/refresh-engagement')
        print(f"Refresh response: {response.status_code}")
        result = response.json()
        print(f"Refresh result: {result}")
        
        if result.get('success'):
            print("✅ Engagement refresh successful")
            print(f"  Hydrated {result.get('hydrated', 0)} items")
        else:
            print(f"❌ Engagement refresh failed: {result.get('error', 'Unknown error')}")
        
        # Test 5: Check JSON file was created with engagement data
        print("\n5. Checking saved JSON file...")
        json_dir = Path.home() / '.skymarshal' / 'json'
        
        # Find the most recent JSON file for this handle
        json_files = list(json_dir.glob(f"{handle.replace('.', '_')}*.json"))
        if not json_files:
            print("❌ No JSON files found")
            return
            
        latest_json = max(json_files, key=lambda p: p.stat().st_mtime)
        print(f"📁 Checking file: {latest_json}")
        
        with open(latest_json, 'r') as f:
            data = json.load(f)
            
        # Count items with engagement
        items_with_engagement = 0
        total_likes = 0
        total_reposts = 0 
        total_replies = 0
        
        for item in data:
            likes = item.get('like_count', 0)
            reposts = item.get('repost_count', 0)
            replies = item.get('reply_count', 0)
            
            if likes > 0 or reposts > 0 or replies > 0:
                items_with_engagement += 1
                total_likes += likes
                total_reposts += reposts
                total_replies += replies
                
        print(f"📊 JSON File Analysis:")
        print(f"  Total items: {len(data)}")
        print(f"  Items with engagement: {items_with_engagement}")
        print(f"  Total likes: {total_likes}")
        print(f"  Total reposts: {total_reposts}")
        print(f"  Total replies: {total_replies}")
        
        if items_with_engagement > 0:
            print("✅ Engagement data persisted to JSON!")
            
            # Show sample item with engagement
            for item in data:
                if (item.get('like_count', 0) > 0 or 
                    item.get('repost_count', 0) > 0 or 
                    item.get('reply_count', 0) > 0):
                    print(f"\n📄 Sample item with engagement:")
                    print(f"  URI: {item.get('uri', '')[:50]}...")
                    print(f"  Text: {item.get('text', '')[:50]}...")
                    print(f"  Likes: {item.get('like_count', 0)}")
                    print(f"  Reposts: {item.get('repost_count', 0)}")
                    print(f"  Replies: {item.get('reply_count', 0)}")
                    break
        else:
            print("❌ No engagement data found in JSON file")
        
        print(f"\n🎉 Test completed!")
        
    except requests.exceptions.ConnectionError:
        print(f"❌ Could not connect to {base_url}")
        print("Make sure the site_gpt5 webapp is running:")
        print("cd site_gpt5 && python app.py")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_site_gpt5_webapp()