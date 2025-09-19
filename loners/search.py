#!/usr/bin/env python3
"""
Skymarshal Search Script

This script provides advanced search and filtering capabilities for Bluesky content.
It can search through downloaded data with various criteria including keywords,
engagement levels, content types, and date ranges.

Usage: python search.py
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

# Add parent directory to path to import skymarshal modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

# Import from skymarshal
from skymarshal.models import ContentItem, SearchFilters, ContentType, UserSettings, parse_datetime
from skymarshal.auth import AuthManager
from skymarshal.data_manager import DataManager
from skymarshal.ui import UIManager

console = Console()

class SearchScript:
    """Standalone search and filtering functionality."""
    
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
    
    def load_data_file(self) -> bool:
        """Load a data file for searching."""
        console.print(Rule("📁 Load Data File", style="bright_cyan"))
        console.print()
        
        # Get available JSON files
        if self.auth.current_handle:
            files = self.data_manager.get_user_files(self.auth.current_handle, 'json')
        else:
            # Show all files if no authenticated user
            files = list(self.json_dir.glob("*.json"))
        
        if not files:
            console.print("📭 No data files found")
            console.print("💡 Run setup.py first to download and process data")
            return False
        
        console.print("Available data files:")
        console.print()
        
        # Show file picker
        selected_file = self.ui.show_file_picker(files)
        if not selected_file:
            return False
        
        # Load the data
        try:
            with console.status("📄 Loading data..."):
                self.current_data = self.data_manager.load_exported_data(selected_file)
            
            self.current_data_file = selected_file
            console.print(f"✅ Loaded {len(self.current_data)} items from {selected_file.name}")
            
            # Update engagement data
            try:
                self.data_manager.hydrate_items(self.current_data)
                console.print("✅ Updated engagement data")
            except Exception as e:
                console.print(f"[yellow]Warning: Could not update engagement data: {e}[/yellow]")
            
            return True
            
        except Exception as e:
            console.print(f"❌ Error loading file: {e}")
            return False
    
    def build_search_filters(self) -> Optional[SearchFilters]:
        """Interactive filter builder."""
        console.print(Rule("🎛️ Build Search Filters", style="bright_yellow"))
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
        
        console.print("Content Type:")
        for key, (_, desc) in content_types.items():
            console.print(f"  [{key}] {desc}")
        
        type_choice = Prompt.ask("Select content type", choices=list(content_types.keys()), default="1", show_choices=False)
        content_type_value, _ = content_types[type_choice]
        filters.content_type = ContentType(content_type_value)
        
        console.print()
        
        # Keyword filters
        if Confirm.ask("Add keyword filters?", default=False):
            keywords_input = Prompt.ask("Enter keywords (comma separated)", default="")
            if keywords_input:
                filters.keywords = [k.strip() for k in keywords_input.split(",") if k.strip()]
        
        console.print()
        
        # Engagement filters
        if Confirm.ask("Add engagement filters?", default=False):
            console.print()
            console.print("Engagement Filter Type:")
            console.print("  [1] Quick presets")
            console.print("  [2] Custom thresholds")
            
            filter_choice = Prompt.ask("Select filter option", choices=["1", "2"], default="1")
            
            if filter_choice == "1":
                self._apply_engagement_presets(filters)
            else:
                self._apply_custom_engagement_filters(filters)
        
        # Date filters
        if Confirm.ask("Add date range filters?", default=False):
            console.print()
            console.print("Date Range (YYYY-MM-DD or ISO8601)")
            start_date = Prompt.ask("Start date", default="")
            end_date = Prompt.ask("End date", default="")
            filters.start_date = start_date or None
            filters.end_date = end_date or None
        
        return filters
    
    def _apply_engagement_presets(self, filters: SearchFilters):
        """Apply engagement presets."""
        console.print()
        console.print("Engagement Presets:")
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
    
    def _apply_custom_engagement_filters(self, filters: SearchFilters):
        """Apply custom engagement filters."""
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
    
    def search_content(self, filters: SearchFilters) -> List[ContentItem]:
        """Search content using filters."""
        if not self.current_data:
            return []
        
        filtered_items = self.current_data.copy()
        
        # Apply filters
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
    
    def sort_results(self, items: List[ContentItem], sort_mode: str) -> List[ContentItem]:
        """Sort search results."""
        if sort_mode == "newest":
            def key_dt(it: ContentItem):
                dt = parse_datetime(it.created_at, datetime.min)
                return dt
            items.sort(key=key_dt, reverse=True)
        elif sort_mode == "oldest":
            def key_dt(it: ContentItem):
                dt = parse_datetime(it.created_at, datetime.min)
                return dt
            items.sort(key=key_dt, reverse=False)
        elif sort_mode == "engagement":
            def key_eng(it: ContentItem):
                return it.engagement_score
            items.sort(key=key_eng, reverse=True)
        elif sort_mode == "likes":
            def key_likes(it: ContentItem):
                return int(it.like_count or 0)
            items.sort(key=key_likes, reverse=True)
        elif sort_mode == "replies":
            def key_replies(it: ContentItem):
                return int(it.reply_count or 0)
            items.sort(key=key_replies, reverse=True)
        elif sort_mode == "reposts":
            def key_reposts(it: ContentItem):
                return int(it.repost_count or 0)
            items.sort(key=key_reposts, reverse=True)
        
        return items
    
    def display_results(self, items: List[ContentItem], limit: int = 20):
        """Display search results."""
        if not items:
            console.print("No results to display")
            return
        
        console.print(f"Results (showing {min(len(items), limit)} of {len(items)})")
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
            
            if item.content_type == 'repost' and self.settings.use_subject_engagement_for_reposts:
                subj_likes = (item.raw_data or {}).get('subject_like_count', 0)
                subj_reposts = (item.raw_data or {}).get('subject_repost_count', 0)
                subj_replies = (item.raw_data or {}).get('subject_reply_count', 0)
                eng = subj_likes + 2*subj_reposts + 3*subj_replies
                like_disp = str(subj_likes)
                repost_disp = str(subj_reposts)
                reply_disp = str(subj_replies)
                eng_disp = str(int(eng))
            else:
                like_disp = str(item.like_count)
                repost_disp = str(item.repost_count)
                reply_disp = str(item.reply_count)
                eng_disp = str(int(item.engagement_score))
            
            table.add_row(
                item.content_type, text_preview,
                like_disp, repost_disp, reply_disp, eng_disp, created
            )
        
        console.print(table)
        
        if len(items) > limit:
            console.print()
            console.print(f"... and {len(items) - limit} more items")
    
    def export_results(self, items: List[ContentItem]):
        """Export search results to file."""
        console.print()
        console.print("💾 Export Results")
        console.print()
        
        formats = {
            "1": ("json", "JSON format"),
            "2": ("csv", "CSV format")
        }
        
        console.print("Export format:")
        for key, (_, desc) in formats.items():
            console.print(f"  [{key}] {desc}")
        
        format_choice = Prompt.ask("Select format", choices=list(formats.keys()), default="1", show_choices=False)
        export_format, _ = formats[format_choice]
        
        filename = Prompt.ask("Filename (without extension)", default="search_results")
        export_path = self.json_dir / f"{filename}.{export_format}"
        
        try:
            if export_format == 'json':
                data = []
                for item in items:
                    data.append({
                        'uri': item.uri,
                        'cid': item.cid,
                        'type': item.content_type,
                        'text': item.text,
                        'created_at': item.created_at,
                        'engagement': {
                            'likes': item.like_count,
                            'reposts': item.repost_count,
                            'replies': item.reply_count,
                            'score': item.engagement_score
                        }
                    })
                
                with open(export_path, 'w') as f:
                    json.dump(data, f, indent=2)
            
            elif export_format == 'csv':
                import csv
                with open(export_path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['URI', 'Type', 'Text', 'Likes', 'Reposts', 'Replies', 'Engagement', 'Created'])
                    
                    for item in items:
                        writer.writerow([
                            item.uri, item.content_type, item.text or '',
                            item.like_count, item.repost_count, item.reply_count,
                            item.engagement_score, item.created_at or ''
                        ])
            
            console.print(f"✅ Exported {len(items)} items to {export_path}")
            
        except Exception as e:
            console.print(f"❌ Export failed: {e}")
    
    def ensure_data_loaded(self) -> bool:
        """Ensure data is loaded, guiding user through the process if needed."""
        if self.current_data:
            return True
        
        # Check if there are any data files available
        if self.auth.current_handle:
            files = self.data_manager.get_user_files(self.auth.current_handle, 'json')
        else:
            files = list(self.json_dir.glob("*.json"))
        
        if not files:
            console.print("📭 No data files found")
            console.print()
            console.print("To search your Bluesky content, you need to download it first.")
            console.print()
            
            if Confirm.ask("Would you like to download your data now?", default=True):
                # Guide user to download data
                console.print()
                console.print("🔐 First, let's authenticate with Bluesky...")
                
                # Authenticate
                while True:
                    handle, action = self.ui.input_with_navigation("Bluesky handle: @", context="handle")
                    if action in ["back", "main"]:
                        return False
                    if handle:
                        handle = self.auth.normalize_handle(handle)
                        break
                
                password, action = self.ui.input_with_navigation("Password: ", password=True, context="password")
                if action in ["back", "main"]:
                    return False
                
                if not self.auth.authenticate_client(handle, password):
                    console.print("❌ Authentication failed")
                    return False
                
                # Download data
                console.print()
                console.print("📦 Now let's download your data...")
                car_path = self.data_manager.download_car(handle)
                if not car_path:
                    console.print("❌ Failed to download data")
                    return False
                
                # Process CAR file
                console.print()
                console.print("🔄 Processing your data...")
                categories = self.ui.select_categories_for_processing()
                json_path = self.data_manager.import_car_replace(car_path, handle, categories=categories)
                
                if not json_path:
                    console.print("❌ Failed to process data")
                    return False
                
                # Load the processed data
                console.print()
                console.print("📄 Loading processed data...")
                self.current_data = self.data_manager.load_exported_data(json_path)
                self.current_data_file = json_path
                
                if not self.current_data:
                    console.print("❌ No content found in processed data")
                    return False
                
                console.print(f"✅ Loaded {len(self.current_data)} items")
                
                # Try to hydrate engagement data (optional)
                try:
                    self.data_manager.hydrate_items(self.current_data)
                    console.print("✅ Updated engagement data")
                except Exception as e:
                    console.print(f"[yellow]Warning: Could not update engagement data: {e}[/yellow]")
                    console.print("[dim]Search will use cached engagement data[/dim]")
                
                return True
            else:
                console.print("❌ Content search requires downloaded data")
                return False
        else:
            # Load existing data file
            console.print("📁 Loading your data...")
            selected_file = self.ui.show_file_picker(files)
            if not selected_file:
                return False
            
            try:
                with console.status("📄 Loading data..."):
                    self.current_data = self.data_manager.load_exported_data(selected_file)
                
                self.current_data_file = selected_file
                console.print(f"✅ Loaded {len(self.current_data)} items from {selected_file.name}")
                
                # Try to hydrate engagement data (optional)
                try:
                    self.data_manager.hydrate_items(self.current_data)
                    console.print("✅ Updated engagement data")
                except Exception as e:
                    console.print(f"[yellow]Warning: Could not update engagement data: {e}[/yellow]")
                    console.print("[dim]Search will use cached engagement data[/dim]")
                
                return True
                
            except Exception as e:
                console.print(f"❌ Error loading file: {e}")
                return False

    def show_menu(self):
        """Display main menu."""
        console.print(Rule("🔍 Search & Filter", style="bright_blue"))
        console.print()
        
        # Ensure data is loaded
        if not self.ensure_data_loaded():
            return False
        
        options = {
            "1": ("Search Content", self.run_search),
            "2": ("Show Data Summary", self.show_data_summary),
            "3": ("Load Different Data", self.load_data_file),
            "q": ("Quit", None)
        }
        
        console.print("Search Options:")
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
    
    def run_search(self):
        """Run search workflow."""
        
        # Build filters
        filters = self.build_search_filters()
        if not filters:
            return
        
        # Search
        with console.status("🔍 Searching..."):
            results = self.search_content(filters)
        
        console.print()
        console.print(f"📊 Found {len(results)} matching items")
        console.print()
        
        if not results:
            console.print("🔍 No items match your criteria")
            return
        
        # Sort options
        sort_opts = {
            "1": ("Newest first", "newest"),
            "2": ("Oldest first", "oldest"),
            "3": ("Highest engagement", "engagement"),
            "4": ("Most likes", "likes"),
            "5": ("Most replies", "replies"),
            "6": ("Most reposts", "reposts")
        }
        
        console.print("Sort by:")
        for k, (label, _) in sort_opts.items():
            console.print(f"  [{k}] {label}")
        
        sort_choice = Prompt.ask("Choose sort", choices=list(sort_opts.keys()), default="1", show_choices=False)
        _, sort_mode = sort_opts[sort_choice]
        
        results = self.sort_results(results, sort_mode)
        
        # Display results
        self.display_results(results)
        
        # Post-search options
        console.print()
        console.print("Options:")
        console.print("  [1] Show all results")
        console.print("  [2] Export results")
        console.print("  [3] New search")
        
        option_choice = Prompt.ask("Select option", choices=["1", "2", "3"], default="1", show_choices=False)
        
        if option_choice == "1":
            self.display_results(results, limit=len(results))
        elif option_choice == "2":
            self.export_results(results)
        elif option_choice == "3":
            self.run_search()
    
    def show_data_summary(self):
        """Show summary of loaded data."""
        
        console.print(Rule("📊 Data Summary", style="bright_cyan"))
        console.print()
        
        total_items = len(self.current_data)
        posts = [item for item in self.current_data if item.content_type == 'post']
        replies = [item for item in self.current_data if item.content_type == 'reply']
        reposts = [item for item in self.current_data if item.content_type == 'repost']
        likes = [item for item in self.current_data if item.content_type == 'like']
        
        pr_items = posts + replies
        total_likes = sum(int(it.like_count or 0) for it in pr_items)
        total_reposts = sum(int(it.repost_count or 0) for it in pr_items)
        total_replies = sum(int(it.reply_count or 0) for it in pr_items)
        
        avg_engagement = 0
        if pr_items:
            total_engagement = sum((int(it.like_count or 0) + 2*int(it.repost_count or 0) + 2.5*int(it.reply_count or 0)) for it in pr_items)
            avg_engagement = total_engagement / len(pr_items)
        
        table = Table(show_header=True, box=None)
        table.add_column("Metric", style="bold", width=20)
        table.add_column("Count", style="cyan", width=8)
        table.add_column("Details", style="dim", width=25)
        
        table.add_row("Total Items", str(total_items), "All content")
        table.add_row("Posts", str(len(posts)), "Original posts")
        table.add_row("Replies", str(len(replies)), "Comments/replies")
        table.add_row("Reposts", str(len(reposts)), "Your repost actions")
        table.add_row("Likes", str(len(likes)), "Your like actions")
        
        if pr_items:
            table.add_row("", "", "")
            table.add_row("Avg Engagement", f"{avg_engagement:.1f}", f"Across {len(pr_items)} posts/replies")
            table.add_row("Total Likes", str(total_likes), "On your posts/replies")
            table.add_row("Total Reposts", str(total_reposts), "On your posts/replies")
            table.add_row("Total Replies", str(total_replies), "On your posts/replies")
        
        console.print(table)
    
    def run(self):
        """Run the search script."""
        console.print()
        console.print("🔍 Skymarshal Search & Filter")
        console.print("=" * 50)
        console.print()
        
        try:
            while True:
                if not self.show_menu():
                    break
                console.print()
        except KeyboardInterrupt:
            console.print("\n👋 Goodbye!")
        except Exception as e:
            console.print(f"\n❌ Unexpected error: {e}")

def main():
    """Main entry point."""
    search_script = SearchScript()
    search_script.run()

if __name__ == "__main__":
    main()