#!/usr/bin/env python3
"""
Skymarshal Nuclear Delete Script

This script provides nuclear deletion capabilities for Bluesky content.
It allows users to delete ALL content (posts, likes, reposts) with multiple safety confirmations.

WARNING: This is a destructive operation that cannot be undone!

Usage: python nuke.py
"""

import os
import sys
from pathlib import Path
from typing import List, Set

# Add parent directory to path to import skymarshal modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.rule import Rule
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn

# Import from skymarshal
from skymarshal.models import UserSettings
from skymarshal.auth import AuthManager
from skymarshal.data_manager import DataManager
from skymarshal.deletion import DeletionManager
from skymarshal.ui import UIManager

console = Console()

class NukeScript:
    """Standalone nuclear deletion functionality."""
    
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
        self.deletion_manager = DeletionManager(self.auth, self.settings)
    
    def _load_settings(self) -> UserSettings:
        """Load user settings or create defaults."""
        try:
            if self.settings_file.exists():
                import json
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
    
    def show_warning(self):
        """Show nuclear deletion warning."""
        console.print(Rule("NUCLEAR DELETE WARNING", style="bright_red"))
        console.print()
        
        warning_text = """
DANGER ZONE: NUCLEAR DELETE

This operation will PERMANENTLY DELETE ALL CONTENT from your Bluesky account:

• ALL POSTS (original content)
• ALL LIKES (your like actions)  
• ALL REPOSTS (your repost actions)

THIS CANNOT BE UNDONE!
NO BACKUP WILL BE CREATED AUTOMATICALLY!
THIS WILL DELETE EVERYTHING!

This is intended for:
• Account deletion preparation
• Complete content cleanup
• Nuclear option when other methods fail

DO NOT PROCEED unless you are absolutely certain!
        """
        
        console.print(Panel(warning_text, title="NUCLEAR DELETE", border_style="bright_red"))
        console.print()
    
    def authenticate_for_nuke(self) -> bool:
        """Authenticate user for nuclear deletion."""
        console.print(Rule("Authentication Required", style="bright_red"))
        console.print()
        
        console.print("Nuclear deletion requires fresh authentication for security.")
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
    
    def select_collections_to_delete(self) -> Set[str]:
        """Select which collections to delete."""
        console.print(Rule("Select Collections to Delete", style="bright_yellow"))
        console.print()
        
        valid_collections = {
            "post": "app.bsky.feed.post",
            "like": "app.bsky.feed.like", 
            "repost": "app.bsky.feed.repost"
        }
        
        console.print("Available collections:")
        console.print("  • post - Original posts")
        console.print("  • like - Your like actions")
        console.print("  • repost - Your repost actions")
        console.print()
        
        console.print("Enter collections to delete (comma-separated):")
        console.print("Examples: 'post' or 'post,like' or 'post,like,repost'")
        console.print()
        
        while True:
            collections_input = Prompt.ask("Collections", default="post,like,repost")
            collections = {s.strip().lower() for s in collections_input.split(",") if s.strip()}
            
            # Validate collections
            valid_selections = collections.intersection(valid_collections.keys())
            invalid_selections = collections - valid_collections.keys()
            
            if invalid_selections:
                console.print(f"Invalid collections: {', '.join(invalid_selections)}")
                console.print(f"Valid options: {', '.join(valid_collections.keys())}")
                continue
            
            if not valid_selections:
                console.print("No valid collections selected")
                continue
            
            console.print(f"Selected collections: {', '.join(valid_selections)}")
            return valid_selections
    
    def create_backup_before_nuke(self, handle: str) -> bool:
        """Create backup before nuclear deletion."""
        console.print(Rule("Create Backup Before Deletion", style="bright_blue"))
        console.print()
        
        console.print("Creating a backup is HIGHLY RECOMMENDED before nuclear deletion!")
        console.print("This will download a complete CAR backup of your account.")
        console.print()
        
        if Confirm.ask("Create backup before deletion?", default=True):
            try:
                console.print(f"Creating backup for @{handle}...")
                car_path = self.data_manager.download_car(handle)
                if car_path:
                    console.print(f"Backup created: {car_path.name}")
                    return True
                else:
                    console.print("Backup creation failed")
                    return False
            except Exception as e:
                console.print(f"Backup error: {e}")
                return False
        else:
            console.print("Proceeding without backup!")
            return True
    
    def confirm_nuclear_deletion(self, handle: str, collections: Set[str]) -> bool:
        """Multiple confirmation steps for nuclear deletion."""
        console.print(Rule("Final Confirmations", style="bright_red"))
        console.print()
        
        # Confirmation 1: Type the phrase
        phrase = f"DELETE ALL {handle}"
        console.print(f"Type exactly: [bold red]{phrase}[/bold red]")
        entered_phrase = Prompt.ask("Confirmation phrase")
        
        if entered_phrase != phrase:
            console.print("Confirmation phrase incorrect. Aborting.")
            return False
        
        # Confirmation 2: Re-type handle
        console.print()
        console.print("Re-type your handle to confirm:")
        entered_handle = Prompt.ask("Handle: @")
        
        if entered_handle.strip().lower() != handle.strip().lower():
            console.print("Handle mismatch. Aborting.")
            return False
        
        # Confirmation 3: Type understanding phrase
        console.print()
        console.print("Type 'I UNDERSTAND' to proceed:")
        understanding = Prompt.ask("Understanding phrase")
        
        if understanding.strip() != 'I UNDERSTAND':
            console.print("Understanding phrase incorrect. Aborting.")
            return False
        
        # Confirmation 4: Final confirmation
        console.print()
        console.print(Panel(
            f"FINAL WARNING\n\n"
            f"This will PERMANENTLY DELETE ALL {', '.join(collections).upper()} from @{handle}!\n\n"
            f"This action CANNOT BE UNDONE!",
            title="FINAL CONFIRMATION",
            border_style="bright_red"
        ))
        
        return Confirm.ask("Proceed with nuclear deletion?", default=False)
    
    def execute_nuclear_deletion(self, collections: Set[str]) -> int:
        """Execute the nuclear deletion."""
        console.print(Rule("Executing Nuclear Deletion", style="bright_red"))
        console.print()
        
        valid_collections = {
            "post": "app.bsky.feed.post",
            "like": "app.bsky.feed.like",
            "repost": "app.bsky.feed.repost"
        }
        
        total_deleted = 0
        total_matched = 0
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            
            for collection_key in collections:
                collection_name = valid_collections[collection_key]
                
                task = progress.add_task(f"Deleting {collection_key}...", total=100)
                
                try:
                    deleted, matched = self.deletion_manager.bulk_remove_by_collection(
                        collection_name, dry_run=False
                    )
                    total_deleted += deleted
                    total_matched += matched
                    
                    console.print(f"{collection_name}: {matched} matched, {deleted} deleted")
                    
                except Exception as e:
                    console.print(f"Failed to delete {collection_name}: {e}")
                
                progress.update(task, completed=100)
        
        return total_deleted, total_matched
    
    def run_nuclear_deletion(self):
        """Run the complete nuclear deletion workflow."""
        # Show warning
        self.show_warning()
        
        if not Confirm.ask("I understand the risks and want to continue", default=False):
            console.print("Nuclear deletion cancelled")
            return
        
        # Authenticate
        if not self.authenticate_for_nuke():
            console.print("Authentication required")
            return
        
        handle = self.auth.current_handle
        
        # Select collections
        collections = self.select_collections_to_delete()
        if not collections:
            console.print("No collections selected")
            return
        
        # Create backup
        if not self.create_backup_before_nuke(handle):
            if not Confirm.ask("Continue without backup?", default=False):
                console.print("Nuclear deletion cancelled")
                return
        
        # Multiple confirmations
        if not self.confirm_nuclear_deletion(handle, collections):
            console.print("Nuclear deletion cancelled")
            return
        
        # Execute deletion
        deleted, matched = self.execute_nuclear_deletion(collections)
        
        # Show results
        console.print()
        console.print(Rule("Nuclear Deletion Complete", style="bright_green"))
        console.print()
        console.print(f"Total records matched: {matched}")
        console.print(f"Total records deleted: {deleted}")
        console.print()
        
        if deleted > 0:
            console.print("Nuclear deletion completed successfully.")
            console.print("Your Bluesky account content has been permanently deleted.")
        else:
            console.print("No records were deleted.")
    
    def run(self):
        """Run the nuclear deletion script."""
        console.print()
        console.print("Skymarshal Nuclear Delete")
        console.print("=" * 50)
        console.print()
        
        try:
            self.run_nuclear_deletion()
        except KeyboardInterrupt:
            console.print("\nNuclear deletion cancelled by user")
        except Exception as e:
            console.print(f"\nUnexpected error: {e}")

def main():
    """Main entry point."""
    nuke_script = NukeScript()
    nuke_script.run()

if __name__ == "__main__":
    main()
