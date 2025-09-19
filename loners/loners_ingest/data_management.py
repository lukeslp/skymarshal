#!/usr/bin/env python3
"""
Skymarshal Data Management Script

This script provides comprehensive data management capabilities for Skymarshal.
It handles file operations, backup management, data cleanup, and file organization.

Usage: python data_management.py
"""

import os
import sys
import json
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
from skymarshal.models import ContentItem, UserSettings
from skymarshal.auth import AuthManager
from skymarshal.data_manager import DataManager
from skymarshal.ui import UIManager

console = Console()

class DataManagementScript:
    """Standalone data management functionality."""
    
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
    
    def show_data_overview(self):
        """Show overview of all data files."""
        console.print(Rule("📊 Data Overview", style="bright_cyan"))
        console.print()
        
        # Get all files
        car_files = list(self.cars_dir.glob("*.car"))
        json_files = list(self.json_dir.glob("*.json"))
        
        # Show summary
        table = Table(show_header=True)
        table.add_column("File Type", style="bold")
        table.add_column("Count", style="cyan")
        table.add_column("Total Size", style="green")
        table.add_column("Description", style="dim")
        
        car_size = sum(f.stat().st_size for f in car_files)
        json_size = sum(f.stat().st_size for f in json_files)
        
        table.add_row("CAR Files", str(len(car_files)), f"{car_size / 1024 / 1024:.1f} MB", "Complete backups")
        table.add_row("JSON Files", str(len(json_files)), f"{json_size / 1024 / 1024:.1f} MB", "Processed data")
        
        console.print(table)
        console.print()
        
        # Show individual files
        if car_files or json_files:
            console.print("Individual Files:")
            console.print()
            
            file_table = Table(show_header=True)
            file_table.add_column("Type", style="cyan", width=6)
            file_table.add_column("Filename", style="white", width=30)
            file_table.add_column("Size", style="green", width=10)
            file_table.add_column("Modified", style="dim", width=15)
            
            for file_path in sorted(car_files + json_files, key=lambda x: x.stat().st_mtime, reverse=True):
                file_type = "CAR" if file_path.suffix == '.car' else "JSON"
                size = file_path.stat().st_size
                modified = datetime.fromtimestamp(file_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                
                file_table.add_row(
                    file_type,
                    file_path.name,
                    f"{size / 1024 / 1024:.1f} MB",
                    modified
                )
            
            console.print(file_table)
        else:
            console.print("📭 No data files found")
            console.print("💡 Use 'Download Data' to create your first backup")
        
        console.print()
    
    def download_car_backup(self):
        """Download complete CAR backup."""
        console.print(Rule("📦 Download CAR Backup", style="bright_blue"))
        console.print()
        
        # Authentication required
        if not self.auth.is_authenticated():
            console.print("🔐 Authentication required")
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
            
            if not self.auth.authenticate_client(handle, password):
                console.print("❌ Authentication failed")
                return False
        
        handle = self.auth.current_handle
        console.print(f"Creating backup for @{handle}...")
        
        car_path = self.data_manager.download_car(handle)
        if car_path:
            console.print(f"✅ CAR backup downloaded: {car_path.name}")
            return True
        else:
            console.print("❌ Failed to download CAR backup")
            return False
    
    def download_api_data(self):
        """Download data via API."""
        console.print(Rule("📡 Download Data via API", style="bright_green"))
        console.print()
        
        # Authentication required
        if not self.auth.is_authenticated():
            console.print("🔐 Authentication required")
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
            
            if not self.auth.authenticate_client(handle, password):
                console.print("❌ Authentication failed")
                return False
        
        handle = self.auth.current_handle
        
        # Get download options
        limit = IntPrompt.ask("Number of items per category to backup", default=self.settings.download_limit_default)
        
        console.print()
        console.print("Select categories to backup:")
        categories = self.ui.select_categories_for_processing()
        
        # Date range option
        use_date_range = Confirm.ask("Limit by date range?", default=False)
        date_start = date_end = None
        if use_date_range:
            console.print("📅 Date Range (YYYY-MM-DD or ISO8601)")
            date_start = Prompt.ask("Start date", default="") or None
            date_end = Prompt.ask("End date", default="") or None
        
        console.print("🔐 Re-authentication required for API access")
        password = Prompt.ask("[bold white]App Password: [/]", password=True)
        
        if not self.auth.authenticate_client(handle, password):
            console.print("❌ Authentication failed")
            return False
        
        with console.status("🔄 Downloading data..."):
            try:
                export_path = self.data_manager.export_user_data(
                    handle, limit, 
                    categories=categories, 
                    date_start=date_start, 
                    date_end=date_end,
                    replace_existing=True
                )
                if export_path:
                    console.print(f"✅ Data downloaded successfully: {export_path.name}")
                    return True
                else:
                    console.print("❌ Download failed")
                    return False
            except Exception as e:
                console.print(f"❌ Download error: {e}")
                return False
    
    def process_car_file(self):
        """Process existing CAR file into JSON format."""
        console.print(Rule("🔄 Process CAR File", style="bright_yellow"))
        console.print()
        
        # Get available CAR files
        car_files = list(self.cars_dir.glob("*.car"))
        if not car_files:
            console.print("📭 No CAR files found")
            console.print("💡 Use 'Download CAR Backup' to create a backup first")
            return False
        
        console.print("Available CAR files:")
        console.print()
        
        # Show file picker
        selected_car = self.ui.show_file_picker(car_files)
        if not selected_car:
            return False
        
        # Get handle for processing
        if self.auth.current_handle:
            handle = self.auth.current_handle
        else:
            # Try to extract handle from filename
            name_parts = selected_car.stem.split('_')
            if name_parts and '.' in name_parts[0]:
                handle = name_parts[0]
            else:
                while True:
                    handle, action = self.ui.input_with_navigation("Enter handle for this CAR file: @", context="handle")
                    if action in ["back", "main"]:
                        return False
                    if handle:
                        handle = self.auth.normalize_handle(handle)
                        break
        
        # Select categories to process
        console.print("Select which categories to process from the backup:")
        categories = self.ui.select_categories_for_processing()
        
        console.print("📦 Processing backup into usable data...")
        imported_path = self.data_manager.import_car_replace(selected_car, handle, categories=categories)
        
        if imported_path:
            console.print(f"✅ Data processed successfully: {imported_path.name}")
            return True
        else:
            console.print("❌ Failed to process CAR file")
            return False
    
    def backup_car_file(self):
        """Create timestamped backup of CAR file."""
        console.print(Rule("💾 Backup CAR File", style="bright_magenta"))
        console.print()
        
        # Get available CAR files
        car_files = list(self.cars_dir.glob("*.car"))
        if not car_files:
            console.print("📭 No CAR files found")
            console.print("💡 Use 'Download CAR Backup' to create a backup first")
            return False
        
        console.print("Available CAR files:")
        console.print()
        
        # Show file picker
        selected_car = self.ui.show_file_picker(car_files)
        if not selected_car:
            return False
        
        # Get handle for backup
        if self.auth.current_handle:
            handle = self.auth.current_handle
        else:
            # Try to extract handle from filename
            name_parts = selected_car.stem.split('_')
            if name_parts and '.' in name_parts[0]:
                handle = name_parts[0]
            else:
                while True:
                    handle, action = self.ui.input_with_navigation("Enter handle for this CAR file: @", context="handle")
                    if action in ["back", "main"]:
                        return False
                    if handle:
                        handle = self.auth.normalize_handle(handle)
                        break
        
        try:
            self.data_manager.backup_car(handle)
            console.print(f"✅ CAR file backed up for @{handle}")
            return True
        except Exception as e:
            console.print(f"❌ Backup failed: {e}")
            return False
    
    def clear_local_data(self):
        """Clear local data files."""
        console.print(Rule("🧹 Clear Local Data", style="bright_red"))
        console.print()
        
        # Get handle
        if self.auth.current_handle:
            handle = self.auth.current_handle
        else:
            while True:
                handle, action = self.ui.input_with_navigation("Handle to clear data for: @", context="handle")
                if action in ["back", "main"]:
                    return False
                if handle:
                    handle = self.auth.normalize_handle(handle)
                    break
        
        console.print(Panel(f"This will delete local JSON and CAR files for @{handle}", title="Clear Local Data", border_style="red"))
        
        if Confirm.ask("Proceed with deleting local files?", default=False):
            deleted = self.data_manager.clear_local_data(handle)
            if deleted:
                console.print(f"✅ Deleted {deleted} local file(s)")
                return True
            else:
                console.print("[dim]Nothing was deleted[/dim]")
                return False
        else:
            console.print("❌ Clear cancelled")
            return False
    
    def organize_files(self):
        """Organize data files by date and type."""
        console.print(Rule("📁 Organize Files", style="bright_blue"))
        console.print()
        
        # Get all files
        car_files = list(self.cars_dir.glob("*.car"))
        json_files = list(self.json_dir.glob("*.json"))
        
        if not car_files and not json_files:
            console.print("📭 No files to organize")
            return False
        
        console.print("Current files:")
        console.print()
        
        file_table = Table(show_header=True)
        file_table.add_column("Type", style="cyan", width=6)
        file_table.add_column("Filename", style="white", width=40)
        file_table.add_column("Size", style="green", width=10)
        file_table.add_column("Modified", style="dim", width=15)
        
        for file_path in sorted(car_files + json_files, key=lambda x: x.stat().st_mtime, reverse=True):
            file_type = "CAR" if file_path.suffix == '.car' else "JSON"
            size = file_path.stat().st_size
            modified = datetime.fromtimestamp(file_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            
            file_table.add_row(
                file_type,
                file_path.name,
                f"{size / 1024 / 1024:.1f} MB",
                modified
            )
        
        console.print(file_table)
        console.print()
        
        if Confirm.ask("Create organized directory structure?", default=False):
            try:
                # Create organized directories
                organized_dir = self.skymarshal_dir / 'organized'
                organized_dir.mkdir(exist_ok=True)
                
                # Create subdirectories by date
                for file_path in car_files + json_files:
                    file_date = datetime.fromtimestamp(file_path.stat().st_mtime).strftime("%Y-%m")
                    date_dir = organized_dir / file_date
                    date_dir.mkdir(exist_ok=True)
                    
                    # Copy file to organized location
                    import shutil
                    shutil.copy2(file_path, date_dir / file_path.name)
                
                console.print(f"✅ Files organized in: {organized_dir}")
                return True
                
            except Exception as e:
                console.print(f"❌ Organization failed: {e}")
                return False
        else:
            console.print("❌ Organization cancelled")
            return False
    
    def show_file_details(self):
        """Show detailed information about a specific file."""
        console.print(Rule("📄 File Details", style="bright_cyan"))
        console.print()
        
        # Get all files
        car_files = list(self.cars_dir.glob("*.car"))
        json_files = list(self.json_dir.glob("*.json"))
        
        if not car_files and not json_files:
            console.print("📭 No files found")
            return False
        
        console.print("Available files:")
        console.print()
        
        # Show file picker
        selected_file = self.ui.show_file_picker(car_files + json_files)
        if not selected_file:
            return False
        
        # Show file details
        stat = selected_file.stat()
        
        details_table = Table(show_header=True)
        details_table.add_column("Property", style="bold")
        details_table.add_column("Value", style="cyan")
        
        details_table.add_row("Filename", selected_file.name)
        details_table.add_row("Type", "CAR" if selected_file.suffix == '.car' else "JSON")
        details_table.add_row("Size", f"{stat.st_size / 1024 / 1024:.2f} MB")
        details_table.add_row("Created", datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S"))
        details_table.add_row("Modified", datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"))
        details_table.add_row("Path", str(selected_file))
        
        console.print(details_table)
        
        # If it's a JSON file, try to show content summary
        if selected_file.suffix == '.json':
            try:
                with open(selected_file, 'r') as f:
                    data = json.load(f)
                
                if isinstance(data, list):
                    console.print()
                    console.print(f"📊 Content Summary:")
                    console.print(f"   • Total items: {len(data)}")
                    
                    if data:
                        # Analyze content types
                        content_types = {}
                        for item in data:
                            content_type = item.get('type', 'unknown')
                            content_types[content_type] = content_types.get(content_type, 0) + 1
                        
                        for content_type, count in content_types.items():
                            console.print(f"   • {content_type}: {count}")
                
            except Exception as e:
                console.print(f"[yellow]Could not analyze file content: {e}[/yellow]")
        
        console.print()
    
    def show_menu(self):
        """Display main menu."""
        console.print(Rule("📁 Data Management", style="bright_cyan"))
        console.print()
        
        options = {
            "1": ("Data Overview", self.show_data_overview),
            "2": ("Download CAR Backup", self.download_car_backup),
            "3": ("Download Data via API", self.download_api_data),
            "4": ("Process CAR File", self.process_car_file),
            "5": ("Backup CAR File", self.backup_car_file),
            "6": ("Clear Local Data", self.clear_local_data),
            "7": ("Organize Files", self.organize_files),
            "8": ("File Details", self.show_file_details),
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
        """Run the data management script."""
        console.print()
        console.print("📁 Skymarshal Data Management")
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
    data_management_script = DataManagementScript()
    data_management_script.run()

if __name__ == "__main__":
    main()