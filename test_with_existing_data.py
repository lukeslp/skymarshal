#!/usr/bin/env python3
"""
Test webapp using existing JSON data to bypass rate limits
"""

import json
from pathlib import Path
from datetime import datetime

def create_test_data_with_engagement():
    """Create test JSON data with engagement to verify webapp display"""
    
    # Create test data with known engagement
    test_data = [
        {
            'uri': 'at://did:plc:horkcrlpr6ooi6bverff6b3w/app.bsky.feed.post/3lzfs3lydvc2p',
            'cid': 'bafyreiabc123',
            'content_type': 'post',
            'text': 'Test post\n\nLike really, go away',
            'created_at': '2025-09-21T23:00:00.000Z',
            'like_count': 1,          # Real engagement data we confirmed
            'repost_count': 0,
            'reply_count': 1,
            'quote_count': 0,
            'engagement_score': 3.5,  # 1 + (2*0) + (2.5*1) = 3.5
            'raw_data': {}
        },
        {
            'uri': 'at://did:plc:horkcrlpr6ooi6bverff6b3w/app.bsky.feed.post/3lzfs3lydvc2y',
            'cid': 'bafyreiabc456',
            'content_type': 'post', 
            'text': 'Another test post with more engagement',
            'created_at': '2025-09-20T15:30:00.000Z',
            'like_count': 5,
            'repost_count': 2,
            'reply_count': 3,
            'quote_count': 1,
            'engagement_score': 16.5,  # 5 + (2*2) + (2.5*3) = 16.5
            'raw_data': {}
        },
        {
            'uri': 'at://did:plc:horkcrlpr6ooi6bverff6b3w/app.bsky.feed.like/3lzfs3lydvc2z',
            'cid': 'bafyreiabc789',
            'content_type': 'like',
            'text': None,
            'created_at': '2025-09-19T12:15:00.000Z',
            'like_count': 0,
            'repost_count': 0,
            'reply_count': 0,
            'quote_count': 0,
            'engagement_score': 0,
            'raw_data': {
                'subject_uri': 'at://did:plc:other/app.bsky.feed.post/abc123',
                'subject_cid': 'bafyreiother123'
            }
        }
    ]
    
    # Save to skymarshal JSON directory
    json_dir = Path.home() / '.skymarshal' / 'json'
    json_dir.mkdir(parents=True, exist_ok=True)
    
    # Use rufferto handle
    handle = 'rufferto_bsky_social'
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    json_file = json_dir / f"{handle}_test_with_engagement_{timestamp}.json"
    
    with open(json_file, 'w') as f:
        json.dump(test_data, f, indent=2, default=str)
    
    print(f"✅ Created test data file: {json_file}")
    print(f"📊 Test data includes:")
    print(f"  - 2 posts with engagement data")
    print(f"  - 1 like")
    print(f"  - Total engagement: {sum(item['engagement_score'] for item in test_data)}")
    
    # Display sample engagement
    for item in test_data:
        if item['like_count'] > 0 or item['repost_count'] > 0 or item['reply_count'] > 0:
            print(f"\n📄 Sample item with engagement:")
            print(f"  Text: {item['text'][:50]}...")
            print(f"  Likes: {item['like_count']}")
            print(f"  Reposts: {item['repost_count']}")
            print(f"  Replies: {item['reply_count']}")
            print(f"  Engagement Score: {item['engagement_score']}")
    
    return json_file

def verify_json_format():
    """Verify the JSON format matches what the webapp expects"""
    
    json_dir = Path.home() / '.skymarshal' / 'json'
    
    # Find test files
    test_files = list(json_dir.glob("*test_with_engagement*.json"))
    
    if not test_files:
        print("❌ No test files found")
        return False
    
    latest_file = max(test_files, key=lambda p: p.stat().st_mtime)
    print(f"🔍 Analyzing file: {latest_file}")
    
    with open(latest_file, 'r') as f:
        data = json.load(f)
    
    print(f"\n📊 File Analysis:")
    print(f"  Format: {'List' if isinstance(data, list) else 'Dict'}")
    print(f"  Total items: {len(data) if isinstance(data, list) else 'N/A'}")
    
    if isinstance(data, list):
        # Count engagement
        items_with_engagement = 0
        total_likes = total_reposts = total_replies = 0
        
        for item in data:
            likes = item.get('like_count', 0)
            reposts = item.get('repost_count', 0) 
            replies = item.get('reply_count', 0)
            
            if likes > 0 or reposts > 0 or replies > 0:
                items_with_engagement += 1
                total_likes += likes
                total_reposts += reposts
                total_replies += replies
        
        print(f"  Items with engagement: {items_with_engagement}")
        print(f"  Total likes: {total_likes}")
        print(f"  Total reposts: {total_reposts}")
        print(f"  Total replies: {total_replies}")
        
        return items_with_engagement > 0
    
    return False

if __name__ == "__main__":
    print("🧪 Creating test data with engagement to verify webapp display...")
    
    # Create test data
    test_file = create_test_data_with_engagement()
    
    # Verify format
    print(f"\n🔍 Verifying JSON format...")
    has_engagement = verify_json_format()
    
    if has_engagement:
        print(f"\n✅ Test data created successfully!")
        print(f"\n💡 Next steps:")
        print(f"1. Wait 5-10 minutes for rate limit to reset")
        print(f"2. Use the webapp at http://localhost:5003")
        print(f"3. Try 'Sign in anyway' mode if auth still rate limited")
        print(f"4. The engagement data should display properly")
        print(f"\n📁 Test file location: {test_file}")
    else:
        print(f"❌ Test data creation failed")