#!/usr/bin/env python3
"""
Skymarshal Loners Launcher

This script provides a menu to launch any of the individual Skymarshal scripts.

Usage: python run.py
"""

import os
import sys
import subprocess
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.prompt import Prompt
from rich.rule import Rule
from rich.panel import Panel

console = Console()

def show_banner():
    """Show the loners banner."""
    banner = """
    ╔══════════════════════════════════════════════════════════════╗
    ║                    SKYMARSHAL LONERS                        ║
    ║              Individual CLI Scripts                         ║
    ║                                                              ║
    ║  Standalone scripts for specific Skymarshal functions       ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    console.print(banner, style="bright_cyan")

def show_menu():
    """Display the main menu."""
    console.print(Rule("Skymarshal Loners", style="bright_blue"))
    console.print()
    
    scripts = {
        "1": ("setup.py", "Initial Setup & Data Processing", "Download and process Bluesky data"),
        "2": ("auth.py", "Authentication Management", "Handle login/logout and session management"),
        "3": ("search.py", "Search & Filter Content", "Advanced search and filtering capabilities"),
        "4": ("stats.py", "Statistics & Analytics", "Comprehensive analytics and statistics"),
        "5": ("delete.py", "Content Deletion", "Safe content deletion with safety checks"),
        "6": ("export.py", "Data Export", "Export data in various formats"),
        "7": ("settings.py", "Settings Management", "Manage user preferences and configuration"),
        "8": ("help.py", "Help & Documentation", "Comprehensive help and documentation"),
        "9": ("data_management.py", "Data Management", "File operations, backup management, and cleanup"),
        "10": ("system_info.py", "System Information", "System status and diagnostic information"),
        "11": ("nuke.py", "Nuclear Delete", "Delete ALL content with multiple confirmations"),
        "12": ("analyze.py", "Account Analysis", "Comprehensive analysis of your Bluesky account"),
        "13": ("find_bots.py", "Bot Detection", "Identify potential bot accounts in your data"),
        "14": ("cleanup.py", "Content Cleanup", "Clean up unwanted content and spam"),
        "q": ("quit", "Quit", "Exit the launcher")
    }
    
    console.print("Available Scripts:")
    console.print()
    
    for key, (script, title, desc) in scripts.items():
        if key == "q":
            console.print(f"  [{key}] {title}")
        else:
            console.print(f"  [{key}] {title}")
            console.print(f"      {desc}")
            console.print()
    
    console.print()
    
    choice = Prompt.ask("Select script to run", choices=list(scripts.keys()), default="1", show_choices=False)
    
    if choice == "q":
        return False
    
    script_name = scripts[choice][0]
    script_title = scripts[choice][1]
    
    # Run the selected script
    console.print()
    console.print(f"Launching {script_title}...")
    console.print()
    
    try:
        # Run the script
        script_path = Path(__file__).parent / script_name
        subprocess.run([sys.executable, str(script_path)], check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"Script failed with exit code {e.returncode}")
    except KeyboardInterrupt:
        console.print("\nScript interrupted by user")
    except Exception as e:
        console.print(f"Error running script: {e}")
    
    console.print()
    return True

def show_help():
    """Show help information."""
    console.print(Rule("Help", style="bright_green"))
    console.print()
    
    help_text = """
    Skymarshal Loners are standalone scripts that extract specific functionality
    from the main Skymarshal application. Each script focuses on a particular
    aspect of Bluesky content management.
    
    Workflow:
    1. Setup - Download and process your Bluesky data
    2. Stats - Analyze your content patterns and engagement
    3. Search - Find specific content using filters
    4. Export - Save filtered results in various formats
    5. Delete - Remove unwanted content (with safety checks)
    
    Prerequisites:
    • Python 3.8 or higher
    • Skymarshal dependencies installed
    • Bluesky account credentials
    
    Data Location:
    • Settings: ~/.car_inspector_settings.json
    • Data: ~/.skymarshal/
    • CAR files: ~/.skymarshal/cars/
    • JSON files: ~/.skymarshal/json/
    
    Safety Features:
    • Authentication required for destructive operations
    • Multiple confirmation prompts
    • Preview before action
    • Comprehensive error handling
    """
    
    console.print(Panel(help_text, title="Skymarshal Loners Help", border_style="dim"))
    console.print()

def main():
    """Main entry point."""
    show_banner()
    
    try:
        while True:
            console.print("Options:")
            console.print("  [1-14] Run specific script")
            console.print("  [h] Help")
            console.print("  [q] Quit")
            console.print()

            choice = Prompt.ask("Select option", choices=["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "h", "q"], default="1", show_choices=False)
            
            if choice == "q":
                console.print("Goodbye!")
                break
            elif choice == "h":
                show_help()
                console.print()
            else:
                if not show_menu():
                    break
                console.print()
                
    except KeyboardInterrupt:
        console.print("\nGoodbye!")
    except Exception as e:
        console.print(f"\nUnexpected error: {e}")

if __name__ == "__main__":
    main()
