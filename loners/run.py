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

def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def show_banner():
    """Show the loners banner."""
    banner = """╔══════════════════════════════════════════════════════════════╗
║                    SKYMARSHAL LONERS                        ║
║              Individual CLI Scripts                         ║
║                                                              ║
║  Standalone scripts for specific Skymarshal functions       ║
╚══════════════════════════════════════════════════════════════╝"""
    console.print(banner, style="bright_cyan")

def get_scripts():
    """Return the scripts dictionary."""
    return {
        "1": ("data_management.py", "Initial Setup & Data Management", "Download/process data and manage files"),
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
        "15": ("ratio_analysis.py", "Ratio Analysis", "Find accounts with poor follower/following ratios"),
        "16": ("inactive_detection.py", "Inactive Detection", "Find potentially inactive or dormant accounts"),
        "h": ("help", "Help", "Show help information"),
        "q": ("quit", "Quit", "Exit the launcher")
    }

def show_main_menu():
    """Display the main menu with all available scripts."""
    clear_screen()
    show_banner()
    console.print()

    scripts = get_scripts()

    console.print("[bold bright_white]Available Scripts:[/]")
    console.print()

    # Group scripts by category for better organization
    setup_scripts = ["1", "2"]
    analysis_scripts = ["3", "4", "12", "15", "16"]
    management_scripts = ["5", "6", "9", "14", "11"]
    support_scripts = ["7", "8", "10"]

    console.print("[bold bright_green]🚀 Setup & Authentication:[/]")
    for key in setup_scripts:
        script, title, desc = scripts[key]
        console.print(f"  [{key:>2}] [bright_white]{title}[/]")
        console.print(f"      [dim]{desc}[/]")

    console.print()
    console.print("[bold bright_blue]🔍 Search & Analysis:[/]")
    for key in analysis_scripts:
        script, title, desc = scripts[key]
        console.print(f"  [{key:>2}] [bright_white]{title}[/]")
        console.print(f"      [dim]{desc}[/]")

    console.print()
    console.print("[bold bright_yellow]🧹 Content Management:[/]")
    for key in management_scripts:
        script, title, desc = scripts[key]
        console.print(f"  [{key:>2}] [bright_white]{title}[/]")
        console.print(f"      [dim]{desc}[/]")

    console.print()
    console.print("[bold bright_magenta]⚙️ System & Support:[/]")
    for key in support_scripts:
        script, title, desc = scripts[key]
        console.print(f"  [{key:>2}] [bright_white]{title}[/]")
        console.print(f"      [dim]{desc}[/]")

    console.print()
    console.print("[bold bright_red]❓ Other Options:[/]")
    console.print(f"  [ h] [bright_white]Help[/]")
    console.print(f"      [dim]Show help information[/]")
    console.print(f"  [ q] [bright_white]Quit[/]")
    console.print(f"      [dim]Exit the launcher[/]")

    console.print()

    choice = Prompt.ask(
        "[bold bright_white]Select option[/]",
        choices=list(scripts.keys()),
        default="1",
        show_choices=False
    )

    return choice, scripts[choice]

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

def run_script(script_info):
    """Run a selected script."""
    script_name, script_title, script_desc = script_info

    console.print()
    console.print(f"[bold bright_green]Launching {script_title}...[/]")
    console.print()

    try:
        script_path = Path(__file__).parent / script_name
        subprocess.run([sys.executable, str(script_path)], check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Script failed with exit code {e.returncode}[/]")
    except KeyboardInterrupt:
        console.print("\n[yellow]Script interrupted by user[/]")
    except Exception as e:
        console.print(f"[red]Error running script: {e}[/]")

    console.print()
    console.print("[dim]Press Enter to return to menu...[/]")
    input()

def main():
    """Main entry point."""
    try:
        while True:
            choice, script_info = show_main_menu()

            if choice == "q":
                clear_screen()
                console.print("[bold bright_blue]Goodbye![/]")
                break
            elif choice == "h":
                clear_screen()
                show_help()
                console.print("[dim]Press Enter to return to menu...[/]")
                input()
            else:
                # Run the selected script
                run_script(script_info)

    except KeyboardInterrupt:
        clear_screen()
        console.print("\n[bold bright_blue]Goodbye![/]")
    except Exception as e:
        console.print(f"\n[red]Unexpected error: {e}[/]")

if __name__ == "__main__":
    main()
