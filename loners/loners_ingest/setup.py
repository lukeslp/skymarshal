#!/usr/bin/env python3
"""
Skymarshal Setup Script - Download and Process CAR Files

This script handles the initial setup process:
1. Authenticate with Bluesky
2. Download complete backup (.car file)
3. Process backup into usable JSON format
4. Set up local data structure

Usage: python setup.py
"""

import os
import sys
import json
from pathlib import Path
from typing import Optional, Set
from datetime import datetime

# Add parent directory to path to import skymarshal modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from atproto import Client
from rich.console import Console
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
from rich.panel import Panel
from rich.rule import Rule

# Import from skymarshal
from skymarshal.models import ContentItem, UserSettings, parse_datetime, merge_content_items
from skymarshal.auth import AuthManager
from skymarshal.data_manager import DataManager
from skymarshal.ui import UIManager

console = Console()

class SetupManager:
    """Handles initial setup and data preparation."""
    
    def __init__(self):
        self.skymarshal_dir = Path.home() / '.skymarshal'
        self.cars_dir = self.skymarshal_dir / 'cars'
        self.json_dir = self.skymarshal_dir / 'json'
        
        # Create directories
        self.skymarshal_dir.mkdir(exist_ok=True)
        self.cars_dir.mkdir(exist_ok=True)
        self.json_dir.mkdir(exist_ok=True)
        
        # Initialize settings
        self.settings_file = Path.home() / '.car_inspector_settings.json'
        self.settings = self._load_settings()
        
        # Initialize managers
        self.ui = UIManager(self.settings)
        self.auth = AuthManager(self.ui)
        self.data_manager = DataManager(self.auth, self.settings, 
                                       self.skymarshal_dir, self.cars_dir, self.json_dir)
    
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
    
    def _save_settings(self):
        """Save current settings."""
        try:
            data = {
                'download_limit_default': self.settings.download_limit_default,
                'default_categories': self.settings.default_categories,
                'records_page_size': self.settings.records_page_size,
                'hydrate_batch_size': self.settings.hydrate_batch_size,
                'category_workers': self.settings.category_workers,
                'file_list_page_size': self.settings.file_list_page_size,
                'high_engagement_threshold': self.settings.high_engagement_threshold,
                'use_subject_engagement_for_reposts': self.settings.use_subject_engagement_for_reposts,
                'fetch_order': self.settings.fetch_order,
            }
            with open(self.settings_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            console.print(f"[yellow]Warning: failed to save settings: {e}[/yellow]")
    
    def authenticate(self) -> bool:
        """Handle authentication."""
        console.print(Rule("🔐 Authentication", style="bright_green"))
        console.print()
        
        if self.auth.is_authenticated():
            console.print("✅ Already authenticated!")
            console.print(f"👤 Handle: @{self.auth.current_handle}")
            if not Confirm.ask("Continue with current session?"):
                self.auth.client = None
                self.auth.current_handle = None
                self.auth.current_did = None
        
        if not self.auth.is_authenticated():
            console.print("🔓 Authentication required")
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
                console.print(f"✅ Logged in as @{self.auth.current_handle}!")
                return True
            else:
                console.print("❌ Authentication failed", style="red")
                if not Confirm.ask("Try again?", default=True):
                    return False
        
        return True
    
    def get_download_options(self) -> tuple:
        """Get download configuration options."""
        console.print()
        console.print("📥 Download Configuration")
        console.print()
        
        limit = IntPrompt.ask("Number of items per category to backup",
                            default=self.settings.download_limit_default)
        
        console.print()
        console.print("Select categories to backup:")
        console.print("  [1] posts & replies   [default: ON]")
        console.print("  [2] likes             [default: OFF]")
        console.print("  [3] reposts           [default: OFF]")
        console.print()
        
        # Initialize defaults
        default_cats = set(self.settings.default_categories)
        selected = {
            'posts': True if not default_cats else ('posts' in default_cats),
            'likes': False if not default_cats else ('likes' in default_cats),
            'reposts': False if not default_cats else ('reposts' in default_cats),
        }
        
        console.print("Type a combination of 1/2/3 to toggle (e.g., 23), or just press Enter to accept.")
        raw = Prompt.ask("Toggle keys (optional)", default="")
        raw = (raw or "").strip().replace(" ", "")
        for ch in raw:
            if ch == '1':
                selected['posts'] = not selected['posts']
            elif ch == '2':
                selected['likes'] = not selected['likes']
            elif ch == '3':
                selected['reposts'] = not selected['reposts']
        
        # Require at least posts/replies
        if not selected['posts']:
            console.print("[yellow]Posts & replies are required; enabling by default[/yellow]")
            selected['posts'] = True
        
        categories = {k for k, v in selected.items() if v}
        
        date_start = date_end = None
        if Confirm.ask("Limit by date range?", default=False):
            console.print("📅 Date Range (YYYY-MM-DD or ISO8601)")
            ds = Prompt.ask("Start date", default="")
            de = Prompt.ask("End date", default="")
            date_start = ds or None
            date_end = de or None
        
        return limit, categories, date_start, date_end
    
    def download_car_backup(self) -> Optional[Path]:
        """Download complete CAR backup."""
        console.print()
        console.print("📦 Downloading Complete Backup")
        console.print()
        
        handle = self.auth.current_handle
        console.print(f"Creating backup for @{handle}...")
        
        car_path = self.data_manager.download_car(handle)
        if car_path:
            console.print(f"✅ CAR backup downloaded: {car_path.name}")
            return car_path
        else:
            console.print("❌ Failed to download CAR backup")
            return None
    
    def download_api_data(self) -> Optional[Path]:
        """Download data via API."""
        console.print()
        console.print("📡 Downloading Data via API")
        console.print()
        
        handle = self.auth.current_handle
        limit, categories, date_start, date_end = self.get_download_options()
        
        console.print("🔐 Re-authentication required for API access")
        password = Prompt.ask("[bold white]App Password: [/]", password=True)
        
        if not self.auth.authenticate_client(handle, password):
            console.print("❌ Authentication failed")
            return None
        
        with console.status("🔄 Downloading data..."):
            try:
                export_path = self.data_manager.export_user_data(
                    handle, limit, 
                    categories=categories, 
                    date_start=date_start, 
                    date_end=date_end,
                    replace_existing=True
                )
                return export_path
            except Exception as e:
                console.print(f"❌ Download error: {e}")
                return None
    
    def process_car_file(self, car_path: Path) -> Optional[Path]:
        """Process CAR file into JSON format."""
        console.print()
        console.print("🔄 Processing CAR File")
        console.print()
        
        handle = self.auth.current_handle
        
        # Select categories to process
        console.print("Select which categories to process from the backup:")
        categories = self.ui.select_categories_for_processing()
        
        console.print("📦 Processing backup into usable data...")
        imported_path = self.data_manager.import_car_replace(car_path, handle, categories=categories)
        
        if imported_path:
            console.print(f"✅ Data processed successfully: {imported_path.name}")
            return imported_path
        else:
            console.print("❌ Failed to process CAR file")
            return None
    
    def show_data_summary(self, json_path: Path):
        """Show summary of processed data."""
        try:
            with console.status("📄 Loading data..."):
                data = self.data_manager.load_exported_data(json_path)
            
            if not data:
                console.print("⚠️ No content found in processed data")
                return
            
            # Calculate basic stats
            total_items = len(data)
            posts = [item for item in data if item.content_type == 'post']
            replies = [item for item in data if item.content_type == 'reply']
            reposts = [item for item in data if item.content_type == 'repost']
            likes = [item for item in data if item.content_type == 'like']
            
            pr_items = posts + replies
            total_likes = sum(int(it.like_count or 0) for it in pr_items)
            total_reposts = sum(int(it.repost_count or 0) for it in pr_items)
            total_replies = sum(int(it.reply_count or 0) for it in pr_items)
            
            avg_engagement = 0
            if pr_items:
                total_engagement = sum((int(it.like_count or 0) + 2*int(it.repost_count or 0) + 2.5*int(it.reply_count or 0)) for it in pr_items)
                avg_engagement = total_engagement / len(pr_items)
            
            console.print()
            console.print(Rule("📊 Data Summary", style="bright_cyan"))
            console.print()
            
            from rich.table import Table
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
            
        except Exception as e:
            console.print(f"❌ Error loading data: {e}")
    
    def run_setup(self):
        """Run the complete setup process."""
        console.print()
        console.print("🚀 Skymarshal Setup")
        console.print("=" * 50)
        console.print()
        
        # Step 1: Authentication
        if not self.authenticate():
            console.print("❌ Setup cancelled - authentication required")
            return False
        
        # Step 2: Choose data source
        console.print()
        console.print("📋 Choose Data Source")
        console.print()
        console.print("(1) 📦 Download complete backup (.car) - recommended")
        console.print("(2) 📡 Download data via API")
        console.print("(3) 📂 Process existing CAR file")
        console.print()
        
        choice = Prompt.ask("Select option", choices=["1", "2", "3"], default="1", show_choices=False)
        
        json_path = None
        
        if choice == "1":
            # Download CAR and process
            car_path = self.download_car_backup()
            if car_path:
                json_path = self.process_car_file(car_path)
        
        elif choice == "2":
            # Download via API
            json_path = self.download_api_data()
        
        elif choice == "3":
            # Process existing CAR
            car_files = self.data_manager.get_user_files(self.auth.current_handle, 'car')
            if not car_files:
                console.print(f"📭 No CAR files found for @{self.auth.current_handle}")
                return False
            
            selected_car = self.ui.show_file_picker(car_files)
            if selected_car:
                json_path = self.process_car_file(selected_car)
        
        # Step 3: Show summary
        if json_path:
            self.show_data_summary(json_path)
            console.print()
            console.print("✅ Setup complete!")
            console.print(f"📁 Data file: {json_path}")
            console.print(f"📁 CAR files: {self.cars_dir}")
            console.print(f"📁 JSON files: {self.json_dir}")
            return True
        else:
            console.print("❌ Setup failed")
            return False

def main():
    """Main entry point."""
    try:
        setup = SetupManager()
        success = setup.run_setup()
        
        if success:
            console.print()
            console.print("🎉 Ready to use Skymarshal!")
            console.print("Run other loner scripts to analyze, search, or manage your data.")
        else:
            console.print()
            console.print("❌ Setup incomplete. Please try again.")
            
    except KeyboardInterrupt:
        console.print("\n👋 Setup cancelled by user")
    except Exception as e:
        console.print(f"\n❌ Unexpected error: {e}")
        console.print("Please report this issue if it persists.")

if __name__ == "__main__":
    main()