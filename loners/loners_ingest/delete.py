#!/usr/bin/env python3
"""
Skymarshal Deletion Script

This script provides safe content deletion capabilities for Bluesky content.
It includes multiple approval modes, dry-run capabilities, and comprehensive safety checks.

Usage: python delete.py
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import List, Optional, Tuple, Any
from datetime import datetime

# Add parent directory to path to import skymarshal modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from atproto import Client
from rich.console import Console
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn

# Import from skymarshal
from skymarshal.models import ContentItem, SearchFilters, ContentType, DeleteMode, UserSettings, parse_datetime
from skymarshal.auth import AuthManager
from skymarshal.data_manager import DataManager
from skymarshal.ui import UIManager

console = Console()

class DeleteScript:
    """Standalone content deletion functionality."""
    
    def __init__(self):
        self.skymarshal_dir = Path.home() / '.skymarshal'
        self.cars_dir = self.skymarshal_dir / 'cars'
        self.json_dir = self.skymarshal_dir / 'json'
        
        # Initialize settings
        self.settings_file = Path.home() / '.car_inspector_settings.json'
        self.settings = self._load_settings()
        
        # Initialize managers
        self.ui = UIManager(self.settings)
        self.auth = AuthManager(self.ui)
        self.data_manager = DataManager(self.auth, self.settings, 
                                       self.skymarshal_dir, self.cars_dir, self.json_dir)
        
        self.current_data: List[ContentItem] = []
        self.current_data_file: Optional[Path] = None
    
    def _load_settings(self) -> UserSettings:
        """Load user settings or create defaults."""
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r') as f:
                    data = json.load(f)
                base = UserSettings()
                for k, v in data.items():
                    if hasattr(base, k):
                        setattr(base, k, v)
                return base
        except Exception:
            pass
        return UserSettings()
    
    def authenticate(self) -> bool:
        """Ensure authentication for deletion operations."""
        if self.auth.is_authenticated():
            return True
        
        console.print(Rule("Authentication Required", style="bright_red"))
        console.print()
        console.print("Deletion operations require authentication.")
        console.print()
        
        while True:
            handle, action = self.ui.input_with_navigation("Bluesky handle: @", context="handle")
            if action in ["back", "main"]:
                return False
            if handle:
                handle = self.auth.normalize_handle(handle)
                break
        
        password, action = self.ui.input_with_navigation("App Password: ", password=True, context="password")
        if action in ["back", "main"]:
            return False
        
        if self.auth.authenticate_client(handle, password):
            console.print(f"Authenticated as @{self.auth.current_handle}")
            return True
        else:
            console.print("Authentication failed")
            return False
    
    def load_data_file(self) -> bool:
        """Load a data file for deletion operations."""
        console.print(Rule("Load Data File", style="bright_cyan"))
        console.print()
        
        # Get available JSON files
        if self.auth.current_handle:
            files = self.data_manager.get_user_files(self.auth.current_handle, 'json')
        else:
            # Show all files if no authenticated user
            files = list(self.json_dir.glob("*.json"))
        
        if not files:
            console.print("No data files found")
            console.print("Run setup.py first to download and process data")
            return False
        
        console.print("Available data files:")
        console.print()
        
        # Show file picker
        selected_file = self.ui.show_file_picker(files)
        if not selected_file:
            return False
        
        # Load the data
        try:
            with console.status("Loading data..."):
                self.current_data = self.data_manager.load_exported_data(selected_file)
            
            self.current_data_file = selected_file
            console.print(f"Loaded {len(self.current_data)} items from {selected_file.name}")
            
            # Update engagement data
            try:
                self.data_manager.hydrate_items(self.current_data)
                console.print("Updated engagement data")
            except Exception as e:
                console.print(f"[yellow]Warning: Could not update engagement data: {e}[/yellow]")
            
            return True
            
        except Exception as e:
            console.print(f"Error loading file: {e}")
            return False
    
    def build_deletion_filters(self) -> Optional[SearchFilters]:
        """Build filters for content to delete."""
        console.print(Rule("Build Deletion Filters", style="bright_red"))
        console.print()
        
        filters = SearchFilters()
        
        # Content type selection
        content_types = {
            "1": ("all", "All content"),
            "2": ("posts", "Original posts only"),
            "3": ("replies", "Replies/comments only"),
            "4": ("reposts", "Reposts only"),
            "5": ("likes", "Likes only"),
        }
        
        console.print("Content Type to Delete:")
        for key, (_, desc) in content_types.items():
            console.print(f"  [{key}] {desc}")
        
        type_choice = Prompt.ask("Select content type", choices=list(content_types.keys()), default="1", show_choices=False)
        content_type_value, _ = content_types[type_choice]
        filters.content_type = ContentType(content_type_value)
        
        console.print()
        
        # Keyword filters
        if Confirm.ask("Delete content containing specific keywords?", default=False):
            keywords_input = Prompt.ask("Enter keywords (comma separated)", default="")
            if keywords_input:
                filters.keywords = [k.strip() for k in keywords_input.split(",") if k.strip()]
        
        console.print()
        
        # Engagement filters
        if Confirm.ask("Delete based on engagement levels?", default=False):
            console.print()
            console.print("Engagement Filter Type:")
            console.print("  [1] Quick presets")
            console.print("  [2] Custom thresholds")
            
            filter_choice = Prompt.ask("Select filter option", choices=["1", "2"], default="1")
            
            if filter_choice == "1":
                self._apply_deletion_presets(filters)
            else:
                self._apply_custom_deletion_filters(filters)
        
        # Date filters
        if Confirm.ask("Delete content from specific date range?", default=False):
            console.print()
            console.print("Date Range (YYYY-MM-DD or ISO8601)")
            start_date = Prompt.ask("Start date", default="")
            end_date = Prompt.ask("End date", default="")
            filters.start_date = start_date or None
            filters.end_date = end_date or None
        
        return filters
    
    def _apply_deletion_presets(self, filters: SearchFilters):
        """Apply deletion-specific presets."""
        console.print()
        console.print("Deletion Presets:")
        console.print("  [1] Dead threads (0 engagement)")
        console.print("  [2] Low engagement (1-5)")
        console.print("  [3] Medium engagement (6-15)")
        console.print("  [4] High engagement (16-50)")
        console.print("  [5] Viral content (50+)")
        
        preset_choice = Prompt.ask("Select preset", choices=["1", "2", "3", "4", "5"], default="1")
        
        if preset_choice == "1":
            filters.min_engagement = 0
            filters.max_engagement = 0
        elif preset_choice == "2":
            filters.min_engagement = 1
            filters.max_engagement = 5
        elif preset_choice == "3":
            filters.min_engagement = 6
            filters.max_engagement = 15
        elif preset_choice == "4":
            filters.min_engagement = 16
            filters.max_engagement = 50
        elif preset_choice == "5":
            filters.min_engagement = 50
            filters.max_engagement = 999999
    
    def _apply_custom_deletion_filters(self, filters: SearchFilters):
        """Apply custom deletion filters."""
        console.print()
        
        if Confirm.ask("Filter by engagement score?", default=False):
            min_eng = IntPrompt.ask("Minimum engagement score", default=0)
            max_eng = IntPrompt.ask("Maximum engagement score", default=999999)
            filters.min_engagement = min_eng
            filters.max_engagement = max_eng
        
        if Confirm.ask("Filter by likes?", default=False):
            min_likes = IntPrompt.ask("Minimum likes", default=0)
            max_likes = IntPrompt.ask("Maximum likes", default=999999)
            filters.min_likes = min_likes
            filters.max_likes = max_likes
        
        if Confirm.ask("Filter by reposts?", default=False):
            min_reposts = IntPrompt.ask("Minimum reposts", default=0)
            max_reposts = IntPrompt.ask("Maximum reposts", default=999999)
            filters.min_reposts = min_reposts
            filters.max_reposts = max_reposts
        
        if Confirm.ask("Filter by replies?", default=False):
            min_replies = IntPrompt.ask("Minimum replies", default=0)
            max_replies = IntPrompt.ask("Maximum replies", default=999999)
            filters.min_replies = min_replies
            filters.max_replies = max_replies
    
    def find_content_to_delete(self, filters: SearchFilters) -> List[ContentItem]:
        """Find content matching deletion criteria."""
        if not self.current_data:
            return []
        
        filtered_items = self.current_data.copy()
        
        # Apply filters (same logic as search script)
        sd = parse_datetime(getattr(filters, 'start_date', None))
        ed = parse_datetime(getattr(filters, 'end_date', None))
        use_subject = self.settings.use_subject_engagement_for_reposts
        
        def counts_for(it: ContentItem):
            if it.content_type == 'repost' and use_subject:
                rd = it.raw_data or {}
                return (
                    int(rd.get('subject_like_count', 0)),
                    int(rd.get('subject_repost_count', 0)),
                    int(rd.get('subject_reply_count', 0))
                )
            return (int(it.like_count or 0), int(it.repost_count or 0), int(it.reply_count or 0))
        
        def passes(it: ContentItem) -> bool:
            # Content type filter
            if filters.content_type != ContentType.ALL:
                if filters.content_type == ContentType.POSTS and it.content_type != 'post':
                    return False
                elif filters.content_type == ContentType.REPLIES and it.content_type != 'reply':
                    return False
                elif filters.content_type == ContentType.REPOSTS and it.content_type != 'repost':
                    return False
                elif filters.content_type == ContentType.LIKES and it.content_type != 'like':
                    return False
            
            # Keyword filter
            if filters.keywords:
                text = (it.text or "").lower()
                if not any(keyword.lower() in text for keyword in filters.keywords):
                    return False
            
            # Engagement filters
            likes, reposts, replies = counts_for(it)
            engagement = likes + 2*reposts + 3*replies
            
            if engagement < filters.min_engagement or engagement > filters.max_engagement:
                return False
            
            if likes < filters.min_likes or likes > filters.max_likes:
                return False
            
            if reposts < filters.min_reposts or reposts > filters.max_reposts:
                return False
            
            if replies < filters.min_replies or replies > filters.max_replies:
                return False
            
            # Date filters
            if sd or ed:
                created_dt = parse_datetime(it.created_at)
                if created_dt:
                    if sd and created_dt < sd:
                        return False
                    if ed and created_dt > ed:
                        return False
            
            return True
        
        # Apply filters
        filtered_items = [it for it in filtered_items if passes(it)]
        
        return filtered_items
    
    def select_deletion_mode(self, item_count: int) -> DeleteMode:
        """Select deletion approval mode."""
        console.print(Rule("🗑️ Deletion Mode Selection", style="bright_red"))
        console.print()
        
        modes = {
            "1": (DeleteMode.ALL_AT_ONCE, f"Delete all {item_count} items at once"),
            "2": (DeleteMode.INDIVIDUAL, "Review and approve each item individually"),
            "3": (DeleteMode.BATCH, "Delete in batches (approve groups of items)"),
            "4": (DeleteMode.CANCEL, "Cancel deletion")
        }
        
        for key, (_, desc) in modes.items():
            console.print(f"  [{key}] {desc}")
        
        choice = Prompt.ask("Select deletion mode", choices=list(modes.keys()), default="1", show_choices=False)
        mode, _ = modes[choice]
        return mode
    
    def preview_deletion(self, items: List[ContentItem], limit: int = 10):
        """Preview items to be deleted."""
        console.print(Rule("👀 Deletion Preview", style="bright_yellow"))
        console.print()
        
        if not items:
            console.print("No items to delete")
            return
        
        console.print(f"⚠️ Found {len(items)} items to delete")
        console.print(f"Showing first {min(len(items), limit)} items:")
        console.print()
        
        table = Table(show_header=True)
        table.add_column("Type", style="cyan", width=6)
        table.add_column("Preview", style="white", width=40)
        table.add_column("Likes", style="red", width=4)
        table.add_column("Reposts", style="blue", width=4)
        table.add_column("Replies", style="yellow", width=4)
        table.add_column("Engagement", style="green", width=6)
        table.add_column("Date", style="dim", width=10)
        
        for item in items[:limit]:
            if item.content_type == 'like':
                subj = (item.raw_data or {}).get('subject_uri')
                text_preview = f"Liked: {subj}" if subj else "Like"
            elif item.content_type == 'repost':
                subj = (item.raw_data or {}).get('subject_uri')
                text_preview = f"Repost: {subj}" if subj else "Repost"
            else:
                text_preview = (item.text[:35] + "...") if item.text and len(item.text) > 35 else (item.text or "")
            
            created = item.created_at[:10] if item.created_at else ""
            
            table.add_row(
                item.content_type, text_preview,
                str(item.like_count), str(item.repost_count), str(item.reply_count),
                str(int(item.engagement_score)), created
            )
        
        console.print(table)
        
        if len(items) > limit:
            console.print()
            console.print(f"... and {len(items) - limit} more items")
        console.print()
    
    def delete_records_by_uri(self, uris: List[str]) -> Tuple[int, List[str]]:
        """Delete records by their at:// URIs."""
        if not self.auth.ensure_authentication():
            return 0, ["Not authenticated"]
        
        errors: List[str] = []
        deleted = 0
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Deleting records...", total=len(uris))
            
            for uri in uris:
                try:
                    parts = uri.split('/') if uri else []
                    if len(parts) >= 5 and uri.startswith('at://'):
                        did = parts[2]
                        # Fallback: replace placeholder DID with the authenticated user's DID
                        if did == 'did:plc:unknown' and self.auth.current_did:
                            did = self.auth.current_did
                        collection = parts[3]
                        rkey = parts[4]
                        self.auth.client.com.atproto.repo.delete_record({
                            'repo': did, 
                            'collection': collection, 
                            'rkey': rkey
                        })
                        deleted += 1
                    else:
                        errors.append(f"Invalid at:// URI: {uri}")
                except Exception as e:
                    errors.append(f"Failed to delete {uri}: {e}")
                finally:
                    progress.advance(task, 1)
        
        return deleted, errors
    
    def delete_all_at_once(self, items: List[ContentItem]) -> int:
        """Delete all items at once with confirmation."""
        console.print(Rule("Bulk Deletion", style="bright_red"))
        console.print()
        
        if not items:
            console.print("No items to delete")
            return 0
        
        # Show preview
        self.preview_deletion(items, limit=5)
        
        # Final confirmation
        console.print(Panel(
            f"WARNING: This will permanently delete {len(items)} items from Bluesky!",
            title="DANGER",
            border_style="bright_red"
        ))
        
        if not Confirm.ask("Are you absolutely sure?", default=False):
            console.print("Deletion cancelled")
            return 0
        
        # Get URIs
        uris = [item.uri for item in items if item.uri]
        
        # Execute deletion
        deleted, errors = self.delete_records_by_uri(uris)
        
        # Show results
        console.print()
        console.print(f"Deleted {deleted} items")
        if errors:
            console.print(f"{len(errors)} errors occurred:")
            for error in errors[:5]:  # Show first 5 errors
                console.print(f"   • {error}")
            if len(errors) > 5:
                console.print(f"   ... and {len(errors) - 5} more errors")
        
        return deleted
    
    def delete_individual_approval(self, items: List[ContentItem]) -> int:
        """Delete items with individual approval."""
        console.print(Rule("Individual Approval Deletion", style="bright_red"))
        console.print()
        
        if not items:
            console.print("No items to delete")
            return 0
        
        deleted = 0
        
        for i, item in enumerate(items, 1):
            console.print(f"Item {i} of {len(items)}")
            console.print()
            
            # Show item details
            panel_content = []
            panel_content.append(f"[bold]Type:[/] {item.content_type}")
            panel_content.append(f"[bold]Created:[/] {item.created_at or 'Unknown'}")
            panel_content.append(f"[bold]Engagement:[/] Likes:{item.like_count} Reposts:{item.repost_count} Replies:{item.reply_count} (Total: {int(item.engagement_score)})")
            panel_content.append("")
            
            if item.text:
                text_content = item.text[:200] + ("..." if len(item.text) > 200 else "")
                panel_content.append(f"[bold]Content:[/]")
                panel_content.append(text_content)
            else:
                panel_content.append("[dim]No text content[/]")
            
            console.print(Panel(
                "\n".join(panel_content),
                title="Item Details",
                border_style="dim"
            ))
            
            console.print()
            
            if Confirm.ask("Delete this item?", default=False):
                try:
                    parts = item.uri.split('/') if item.uri else []
                    if len(parts) >= 5 and item.uri.startswith('at://'):
                        did = parts[2]
                        if did == 'did:plc:unknown' and self.auth.current_did:
                            did = self.auth.current_did
                        collection = parts[3]
                        rkey = parts[4]
                        self.auth.client.com.atproto.repo.delete_record({
                            'repo': did, 
                            'collection': collection, 
                            'rkey': rkey
                        })
                        deleted += 1
                        console.print("Deleted")
                    else:
                        console.print("Invalid URI")
                except Exception as e:
                    console.print(f"Deletion failed: {e}")
            else:
                console.print("Skipped")
            
            console.print()
            
            if i < len(items) and not Confirm.ask("Continue to next item?", default=True):
                break
        
        console.print(f"Deleted {deleted} items total")
        return deleted
    
    def delete_batch_approval(self, items: List[ContentItem], batch_size: int = 10) -> int:
        """Delete items in batches with approval."""
        console.print(Rule("Batch Approval Deletion", style="bright_red"))
        console.print()
        
        if not items:
            console.print("No items to delete")
            return 0
        
        deleted = 0
        total_batches = (len(items) + batch_size - 1) // batch_size
        
        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(items))
            batch_items = items[start_idx:end_idx]
            
            console.print(f"Batch {batch_num + 1} of {total_batches} ({len(batch_items)} items)")
            console.print()
            
            # Show batch preview
            self.preview_deletion(batch_items, limit=len(batch_items))
            
            if Confirm.ask(f"Delete this batch of {len(batch_items)} items?", default=False):
                # Get URIs
                uris = [item.uri for item in batch_items if item.uri]
                
                # Execute deletion
                batch_deleted, errors = self.delete_records_by_uri(uris)
                deleted += batch_deleted
                
                console.print(f"Deleted {batch_deleted} items from this batch")
                if errors:
                    console.print(f"{len(errors)} errors in this batch")
            else:
                console.print("Skipped this batch")
            
            console.print()
            
            if batch_num < total_batches - 1 and not Confirm.ask("Continue to next batch?", default=True):
                break
        
        console.print(f"Deleted {deleted} items total")
        return deleted
    
    def run_deletion_workflow(self):
        """Run the complete deletion workflow."""
        if not self.current_data:
            console.print("No data loaded")
            console.print("Load a data file first")
            return
        
        # Build filters
        filters = self.build_deletion_filters()
        if not filters:
            return
        
        # Find content to delete
        with console.status("Finding content to delete..."):
            items = self.find_content_to_delete(filters)
        
        console.print()
        console.print(f"Found {len(items)} items matching deletion criteria")
        console.print()
        
        if not items:
            console.print("No items match your criteria")
            return
        
        # Preview deletion
        self.preview_deletion(items, limit=10)
        
        # Select deletion mode
        mode = self.select_deletion_mode(len(items))
        
        if mode == DeleteMode.CANCEL:
            console.print("Deletion cancelled")
            return
        
        # Execute deletion based on mode
        if mode == DeleteMode.ALL_AT_ONCE:
            self.delete_all_at_once(items)
        elif mode == DeleteMode.INDIVIDUAL:
            self.delete_individual_approval(items)
        elif mode == DeleteMode.BATCH:
            batch_size = IntPrompt.ask("Batch size", default=10)
            self.delete_batch_approval(items, batch_size)
    
    def show_menu(self):
        """Display main menu."""
        console.print(Rule("Content Deletion", style="bright_red"))
        console.print()
        
        if not self.current_data:
            console.print("No data loaded")
            console.print("Use 'Load Data File' to load data for deletion")
            console.print()
        
        options = {
            "1": ("Load Data File", self.load_data_file),
            "2": ("Delete Content", self.run_deletion_workflow),
            "3": ("Authenticate", self.authenticate),
            "q": ("Quit", None)
        }
        
        console.print("Options:")
        for key, (desc, _) in options.items():
            console.print(f"  [{key}] {desc}")
        console.print()
        
        choice = Prompt.ask("Select option", choices=list(options.keys()), default="1", show_choices=False)
        
        if choice == "q":
            return False
        
        if choice in options:
            _, func = options[choice]
            if func:
                func()
                console.print()
                if not Confirm.ask("Continue?", default=True):
                    return False
        
        return True
    
    def run(self):
        """Run the deletion script."""
        console.print()
        console.print("Skymarshal Content Deletion")
        console.print("=" * 50)
        console.print()
        
        # Show warning
        console.print(Panel(
            "WARNING: This tool permanently deletes content from Bluesky!\n"
            "Always backup your data before deletion operations.\n"
            "Deletions cannot be undone.",
            title="DANGER ZONE",
            border_style="bright_red"
        ))
        console.print()
        
        if not Confirm.ask("I understand the risks and want to continue", default=False):
            console.print("Operation cancelled")
            return
        
        try:
            while True:
                if not self.show_menu():
                    break
                console.print()
        except KeyboardInterrupt:
            console.print("\nGoodbye!")
        except Exception as e:
            console.print(f"\nUnexpected error: {e}")

def main():
    """Main entry point."""
    delete_script = DeleteScript()
    delete_script.run()

if __name__ == "__main__":
    main()
