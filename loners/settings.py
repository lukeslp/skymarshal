#!/usr/bin/env python3
"""
Skymarshal Settings Management Script

This script provides interactive settings management for Skymarshal.
It allows users to view, modify, and manage their preferences and configuration.

Usage: python settings.py
"""

import os
import sys
import json
from pathlib import Path
from typing import Any

# Add parent directory to path to import skymarshal modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

# Import from skymarshal
from skymarshal.models import UserSettings
from skymarshal.settings import SettingsManager

console = Console()

class SettingsScript:
    """Standalone settings management functionality."""
    
    def __init__(self):
        self.settings_file = Path.home() / '.car_inspector_settings.json'
        self.settings_manager = SettingsManager(self.settings_file)
    
    def show_current_settings(self):
        """Display current settings in a formatted table."""
        console.print(Rule("⚙️ Current Settings", style="bright_magenta"))
        console.print()
        
        settings = self.settings_manager.settings
        
        table = Table(show_header=True)
        table.add_column("Setting", style="bold", width=30)
        table.add_column("Value", style="cyan", width=20)
        table.add_column("Description", style="dim", width=40)
        
        settings_info = [
            ("Download Limit Default", str(settings.download_limit_default), "Default items per category to backup"),
            ("Default Categories", ','.join(settings.default_categories), "Categories to fetch by default"),
            ("Records Page Size", str(settings.records_page_size), "Items per page in API requests (1-100)"),
            ("Hydrate Batch Size", str(settings.hydrate_batch_size), "Records per batch for engagement updates (1-25)"),
            ("Category Workers", str(settings.category_workers), "Parallel downloads for faster processing"),
            ("File List Page Size", str(settings.file_list_page_size), "Files shown per page in file picker"),
            ("High Engagement Threshold", str(settings.high_engagement_threshold), "Score for 'high engagement' classification"),
            ("Use Subject Engagement for Reposts", 'Yes' if settings.use_subject_engagement_for_reposts else 'No', "Use original post engagement for reposts"),
            ("Fetch Order", settings.fetch_order, "Download newest or oldest first"),
        ]
        
        for setting, value, description in settings_info:
            table.add_row(setting, value, description)
        
        console.print(table)
        console.print()
    
    def edit_setting(self):
        """Interactive setting editor."""
        console.print(Rule("✏️ Edit Settings", style="bright_yellow"))
        console.print()
        
        settings = self.settings_manager.settings
        
        # Create numbered list of editable settings
        editable_settings = [
            ("download_limit_default", "Default download limit (per category)", str(settings.download_limit_default), "int"),
            ("default_categories", "Default categories to fetch", ','.join(settings.default_categories), "categories"),
            ("records_page_size", "API page size (listRecords)", str(settings.records_page_size), "int"),
            ("hydrate_batch_size", "Update batch size for engagement info", str(settings.hydrate_batch_size), "int"),
            ("category_workers", "Parallel category workers", str(settings.category_workers), "int"),
            ("file_list_page_size", "File picker page size", str(settings.file_list_page_size), "int"),
            ("high_engagement_threshold", "High engagement threshold", str(settings.high_engagement_threshold), "int"),
            ("use_subject_engagement_for_reposts", "Use subject engagement for reposts", 'on' if settings.use_subject_engagement_for_reposts else 'off', "boolean"),
            ("fetch_order", "Fetch order (newest|oldest)", settings.fetch_order, "order"),
        ]
        
        console.print("Available settings to edit:")
        console.print()
        
        for i, (key, label, current_value, _) in enumerate(editable_settings, 1):
            console.print(f"  [{i}] {label}: {current_value}")
        
        console.print()
        console.print("  [b] Back to main menu")
        console.print()
        
        while True:
            choice = Prompt.ask("Select setting to edit", choices=[str(i) for i in range(1, len(editable_settings) + 1)] + ['b'], default='b', show_choices=False)
            
            if choice == 'b':
                break
            
            try:
                idx = int(choice) - 1
                key, label, current_value, setting_type = editable_settings[idx]
                
                console.print()
                console.print(f"Editing: {label}")
                console.print(f"Current value: {current_value}")
                console.print()
                
                if setting_type == "categories":
                    console.print("Enter categories (comma-separated): posts, likes, reposts")
                    console.print("Or enter 'all' for all categories")
                    new_value = Prompt.ask("New value", default=current_value)
                elif setting_type == "boolean":
                    console.print("Enter: on/off, true/false, yes/no, y/n, 1/0")
                    new_value = Prompt.ask("New value", default=current_value)
                elif setting_type == "order":
                    console.print("Enter: newest or oldest")
                    new_value = Prompt.ask("New value", default=current_value)
                else:
                    new_value = Prompt.ask("New value", default=current_value)
                
                # Validate and update the setting
                try:
                    self.settings_manager._update_setting(key, new_value)
                    self.settings_manager.save_user_settings()
                    console.print("✅ Setting updated successfully!")
                    
                    # Update the current value in the list for next iteration
                    editable_settings[idx] = (key, label, new_value, setting_type)
                    
                except Exception as e:
                    console.print(f"❌ Invalid value: {e}")
                
                console.print()
                
            except (ValueError, IndexError):
                console.print("❌ Invalid selection")
                console.print()
    
    def reset_to_defaults(self):
        """Reset all settings to default values."""
        console.print(Rule("🔄 Reset to Defaults", style="bright_red"))
        console.print()
        
        console.print("This will reset all settings to their default values.")
        console.print("Current settings will be lost!")
        console.print()
        
        if Confirm.ask("Are you sure you want to reset all settings?", default=False):
            try:
                # Create new default settings
                default_settings = UserSettings()
                
                # Update the settings manager
                self.settings_manager.settings = default_settings
                self.settings_manager.save_user_settings()
                
                console.print("✅ Settings reset to defaults!")
                
            except Exception as e:
                console.print(f"❌ Failed to reset settings: {e}")
        else:
            console.print("❌ Reset cancelled")
        
        console.print()
    
    def show_settings_help(self):
        """Show detailed help for settings."""
        console.print(Rule("❓ Settings Help", style="bright_blue"))
        console.print()
        
        help_text = """
# Settings Help

## Performance Settings

**Download Limit**: Default number of items to download per category
- Higher values = more data but slower downloads
- Recommended: 100-500 for most users

**Records Page Size**: Items per page in API requests (1-100)
- Higher values = fewer API calls but more memory
- Recommended: 50-100

**Update Batch Size**: Records processed in each batch (1-25) when refreshing engagement info
- Lower values = less memory usage but slower processing
- Recommended: 10-25

**Category Workers**: Parallel downloads for faster processing
- Higher values = faster downloads but more resource usage
- Recommended: 2-4

## Display Settings

**File List Page Size**: Files shown per page in file picker
- Higher values = fewer pages but longer lists
- Recommended: 10-20

**High Engagement Threshold**: Score to consider content 'high engagement'
- Used for statistics and filtering
- Recommended: 20-50

**Fetch Order**: Whether to download newest or oldest first
- 'newest': Most recent content first
- 'oldest': Oldest content first

## Content Settings

**Default Categories**: What to download by default
- 'posts': Original posts only
- 'likes': Your like actions
- 'reposts': Your repost actions
- 'all': All categories

**Use Subject Engagement for Reposts**: Use original post engagement for reposts
- 'on': Shows engagement of the original post
- 'off': Shows engagement of your repost action

## Tips

- Lower batch sizes use less memory but may be slower
- Higher worker counts speed up downloads but use more resources
- Test settings with small downloads first
- Reset to defaults if you encounter issues
        """
        
        console.print(Panel(help_text, title="Settings Help", border_style="dim"))
        console.print()
    
    def export_settings(self):
        """Export current settings to a file."""
        console.print(Rule("💾 Export Settings", style="bright_green"))
        console.print()
        
        try:
            # Create export data
            settings_data = {
                'download_limit_default': self.settings_manager.settings.download_limit_default,
                'default_categories': self.settings_manager.settings.default_categories,
                'records_page_size': self.settings_manager.settings.records_page_size,
                'hydrate_batch_size': self.settings_manager.settings.hydrate_batch_size,
                'category_workers': self.settings_manager.settings.category_workers,
                'file_list_page_size': self.settings_manager.settings.file_list_page_size,
                'high_engagement_threshold': self.settings_manager.settings.high_engagement_threshold,
                'use_subject_engagement_for_reposts': self.settings_manager.settings.use_subject_engagement_for_reposts,
                'fetch_order': self.settings_manager.settings.fetch_order,
                'export_time': str(Path.home()),
                'export_note': 'Skymarshal settings export'
            }
            
            # Get export filename
            filename = Prompt.ask("Export filename (without extension)", default="skymarshal_settings_backup")
            export_path = Path.home() / f"{filename}.json"
            
            # Write export file
            with open(export_path, 'w') as f:
                json.dump(settings_data, f, indent=2)
            
            console.print(f"✅ Settings exported to: {export_path}")
            
        except Exception as e:
            console.print(f"❌ Export failed: {e}")
        
        console.print()
    
    def import_settings(self):
        """Import settings from a file."""
        console.print(Rule("📥 Import Settings", style="bright_cyan"))
        console.print()
        
        # Look for settings files in home directory
        home_dir = Path.home()
        settings_files = list(home_dir.glob("skymarshal_settings*.json"))
        
        if not settings_files:
            console.print("📭 No settings backup files found in home directory")
            console.print("💡 Use 'Export Settings' to create a backup first")
            return
        
        console.print("Available settings files:")
        console.print()
        
        for i, file_path in enumerate(settings_files, 1):
            console.print(f"  [{i}] {file_path.name}")
        
        console.print()
        console.print("  [b] Back to main menu")
        console.print()
        
        choice = Prompt.ask("Select file to import", choices=[str(i) for i in range(1, len(settings_files) + 1)] + ['b'], default='b', show_choices=False)
        
        if choice == 'b':
            return
        
        try:
            idx = int(choice) - 1
            import_file = settings_files[idx]
            
            console.print()
            console.print(f"Importing from: {import_file.name}")
            console.print()
            
            if Confirm.ask("This will replace your current settings. Continue?", default=False):
                # Load import data
                with open(import_file, 'r') as f:
                    import_data = json.load(f)
                
                # Update settings
                for key, value in import_data.items():
                    if hasattr(self.settings_manager.settings, key):
                        setattr(self.settings_manager.settings, key, value)
                
                # Save settings
                self.settings_manager.save_user_settings()
                
                console.print("✅ Settings imported successfully!")
                
            else:
                console.print("❌ Import cancelled")
                
        except (ValueError, IndexError):
            console.print("❌ Invalid selection")
        except Exception as e:
            console.print(f"❌ Import failed: {e}")
        
        console.print()
    
    def show_menu(self):
        """Display main menu."""
        console.print(Rule("⚙️ Settings Management", style="bright_magenta"))
        console.print()
        
        options = {
            "1": ("View Current Settings", self.show_current_settings),
            "2": ("Edit Settings", self.edit_setting),
            "3": ("Reset to Defaults", self.reset_to_defaults),
            "4": ("Export Settings", self.export_settings),
            "5": ("Import Settings", self.import_settings),
            "6": ("Settings Help", self.show_settings_help),
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
        """Run the settings script."""
        console.print()
        console.print("⚙️ Skymarshal Settings Management")
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
    settings_script = SettingsScript()
    settings_script.run()

if __name__ == "__main__":
    main()