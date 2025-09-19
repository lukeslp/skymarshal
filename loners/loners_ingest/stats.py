#!/usr/bin/env python3
"""
Skymarshal Statistics Script

This script provides comprehensive analytics and statistics for Bluesky content.
It analyzes engagement patterns, temporal trends, content performance, and more.

Usage: python stats.py
"""

import os
import sys
import json
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, Counter

# Add parent directory to path to import skymarshal modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

# Import from skymarshal
from skymarshal.models import ContentItem, UserSettings, parse_datetime
from skymarshal.auth import AuthManager
from skymarshal.data_manager import DataManager
from skymarshal.ui import UIManager

console = Console()

class StatsScript:
    """Standalone statistics and analytics functionality."""
    
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
        """Load a data file for analysis."""
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
    
    def show_basic_stats(self):
        """Show basic content statistics."""
        
        console.print(Rule("📊 Basic Statistics", style="bright_cyan"))
        console.print()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
            console=console,
        ) as progress:
            task = progress.add_task("Computing statistics...", total=1)
            
            total_items = len(self.current_data)
            posts = [item for item in self.current_data if item.content_type == 'post']
            replies = [item for item in self.current_data if item.content_type == 'reply']
            repost_items = [item for item in self.current_data if item.content_type == 'repost']
            like_items = [item for item in self.current_data if item.content_type == 'like']
            
            pr_items = posts + replies
            
            # Compute totals only over posts/replies
            total_likes = sum(int(it.like_count or 0) for it in pr_items)
            total_reposts = sum(int(it.repost_count or 0) for it in pr_items)
            total_replies = sum(int(it.reply_count or 0) for it in pr_items)
            total_engagement = sum((int(it.like_count or 0) + 2*int(it.repost_count or 0) + 2.5*int(it.reply_count or 0)) for it in pr_items)
            
            # Averages are per post/reply, not per total items
            avg_engagement = (total_engagement / len(pr_items)) if pr_items else 0
            avg_likes = (total_likes / len(pr_items)) if pr_items else 0
            dead_threads = [it for it in pr_items if it.like_count == 0 and it.repost_count == 0 and it.reply_count == 0]
            high_engagement = [it for it in pr_items if (it.like_count + 2*it.repost_count + 2.5*it.reply_count) >= self.settings.high_engagement_threshold]
            
            progress.update(task, completed=1)
        
        # Display results
        title = f"Statistics for {self.current_data_file.name if self.current_data_file else 'Current Data'}"
        stats_table = Table(title=title)
        stats_table.add_column("Metric", style="bold")
        stats_table.add_column("Value", style="bright_white")
        stats_table.add_column("Details", style="dim")
        
        # Basic counts
        stats_table.add_row("Total Items", str(total_items), "Everything")
        stats_table.add_row("Posts", str(len(posts)), "Posts")
        stats_table.add_row("Replies", str(len(replies)), "Comments/replies")
        stats_table.add_row("Reposts", str(len(repost_items)), "Your repost actions")
        stats_table.add_row("Likes", str(len(like_items)), "Your like actions")
        
        # Engagement totals
        stats_table.add_row("", "", "")
        denom = max(1, len(pr_items))
        stats_table.add_row("Total Likes", str(total_likes), f"Avg: {total_likes/denom:.1f} per post/reply")
        stats_table.add_row("Total Reposts (on posts)", str(total_reposts), f"Avg: {total_reposts/denom:.1f} per post/reply")
        stats_table.add_row("Total Replies", str(total_replies), f"Avg: {total_replies/denom:.1f} per post/reply")
        stats_table.add_row("Total Engagement", f"{int(total_engagement)}", f"Avg: {avg_engagement:.1f} per post/reply")
        stats_table.add_row("Avg Likes (posts/replies)", f"{avg_likes:.1f}", "Baseline for categories")
        
        # Engagement analysis & categories
        stats_table.add_row("", "", "")
        stats_table.add_row("High Engagement", str(len(high_engagement)), f"{self.settings.high_engagement_threshold}+ engagement score")

        # Likes-based categories (based on runtime avg) - only for posts, not replies
        avg_likes_runtime = getattr(self.settings, 'avg_likes_per_post', avg_likes) or avg_likes
        # Clamp thresholds to sensible minimums when average is near zero
        half = max(0.0, avg_likes_runtime * 0.5)
        one_half = max(1.0, avg_likes_runtime * 1.5)
        double = max(1.0, avg_likes_runtime * 2.0)
        
        # Dead threads: posts and replies with 0 engagement
        cat_dead = [it for it in pr_items if (it.like_count or 0) == 0]
        
        # Performance categories: posts only
        posts_only = [it for it in pr_items if it.content_type == "post"]
        cat_bomber = [it for it in posts_only if 0 < (it.like_count or 0) <= half]
        cat_mid = [it for it in posts_only if half < (it.like_count or 0) <= one_half]
        cat_banger = [it for it in posts_only if (it.like_count or 0) >= double]
        cat_viral = [it for it in posts_only if (it.like_count or 0) >= 2000]
        stats_table.add_row("", "", "")
        stats_table.add_row("Dead Threads", str(len(cat_dead)), "0 likes")
        stats_table.add_row("Bombers (posts)", str(len(cat_bomber)), f"≤ {half:.1f} likes")
        stats_table.add_row("Mid (posts)", str(len(cat_mid)), f"~ avg ({avg_likes_runtime:.1f})")
        stats_table.add_row("Bangers (posts)", str(len(cat_banger)), f"≥ {double:.1f} likes")
        stats_table.add_row("Viral (posts)", str(len(cat_viral)), "≥ 2000 likes")
        
        console.print(stats_table)
        console.print()
    
    def show_engagement_breakdown(self):
        """Show detailed engagement breakdown."""
        
        console.print(Rule("📈 Engagement Breakdown", style="bright_yellow"))
        console.print()
        
        pr_items = [item for item in self.current_data if item.content_type in ('post', 'reply')]
        if not pr_items:
            console.print("📭 No posts/replies to analyze")
            return
        
        ranges = [
            (0, 0, "💀 Dead"),
            (1, 5, "🌱 Low"),
            (6, 15, "📈 Medium"),
            (16, 50, "🔥 High"),
            (51, float('inf'), "🚀 Viral")
        ]
        
        table = Table()
        table.add_column("Range", style="bold")
        table.add_column("Count", style="bright_white")
        table.add_column("Percentage", style="dim")
        
        total = len(pr_items)
        
        for min_eng, max_eng, label in ranges:
            if max_eng == float('inf'):
                count = len([item for item in pr_items if item.engagement_score >= min_eng])
            else:
                count = len([item for item in pr_items if min_eng <= item.engagement_score <= max_eng])
            
            percentage = (count / total * 100) if total else 0
            table.add_row(label, str(count), f"{percentage:.1f}%")
        
        console.print(table)
        console.print()
    
    def show_temporal_analysis(self):
        """Show engagement by time patterns."""
        
        console.print(Rule("🕒 Temporal Analysis", style="bright_magenta"))
        console.print()
        
        items = [it for it in self.current_data if it.content_type in ('post','reply') and it.created_at]
        if not items:
            console.print("[dim]No timestamped posts/replies to analyze[/dim]")
            return
        
        by_hour = {h: 0 for h in range(24)}
        by_day = {d: 0 for d in range(7)}
        by_month = defaultdict(int)
        
        for it in items:
            dt = parse_datetime(it.created_at)
            if not dt:
                continue
            eng = int(it.like_count or 0) + 2*int(it.repost_count or 0) + 2.5*int(it.reply_count or 0)
            by_hour[dt.hour] += eng
            by_day[dt.weekday()] += eng
            by_month[f"{dt.year}-{dt.month:02d}"] += eng
        
        # Hour analysis
        hours_sorted = sorted(by_hour.items(), key=lambda kv: kv[1], reverse=True)
        top_hours = {h for h, _ in hours_sorted[:5]}
        bottom_hours = {h for h, _ in sorted(by_hour.items(), key=lambda kv: kv[1])[:5]}
        
        table = Table(title="By Hour of Day")
        table.add_column("Hour", style="bold")
        table.add_column("Engagement", style="cyan")
        table.add_column("", style="green")
        
        for h in range(24):
            mark = ""
            style = None
            if h in top_hours:
                mark = "⬆️"
                style = "bold green"
            elif h in bottom_hours:
                mark = "⬇️"
                style = "dim"
            
            hr = f"{h:02d}:00"
            val = str(by_hour[h])
            
            if style:
                table.add_row(f"[bold]{hr}[/bold]" if h in top_hours else hr, 
                           f"[{style}]{val}[/{style}]", mark)
            else:
                table.add_row(hr, val, mark)
        
        console.print(table)
        console.print()
        
        # Day of week analysis
        dow_names = {0:'Mon',1:'Tue',2:'Wed',3:'Thu',4:'Fri',5:'Sat',6:'Sun'}
        table2 = Table(title="By Day of Week")
        table2.add_column("Day", style="bold")
        table2.add_column("Engagement", style="cyan")
        
        for d in range(7):
            table2.add_row(dow_names[d], str(by_day[d]))
        
        console.print(table2)
        console.print()
        
        # Monthly analysis (if enough data)
        if len(by_month) > 1:
            table3 = Table(title="By Month")
            table3.add_column("Month", style="bold")
            table3.add_column("Engagement", style="cyan")
            
            for month in sorted(by_month.keys()):
                table3.add_row(month, str(by_month[month]))
            
            console.print(table3)
            console.print()
    
    def show_top_content(self):
        """Show top performing content."""
        
        console.print(Rule("🔥 Top Content", style="bright_red"))
        console.print()
        
        pr_items = [item for item in self.current_data if item.content_type in ('post', 'reply')]
        if not pr_items:
            console.print("📭 No posts/replies to analyze")
            return
        
        # Sort by engagement score
        sorted_items = sorted(pr_items, key=lambda x: x.engagement_score, reverse=True)
        top_items = sorted_items[:10]
        
        table = Table(show_header=True)
        table.add_column("Rank", style="bold", width=4)
        table.add_column("Type", style="cyan", width=6)
        table.add_column("Preview", style="white", width=40)
        table.add_column("Likes", style="red", width=4)
        table.add_column("Reposts", style="blue", width=4)
        table.add_column("Replies", style="yellow", width=4)
        table.add_column("Engagement", style="green", width=6)
        table.add_column("Date", style="dim", width=10)
        
        for i, item in enumerate(top_items, 1):
            text_preview = (item.text[:35] + "...") if item.text and len(item.text) > 35 else (item.text or "")
            created = item.created_at[:10] if item.created_at else ""
            
            table.add_row(
                str(i), item.content_type, text_preview,
                str(item.like_count), str(item.repost_count), str(item.reply_count),
                str(int(item.engagement_score)), created
            )
        
        console.print(table)
        console.print()
    
    def show_dead_threads(self):
        """Show content with no engagement."""
        
        console.print(Rule("💀 Dead Threads", style="dim"))
        console.print()
        
        pr_items = [item for item in self.current_data if item.content_type in ('post', 'reply')]
        dead_threads = [it for it in pr_items if it.like_count == 0 and it.repost_count == 0 and it.reply_count == 0]
        
        if not dead_threads:
            console.print("🎉 No dead threads found!")
            return
        
        console.print(f"Found {len(dead_threads)} dead threads (0 engagement)")
        console.print()
        
        table = Table(show_header=True)
        table.add_column("Type", style="cyan", width=6)
        table.add_column("Preview", style="white", width=50)
        table.add_column("Date", style="dim", width=10)
        
        for item in dead_threads[:20]:  # Show first 20
            text_preview = (item.text[:45] + "...") if item.text and len(item.text) > 45 else (item.text or "")
            created = item.created_at[:10] if item.created_at else ""
            
            table.add_row(item.content_type, text_preview, created)
        
        console.print(table)
        
        if len(dead_threads) > 20:
            console.print()
            console.print(f"... and {len(dead_threads) - 20} more dead threads")
        console.print()
    
    def show_content_distribution(self):
        """Show content type distribution."""
        
        console.print(Rule("📊 Content Distribution", style="bright_blue"))
        console.print()
        
        # Count by content type
        type_counts = Counter(item.content_type for item in self.current_data)
        
        table = Table()
        table.add_column("Content Type", style="bold")
        table.add_column("Count", style="cyan")
        table.add_column("Percentage", style="dim")
        
        total = len(self.current_data)
        
        for content_type, count in type_counts.most_common():
            percentage = (count / total * 100) if total else 0
            table.add_row(content_type.title(), str(count), f"{percentage:.1f}%")
        
        console.print(table)
        console.print()
    
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
            console.print("To analyze your Bluesky data, you need to download it first.")
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
                
                password, action = self.ui.input_with_navigation("App Password: ", password=True, context="password")
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
                    console.print("[dim]Statistics will use cached engagement data[/dim]")
                
                return True
            else:
                console.print("❌ Data analysis requires downloaded data")
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
                    console.print("[dim]Statistics will use cached engagement data[/dim]")
                
                return True
                
            except Exception as e:
                console.print(f"❌ Error loading file: {e}")
                return False

    def show_menu(self):
        """Display main menu."""
        console.print(Rule("📊 Statistics & Analytics", style="bright_cyan"))
        console.print()
        
        # Ensure data is loaded
        if not self.ensure_data_loaded():
            return False
        
        options = {
            "1": ("Basic Statistics", self.show_basic_stats),
            "2": ("Engagement Breakdown", self.show_engagement_breakdown),
            "3": ("Temporal Analysis", self.show_temporal_analysis),
            "4": ("Top Content", self.show_top_content),
            "5": ("Dead Threads", self.show_dead_threads),
            "6": ("Content Distribution", self.show_content_distribution),
            "7": ("All Reports", self.show_all_reports),
            "8": ("Load Different Data", self.load_data_file),
            "q": ("Quit", None)
        }
        
        console.print("Analysis Options:")
        for key, (desc, _) in options.items():
            console.print(f"  [{key}] {desc}")
        console.print()
        
        choice = Prompt.ask("Select analysis", choices=list(options.keys()), default="1", show_choices=False)
        
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
    
    def show_all_reports(self):
        """Show all statistics reports."""
        
        console.print(Rule("📊 Complete Analytics Report", style="bright_green"))
        console.print()
        
        reports = [
            ("Basic Statistics", self.show_basic_stats),
            ("Engagement Breakdown", self.show_engagement_breakdown),
            ("Temporal Analysis", self.show_temporal_analysis),
            ("Top Content", self.show_top_content),
            ("Dead Threads", self.show_dead_threads),
            ("Content Distribution", self.show_content_distribution),
        ]
        
        for title, func in reports:
            console.print(Rule(f"📊 {title}", style="dim"))
            func()
            console.print()
            
            if not Confirm.ask("Continue to next report?", default=True):
                break
    
    def run(self):
        """Run the statistics script."""
        console.print()
        console.print("📊 Skymarshal Statistics & Analytics")
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
    stats_script = StatsScript()
    stats_script.run()

if __name__ == "__main__":
    main()