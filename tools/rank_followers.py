#!/usr/bin/env python3
"""
Standalone CLI tool for Follower Ranking.
Wraps skymarshal.followers functionality.
"""
import sys
import os
import argparse
from rich.console import Console
from rich.table import Table

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skymarshal.followers import FollowerManager
from skymarshal.auth import AuthManager
from skymarshal.settings import SettingsManager

console = Console()

def main():
    parser = argparse.ArgumentParser(description="Rank Bluesky followers by popularity.")
    parser.add_argument("--handle", help="Target handle (defaults to authenticated user)")
    parser.add_argument("--limit", type=int, default=100, help="Number of followers to rank")
    args = parser.parse_args()

    settings_mgr = SettingsManager() 
    auth = AuthManager()
    
    if not auth.load_session():
        console.print("[yellow]Not authenticated.[/] Please run 'python -m skymarshal' to login first.")
        return

    target_handle = args.handle or auth.current_handle
    if not target_handle:
        console.print("[red]No handle specified.[/]")
        return
        
    console.print(f"[dim]Ranking top {args.limit} followers for {target_handle}...[/]")
    
    fm = FollowerManager(auth, settings_mgr)

    try:
        with console.status("Fetching profiles..."):
            ranked = fm.rank_followers(target_handle, limit=args.limit)
            
        if not ranked:
            console.print("No followers found.")
            return

        table = Table(title=f"Follower Ranking for {target_handle}")
        table.add_column("Rank", style="dim")
        table.add_column("Handle", style="cyan")
        table.add_column("Followers", justify="right")
        table.add_column("Following", justify="right")
        
        for i, p in enumerate(ranked[:50], 1):
            table.add_row(
                str(i),
                f"@{p.get('handle')}",
                str(p.get('followers_count')),
                str(p.get('following_count'))
            )
            
        console.print(table)
        if len(ranked) > 50:
            console.print(f"[dim]...and {len(ranked) - 50} more[/]")
            
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")

if __name__ == "__main__":
    main()
