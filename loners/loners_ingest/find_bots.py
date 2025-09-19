#!/usr/bin/env python3
"""
Skymarshal Bot Detection Script
This script identifies potential bot accounts in your Bluesky data using
various detection algorithms and pattern analysis.
Usage: python find_bots.py
"""
import os
import sys
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
    from rich.prompt import Prompt, Confirm, IntPrompt, FloatPrompt
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

class BotDetectionLoner:
    """Standalone bot detection tool."""

    def __init__(self):
        """Initialize the bot detection tool."""
        self.auth_manager = AuthManager()
        self.data_manager = DataManager()
        self.ui_manager = UIManager()
        self.current_data = None
        self.bot_patterns = []

    def run(self):
        """Run the bot detection tool."""
        console.print(Panel.fit(
            "🤖 [bold blue]Skymarshal Bot Detection[/bold blue]\n\n"
            "Identify potential bot accounts in your Bluesky data\n"
            "Using pattern analysis and behavioral detection",
            title="🤖 Bot Detection",
            style="red"
        ))

        try:
            # Initialize components
            if not self._initialize():
                return

            # Main menu loop
            while True:
                console.print()
                console.print(Rule("🤖 Bot Detection Options", style="red"))

                options = [
                    "1. 🔍 Quick Bot Scan",
                    "2. 📊 Detailed Bot Analysis",
                    "3. 🎯 Custom Detection Rules",
                    "4. 📈 Bot Pattern Analysis",
                    "5. 💾 Export Bot Results",
                    "6. 🧹 Remove Bot Content",
                    "7. ❓ Help",
                    "8. 🚪 Exit"
                ]

                for option in options:
                    console.print(f"   {option}")

                console.print()
                choice = Prompt.ask("Select option", choices=["1", "2", "3", "4", "5", "6", "7", "8"], default="1")

                if choice == "1":
                    self._quick_bot_scan()
                elif choice == "2":
                    self._detailed_bot_analysis()
                elif choice == "3":
                    self._custom_detection_rules()
                elif choice == "4":
                    self._bot_pattern_analysis()
                elif choice == "5":
                    self._export_bot_results()
                elif choice == "6":
                    self._remove_bot_content()
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
            console.print("⚠️ No data loaded for bot detection")
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

    def _quick_bot_scan(self):
        """Perform a quick bot scan using standard criteria."""
        if not self._ensure_data_loaded():
            return

        console.print(Rule("🔍 Quick Bot Scan", style="yellow"))

        try:
            with Status("🤖 [bold blue]Scanning for bot patterns...[/bold blue]", console=console):
                bot_results = self._detect_bots_standard()

            if not bot_results['potential_bots']:
                console.print("✅ No obvious bot patterns detected in your data")
                return

            console.print(f"⚠️ Found {len(bot_results['potential_bots'])} items with potential bot characteristics")

            # Show summary
            self._display_bot_summary(bot_results)

            # Offer detailed analysis
            if Confirm.ask("\nWould you like to see detailed analysis?", default=True):
                self._show_bot_details(bot_results['potential_bots'][:10])

        except Exception as e:
            console.print(f"❌ Bot scan failed: {e}")

    def _detect_bots_standard(self) -> Dict[str, Any]:
        """Detect bots using standard criteria."""
        potential_bots = []
        bot_indicators = {
            'repetitive_content': 0,
            'unusual_timing': 0,
            'suspicious_handles': 0,
            'automated_patterns': 0
        }

        # Analyze posts for bot patterns
        posts = [item for item in self.current_data if item.get('type') == 'post']

        # Check for repetitive content
        text_frequency = {}
        for post in posts:
            text = post.get('text', '').strip().lower()
            if len(text) > 10:  # Ignore very short posts
                text_frequency[text] = text_frequency.get(text, 0) + 1

        # Find repetitive content
        for text, count in text_frequency.items():
            if count >= 3:  # Same text posted 3+ times
                bot_indicators['repetitive_content'] += count
                for post in posts:
                    if post.get('text', '').strip().lower() == text:
                        post['bot_reason'] = f"Repetitive content (posted {count} times)"
                        potential_bots.append(post)

        # Check for suspicious timing patterns
        self._check_timing_patterns(posts, potential_bots, bot_indicators)

        # Check for automated-looking content
        self._check_automated_patterns(posts, potential_bots, bot_indicators)

        return {
            'potential_bots': potential_bots,
            'indicators': bot_indicators,
            'total_analyzed': len(posts)
        }

    def _check_timing_patterns(self, posts: List[Dict], potential_bots: List[Dict], indicators: Dict):
        """Check for suspicious timing patterns."""
        # Look for posts at exact intervals (like every hour)
        from datetime import datetime

        timestamps = []
        for post in posts:
            try:
                if 'created_at' in post:
                    ts = datetime.fromisoformat(post['created_at'].replace('Z', '+00:00'))
                    timestamps.append((ts, post))
            except:
                continue

        # Sort by timestamp
        timestamps.sort(key=lambda x: x[0])

        # Check for regular intervals
        if len(timestamps) >= 3:
            intervals = []
            for i in range(1, len(timestamps)):
                interval = (timestamps[i][0] - timestamps[i-1][0]).total_seconds() / 60  # minutes
                intervals.append(interval)

            # Look for very regular intervals (within 5 minutes of each other)
            regular_intervals = 0
            if intervals:
                avg_interval = sum(intervals) / len(intervals)
                for interval in intervals:
                    if abs(interval - avg_interval) < 5 and 55 <= avg_interval <= 65:  # Hourly posts
                        regular_intervals += 1

            if regular_intervals >= 3:
                indicators['unusual_timing'] += regular_intervals
                for _, post in timestamps:
                    if post not in potential_bots:
                        post['bot_reason'] = "Suspicious posting intervals (too regular)"
                        potential_bots.append(post)

    def _check_automated_patterns(self, posts: List[Dict], potential_bots: List[Dict], indicators: Dict):
        """Check for automated content patterns."""
        import re

        for post in posts:
            text = post.get('text', '')

            # Check for URL-heavy content
            urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', text)
            if len(urls) >= 2:
                indicators['automated_patterns'] += 1
                post['bot_reason'] = f"Multiple URLs ({len(urls)} links)"
                if post not in potential_bots:
                    potential_bots.append(post)

            # Check for excessive hashtags
            hashtags = re.findall(r'#\w+', text)
            if len(hashtags) >= 5:
                indicators['automated_patterns'] += 1
                post['bot_reason'] = f"Excessive hashtags ({len(hashtags)} tags)"
                if post not in potential_bots:
                    potential_bots.append(post)

            # Check for very short, repetitive words
            words = text.split()
            if len(words) >= 3 and len(set(words)) <= 2:
                indicators['automated_patterns'] += 1
                post['bot_reason'] = "Repetitive word pattern"
                if post not in potential_bots:
                    potential_bots.append(post)

    def _display_bot_summary(self, bot_results: Dict[str, Any]):
        """Display bot detection summary."""
        console.print("\n🤖 Bot Detection Summary:")

        table = Table()
        table.add_column("Indicator", style="cyan")
        table.add_column("Count", style="white", justify="right")
        table.add_column("Severity", style="yellow")

        indicators = bot_results['indicators']

        for indicator, count in indicators.items():
            if count > 0:
                severity = "🔴 High" if count >= 10 else "🟡 Medium" if count >= 5 else "🟢 Low"
                readable_name = indicator.replace('_', ' ').title()
                table.add_row(readable_name, str(count), severity)

        console.print(table)

        total_bots = len(bot_results['potential_bots'])
        total_analyzed = bot_results['total_analyzed']

        if total_analyzed > 0:
            percentage = (total_bots / total_analyzed) * 100
            console.print(f"\n📊 Bot Likelihood: {percentage:.1f}% of content shows bot characteristics")

    def _show_bot_details(self, bot_items: List[Dict]):
        """Show detailed information about detected bots."""
        console.print("\n🔍 Detailed Bot Analysis:")

        for i, item in enumerate(bot_items, 1):
            text_preview = (item.get('text', '')[:80] + '...') if len(item.get('text', '')) > 80 else item.get('text', '')
            reason = item.get('bot_reason', 'Unknown')
            created_at = item.get('created_at', 'Unknown')

            console.print(f"\n{i}. [bold red]Potential Bot Content[/bold red]")
            console.print(f"   Text: {text_preview}")
            console.print(f"   Reason: {reason}")
            console.print(f"   Created: {created_at}")

    def _detailed_bot_analysis(self):
        """Perform detailed bot analysis with advanced algorithms."""
        if not self._ensure_data_loaded():
            return

        console.print(Rule("📊 Detailed Bot Analysis", style="blue"))

        # Get analysis parameters
        sensitivity = Prompt.ask(
            "Detection sensitivity",
            choices=["low", "medium", "high"],
            default="medium"
        )

        min_confidence = FloatPrompt.ask("Minimum confidence score (0.0-1.0)", default=0.7)

        try:
            with Status("🤖 [bold blue]Running detailed bot analysis...[/bold blue]", console=console):
                detailed_results = self._advanced_bot_detection(sensitivity, min_confidence)

            self._display_detailed_results(detailed_results)

        except Exception as e:
            console.print(f"❌ Detailed analysis failed: {e}")

    def _advanced_bot_detection(self, sensitivity: str, min_confidence: float) -> Dict[str, Any]:
        """Advanced bot detection with confidence scoring."""
        posts = [item for item in self.current_data if item.get('type') == 'post']

        confidence_multiplier = {
            'low': 0.5,
            'medium': 1.0,
            'high': 1.5
        }[sensitivity]

        scored_posts = []

        for post in posts:
            confidence_score = self._calculate_bot_confidence(post) * confidence_multiplier

            if confidence_score >= min_confidence:
                post['bot_confidence'] = confidence_score
                scored_posts.append(post)

        # Sort by confidence score
        scored_posts.sort(key=lambda x: x['bot_confidence'], reverse=True)

        return {
            'bot_posts': scored_posts,
            'sensitivity': sensitivity,
            'min_confidence': min_confidence,
            'total_analyzed': len(posts)
        }

    def _calculate_bot_confidence(self, post: Dict) -> float:
        """Calculate bot confidence score for a post."""
        confidence = 0.0
        text = post.get('text', '')

        # Factor 1: Repetitive content (check against other posts)
        posts = [item for item in self.current_data if item.get('type') == 'post']
        same_text_count = sum(1 for p in posts if p.get('text', '').strip().lower() == text.strip().lower())
        if same_text_count >= 3:
            confidence += 0.4

        # Factor 2: URL density
        import re
        urls = re.findall(r'http[s]?://\S+', text)
        if len(urls) >= 2:
            confidence += 0.3

        # Factor 3: Hashtag spam
        hashtags = re.findall(r'#\w+', text)
        if len(hashtags) >= 5:
            confidence += 0.2
        elif len(hashtags) >= 3:
            confidence += 0.1

        # Factor 4: Text quality
        words = text.split()
        if len(words) > 0:
            unique_words = len(set(words))
            repetition_ratio = 1 - (unique_words / len(words))
            if repetition_ratio > 0.5:
                confidence += 0.2

        # Factor 5: Very short or very long posts
        if len(text) < 10 or len(text) > 500:
            confidence += 0.1

        return min(confidence, 1.0)  # Cap at 1.0

    def _display_detailed_results(self, results: Dict[str, Any]):
        """Display detailed bot analysis results."""
        bot_posts = results['bot_posts']

        if not bot_posts:
            console.print("✅ No high-confidence bot content detected")
            return

        console.print(f"🤖 Found {len(bot_posts)} high-confidence bot posts")

        table = Table(title="Bot Detection Results")
        table.add_column("Rank", style="cyan", justify="right")
        table.add_column("Confidence", style="red", justify="right")
        table.add_column("Content Preview", style="white")
        table.add_column("Date", style="dim")

        for i, post in enumerate(bot_posts[:15], 1):
            confidence = post['bot_confidence']
            text_preview = (post.get('text', '')[:50] + '...') if len(post.get('text', '')) > 50 else post.get('text', '')
            created_at = post.get('created_at', 'Unknown')[:10]  # Just date part

            table.add_row(
                str(i),
                f"{confidence:.2f}",
                text_preview,
                created_at
            )

        console.print(table)

        if len(bot_posts) > 15:
            console.print(f"[dim]... and {len(bot_posts) - 15} more potential bot posts[/dim]")

    def _custom_detection_rules(self):
        """Allow users to define custom bot detection rules."""
        console.print(Rule("🎯 Custom Detection Rules", style="cyan"))

        console.print("Define your custom bot detection criteria:")

        # Get custom parameters
        min_repetitions = IntPrompt.ask("Minimum repetitions to flag as bot", default=3)
        max_urls_per_post = IntPrompt.ask("Maximum URLs per post", default=2)
        max_hashtags = IntPrompt.ask("Maximum hashtags per post", default=5)
        check_timing = Confirm.ask("Check for suspicious timing patterns?", default=True)

        try:
            with Status("🎯 [bold blue]Applying custom rules...[/bold blue]", console=console):
                custom_results = self._apply_custom_rules(
                    min_repetitions, max_urls_per_post, max_hashtags, check_timing
                )

            if custom_results['flagged_posts']:
                console.print(f"🎯 Custom rules flagged {len(custom_results['flagged_posts'])} posts")
                self._show_bot_details(custom_results['flagged_posts'][:10])
            else:
                console.print("✅ No posts flagged by your custom rules")

        except Exception as e:
            console.print(f"❌ Custom detection failed: {e}")

    def _apply_custom_rules(self, min_reps: int, max_urls: int, max_hashtags: int, check_timing: bool) -> Dict[str, Any]:
        """Apply custom detection rules."""
        import re
        posts = [item for item in self.current_data if item.get('type') == 'post']
        flagged_posts = []

        # Check repetitions
        text_counts = {}
        for post in posts:
            text = post.get('text', '').strip().lower()
            if len(text) > 10:
                text_counts[text] = text_counts.get(text, 0) + 1

        for post in posts:
            text = post.get('text', '').strip().lower()
            flagged = False

            # Check repetition threshold
            if text_counts.get(text, 0) >= min_reps:
                post['custom_flag_reason'] = f"Repeated {text_counts[text]} times"
                flagged = True

            # Check URL count
            urls = re.findall(r'http[s]?://\S+', post.get('text', ''))
            if len(urls) > max_urls:
                post['custom_flag_reason'] = f"Too many URLs ({len(urls)})"
                flagged = True

            # Check hashtag count
            hashtags = re.findall(r'#\w+', post.get('text', ''))
            if len(hashtags) > max_hashtags:
                post['custom_flag_reason'] = f"Too many hashtags ({len(hashtags)})"
                flagged = True

            if flagged:
                flagged_posts.append(post)

        return {
            'flagged_posts': flagged_posts,
            'rules_applied': {
                'min_repetitions': min_reps,
                'max_urls': max_urls,
                'max_hashtags': max_hashtags,
                'check_timing': check_timing
            }
        }

    def _bot_pattern_analysis(self):
        """Analyze patterns in detected bots."""
        console.print(Rule("📈 Bot Pattern Analysis", style="magenta"))

        if not self._ensure_data_loaded():
            return

        try:
            with Status("📈 [bold blue]Analyzing bot patterns...[/bold blue]", console=console):
                pattern_data = self._analyze_bot_patterns()

            console.print("📊 Bot Pattern Analysis:")

            # Show pattern distribution
            table = Table()
            table.add_column("Pattern Type", style="cyan")
            table.add_column("Occurrences", style="white", justify="right")
            table.add_column("Percentage", style="yellow", justify="right")

            total_patterns = sum(pattern_data['patterns'].values())

            for pattern, count in pattern_data['patterns'].items():
                percentage = (count / total_patterns) * 100 if total_patterns > 0 else 0
                table.add_row(
                    pattern.replace('_', ' ').title(),
                    str(count),
                    f"{percentage:.1f}%"
                )

            console.print(table)

            # Show insights
            if pattern_data['insights']:
                console.print("\n💡 Pattern Insights:")
                for insight in pattern_data['insights']:
                    console.print(f"  • {insight}")

        except Exception as e:
            console.print(f"❌ Pattern analysis failed: {e}")

    def _analyze_bot_patterns(self) -> Dict[str, Any]:
        """Analyze patterns in bot behavior."""
        posts = [item for item in self.current_data if item.get('type') == 'post']

        patterns = {
            'repetitive_text': 0,
            'url_spam': 0,
            'hashtag_spam': 0,
            'timing_suspicious': 0,
            'short_bursts': 0
        }

        insights = []

        # Analyze text repetition
        text_frequency = {}
        for post in posts:
            text = post.get('text', '').strip().lower()
            if len(text) > 10:
                text_frequency[text] = text_frequency.get(text, 0) + 1

        patterns['repetitive_text'] = sum(1 for count in text_frequency.values() if count >= 3)

        # Analyze URL patterns
        import re
        for post in posts:
            urls = re.findall(r'http[s]?://\S+', post.get('text', ''))
            if len(urls) >= 2:
                patterns['url_spam'] += 1

            hashtags = re.findall(r'#\w+', post.get('text', ''))
            if len(hashtags) >= 5:
                patterns['hashtag_spam'] += 1

        # Generate insights
        total_posts = len(posts)
        if total_posts > 0:
            rep_percentage = (patterns['repetitive_text'] / total_posts) * 100
            if rep_percentage > 20:
                insights.append(f"High repetition: {rep_percentage:.1f}% of content is repetitive")

            url_percentage = (patterns['url_spam'] / total_posts) * 100
            if url_percentage > 10:
                insights.append(f"URL spam detected: {url_percentage:.1f}% of posts contain multiple URLs")

        return {
            'patterns': patterns,
            'insights': insights,
            'total_analyzed': total_posts
        }

    def _export_bot_results(self):
        """Export bot detection results."""
        if not self._ensure_data_loaded():
            return

        console.print(Rule("💾 Export Bot Results", style="green"))

        export_format = Prompt.ask(
            "Export format",
            choices=["json", "csv", "txt"],
            default="csv"
        )

        filename = Prompt.ask(
            "Output filename",
            default=f"skymarshal_bots_{int(datetime.now().timestamp())}.{export_format}"
        )

        try:
            with Status("💾 [bold blue]Exporting bot results...[/bold blue]", console=console):
                # Run detection to get fresh results
                bot_results = self._detect_bots_standard()

                if export_format == 'json':
                    export_data = {
                        'account': self.auth_manager.current_handle,
                        'exported_at': datetime.now().isoformat(),
                        'detection_summary': bot_results['indicators'],
                        'potential_bots': bot_results['potential_bots']
                    }

                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(export_data, f, indent=2, ensure_ascii=False)

                elif export_format == 'csv':
                    import csv
                    with open(filename, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=['text', 'created_at', 'bot_reason', 'type'])
                        writer.writeheader()

                        for bot in bot_results['potential_bots']:
                            writer.writerow({
                                'text': bot.get('text', ''),
                                'created_at': bot.get('created_at', ''),
                                'bot_reason': bot.get('bot_reason', ''),
                                'type': bot.get('type', '')
                            })

                else:  # txt format
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(f"Skymarshal Bot Detection Report\n")
                        f.write(f"Account: {self.auth_manager.current_handle}\n")
                        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

                        f.write(f"Detection Summary:\n")
                        for indicator, count in bot_results['indicators'].items():
                            f.write(f"- {indicator.replace('_', ' ').title()}: {count}\n")

                        f.write(f"\nPotential Bot Content ({len(bot_results['potential_bots'])} items):\n")
                        for i, bot in enumerate(bot_results['potential_bots'], 1):
                            f.write(f"{i}. {bot.get('text', '')[:100]}...\n")
                            f.write(f"   Reason: {bot.get('bot_reason', '')}\n\n")

            file_size = Path(filename).stat().st_size
            console.print(f"✅ Exported bot results to {filename} ({file_size:,} bytes)")

        except Exception as e:
            console.print(f"❌ Export failed: {e}")

    def _remove_bot_content(self):
        """Remove detected bot content."""
        console.print(Rule("🧹 Remove Bot Content", style="red"))

        console.print("⚠️ This will permanently delete bot content from your data")
        console.print("💡 Make sure to backup your data first")

        if not Confirm.ask("Are you sure you want to proceed?", default=False):
            console.print("❌ Operation cancelled")
            return

        if not self._ensure_data_loaded():
            return

        try:
            with Status("🧹 [bold blue]Identifying bot content for removal...[/bold blue]", console=console):
                bot_results = self._detect_bots_standard()

            bot_posts = bot_results['potential_bots']
            if not bot_posts:
                console.print("✅ No bot content to remove")
                return

            console.print(f"🎯 Found {len(bot_posts)} potential bot posts to remove")

            # Show preview
            for i, post in enumerate(bot_posts[:5], 1):
                text_preview = (post.get('text', '')[:60] + '...') if len(post.get('text', '')) > 60 else post.get('text', '')
                console.print(f"{i}. {text_preview}")

            if len(bot_posts) > 5:
                console.print(f"... and {len(bot_posts) - 5} more posts")

            if not Confirm.ask(f"\nRemove these {len(bot_posts)} bot posts?", default=False):
                console.print("❌ Removal cancelled")
                return

            # Remove bot posts from current data
            bot_texts = set(post.get('text', '') for post in bot_posts)
            original_count = len(self.current_data)

            self.current_data = [
                item for item in self.current_data
                if item.get('text', '') not in bot_texts
            ]

            removed_count = original_count - len(self.current_data)
            console.print(f"✅ Removed {removed_count} bot posts from loaded data")
            console.print("💡 Changes are in memory only - export to save permanently")

        except Exception as e:
            console.print(f"❌ Bot removal failed: {e}")

    def _show_help(self):
        """Show help information."""
        console.print(Rule("❓ Bot Detection Help", style="red"))

        help_content = """
[bold red]Bot Detection Overview[/bold red]
This tool identifies potential bot accounts and automated content in your Bluesky data
using various detection algorithms and pattern analysis techniques.

[bold cyan]Detection Methods[/bold cyan]
• [bold]Repetitive Content[/bold]: Same text posted multiple times
• [bold]Timing Patterns[/bold]: Posts at suspiciously regular intervals
• [bold]URL Spam[/bold]: Posts with excessive links
• [bold]Hashtag Spam[/bold]: Posts with too many hashtags
• [bold]Automated Patterns[/bold]: Very repetitive or template-like content

[bold yellow]Analysis Types[/bold yellow]
• [bold]Quick Scan[/bold]: Fast detection using standard criteria
• [bold]Detailed Analysis[/bold]: Advanced algorithms with confidence scoring
• [bold]Custom Rules[/bold]: User-defined detection parameters
• [bold]Pattern Analysis[/bold]: Statistical analysis of bot behavior

[bold green]Understanding Results[/bold green]
• [bold]Confidence Score[/bold]: 0.0-1.0 likelihood of bot behavior
• [bold]Bot Indicators[/bold]: Specific patterns that triggered detection
• [bold]Severity Levels[/bold]: Low/Medium/High based on indicator counts

[bold magenta]Safety Features[/bold magenta]
• [bold]Preview Mode[/bold]: See what will be affected before removal
• [bold]Multiple Confirmations[/bold]: Prevent accidental deletions
• [bold]Backup Reminders[/bold]: Always backup before making changes
• [bold]In-Memory Operations[/bold]: Changes aren't permanent until exported

[bold blue]Best Practices[/bold blue]
• Start with quick scan to get overview
• Use medium sensitivity for balanced detection
• Review results manually before removal
• Export results for record keeping
• Regular scanning helps maintain data quality
        """

        console.print(Panel(help_content, title="❓ Help", style="red"))

if __name__ == "__main__":
    app = BotDetectionLoner()
    app.run()