#!/usr/bin/env python3
"""
Debug script to test hydration functionality.

This script helps diagnose why hydrate_items might not be updating engagement data.
"""
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from skymarshal.models import ContentItem, UserSettings
from skymarshal.auth import AuthManager  
from skymarshal.data_manager import DataManager
from skymarshal.models import console
from atproto import Client


def create_test_items():
    """Create test ContentItem objects for debugging."""
    return [
        ContentItem(
            uri="at://did:plc:test/app.bsky.feed.post/test1",
            cid="test1",
            content_type="post",
            text="Test post 1",
            created_at="2023-01-01T00:00:00Z",
            like_count=0,
            repost_count=0,
            reply_count=0,
            engagement_score=0,
            raw_data=None
        ),
        ContentItem(
            uri="at://did:plc:test/app.bsky.feed.post/test2", 
            cid="test2",
            content_type="post",
            text="Test post 2",
            created_at="2023-01-01T00:00:00Z", 
            like_count=0,
            repost_count=0,
            reply_count=0,
            engagement_score=0,
            raw_data=None
        ),
        ContentItem(
            uri="at://did:plc:test/app.bsky.feed.like/like1",
            cid="like1", 
            content_type="like",
            text=None,
            created_at="2023-01-01T00:00:00Z",
            like_count=0,
            repost_count=0,
            reply_count=0,
            engagement_score=0,
            raw_data={"subject_uri": "at://did:plc:other/app.bsky.feed.post/subject1"}
        ),
    ]


def test_hydration_setup():
    """Test the hydration setup without actual API calls."""
    console.print("[bold blue]Testing hydration setup...[/bold blue]")
    
    # Create test items
    items = create_test_items()
    
    console.print(f"Created {len(items)} test items:")
    for i, item in enumerate(items):
        console.print(f"  {i+1}. URI: {item.uri}")
        console.print(f"     Type: {item.content_type}")
        console.print(f"     Engagement: likes={item.like_count}, reposts={item.repost_count}, replies={item.reply_count}")
        console.print()
    
    # Create mock auth manager
    auth_manager = AuthManager()
    
    # Create settings
    settings = UserSettings()
    
    # Create temp directories
    temp_dir = Path("/tmp/skymarshal_debug")
    temp_dir.mkdir(exist_ok=True)
    
    # Create data manager
    data_manager = DataManager(
        auth_manager=auth_manager,
        settings=settings,
        skymarshal_dir=temp_dir,
        backups_dir=temp_dir / "backups",
        json_dir=temp_dir / "json"
    )
    
    console.print("[bold green]Setup complete.[/bold green]")
    console.print()
    console.print("[bold yellow]Next steps to debug actual hydration:[/bold yellow]")
    console.print("1. Authenticate with a real Bluesky account")
    console.print("2. Use real URIs from your account")
    console.print("3. Call data_manager.hydrate_items(items)")
    console.print("4. Watch the debug output to see where the process fails")
    
    return data_manager, items


def test_at_protocol_response():
    """Test what the AT Protocol API response looks like."""
    console.print("[bold blue]Testing AT Protocol response structure...[/bold blue]")
    
    try:
        from atproto import models
        
        # Check the PostView structure
        console.print("PostView fields:")
        if hasattr(models.AppBskyFeedDefs, 'PostView'):
            post_view = models.AppBskyFeedDefs.PostView
            if hasattr(post_view, 'model_fields'):
                for field_name, field_info in post_view.model_fields.items():
                    if 'count' in field_name.lower():
                        console.print(f"  [cyan]{field_name}[/cyan]: {field_info}")
        
        console.print()
        console.print("Expected engagement fields in API response:")
        console.print("  - like_count (alias: likeCount)")
        console.print("  - repost_count (alias: repostCount)")  
        console.print("  - reply_count (alias: replyCount)")
        console.print("  - quote_count (alias: quoteCount)")
        
    except Exception as e:
        console.print(f"Error examining models: {e}")


if __name__ == "__main__":
    console.print("[bold cyan]Skymarshal Hydration Debugging Tool[/bold cyan]")
    console.print()
    
    test_at_protocol_response()
    console.print()
    
    data_manager, items = test_hydration_setup()
    
    console.print()
    console.print("[bold red]Note:[/bold red] This script sets up debugging infrastructure.")
    console.print("To test actual hydration, you need to:")
    console.print("1. Authenticate: auth_manager.authenticate_client(handle, password)")
    console.print("2. Use real URIs from your Bluesky account")
    console.print("3. Call: data_manager.hydrate_items(items)")