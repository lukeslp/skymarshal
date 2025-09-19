#!/usr/bin/env python3
"""
Skymarshal Account Analysis Script
This script provides comprehensive analysis of your Bluesky account including
follower analysis, engagement patterns, and content statistics.
Usage: python analyze.py
"""
import os
import sys
import asyncio
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm, IntPrompt
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.rule import Rule
    from rich.text import Text
    from rich.status import Status
except ImportError:
    print("❌ Required packages not installed. Run: pip install rich")
    sys.exit(1)

try:
    from skymarshal.auth import AuthManager
    from skymarshal.data_manager import DataManager
    from skymarshal.ui import UIManager
    from skymarshal.models import ContentItem, console
except ImportError as e:
    print(f"❌ Failed to import Skymarshal modules: {e}")
    print("💡 Make sure you're running this from the skymarshal directory")
    sys.exit(1)

console = Console()

class AccountAnalysisLoner:
    """Standalone account analysis tool."""

    def __init__(self):
        """Initialize the account analysis tool."""
        self.auth_manager = AuthManager()
        self.data_manager = DataManager()
        self.ui_manager = UIManager()
        self.current_data = None

    def run(self):
        """Run the account analysis tool."""
        console.print(Panel.fit(
            "📊 [bold blue]Skymarshal Account Analysis[/bold blue]\n\n"
            "Comprehensive analysis of your Bluesky account\n"
            "Follower patterns, engagement analysis, and content insights",
            title="📊 Account Analysis",
            style="blue"
        ))

        try:
            # Initialize components
            if not self._initialize():
                return

            # Main menu loop
            while True:
                console.print()
                console.print(Rule("📊 Analysis Options", style="blue"))

                options = [
                    "1. 📈 Basic Account Statistics",
                    "2. 🎯 Engagement Analysis",
                    "3. 📅 Content Timeline Analysis",
                    "4. 🔍 Content Quality Analysis",
                    "5. 📊 Follower Growth Analysis",
                    "6. 💾 Export Analysis Results",
                    "7. ❓ Help",
                    "8. 🚪 Exit"
                ]

                for option in options:
                    console.print(f"   {option}")

                console.print()
                choice = Prompt.ask("Select option", choices=["1", "2", "3", "4", "5", "6", "7", "8"], default="1")

                if choice == "1":
                    self._basic_statistics()
                elif choice == "2":
                    self._engagement_analysis()
                elif choice == "3":
                    self._timeline_analysis()
                elif choice == "4":
                    self._content_quality_analysis()
                elif choice == "5":
                    self._follower_growth_analysis()
                elif choice == "6":
                    self._export_analysis()
                elif choice == "7":
                    self._show_help()
                elif choice == "8":
                    console.print("👋 Goodbye!")
                    break

        except KeyboardInterrupt:
            console.print("\n👋 Goodbye!")
        except Exception as e:
            console.print(f"❌ Error: {e}")

    def _initialize(self) -> bool:
        """Initialize the application components."""
        try:
            with Status("🔧 [bold blue]Initializing components...[/bold blue]", console=console):
                # Check authentication
                if not self.auth_manager.current_handle:
                    console.print("❌ Not authenticated. Please run authentication first.")
                    console.print("💡 Run: python auth.py")
                    return False

                console.print(f"✅ Connected as [bold cyan]{self.auth_manager.current_handle}[/bold cyan]")
                return True

        except Exception as e:
            console.print(f"❌ Initialization failed: {e}")
            return False

    def _ensure_data_loaded(self) -> bool:
        """Ensure we have data loaded for analysis."""
        if not self.current_data:
            console.print("⚠️ No data loaded for analysis")
            console.print("💡 Let's load your data first")

            # Check for available data files
            if self.auth_manager.current_handle:
                files = self.data_manager.get_user_files(self.auth_manager.current_handle, 'json')
            else:
                files = list(Path('~/.skymarshal/json/').expanduser().glob("*.json"))

            if not files:
                console.print("📥 No data files found. Let's download your data.")
                if Confirm.ask("Would you like to download your data now?", default=True):
                    return self._download_and_process_data()
                return False
            else:
                console.print(f"📁 Found {len(files)} data files")
                if Confirm.ask("Load the most recent data file?", default=True):
                    return self._load_most_recent_data(files)
                return False
        return True

    def _download_and_process_data(self) -> bool:
        """Download and process user data."""
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("📥 Downloading data...", total=None)

                # Use DataManager to download data
                success = self.data_manager.download_and_process_car(self.auth_manager.current_handle)

                if success:
                    progress.update(task, description="✅ Data downloaded and processed")
                    # Load the newly processed data
                    files = self.data_manager.get_user_files(self.auth_manager.current_handle, 'json')
                    if files:
                        return self._load_most_recent_data(files)
                else:
                    progress.update(task, description="❌ Download failed")
                    return False

        except Exception as e:
            console.print(f"❌ Download failed: {e}")
            return False

    def _load_most_recent_data(self, files: List[Path]) -> bool:
        """Load the most recent data file."""
        try:
            # Sort by modification time, newest first
            latest_file = max(files, key=lambda x: x.stat().st_mtime)

            with Status(f"📂 [bold blue]Loading {latest_file.name}...[/bold blue]", console=console):
                self.current_data = self.data_manager.load_json_data(latest_file)

            if self.current_data:
                console.print(f"✅ Loaded {len(self.current_data)} items from {latest_file.name}")
                return True
            else:
                console.print("❌ Failed to load data")
                return False

        except Exception as e:
            console.print(f"❌ Failed to load data: {e}")
            return False

    def _basic_statistics(self):
        """Show basic account statistics."""
        if not self._ensure_data_loaded():
            return

        console.print(Rule("📈 Basic Account Statistics", style="cyan"))

        try:
            with Status("📊 [bold blue]Calculating statistics...[/bold blue]", console=console):
                stats = self._calculate_basic_stats()

            # Create statistics table
            table = Table(title="📊 Account Overview")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="white", justify="right")
            table.add_column("Details", style="dim")

            table.add_row("Total Items", str(stats['total_items']), "Posts, likes, reposts")
            table.add_row("Posts", str(stats['posts']), "Original content")
            table.add_row("Likes", str(stats['likes']), "Liked content")
            table.add_row("Reposts", str(stats['reposts']), "Shared content")
            table.add_row("", "", "")
            table.add_row("Avg Engagement", f"{stats['avg_engagement']:.2f}", "Likes + reposts + replies")
            table.add_row("Total Engagement", str(stats['total_engagement']), "All interactions")
            table.add_row("Engagement Rate", f"{stats['engagement_rate']:.1f}%", "Engaged items / total")

            console.print(table)

            # Show top performing content
            if stats['top_posts']:
                console.print("\n🔥 Top Performing Posts:")
                for i, post in enumerate(stats['top_posts'][:3], 1):
                    engagement = post.get('likes', 0) + post.get('reposts', 0) + post.get('replies', 0)
                    text_preview = (post.get('text', '')[:50] + '...') if len(post.get('text', '')) > 50 else post.get('text', '')
                    console.print(f"  {i}. {text_preview} ({engagement} interactions)")

        except Exception as e:
            console.print(f"❌ Statistics calculation failed: {e}")

    def _calculate_basic_stats(self) -> Dict[str, Any]:
        """Calculate basic statistics from current data."""
        stats = {
            'total_items': len(self.current_data),
            'posts': 0,
            'likes': 0,
            'reposts': 0,
            'total_engagement': 0,
            'avg_engagement': 0,
            'engagement_rate': 0,
            'top_posts': []
        }

        posts_with_engagement = []

        for item in self.current_data:
            content_type = item.get('type', 'unknown')

            if content_type == 'post':
                stats['posts'] += 1
                engagement = item.get('likes', 0) + item.get('reposts', 0) + item.get('replies', 0)
                stats['total_engagement'] += engagement

                if engagement > 0:
                    posts_with_engagement.append(item)

            elif content_type == 'like':
                stats['likes'] += 1
            elif content_type == 'repost':
                stats['reposts'] += 1

        if stats['posts'] > 0:
            stats['avg_engagement'] = stats['total_engagement'] / stats['posts']
            stats['engagement_rate'] = (len(posts_with_engagement) / stats['posts']) * 100

        # Sort posts by engagement
        stats['top_posts'] = sorted(posts_with_engagement,
                                  key=lambda x: x.get('likes', 0) + x.get('reposts', 0) + x.get('replies', 0),
                                  reverse=True)

        return stats

    def _engagement_analysis(self):
        """Perform detailed engagement analysis."""
        if not self._ensure_data_loaded():
            return

        console.print(Rule("🎯 Engagement Analysis", style="yellow"))

        try:
            with Status("🎯 [bold blue]Analyzing engagement patterns...[/bold blue]", console=console):
                engagement_data = self._analyze_engagement()

            # Show engagement distribution
            console.print("📊 Engagement Distribution:")

            table = Table()
            table.add_column("Engagement Level", style="cyan")
            table.add_column("Posts", style="white", justify="right")
            table.add_column("Percentage", style="green", justify="right")
            table.add_column("Avg Engagement", style="yellow", justify="right")

            for level, data in engagement_data['distribution'].items():
                percentage = (data['count'] / engagement_data['total_posts']) * 100 if engagement_data['total_posts'] > 0 else 0
                avg_eng = data['total_engagement'] / data['count'] if data['count'] > 0 else 0

                table.add_row(
                    level,
                    str(data['count']),
                    f"{percentage:.1f}%",
                    f"{avg_eng:.1f}"
                )

            console.print(table)

            # Show insights
            insights = self._generate_engagement_insights(engagement_data)
            if insights:
                console.print("\n💡 Insights:")
                for insight in insights:
                    console.print(f"  • {insight}")

        except Exception as e:
            console.print(f"❌ Engagement analysis failed: {e}")

    def _analyze_engagement(self) -> Dict[str, Any]:
        """Analyze engagement patterns."""
        posts = [item for item in self.current_data if item.get('type') == 'post']

        engagement_data = {
            'total_posts': len(posts),
            'distribution': {
                'Dead (0)': {'count': 0, 'total_engagement': 0},
                'Low (1-2)': {'count': 0, 'total_engagement': 0},
                'Medium (3-10)': {'count': 0, 'total_engagement': 0},
                'High (11-50)': {'count': 0, 'total_engagement': 0},
                'Viral (50+)': {'count': 0, 'total_engagement': 0}
            }
        }

        for post in posts:
            engagement = post.get('likes', 0) + post.get('reposts', 0) + post.get('replies', 0)

            if engagement == 0:
                level = 'Dead (0)'
            elif engagement <= 2:
                level = 'Low (1-2)'
            elif engagement <= 10:
                level = 'Medium (3-10)'
            elif engagement <= 50:
                level = 'High (11-50)'
            else:
                level = 'Viral (50+)'

            engagement_data['distribution'][level]['count'] += 1
            engagement_data['distribution'][level]['total_engagement'] += engagement

        return engagement_data

    def _generate_engagement_insights(self, engagement_data: Dict[str, Any]) -> List[str]:
        """Generate insights from engagement analysis."""
        insights = []
        total_posts = engagement_data['total_posts']

        if total_posts == 0:
            return ["No posts found for analysis"]

        dead_posts = engagement_data['distribution']['Dead (0)']['count']
        high_posts = engagement_data['distribution']['High (11-50)']['count'] + engagement_data['distribution']['Viral (50+)']['count']

        dead_percentage = (dead_posts / total_posts) * 100
        high_percentage = (high_posts / total_posts) * 100

        if dead_percentage > 50:
            insights.append(f"{dead_percentage:.1f}% of your posts have no engagement - consider reviewing your content strategy")
        elif dead_percentage < 20:
            insights.append(f"Great engagement! Only {dead_percentage:.1f}% of your posts have zero engagement")

        if high_percentage > 20:
            insights.append(f"Excellent! {high_percentage:.1f}% of your posts have high engagement")
        elif high_percentage > 10:
            insights.append(f"Good performance with {high_percentage:.1f}% high-engagement posts")

        return insights

    def _timeline_analysis(self):
        """Analyze content timeline patterns."""
        if not self._ensure_data_loaded():
            return

        console.print(Rule("📅 Content Timeline Analysis", style="magenta"))

        try:
            with Status("📅 [bold blue]Analyzing timeline patterns...[/bold blue]", console=console):
                timeline_data = self._analyze_timeline()

            console.print("📅 Posting Activity by Period:")

            table = Table()
            table.add_column("Time Period", style="cyan")
            table.add_column("Posts", style="white", justify="right")
            table.add_column("Avg Engagement", style="yellow", justify="right")
            table.add_column("Best Time", style="green")

            for period, data in timeline_data.items():
                avg_engagement = data['total_engagement'] / data['posts'] if data['posts'] > 0 else 0

                table.add_row(
                    period,
                    str(data['posts']),
                    f"{avg_engagement:.1f}",
                    data.get('best_time', 'N/A')
                )

            console.print(table)

        except Exception as e:
            console.print(f"❌ Timeline analysis failed: {e}")

    def _analyze_timeline(self) -> Dict[str, Any]:
        """Analyze posting timeline patterns."""
        from datetime import datetime, timedelta

        posts = [item for item in self.current_data if item.get('type') == 'post']

        # Initialize timeline data
        timeline_data = {
            'Last 7 days': {'posts': 0, 'total_engagement': 0},
            'Last 30 days': {'posts': 0, 'total_engagement': 0},
            'Last 90 days': {'posts': 0, 'total_engagement': 0},
            'Older': {'posts': 0, 'total_engagement': 0}
        }

        now = datetime.now()

        for post in posts:
            # Try to parse created_at timestamp
            engagement = post.get('likes', 0) + post.get('reposts', 0) + post.get('replies', 0)

            try:
                if 'created_at' in post:
                    created_at = datetime.fromisoformat(post['created_at'].replace('Z', '+00:00'))
                    days_ago = (now - created_at).days

                    if days_ago <= 7:
                        timeline_data['Last 7 days']['posts'] += 1
                        timeline_data['Last 7 days']['total_engagement'] += engagement
                    elif days_ago <= 30:
                        timeline_data['Last 30 days']['posts'] += 1
                        timeline_data['Last 30 days']['total_engagement'] += engagement
                    elif days_ago <= 90:
                        timeline_data['Last 90 days']['posts'] += 1
                        timeline_data['Last 90 days']['total_engagement'] += engagement
                    else:
                        timeline_data['Older']['posts'] += 1
                        timeline_data['Older']['total_engagement'] += engagement
                else:
                    # No timestamp, put in "Older"
                    timeline_data['Older']['posts'] += 1
                    timeline_data['Older']['total_engagement'] += engagement

            except:
                # Failed to parse timestamp
                timeline_data['Older']['posts'] += 1
                timeline_data['Older']['total_engagement'] += engagement

        return timeline_data

    def _content_quality_analysis(self):
        """Analyze content quality metrics."""
        if not self._ensure_data_loaded():
            return

        console.print(Rule("🔍 Content Quality Analysis", style="green"))

        try:
            with Status("🔍 [bold blue]Analyzing content quality...[/bold blue]", console=console):
                quality_data = self._analyze_content_quality()

            # Show quality metrics
            console.print("📝 Content Quality Metrics:")

            table = Table()
            table.add_column("Metric", style="cyan")
            table.add_column("Average", style="white", justify="right")
            table.add_column("Range", style="dim")

            for metric, data in quality_data.items():
                if isinstance(data, dict) and 'average' in data:
                    range_text = f"{data['min']} - {data['max']}"
                    table.add_row(metric, f"{data['average']:.1f}", range_text)

            console.print(table)

            # Show content recommendations
            recommendations = self._generate_quality_recommendations(quality_data)
            if recommendations:
                console.print("\n💡 Content Recommendations:")
                for rec in recommendations:
                    console.print(f"  • {rec}")

        except Exception as e:
            console.print(f"❌ Content quality analysis failed: {e}")

    def _analyze_content_quality(self) -> Dict[str, Any]:
        """Analyze content quality metrics."""
        posts = [item for item in self.current_data if item.get('type') == 'post']

        if not posts:
            return {}

        # Analyze text length
        text_lengths = []
        engagement_scores = []

        for post in posts:
            text = post.get('text', '')
            text_lengths.append(len(text))

            engagement = post.get('likes', 0) + post.get('reposts', 0) + post.get('replies', 0)
            engagement_scores.append(engagement)

        quality_data = {}

        if text_lengths:
            quality_data['Text Length (chars)'] = {
                'average': sum(text_lengths) / len(text_lengths),
                'min': min(text_lengths),
                'max': max(text_lengths)
            }

        if engagement_scores:
            quality_data['Engagement Score'] = {
                'average': sum(engagement_scores) / len(engagement_scores),
                'min': min(engagement_scores),
                'max': max(engagement_scores)
            }

        return quality_data

    def _generate_quality_recommendations(self, quality_data: Dict[str, Any]) -> List[str]:
        """Generate content quality recommendations."""
        recommendations = []

        if 'Text Length (chars)' in quality_data:
            avg_length = quality_data['Text Length (chars)']['average']

            if avg_length < 50:
                recommendations.append("Consider writing longer, more detailed posts for better engagement")
            elif avg_length > 300:
                recommendations.append("Try shorter posts occasionally - they often get better engagement")

        if 'Engagement Score' in quality_data:
            avg_engagement = quality_data['Engagement Score']['average']

            if avg_engagement < 2:
                recommendations.append("Focus on posting at optimal times and engaging with your audience")
            elif avg_engagement > 10:
                recommendations.append("Great engagement! Consider posting more frequently")

        return recommendations

    def _follower_growth_analysis(self):
        """Analyze follower growth patterns (simplified)."""
        console.print(Rule("📊 Follower Growth Analysis", style="blue"))

        console.print("📈 Follower Growth Analysis")
        console.print("This feature analyzes your posting patterns to infer growth trends.")
        console.print()

        if not self._ensure_data_loaded():
            return

        try:
            with Status("📊 [bold blue]Analyzing growth patterns...[/bold blue]", console=console):
                growth_data = self._analyze_growth_patterns()

            console.print("📊 Activity Trends:")

            table = Table()
            table.add_column("Period", style="cyan")
            table.add_column("Posts", style="white", justify="right")
            table.add_column("Engagement", style="yellow", justify="right")
            table.add_column("Trend", style="green")

            for period, data in growth_data.items():
                trend = "📈 Growing" if data['posts'] > data.get('previous_posts', 0) else "📉 Declining" if data['posts'] < data.get('previous_posts', 0) else "➡️ Stable"

                table.add_row(
                    period,
                    str(data['posts']),
                    str(data['total_engagement']),
                    trend
                )

            console.print(table)

            console.print("\n💡 Growth insights based on your posting activity and engagement patterns")

        except Exception as e:
            console.print(f"❌ Growth analysis failed: {e}")

    def _analyze_growth_patterns(self) -> Dict[str, Any]:
        """Analyze growth patterns from posting data."""
        posts = [item for item in self.current_data if item.get('type') == 'post']

        # Group posts by time periods
        from datetime import datetime, timedelta
        now = datetime.now()

        periods = {
            'This month': {'posts': 0, 'total_engagement': 0},
            'Last month': {'posts': 0, 'total_engagement': 0},
            '2 months ago': {'posts': 0, 'total_engagement': 0},
            '3+ months ago': {'posts': 0, 'total_engagement': 0}
        }

        for post in posts:
            engagement = post.get('likes', 0) + post.get('reposts', 0) + post.get('replies', 0)

            try:
                if 'created_at' in post:
                    created_at = datetime.fromisoformat(post['created_at'].replace('Z', '+00:00'))
                    days_ago = (now - created_at).days

                    if days_ago <= 30:
                        periods['This month']['posts'] += 1
                        periods['This month']['total_engagement'] += engagement
                    elif days_ago <= 60:
                        periods['Last month']['posts'] += 1
                        periods['Last month']['total_engagement'] += engagement
                    elif days_ago <= 90:
                        periods['2 months ago']['posts'] += 1
                        periods['2 months ago']['total_engagement'] += engagement
                    else:
                        periods['3+ months ago']['posts'] += 1
                        periods['3+ months ago']['total_engagement'] += engagement
            except:
                periods['3+ months ago']['posts'] += 1
                periods['3+ months ago']['total_engagement'] += engagement

        return periods

    def _export_analysis(self):
        """Export analysis results."""
        if not self._ensure_data_loaded():
            return

        console.print(Rule("💾 Export Analysis Results", style="green"))

        export_format = Prompt.ask(
            "Export format",
            choices=["json", "csv", "txt"],
            default="json"
        )

        filename = Prompt.ask(
            "Output filename",
            default=f"skymarshal_analysis_{int(datetime.now().timestamp())}.{export_format}"
        )

        try:
            with Status("💾 [bold blue]Exporting analysis results...[/bold blue]", console=console):
                # Generate comprehensive analysis
                analysis_results = {
                    'account': self.auth_manager.current_handle,
                    'generated_at': datetime.now().isoformat(),
                    'basic_stats': self._calculate_basic_stats(),
                    'engagement_analysis': self._analyze_engagement(),
                    'timeline_analysis': self._analyze_timeline(),
                    'quality_analysis': self._analyze_content_quality(),
                    'growth_analysis': self._analyze_growth_patterns()
                }

                if export_format == 'json':
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(analysis_results, f, indent=2, ensure_ascii=False)
                elif export_format == 'csv':
                    # Create a simplified CSV version
                    import csv
                    with open(filename, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        writer.writerow(['Metric', 'Value'])

                        # Basic stats
                        stats = analysis_results['basic_stats']
                        writer.writerow(['Total Items', stats['total_items']])
                        writer.writerow(['Posts', stats['posts']])
                        writer.writerow(['Likes', stats['likes']])
                        writer.writerow(['Reposts', stats['reposts']])
                        writer.writerow(['Average Engagement', f"{stats['avg_engagement']:.2f}"])

                else:  # txt format
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(f"Skymarshal Analysis Report\n")
                        f.write(f"Account: {self.auth_manager.current_handle}\n")
                        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

                        stats = analysis_results['basic_stats']
                        f.write(f"Basic Statistics:\n")
                        f.write(f"- Total Items: {stats['total_items']}\n")
                        f.write(f"- Posts: {stats['posts']}\n")
                        f.write(f"- Likes: {stats['likes']}\n")
                        f.write(f"- Reposts: {stats['reposts']}\n")
                        f.write(f"- Average Engagement: {stats['avg_engagement']:.2f}\n")

            file_size = Path(filename).stat().st_size
            console.print(f"✅ Exported analysis to {filename} ({file_size:,} bytes)")

        except Exception as e:
            console.print(f"❌ Export failed: {e}")

    def _show_help(self):
        """Show help information."""
        console.print(Rule("❓ Account Analysis Help", style="blue"))

        help_content = """
[bold blue]Account Analysis Overview[/bold blue]
This tool provides comprehensive analysis of your Bluesky account data including
posting patterns, engagement metrics, and content quality insights.

[bold cyan]Analysis Types[/bold cyan]
• [bold]Basic Statistics[/bold]: Overview of your account activity and engagement
• [bold]Engagement Analysis[/bold]: Detailed breakdown of how your content performs
• [bold]Timeline Analysis[/bold]: Posting patterns and timing insights
• [bold]Content Quality[/bold]: Analysis of content characteristics and recommendations
• [bold]Follower Growth[/bold]: Growth patterns based on activity trends

[bold yellow]Data Requirements[/bold yellow]
• Authenticated Skymarshal session
• Downloaded account data (CAR file or JSON export)
• Recent account activity for meaningful analysis

[bold green]Understanding Results[/bold green]
• [bold]Engagement Score[/bold]: Total likes + reposts + replies for each post
• [bold]Engagement Rate[/bold]: Percentage of posts that received any engagement
• [bold]Dead Posts[/bold]: Posts with zero engagement
• [bold]Viral Posts[/bold]: Posts with 50+ interactions

[bold magenta]Tips for Better Analysis[/bold magenta]
• Ensure your data is recent (within last 30-90 days)
• Regular analysis helps track improvement trends
• Compare results over time to measure growth
• Use insights to optimize posting strategy

[bold red]Export Options[/bold red]
• [bold]JSON[/bold]: Complete structured data for external analysis
• [bold]CSV[/bold]: Spreadsheet-compatible summary data
• [bold]TXT[/bold]: Human-readable report format
        """

        console.print(Panel(help_content, title="❓ Help", style="blue"))

if __name__ == "__main__":
    app = AccountAnalysisLoner()
    app.run()