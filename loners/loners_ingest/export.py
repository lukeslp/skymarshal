#!/usr/bin/env python3
"""
Skymarshal Export Script

This script provides data export capabilities for Bluesky content.
It can export data in various formats (JSON, CSV) with filtering options.

Usage: python export.py
"""

import os
import sys
import json
import csv
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

class ExportScript:
    """Standalone data export functionality."""
    
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
        """Load a data file for export."""
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
    
    def build_export_filters(self) -> Optional[SearchFilters]:
        """Build filters for content to export."""
        console.print(Rule("Build Export Filters", style="bright_yellow"))
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
        
        console.print("Content Type to Export:")
        for key, (_, desc) in content_types.items():
            console.print(f"  [{key}] {desc}")
        
        type_choice = Prompt.ask("Select content type", choices=list(content_types.keys()), default="1", show_choices=False)
        content_type_value, _ = content_types[type_choice]
        filters.content_type = ContentType(content_type_value)
        
        console.print()
        
        # Keyword filters
        if Confirm.ask("Export content containing specific keywords?", default=False):
            keywords_input = Prompt.ask("Enter keywords (comma separated)", default="")
            if keywords_input:
                filters.keywords = [k.strip() for k in keywords_input.split(",") if k.strip()]
        
        console.print()
        
        # Engagement filters
        if Confirm.ask("Export based on engagement levels?", default=False):
            console.print()
            console.print("Engagement Filter Type:")
            console.print("  [1] Quick presets")
            console.print("  [2] Custom thresholds")
            
            filter_choice = Prompt.ask("Select filter option", choices=["1", "2"], default="1")
            
            if filter_choice == "1":
                self._apply_export_presets(filters)
            else:
                self._apply_custom_export_filters(filters)
        
        # Date filters
        if Confirm.ask("Export content from specific date range?", default=False):
            console.print()
            console.print("Date Range (YYYY-MM-DD or ISO8601)")
            start_date = Prompt.ask("Start date", default="")
            end_date = Prompt.ask("End date", default="")
            filters.start_date = start_date or None
            filters.end_date = end_date or None
        
        return filters
    
    def _apply_export_presets(self, filters: SearchFilters):
        """Apply export-specific presets."""
        console.print()
        console.print("Export Presets:")
        console.print("  [1] Dead threads (0 engagement)")
        console.print("  [2] Low engagement (1-5)")
        console.print("  [3] Medium engagement (6-15)")
        console.print("  [4] High engagement (16-50)")
        console.print("  [5] Viral content (50+)")
        console.print("  [6] All content (no filter)")
        
        preset_choice = Prompt.ask("Select preset", choices=["1", "2", "3", "4", "5", "6"], default="6")
        
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
        # Option 6 leaves filters unchanged (all content)
    
    def _apply_custom_export_filters(self, filters: SearchFilters):
        """Apply custom export filters."""
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
    
    def filter_content(self, filters: SearchFilters) -> List[ContentItem]:
        """Filter content based on criteria."""
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
    
    def export_to_json(self, items: List[ContentItem], filename: str) -> bool:
        """Export items to JSON format."""
        try:
            export_path = self.json_dir / f"{filename}.json"
            
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
                    },
                    'raw_data': item.raw_data
                })
            
            with open(export_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            console.print(f"Exported {len(items)} items to {export_path}")
            return True
            
        except Exception as e:
            console.print(f"JSON export failed: {e}")
            return False
    
    def export_to_csv(self, items: List[ContentItem], filename: str) -> bool:
        """Export items to CSV format."""
        try:
            export_path = self.json_dir / f"{filename}.csv"
            
            with open(export_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'URI', 'CID', 'Type', 'Text', 'Created At',
                    'Likes', 'Reposts', 'Replies', 'Engagement Score',
                    'Raw Data'
                ])
                
                for item in items:
                    writer.writerow([
                        item.uri,
                        item.cid,
                        item.content_type,
                        item.text or '',
                        item.created_at or '',
                        item.like_count,
                        item.repost_count,
                        item.reply_count,
                        item.engagement_score,
                        json.dumps(item.raw_data) if item.raw_data else ''
                    ])
            
            console.print(f"Exported {len(items)} items to {export_path}")
            return True
            
        except Exception as e:
            console.print(f"CSV export failed: {e}")
            return False
    
    def export_to_markdown(self, items: List[ContentItem], filename: str) -> bool:
        """Export items to Markdown format."""
        try:
            export_path = self.json_dir / f"{filename}.md"
            
            with open(export_path, 'w', encoding='utf-8') as f:
                f.write(f"# Bluesky Content Export\n\n")
                f.write(f"Exported on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total items: {len(items)}\n\n")
                
                for i, item in enumerate(items, 1):
                    f.write(f"## {i}. {item.content_type.title()}\n\n")
                    f.write(f"**URI:** `{item.uri}`\n\n")
                    f.write(f"**Created:** {item.created_at or 'Unknown'}\n\n")
                    f.write(f"**Engagement:** {item.like_count} likes, {item.repost_count} reposts, {item.reply_count} replies (Score: {item.engagement_score})\n\n")
                    
                    if item.text:
                        f.write(f"**Content:**\n\n")
                        f.write(f"{item.text}\n\n")
                    
                    f.write("---\n\n")
            
            console.print(f"✅ Exported {len(items)} items to {export_path}")
            return True
            
        except Exception as e:
            console.print(f"❌ Markdown export failed: {e}")
            return False
    
    def run_export_workflow(self):
        """Run the complete export workflow."""
        if not self.current_data:
            console.print("❌ No data loaded")
            console.print("💡 Load a data file first")
            return
        
        # Build filters
        filters = self.build_export_filters()
        if not filters:
            return
        
        # Filter content
        with console.status("🔍 Filtering content..."):
            items = self.filter_content(filters)
        
        console.print()
        console.print(f"📊 Found {len(items)} items matching export criteria")
        console.print()
        
        if not items:
            console.print("🔍 No items match your criteria")
            return
        
        # Show preview
        console.print("Preview of items to export:")
        console.print()
        
        table = Table(show_header=True)
        table.add_column("Type", style="cyan", width=6)
        table.add_column("Preview", style="white", width=40)
        table.add_column("Likes", style="red", width=4)
        table.add_column("Reposts", style="blue", width=4)
        table.add_column("Replies", style="yellow", width=4)
        table.add_column("Engagement", style="green", width=6)
        table.add_column("Date", style="dim", width=10)
        
        for item in items[:5]:  # Show first 5
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
        
        if len(items) > 5:
            console.print()
            console.print(f"... and {len(items) - 5} more items")
        
        console.print()
        
        # Select export format
        formats = {
            "1": ("json", "JSON format (structured data)"),
            "2": ("csv", "CSV format (spreadsheet compatible)"),
            "3": ("md", "Markdown format (human readable)"),
            "4": ("all", "All formats")
        }
        
        console.print("Export format:")
        for key, (_, desc) in formats.items():
            console.print(f"  [{key}] {desc}")
        
        format_choice = Prompt.ask("Select format", choices=list(formats.keys()), default="1", show_choices=False)
        export_format, _ = formats[format_choice]
        
        # Get filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"export_{timestamp}"
        filename = Prompt.ask("Filename (without extension)", default=default_filename)
        
        # Execute export
        success_count = 0
        
        if export_format == "json":
            if self.export_to_json(items, filename):
                success_count += 1
        elif export_format == "csv":
            if self.export_to_csv(items, filename):
                success_count += 1
        elif export_format == "md":
            if self.export_to_markdown(items, filename):
                success_count += 1
        elif export_format == "all":
            if self.export_to_json(items, filename):
                success_count += 1
            if self.export_to_csv(items, filename):
                success_count += 1
            if self.export_to_markdown(items, filename):
                success_count += 1
        
        console.print()
        if success_count > 0:
            console.print(f"Export completed successfully ({success_count} file(s) created)")
            console.print(f"Files saved to: {self.json_dir}")
        else:
            console.print("Export failed")
    
    def show_menu(self):
        """Display main menu."""
        console.print(Rule("Data Export", style="bright_green"))
        console.print()
        
        if not self.current_data:
            console.print("No data loaded")
            console.print("Use 'Load Data File' to load data for export")
            console.print()
        
        options = {
            "1": ("Load Data File", self.load_data_file),
            "2": ("Export Content", self.run_export_workflow),
            "3": ("Show Data Summary", self.show_data_summary),
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
    
    def show_data_summary(self):
        """Show summary of loaded data."""
        if not self.current_data:
            console.print("No data loaded")
            return
        
        console.print(Rule("Data Summary", style="bright_cyan"))
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
        """Run the export script."""
        console.print()
        console.print("Skymarshal Data Export")
        console.print("=" * 50)
        console.print()
        
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
    export_script = ExportScript()
    export_script.run()

if __name__ == "__main__":
    main()
