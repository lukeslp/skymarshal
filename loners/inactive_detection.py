#!/usr/bin/env python3
"""
Skymarshal Inactive Account Detection Script
This script identifies potentially inactive or dormant accounts based on
engagement patterns, posting frequency, and activity metrics.
Usage: python inactive_detection.py
"""
import os
import sys
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

# Add parent directory to path to import skymarshal modules
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm, IntPrompt, FloatPrompt
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.rule import Rule
    from rich.text import Text
    from rich.status import Status
except ImportError:
    print("❌ Required packages not installed. Run: pip install rich")
    sys.exit(1)

try:
    # Import from skymarshal
    from skymarshal.models import ContentItem, UserSettings, parse_datetime
    from skymarshal.auth import AuthManager
    from skymarshal.ui import UIManager
except ImportError as e:
    print(f"❌ Failed to import Skymarshal modules: {e}")
    print("💡 Make sure you're running this from the internal/loners directory")
    print("💡 And ensure Skymarshal is installed: pip install -e ../..")
    sys.exit(1)

console = Console()

class InactiveDetectionLoner:
    """Standalone inactive account detection functionality."""

    def __init__(self):
        self.settings_file = Path.home() / '.car_inspector_settings.json'
        self.settings = self._load_settings()
        self.ui = UIManager(self.settings)
        self.auth = AuthManager(self.ui)

    def _load_settings(self) -> UserSettings:
        """Load user settings from file."""
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r') as f:
                    settings_data = json.load(f)
                return UserSettings(**settings_data)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not load settings: {e}[/yellow]")

        # Return default settings
        return UserSettings()

    def _save_settings(self):
        """Save current settings to file."""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings.to_dict(), f, indent=2)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not save settings: {e}[/yellow]")

    def run(self):
        """Main entry point for the inactive detection script."""
        try:
            console.clear()
            self._show_header()

            if not self.auth.ensure_authentication():
                console.print("[red]❌ Authentication required for inactive detection[/red]")
                return

            # Note: This is a simplified version for demonstration
            # Full inactive detection would require access to follower/following data
            # which isn't available through the standard Skymarshal ContentItem model

            console.print("[yellow]⚠️ Inactive Detection - Simplified Version[/yellow]")
            console.print()
            console.print("This script identifies potentially inactive accounts based on engagement patterns.")
            console.print("However, the full inactive detection functionality requires follower/following data")
            console.print("that isn't available in the current Skymarshal data model.")
            console.print()

            console.print("[bold bright_blue]Available Options:[/bold bright_blue]")
            console.print("1. [bright_white]Content-based Activity Analysis[/] - Analyze your own posting patterns")
            console.print("2. [bright_white]Engagement Pattern Analysis[/] - Find low-engagement periods")
            console.print("3. [bright_white]Show Help[/] - Learn about inactive detection concepts")
            console.print("4. [bright_white]Exit[/] - Return to main menu")
            console.print()

            while True:
                choice = Prompt.ask(
                    "Select option",
                    choices=["1", "2", "3", "4"],
                    default="1"
                )

                if choice == "1":
                    self._analyze_content_activity()
                elif choice == "2":
                    self._analyze_engagement_patterns()
                elif choice == "3":
                    self._show_help()
                elif choice == "4":
                    break

                console.print()
                if not Confirm.ask("Continue with inactive detection analysis?", default=True):
                    break

        except KeyboardInterrupt:
            console.print("\n[yellow]Inactive detection cancelled[/yellow]")
        except Exception as e:
            console.print(f"[red]❌ Error in inactive detection: {e}[/red]")

    def _show_header(self):
        """Show the script header."""
        console.print(Rule("[bold bright_blue]💤 Inactive Account Detection[/bold bright_blue]", style="bright_blue"))
        console.print()
        console.print("Identify potentially inactive or dormant accounts based on activity patterns.")
        console.print()

    def _analyze_content_activity(self):
        """Analyze your own content posting activity patterns."""
        console.print(Rule("📊 Content Activity Analysis", style="bright_green"))
        console.print()

        # Load user's content data
        data_dir = Path.home() / '.skymarshal' / 'json'
        if not data_dir.exists():
            console.print("[red]❌ No data found. Run setup.py first to download your data.[/red]")
            return

        # Convert handle to filename format (dots become underscores)
        handle_for_filename = self.auth.current_handle.replace('.', '_')
        json_files = list(data_dir.glob(f'*{handle_for_filename}*.json'))
        if not json_files:
            console.print(f"[red]❌ No data files found for @{self.auth.current_handle}[/red]")
            return

        # Load the most recent data file
        latest_file = max(json_files, key=lambda f: f.stat().st_mtime)

        try:
            with open(latest_file, 'r') as f:
                data = json.load(f)

            posts = [item for item in data if item.get('record_type') == 'app.bsky.feed.post']

            if not posts:
                console.print("[yellow]⚠️ No posts found in data[/yellow]")
                return

            # Analyze posting patterns
            self._display_activity_analysis(posts)

        except Exception as e:
            console.print(f"[red]❌ Error analyzing content: {e}[/red]")

    def _display_activity_analysis(self, posts: List[Dict]):
        """Display activity analysis results."""
        if not posts:
            return

        # Group posts by month
        monthly_counts = {}
        for post in posts:
            try:
                created_at = post.get('created_at', '')
                dt = parse_datetime(created_at)
                if dt:
                    month_key = f"{dt.year}-{dt.month:02d}"
                    monthly_counts[month_key] = monthly_counts.get(month_key, 0) + 1
            except:
                continue

        if not monthly_counts:
            console.print("[yellow]⚠️ Could not parse post dates[/yellow]")
            return

        # Create activity table
        table = Table(title="📊 Monthly Posting Activity")
        table.add_column("Month", style="cyan")
        table.add_column("Posts", justify="right", style="green")
        table.add_column("Activity Level", style="yellow")

        total_posts = len(posts)
        avg_monthly = total_posts / len(monthly_counts) if monthly_counts else 0

        for month in sorted(monthly_counts.keys()):
            count = monthly_counts[month]
            if count == 0:
                level = "🔴 Inactive"
            elif count < avg_monthly * 0.5:
                level = "🟡 Low"
            elif count < avg_monthly * 1.5:
                level = "🟢 Normal"
            else:
                level = "🔵 High"

            table.add_row(month, str(count), level)

        console.print(table)
        console.print()
        console.print(f"[dim]Total Posts: {total_posts} | Average per Month: {avg_monthly:.1f}[/dim]")

    def _analyze_engagement_patterns(self):
        """Analyze engagement patterns to identify low-activity periods."""
        console.print(Rule("📈 Engagement Pattern Analysis", style="bright_green"))
        console.print()
        console.print("[yellow]This analysis would examine engagement rates over time[/yellow]")
        console.print("[yellow]to identify periods of low interaction with your content.[/yellow]")
        console.print()
        console.print("Implementation requires:")
        console.print("• Historical engagement data")
        console.print("• Like/repost/comment tracking over time")
        console.print("• Statistical analysis of engagement trends")
        console.print()
        console.print("[dim]This feature would be implemented in a future version.[/dim]")

    def _show_help(self):
        """Show help information about inactive detection."""
        help_content = """
[bold bright_blue]Inactive Account Detection Help[/bold bright_blue]

[bold]What is Inactive Detection?[/bold]
Inactive detection identifies accounts that show little to no engagement or activity
over a specified period. This can help clean up your following list.

[bold]Key Indicators of Inactive Accounts:[/bold]
• No posts for extended periods (30+ days)
• Very low engagement rates (few likes/reposts)
• Incomplete or outdated profile information
• Following/follower ratio anomalies
• No recent interactions with your content

[bold]Detection Methods:[/bold]
• [bright_green]Time-based:[/] Last activity date analysis
• [bright_green]Engagement-based:[/] Low interaction patterns
• [bright_green]Profile-based:[/] Incomplete profile indicators
• [bright_green]Pattern-based:[/] Unusual activity patterns

[bold]Safety Considerations:[/bold]
• Some accounts may be lurkers (active readers, not posters)
• Seasonal activity variations are normal
• Always review before bulk unfollowing
• Consider account age and historical activity

[bold]Best Practices:[/bold]
• Set reasonable inactivity thresholds (30-90 days)
• Review results manually before taking action
• Consider re-checking accounts periodically
• Maintain a whitelist of important accounts

[yellow]Note:[/yellow] Full inactive detection requires access to follower/following
data which isn't available in the current simplified version.
        """

        console.print(Panel(help_content, title="❓ Inactive Detection Help", style="yellow"))

def main():
    """Main entry point for the script."""
    detector = InactiveDetectionLoner()
    detector.run()

if __name__ == "__main__":
    main()
