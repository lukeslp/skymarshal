#!/usr/bin/env python3
"""
Skymarshal Authentication Script

This script handles Bluesky authentication and session management.
It can authenticate users, validate sessions, and manage credentials.

Usage: python auth.py
"""

import os
import sys
import json
from pathlib import Path
from typing import Optional

# Add parent directory to path to import skymarshal modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from atproto import Client
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

# Import from skymarshal
from skymarshal.models import UserSettings
from skymarshal.auth import AuthManager
from skymarshal.ui import UIManager

console = Console()

class AuthScript:
    """Standalone authentication management."""
    
    def __init__(self):
        self.settings_file = Path.home() / '.car_inspector_settings.json'
        self.settings = self._load_settings()
        self.ui = UIManager(self.settings)
        self.auth = AuthManager(self.ui)
    
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
    
    def show_auth_status(self):
        """Display current authentication status."""
        console.print(Rule("🔐 Authentication Status", style="bright_green"))
        console.print()
        
        if self.auth.is_authenticated():
            console.print("✅ Authenticated")
            console.print(f"👤 Handle: @{self.auth.current_handle}")
            console.print(f"🆔 DID: {self.auth.current_did}")
            
            # Test API connection
            try:
                profile = self.auth.client.get_profile(self.auth.current_handle)
                console.print("🌐 API Connection: ✅ Working")
                console.print(f"📊 Display Name: {profile.display_name or 'Not set'}")
                console.print(f"📝 Bio: {(profile.description or 'Not set')[:100]}...")
            except Exception as e:
                console.print(f"🌐 API Connection: ❌ Failed ({e})")
        else:
            console.print("❌ Not authenticated")
            console.print("💡 Use 'Login' option to authenticate")
    
    def login(self) -> bool:
        """Perform login process."""
        console.print(Rule("🔓 Login", style="bright_blue"))
        console.print()
        
        console.print("Enter your Bluesky credentials:")
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
        
        console.print()
        with console.status("🔄 Authenticating..."):
            if self.auth.authenticate_client(handle, password):
                console.print(f"✅ Successfully logged in as @{self.auth.current_handle}!")
                
                # Get additional profile info
                try:
                    profile = self.auth.client.get_profile(handle)
                    self.auth.current_did = profile.did
                    console.print(f"🆔 DID: {profile.did}")
                    console.print(f"📊 Display Name: {profile.display_name or 'Not set'}")
                except Exception as e:
                    console.print(f"[yellow]Warning: Could not fetch profile info: {e}[/yellow]")
                
                return True
            else:
                console.print("❌ Authentication failed")
                if not Confirm.ask("Try again?", default=True):
                    return False
    
    def logout(self):
        """Logout and clear session."""
        console.print(Rule("🚪 Logout", style="bright_red"))
        console.print()
        
        if not self.auth.is_authenticated():
            console.print("❌ Not currently authenticated")
            return
        
        console.print(f"👤 Current user: @{self.auth.current_handle}")
        
        if Confirm.ask("Are you sure you want to logout?", default=False):
            self.auth.client = None
            self.auth.current_handle = None
            self.auth.current_did = None
            console.print("✅ Logged out successfully")
        else:
            console.print("❌ Logout cancelled")
    
    def switch_account(self) -> bool:
        """Switch to a different account."""
        console.print(Rule("🔄 Switch Account", style="bright_yellow"))
        console.print()
        
        if not self.auth.is_authenticated():
            console.print("❌ Not currently authenticated")
            console.print("💡 Use 'Login' option first")
            return False
        
        console.print(f"👤 Current user: @{self.auth.current_handle}")
        console.print()
        
        if Confirm.ask("Switch to a different account?", default=False):
            # Logout current session
            self.auth.client = None
            self.auth.current_handle = None
            self.auth.current_did = None
            
            # Login new account
            return self.login()
        else:
            console.print("❌ Account switch cancelled")
            return False
    
    def test_api_connection(self):
        """Test API connection and show account info."""
        console.print(Rule("🌐 API Connection Test", style="bright_cyan"))
        console.print()
        
        if not self.auth.is_authenticated():
            console.print("❌ Not authenticated")
            console.print("💡 Use 'Login' option first")
            return
        
        handle = self.auth.current_handle
        console.print(f"Testing API connection for @{handle}...")
        console.print()
        
        try:
            with console.status("🔄 Testing connection..."):
                # Test basic profile fetch
                profile = self.auth.client.get_profile(handle)
                
                # Test repository access
                repo_info = self.auth.client.com.atproto.repo.describe_repo({'repo': handle})
                
                # Test record listing
                records = self.auth.client.com.atproto.repo.list_records({
                    'repo': handle,
                    'collection': 'app.bsky.feed.post',
                    'limit': 1
                })
            
            console.print("✅ API Connection: Working")
            console.print()
            
            # Show account details
            table = Table(show_header=True)
            table.add_column("Property", style="bold")
            table.add_column("Value", style="cyan")
            
            table.add_row("Handle", f"@{handle}")
            table.add_row("DID", profile.did)
            table.add_row("Display Name", profile.display_name or "Not set")
            table.add_row("Bio", (profile.description or "Not set")[:50] + "..." if len(profile.description or "") > 50 else (profile.description or "Not set"))
            table.add_row("Followers", str(profile.followers_count or 0))
            table.add_row("Following", str(profile.follows_count or 0))
            table.add_row("Posts", str(profile.posts_count or 0))
            table.add_row("Repository Records", str(repo_info.total_records or 0))
            
            console.print(table)
            
        except Exception as e:
            console.print(f"❌ API Connection: Failed")
            console.print(f"Error: {e}")
            console.print()
            console.print("💡 This might indicate:")
            console.print("   • Network connectivity issues")
            console.print("   • Invalid credentials")
            console.print("   • Bluesky API is down")
            console.print("   • Rate limiting")
    
    def show_menu(self):
        """Display main menu."""
        console.print(Rule("🔐 Authentication Manager", style="bright_green"))
        console.print()
        
        # Show current status
        self.show_auth_status()
        console.print()
        
        # Menu options
        options = {
            "1": ("Login", self.login),
            "2": ("Logout", self.logout),
            "3": ("Switch Account", self.switch_account),
            "4": ("Test API Connection", self.test_api_connection),
            "5": ("Show Status", self.show_auth_status),
            "q": ("Quit", None)
        }
        
        console.print("Options:")
        for key, (desc, _) in options.items():
            console.print(f"  [{key}] {desc}")
        console.print()
        
        choice = Prompt.ask("Select option", choices=list(options.keys()), default="5", show_choices=False)
        
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
        """Run the authentication script."""
        console.print()
        console.print("🔐 Skymarshal Authentication Manager")
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
    auth_script = AuthScript()
    auth_script.run()

if __name__ == "__main__":
    main()