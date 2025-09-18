#!/usr/bin/env python3
"""
Skymarshal System Information Script

This script provides comprehensive system information and status for Skymarshal.
It shows system details, configuration, data status, and diagnostic information.

Usage: python system_info.py
"""

import os
import sys
import json
import platform
import psutil
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

# Add parent directory to path to import skymarshal modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

# Import from skymarshal
from skymarshal.models import UserSettings

console = Console()

class SystemInfoScript:
    """Standalone system information functionality."""
    
    def __init__(self):
        self.skymarshal_dir = Path.home() / '.skymarshal'
        self.cars_dir = self.skymarshal_dir / 'cars'
        self.json_dir = self.skymarshal_dir / 'json'
        self.settings_file = Path.home() / '.car_inspector_settings.json'
        self.settings = self._load_settings()
    
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
    
    def show_system_overview(self):
        """Show overall system information."""
        console.print(Rule("💻 System Overview", style="bright_blue"))
        console.print()
        
        # System information
        system_info = {
            "Platform": platform.platform(),
            "Python Version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "Architecture": platform.architecture()[0],
            "Processor": platform.processor() or "Unknown",
            "Memory": f"{psutil.virtual_memory().total / 1024 / 1024 / 1024:.1f} GB",
            "Disk Space": f"{psutil.disk_usage('/').free / 1024 / 1024 / 1024:.1f} GB free"
        }
        
        table = Table(show_header=True)
        table.add_column("Property", style="bold")
        table.add_column("Value", style="cyan")
        
        for key, value in system_info.items():
            table.add_row(key, value)
        
        console.print(table)
        console.print()
    
    def show_skymarshal_status(self):
        """Show Skymarshal application status."""
        console.print(Rule("🚀 Skymarshal Status", style="bright_green"))
        console.print()
        
        # Check directories
        directories = {
            "Main Directory": self.skymarshal_dir,
            "CAR Files": self.cars_dir,
            "JSON Files": self.json_dir,
        }
        
        table = Table(show_header=True)
        table.add_column("Directory", style="bold")
        table.add_column("Path", style="cyan")
        table.add_column("Exists", style="green")
        table.add_column("Files", style="yellow")
        
        for name, path in directories.items():
            exists = "✅" if path.exists() else "❌"
            file_count = len(list(path.glob("*"))) if path.exists() else 0
            table.add_row(name, str(path), exists, str(file_count))
        
        console.print(table)
        console.print()
        
        # Check settings file
        settings_status = "✅" if self.settings_file.exists() else "❌"
        console.print(f"Settings File: {settings_status} {self.settings_file}")
        console.print()
    
    def show_data_status(self):
        """Show data files status."""
        console.print(Rule("📊 Data Status", style="bright_cyan"))
        console.print()
        
        # Get all files
        car_files = list(self.cars_dir.glob("*.car")) if self.cars_dir.exists() else []
        json_files = list(self.json_dir.glob("*.json")) if self.json_dir.exists() else []
        
        if not car_files and not json_files:
            console.print("📭 No data files found")
            console.print("💡 Use other loner scripts to download and process data")
            return
        
        # Show file summary
        table = Table(show_header=True)
        table.add_column("File Type", style="bold")
        table.add_column("Count", style="cyan")
        table.add_column("Total Size", style="green")
        table.add_column("Latest File", style="yellow")
        
        car_size = sum(f.stat().st_size for f in car_files) if car_files else 0
        json_size = sum(f.stat().st_size for f in json_files) if json_files else 0
        
        latest_car = max(car_files, key=lambda x: x.stat().st_mtime).name if car_files else "None"
        latest_json = max(json_files, key=lambda x: x.stat().st_mtime).name if json_files else "None"
        
        table.add_row("CAR Files", str(len(car_files)), f"{car_size / 1024 / 1024:.1f} MB", latest_car)
        table.add_row("JSON Files", str(len(json_files)), f"{json_size / 1024 / 1024:.1f} MB", latest_json)
        
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
        
        console.print()
    
    def show_settings_status(self):
        """Show current settings status."""
        console.print(Rule("⚙️ Settings Status", style="bright_magenta"))
        console.print()
        
        settings = self.settings
        
        table = Table(show_header=True)
        table.add_column("Setting", style="bold")
        table.add_column("Value", style="cyan")
        table.add_column("Status", style="green")
        
        settings_info = [
            ("Download Limit Default", str(settings.download_limit_default), "✅"),
            ("Default Categories", ','.join(settings.default_categories), "✅"),
            ("Records Page Size", str(settings.records_page_size), "✅"),
            ("Hydrate Batch Size", str(settings.hydrate_batch_size), "✅"),
            ("Category Workers", str(settings.category_workers), "✅"),
            ("File List Page Size", str(settings.file_list_page_size), "✅"),
            ("High Engagement Threshold", str(settings.high_engagement_threshold), "✅"),
            ("Use Subject Engagement for Reposts", 'Yes' if settings.use_subject_engagement_for_reposts else 'No', "✅"),
            ("Fetch Order", settings.fetch_order, "✅"),
        ]
        
        for setting, value, status in settings_info:
            table.add_row(setting, value, status)
        
        console.print(table)
        console.print()
    
    def show_dependencies_status(self):
        """Show dependencies and their status."""
        console.print(Rule("📦 Dependencies Status", style="bright_yellow"))
        console.print()
        
        dependencies = [
            ("atproto", "AT Protocol client"),
            ("rich", "Rich terminal formatting"),
            ("psutil", "System information"),
            ("pathlib", "Path handling"),
            ("json", "JSON processing"),
            ("datetime", "Date/time handling"),
        ]
        
        table = Table(show_header=True)
        table.add_column("Package", style="bold")
        table.add_column("Description", style="cyan")
        table.add_column("Status", style="green")
        
        for package, description in dependencies:
            try:
                __import__(package)
                status = "✅ Available"
            except ImportError:
                status = "❌ Missing"
            
            table.add_row(package, description, status)
        
        console.print(table)
        console.print()
    
    def show_network_status(self):
        """Show network connectivity status."""
        console.print(Rule("🌐 Network Status", style="bright_blue"))
        console.print()
        
        import socket
        import urllib.request
        import urllib.error
        
        # Test basic connectivity
        connectivity_tests = [
            ("Internet", "8.8.8.8", 53),
            ("Bluesky API", "bsky.social", 443),
            ("AT Protocol", "bsky.social", 443),
        ]
        
        table = Table(show_header=True)
        table.add_column("Service", style="bold")
        table.add_column("Host", style="cyan")
        table.add_column("Port", style="green")
        table.add_column("Status", style="yellow")
        
        for service, host, port in connectivity_tests:
            try:
                socket.create_connection((host, port), timeout=5)
                status = "✅ Connected"
            except (socket.timeout, socket.gaierror, ConnectionRefusedError):
                status = "❌ Failed"
            
            table.add_row(service, host, str(port), status)
        
        console.print(table)
        console.print()
        
        # Test HTTP connectivity
        try:
            urllib.request.urlopen("https://bsky.social", timeout=10)
            console.print("✅ HTTPS connectivity to Bluesky: Working")
        except (urllib.error.URLError, socket.timeout):
            console.print("❌ HTTPS connectivity to Bluesky: Failed")
        
        console.print()
    
    def show_diagnostic_info(self):
        """Show diagnostic information."""
        console.print(Rule("🔧 Diagnostic Information", style="bright_red"))
        console.print()
        
        # Python environment
        console.print("Python Environment:")
        console.print(f"  • Python executable: {sys.executable}")
        console.print(f"  • Python path: {sys.path[0]}")
        console.print(f"  • Working directory: {os.getcwd()}")
        console.print()
        
        # Environment variables
        env_vars = ["HOME", "USER", "PATH", "PYTHONPATH"]
        console.print("Environment Variables:")
        for var in env_vars:
            value = os.environ.get(var, "Not set")
            if var == "PATH":
                value = f"{len(value.split(':'))} paths"
            console.print(f"  • {var}: {value}")
        console.print()
        
        # File permissions
        console.print("File Permissions:")
        for path_name, path in [("Home", Path.home()), ("Skymarshal", self.skymarshal_dir)]:
            try:
                if path.exists():
                    stat = path.stat()
                    readable = "✅" if os.access(path, os.R_OK) else "❌"
                    writable = "✅" if os.access(path, os.W_OK) else "❌"
                    console.print(f"  • {path_name}: Read {readable}, Write {writable}")
                else:
                    console.print(f"  • {path_name}: ❌ Does not exist")
            except Exception as e:
                console.print(f"  • {path_name}: ❌ Error: {e}")
        
        console.print()
    
    def run_system_check(self):
        """Run comprehensive system check."""
        console.print(Rule("🔍 System Check", style="bright_green"))
        console.print()
        
        checks = [
            ("System Overview", self.show_system_overview),
            ("Skymarshal Status", self.show_skymarshal_status),
            ("Data Status", self.show_data_status),
            ("Settings Status", self.show_settings_status),
            ("Dependencies Status", self.show_dependencies_status),
            ("Network Status", self.show_network_status),
            ("Diagnostic Information", self.show_diagnostic_info),
        ]
        
        for title, check_func in checks:
            console.print(Rule(f"🔍 {title}", style="dim"))
            check_func()
            
            if not Confirm.ask("Continue to next check?", default=True):
                break
        
        console.print()
        console.print("✅ System check complete!")
    
    def show_menu(self):
        """Display main menu."""
        console.print(Rule("ℹ️ System Information", style="bright_blue"))
        console.print()
        
        options = {
            "1": ("System Overview", self.show_system_overview),
            "2": ("Skymarshal Status", self.show_skymarshal_status),
            "3": ("Data Status", self.show_data_status),
            "4": ("Settings Status", self.show_settings_status),
            "5": ("Dependencies Status", self.show_dependencies_status),
            "6": ("Network Status", self.show_network_status),
            "7": ("Diagnostic Information", self.show_diagnostic_info),
            "8": ("Run System Check", self.run_system_check),
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
        """Run the system info script."""
        console.print()
        console.print("ℹ️ Skymarshal System Information")
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
    system_info_script = SystemInfoScript()
    system_info_script.run()

if __name__ == "__main__":
    main()