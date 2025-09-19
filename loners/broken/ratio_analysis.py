#!/usr/bin/env python3
"""
Skymarshal Ratio Analysis Script
This script identifies accounts with poor follower-to-following ratios.
It helps identify accounts that may be spammy or provide low value engagement.
Usage: python ratio_analysis.py
"""
import os
import sys
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

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

class RatioAnalysisLoner:
    """Standalone ratio analysis functionality."""

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
        """Main entry point for the ratio analysis script."""
        try:
            console.clear()
            self._show_header()

            if not self.auth.ensure_authentication():
                console.print("[red]❌ Authentication required for ratio analysis[/red]")
                return

            # Note: This is a simplified version for demonstration
            # Full ratio analysis would require access to follower/following data
            # which isn't available through the standard Skymarshal ContentItem model

            console.print("[yellow]⚠️ Ratio Analysis - Simplified Version[/yellow]")
            console.print()
            console.print("This script analyzes follower-to-following ratios to identify potentially")
            console.print("problematic accounts. However, the full ratio analysis functionality requires")
            console.print("follower/following data that isn't available in the current Skymarshal data model.")
            console.print()

            console.print("[bold bright_blue]Available Options:[/bold bright_blue]")
            console.print("1. [bright_white]Content Engagement Ratio Analysis[/] - Analyze your content performance")
            console.print("2. [bright_white]Posting Frequency Analysis[/] - Examine posting patterns")
            console.print("3. [bright_white]Show Help[/] - Learn about ratio analysis concepts")
            console.print("4. [bright_white]Exit[/] - Return to main menu")
            console.print()

            while True:
                choice = Prompt.ask(
                    "Select option",
                    choices=["1", "2", "3", "4"],
                    default="1"
                )

                if choice == "1":
                    self._analyze_engagement_ratios()
                elif choice == "2":
                    self._analyze_posting_frequency()
                elif choice == "3":
                    self._show_help()
                elif choice == "4":
                    break

                console.print()
                if not Confirm.ask("Continue with ratio analysis?", default=True):
                    break

        except KeyboardInterrupt:
            console.print("\n[yellow]Ratio analysis cancelled[/yellow]")
        except Exception as e:
            console.print(f"[red]❌ Error in ratio analysis: {e}[/red]")

    def _show_header(self):
        """Show the script header."""
        console.print(Rule("[bold bright_blue]📈 Ratio Analysis[/bold bright_blue]", style="bright_blue"))
        console.print()
        console.print("Analyze ratios and patterns to identify problematic accounts or content.")
        console.print()

    def _analyze_engagement_ratios(self):
        """Analyze engagement ratios for your content."""
        console.print(Rule("📊 Content Engagement Ratio Analysis", style="bright_green"))
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

            # Analyze engagement ratios
            self._display_engagement_analysis(posts)

        except Exception as e:
            console.print(f"[red]❌ Error analyzing engagement: {e}[/red]")

    def _display_engagement_analysis(self, posts: List[Dict]):
        """Display engagement analysis results."""
        if not posts:
            return

        # Calculate engagement ratios
        high_engagement = []
        medium_engagement = []
        low_engagement = []
        zero_engagement = []

        for post in posts:
            likes = post.get('like_count', 0) or 0
            reposts = post.get('repost_count', 0) or 0
            replies = post.get('reply_count', 0) or 0

            total_engagement = likes + reposts + replies

            if total_engagement == 0:
                zero_engagement.append(post)
            elif total_engagement < 5:
                low_engagement.append(post)
            elif total_engagement < 20:
                medium_engagement.append(post)
            else:
                high_engagement.append(post)

        # Create ratio table
        table = Table(title="📈 Engagement Ratio Analysis")
        table.add_column("Category", style="cyan")
        table.add_column("Posts", justify="right", style="green")
        table.add_column("Percentage", justify="right", style="yellow")
        table.add_column("Ratio", style="magenta")

        total_posts = len(posts)

        categories = [
            ("🔴 Zero Engagement", len(zero_engagement)),
            ("🟡 Low Engagement (1-4)", len(low_engagement)),
            ("🟢 Medium Engagement (5-19)", len(medium_engagement)),
            ("🔵 High Engagement (20+)", len(high_engagement))
        ]

        for category, count in categories:
            percentage = (count / total_posts * 100) if total_posts > 0 else 0
            ratio = f"1:{total_posts/count:.1f}" if count > 0 else "N/A"
            table.add_row(category, str(count), f"{percentage:.1f}%", ratio)

        console.print(table)
        console.print()
        console.print(f"[dim]Total Posts Analyzed: {total_posts}[/dim]")

        # Show recommendations
        if len(zero_engagement) > total_posts * 0.3:
            console.print("[red]⚠️ High number of posts with zero engagement - consider reviewing content strategy[/red]")
        elif len(high_engagement) > total_posts * 0.2:
            console.print("[green]✓ Good engagement ratios - your content is performing well[/green]")

    def _analyze_posting_frequency(self):
        """Analyze posting frequency patterns."""
        console.print(Rule("📅 Posting Frequency Analysis", style="bright_green"))
        console.print()
        console.print("[yellow]This analysis examines posting frequency patterns[/yellow]")
        console.print("[yellow]to identify optimal posting schedules and detect spam-like behavior.[/yellow]")
        console.print()
        console.print("Frequency analysis includes:")
        console.print("• Posts per day/week/month")
        console.print("• Time-of-day posting patterns")
        console.print("• Burst posting detection")
        console.print("• Consistency metrics")
        console.print()
        console.print("[dim]This feature would be implemented in a future version.[/dim]")

    def _show_help(self):
        """Show help information about ratio analysis."""
        help_content = """
[bold bright_blue]Ratio Analysis Help[/bold bright_blue]

[bold]What is Ratio Analysis?[/bold]
Ratio analysis examines relationships between different metrics to identify
patterns, anomalies, or problematic accounts/content.

[bold]Types of Ratios:[/bold]
• [bright_green]Follower/Following Ratio:[/] Indicates account quality
• [bright_green]Engagement Ratio:[/] Posts vs. likes/reposts/comments
• [bright_green]Content Ratio:[/] Original posts vs. reposts
• [bright_green]Activity Ratio:[/] Posting frequency vs. account age

[bold]Common Ratio Indicators:[/bold]
• [red]Poor Ratios:[/] High following, low followers (potential spam)
• [red]Suspicious Ratios:[/] Very high follower/following ratios (bought followers)
• [green]Good Ratios:[/] Balanced follower/following with good engagement
• [yellow]Bot-like Ratios:[/] Extreme ratios in any direction

[bold]Follower/Following Guidelines:[/bold]
• [green]Healthy:[/] 0.5 - 2.0 ratio (followers/following)
• [yellow]Questionable:[/] < 0.1 or > 10.0 ratio
• [red]Problematic:[/] < 0.05 or > 50.0 ratio

[bold]Best Practices:[/bold]
• Consider account age and purpose
• Look at engagement quality, not just quantity
• Review posting patterns and content quality
• Use multiple indicators, not just ratios
• Manual review is recommended before action

[yellow]Note:[/yellow] Full ratio analysis requires access to follower/following
data which isn't available in the current simplified version.
        """

        console.print(Panel(help_content, title="❓ Ratio Analysis Help", style="yellow"))

def main():
    """Main entry point for the script."""
    analyzer = RatioAnalysisLoner()
    analyzer.run()

if __name__ == "__main__":
    main()
