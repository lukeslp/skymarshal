#!/usr/bin/env python3
"""
Standalone CLI tool for Bot Detection.
Wraps skymarshal.bot_detection functionality.
"""
import sys
import os
import argparse
from typing import List, Dict
from rich.console import Console
from rich.table import Table

# Add parent directory to path to allow importing skymarshal
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skymarshal.bot_detection import BotDetector
from skymarshal.followers import FollowerManager
from skymarshal.auth import AuthManager
from skymarshal.settings import SettingsManager
from skymarshal.ui import UIManager

console = Console()

def display_suspects(suspects: List[Dict]):
    """Display identified suspects in a table."""
    if not suspects:
        console.print("[green]No bot indicators found.[/]")
        return

    table = Table(title="Potential Bot Indicators")
    table.add_column("Handle", style="cyan")
    table.add_column("Ratio", justify="right")
    table.add_column("Followers", justify="right")
    table.add_column("Following", justify="right")
    table.add_column("Probability", style="red")

    for s in suspects:
        table.add_row(
            f"@{s.get('handle')}",
            f"{s.get('ratio', 0):.3f}",
            str(s.get('followers_count')),
            str(s.get('following_count')),
            s.get('bot_probability', 'unknown')
        )
    console.print(table)

def main():
    parser = argparse.ArgumentParser(description="Analyze Bluesky followers for bot indicators.")
    parser.add_argument("--handle", help="Target handle (defaults to authenticated user)")
    parser.add_argument("--limit", type=int, default=1000, help="Max followers to analyze")
    parser.add_argument("--threshold", type=float, default=0.1, help="Flag specific ratio threshold")
    args = parser.parse_args()

    # Initialize components
    # Just generic mocks for UI/Settings as standalone doesn't need full TUI
    settings_mgr = SettingsManager() 
    auth = AuthManager()
    
    if not auth.load_session():
        console.print("[yellow]Not authenticated.[/] Please run 'python -m skymarshal' to login first.")
        # Alternatively we could prompt for login here, but reusing session is cleaner
        return

    target_handle = args.handle or auth.current_handle
    if not target_handle:
        console.print("[red]No handle specified and no session handle found.[/]")
        return
        
    console.print(f"[dim]Analyzing top {args.limit} followers for {target_handle}...[/]")
    
    # Initialize implementation classes
    fm = FollowerManager(auth, settings_mgr)
    bot_detector = BotDetector(settings_mgr)

    try:
        with console.status("Fetching and analyzing..."):
            profiles = fm.rank_followers(target_handle, limit=args.limit)
            suspects = bot_detector.analyze_indicators(profiles)
            
        display_suspects(suspects)
        
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")

if __name__ == "__main__":
    main()
