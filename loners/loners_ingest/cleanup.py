#!/usr/bin/env python3
"""
Skymarshal Content Cleanup Script
This script provides comprehensive cleanup capabilities for your Bluesky content.
It helps identify and remove unwanted content like spam, duplicates, and low-quality posts.
Usage: python cleanup.py
"""
import os
import sys
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

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

class ContentCleanupLoner:
    """Standalone content cleanup tool."""

    def __init__(self):
        """Initialize the content cleanup tool."""
        self.auth_manager = AuthManager()
        self.data_manager = DataManager()
        self.ui_manager = UIManager()
        self.current_data = None
        self.cleanup_candidates = []

    def run(self):
        """Run the content cleanup tool."""
        console.print(Panel.fit(
            "🧹 [bold blue]Skymarshal Content Cleanup[/bold blue]\n\n"
            "Clean up your Bluesky content by removing unwanted items\n"
            "Spam, duplicates, low-quality content, and more",
            title="🧹 Content Cleanup",
            style="red"
        ))

        try:
            # Initialize components
            if not self._initialize():
                return

            # Main menu loop
            while True:
                console.print()
                console.print(Rule("🧹 Cleanup Options", style="red"))

                options = [
                    "1. 🔍 Find Cleanup Candidates",
                    "2. 🗑️ Remove Duplicate Content",
                    "3. 💀 Clean Up Dead Posts",
                    "4. 🤖 Remove Bot-like Content",
                    "5. 📅 Clean Up Old Content",
                    "6. 🎯 Custom Cleanup Rules",
                    "7. 💾 Export Cleanup Results",
                    "8. ❓ Help",
                    "9. 🚪 Exit"
                ]

                for option in options:
                    console.print(f"   {option}")

                console.print()
                choice = Prompt.ask("Select option", choices=["1", "2", "3", "4", "5", "6", "7", "8", "9"], default="1")

                if choice == "1":
                    self._find_cleanup_candidates()
                elif choice == "2":
                    self._remove_duplicates()
                elif choice == "3":
                    self._cleanup_dead_posts()
                elif choice == "4":
                    self._remove_bot_content()
                elif choice == "5":
                    self._cleanup_old_content()
                elif choice == "6":
                    self._custom_cleanup_rules()
                elif choice == "7":
                    self._export_cleanup_results()
                elif choice == "8":
                    self._show_help()
                elif choice == "9":
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
        """Ensure we have data loaded for cleanup."""
        if not self.current_data:
            console.print("⚠️ No data loaded for cleanup")
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

    def _find_cleanup_candidates(self):
        """Find all potential cleanup candidates."""
        if not self._ensure_data_loaded():
            return

        console.print(Rule("🔍 Finding Cleanup Candidates", style="yellow"))

        try:
            with Status("🔍 [bold blue]Analyzing content for cleanup...[/bold blue]", console=console):
                candidates = self._identify_cleanup_candidates()

            self.cleanup_candidates = candidates['all_candidates']

            console.print(f"🎯 Found {len(self.cleanup_candidates)} potential cleanup candidates")

            # Show summary
            self._display_cleanup_summary(candidates)

            # Offer detailed view
            if self.cleanup_candidates and Confirm.ask("\nWould you like to see detailed breakdown?", default=True):
                self._show_cleanup_details(candidates)

        except Exception as e:
            console.print(f"❌ Cleanup analysis failed: {e}")

    def _identify_cleanup_candidates(self) -> Dict[str, Any]:
        """Identify all types of cleanup candidates."""
        candidates = {
            'duplicates': [],
            'dead_posts': [],
            'bot_content': [],
            'old_content': [],
            'low_quality': [],
            'all_candidates': []
        }

        posts = [item for item in self.current_data if item.get('type') == 'post']
        likes = [item for item in self.current_data if item.get('type') == 'like']
        reposts = [item for item in self.current_data if item.get('type') == 'repost']

        # Find duplicates
        candidates['duplicates'] = self._find_duplicates(posts)

        # Find dead posts (no engagement)
        for post in posts:
            engagement = post.get('likes', 0) + post.get('reposts', 0) + post.get('replies', 0)
            if engagement == 0:
                post['cleanup_reason'] = "No engagement (dead post)"
                candidates['dead_posts'].append(post)

        # Find bot-like content
        candidates['bot_content'] = self._find_bot_content(posts)

        # Find old content
        cutoff_date = datetime.now() - timedelta(days=365)  # 1 year old
        for post in posts:
            try:
                if 'created_at' in post:
                    created_at = datetime.fromisoformat(post['created_at'].replace('Z', '+00:00'))
                    if created_at < cutoff_date:
                        post['cleanup_reason'] = f"Old content (from {created_at.strftime('%Y-%m-%d')})"
                        candidates['old_content'].append(post)
            except:
                continue

        # Find low quality content
        for post in posts:
            text = post.get('text', '')
            if len(text.strip()) < 10:  # Very short posts
                post['cleanup_reason'] = "Very short content"
                candidates['low_quality'].append(post)

        # Combine all candidates (avoid duplicates)
        all_candidates = []
        seen_ids = set()

        for category, items in candidates.items():
            if category == 'all_candidates':
                continue
            for item in items:
                item_id = item.get('uri', item.get('text', ''))[:50]  # Use URI or text snippet as ID
                if item_id not in seen_ids:
                    seen_ids.add(item_id)
                    all_candidates.append(item)

        candidates['all_candidates'] = all_candidates
        return candidates

    def _find_duplicates(self, posts: List[Dict]) -> List[Dict]:
        """Find duplicate posts."""
        duplicates = []
        text_groups = {}

        # Group posts by text
        for post in posts:
            text = post.get('text', '').strip().lower()
            if len(text) > 5:  # Ignore very short text
                if text not in text_groups:
                    text_groups[text] = []
                text_groups[text].append(post)

        # Find groups with duplicates
        for text, group in text_groups.items():
            if len(group) > 1:
                # Keep the first one, mark others as duplicates
                for duplicate in group[1:]:
                    duplicate['cleanup_reason'] = f"Duplicate content (posted {len(group)} times)"
                    duplicates.append(duplicate)

        return duplicates

    def _find_bot_content(self, posts: List[Dict]) -> List[Dict]:
        """Find bot-like content."""
        bot_content = []
        import re

        for post in posts:
            text = post.get('text', '')

            # Check for multiple URLs
            urls = re.findall(r'http[s]?://\S+', text)
            if len(urls) >= 3:
                post['cleanup_reason'] = f"Multiple URLs ({len(urls)} links)"
                bot_content.append(post)
                continue

            # Check for excessive hashtags
            hashtags = re.findall(r'#\w+', text)
            if len(hashtags) >= 8:
                post['cleanup_reason'] = f"Excessive hashtags ({len(hashtags)} tags)"
                bot_content.append(post)
                continue

            # Check for repetitive patterns
            words = text.split()
            if len(words) >= 5 and len(set(words)) <= 3:
                post['cleanup_reason'] = "Repetitive word pattern"
                bot_content.append(post)

        return bot_content

    def _display_cleanup_summary(self, candidates: Dict[str, Any]):
        """Display cleanup summary."""
        console.print("\n🧹 Cleanup Summary:")

        table = Table()
        table.add_column("Category", style="cyan")
        table.add_column("Count", style="white", justify="right")
        table.add_column("Description", style="dim")

        table.add_row("Duplicates", str(len(candidates['duplicates'])), "Identical content posted multiple times")
        table.add_row("Dead Posts", str(len(candidates['dead_posts'])), "Posts with zero engagement")
        table.add_row("Bot Content", str(len(candidates['bot_content'])), "Automated or spam-like content")
        table.add_row("Old Content", str(len(candidates['old_content'])), "Content older than 1 year")
        table.add_row("Low Quality", str(len(candidates['low_quality'])), "Very short or minimal content")
        table.add_row("", "", "")
        table.add_row("Total Candidates", str(len(candidates['all_candidates'])), "Unique items for potential cleanup")

        console.print(table)

    def _show_cleanup_details(self, candidates: Dict[str, Any]):
        """Show detailed cleanup breakdown."""
        console.print("\n📋 Cleanup Details:")

        for category, items in candidates.items():
            if category == 'all_candidates' or not items:
                continue

            console.print(f"\n{category.replace('_', ' ').title()} ({len(items)} items):")

            for i, item in enumerate(items[:3], 1):  # Show first 3 of each category
                text_preview = (item.get('text', '')[:60] + '...') if len(item.get('text', '')) > 60 else item.get('text', '')
                reason = item.get('cleanup_reason', 'Unknown')
                console.print(f"  {i}. {text_preview}")
                console.print(f"     Reason: {reason}")

            if len(items) > 3:
                console.print(f"     ... and {len(items) - 3} more items")

    def _remove_duplicates(self):
        """Remove duplicate content."""
        if not self._ensure_data_loaded():
            return

        console.print(Rule("🗑️ Remove Duplicate Content", style="red"))

        try:
            with Status("🔍 [bold blue]Finding duplicates...[/bold blue]", console=console):
                duplicates = self._find_duplicates([item for item in self.current_data if item.get('type') == 'post'])

            if not duplicates:
                console.print("✅ No duplicate content found")
                return

            console.print(f"🎯 Found {len(duplicates)} duplicate posts")

            # Show preview
            for i, dup in enumerate(duplicates[:5], 1):
                text_preview = (dup.get('text', '')[:60] + '...') if len(dup.get('text', '')) > 60 else dup.get('text', '')
                console.print(f"{i}. {text_preview}")

            if len(duplicates) > 5:
                console.print(f"... and {len(duplicates) - 5} more duplicates")

            if Confirm.ask(f"\nRemove {len(duplicates)} duplicate posts?", default=False):
                self._execute_cleanup(duplicates, "duplicates")

        except Exception as e:
            console.print(f"❌ Duplicate removal failed: {e}")

    def _cleanup_dead_posts(self):
        """Clean up posts with no engagement."""
        if not self._ensure_data_loaded():
            return

        console.print(Rule("💀 Clean Up Dead Posts", style="dim"))

        # Get parameters
        min_age_days = IntPrompt.ask("Minimum age in days for dead posts", default=30)

        try:
            with Status("💀 [bold blue]Finding dead posts...[/bold blue]", console=console):
                dead_posts = self._find_dead_posts(min_age_days)

            if not dead_posts:
                console.print("✅ No dead posts found matching criteria")
                return

            console.print(f"💀 Found {len(dead_posts)} dead posts (older than {min_age_days} days with no engagement)")

            # Show preview
            for i, post in enumerate(dead_posts[:5], 1):
                text_preview = (post.get('text', '')[:60] + '...') if len(post.get('text', '')) > 60 else post.get('text', '')
                created_at = post.get('created_at', 'Unknown')[:10]
                console.print(f"{i}. {text_preview} (from {created_at})")

            if len(dead_posts) > 5:
                console.print(f"... and {len(dead_posts) - 5} more dead posts")

            if Confirm.ask(f"\nRemove {len(dead_posts)} dead posts?", default=False):
                self._execute_cleanup(dead_posts, "dead posts")

        except Exception as e:
            console.print(f"❌ Dead post cleanup failed: {e}")

    def _find_dead_posts(self, min_age_days: int) -> List[Dict]:
        """Find dead posts (no engagement) older than specified days."""
        dead_posts = []
        cutoff_date = datetime.now() - timedelta(days=min_age_days)

        posts = [item for item in self.current_data if item.get('type') == 'post']

        for post in posts:
            # Check engagement
            engagement = post.get('likes', 0) + post.get('reposts', 0) + post.get('replies', 0)
            if engagement > 0:
                continue

            # Check age
            try:
                if 'created_at' in post:
                    created_at = datetime.fromisoformat(post['created_at'].replace('Z', '+00:00'))
                    if created_at < cutoff_date:
                        post['cleanup_reason'] = f"Dead post (no engagement, {min_age_days}+ days old)"
                        dead_posts.append(post)
            except:
                # If we can't parse date, assume it's old enough
                post['cleanup_reason'] = "Dead post (no engagement, unknown age)"
                dead_posts.append(post)

        return dead_posts

    def _remove_bot_content(self):
        """Remove bot-like content."""
        if not self._ensure_data_loaded():
            return

        console.print(Rule("🤖 Remove Bot-like Content", style="red"))

        try:
            with Status("🤖 [bold blue]Detecting bot content...[/bold blue]", console=console):
                bot_content = self._find_bot_content([item for item in self.current_data if item.get('type') == 'post'])

            if not bot_content:
                console.print("✅ No bot-like content detected")
                return

            console.print(f"🤖 Found {len(bot_content)} posts with bot-like characteristics")

            # Show preview
            for i, post in enumerate(bot_content[:5], 1):
                text_preview = (post.get('text', '')[:60] + '...') if len(post.get('text', '')) > 60 else post.get('text', '')
                reason = post.get('cleanup_reason', 'Unknown')
                console.print(f"{i}. {text_preview}")
                console.print(f"   Reason: {reason}")

            if len(bot_content) > 5:
                console.print(f"... and {len(bot_content) - 5} more bot-like posts")

            if Confirm.ask(f"\nRemove {len(bot_content)} bot-like posts?", default=False):
                self._execute_cleanup(bot_content, "bot content")

        except Exception as e:
            console.print(f"❌ Bot content removal failed: {e}")

    def _cleanup_old_content(self):
        """Clean up old content."""
        if not self._ensure_data_loaded():
            return

        console.print(Rule("📅 Clean Up Old Content", style="blue"))

        # Get parameters
        max_age_days = IntPrompt.ask("Maximum age in days to keep", default=365)
        content_types = Prompt.ask(
            "Content types to clean",
            choices=["posts", "likes", "reposts", "all"],
            default="all"
        )

        try:
            with Status("📅 [bold blue]Finding old content...[/bold blue]", console=console):
                old_content = self._find_old_content(max_age_days, content_types)

            if not old_content:
                console.print(f"✅ No content older than {max_age_days} days found")
                return

            console.print(f"📅 Found {len(old_content)} items older than {max_age_days} days")

            # Show breakdown by type
            type_counts = {}
            for item in old_content:
                item_type = item.get('type', 'unknown')
                type_counts[item_type] = type_counts.get(item_type, 0) + 1

            for item_type, count in type_counts.items():
                console.print(f"  • {item_type.title()}: {count}")

            if Confirm.ask(f"\nRemove {len(old_content)} old items?", default=False):
                self._execute_cleanup(old_content, "old content")

        except Exception as e:
            console.print(f"❌ Old content cleanup failed: {e}")

    def _find_old_content(self, max_age_days: int, content_types: str) -> List[Dict]:
        """Find content older than specified days."""
        old_content = []
        cutoff_date = datetime.now() - timedelta(days=max_age_days)

        # Filter by content type
        if content_types == "all":
            items = self.current_data
        elif content_types == "posts":
            items = [item for item in self.current_data if item.get('type') == 'post']
        elif content_types == "likes":
            items = [item for item in self.current_data if item.get('type') == 'like']
        elif content_types == "reposts":
            items = [item for item in self.current_data if item.get('type') == 'repost']
        else:
            items = self.current_data

        for item in items:
            try:
                if 'created_at' in item:
                    created_at = datetime.fromisoformat(item['created_at'].replace('Z', '+00:00'))
                    if created_at < cutoff_date:
                        item['cleanup_reason'] = f"Old content (from {created_at.strftime('%Y-%m-%d')})"
                        old_content.append(item)
            except:
                continue

        return old_content

    def _custom_cleanup_rules(self):
        """Apply custom cleanup rules."""
        if not self._ensure_data_loaded():
            return

        console.print(Rule("🎯 Custom Cleanup Rules", style="cyan"))

        console.print("Define your custom cleanup criteria:")

        # Get custom parameters
        min_text_length = IntPrompt.ask("Minimum text length (0 = no limit)", default=0)
        max_text_length = IntPrompt.ask("Maximum text length (0 = no limit)", default=0)
        max_hashtags = IntPrompt.ask("Maximum hashtags (0 = no limit)", default=0)
        max_urls = IntPrompt.ask("Maximum URLs (0 = no limit)", default=0)
        keywords_to_remove = Prompt.ask("Keywords to remove (comma-separated, optional)", default="").strip()

        try:
            with Status("🎯 [bold blue]Applying custom rules...[/bold blue]", console=console):
                custom_candidates = self._apply_custom_cleanup_rules(
                    min_text_length, max_text_length, max_hashtags, max_urls, keywords_to_remove
                )

            if not custom_candidates:
                console.print("✅ No content matches your custom cleanup criteria")
                return

            console.print(f"🎯 Found {len(custom_candidates)} items matching custom criteria")

            # Show preview
            for i, item in enumerate(custom_candidates[:5], 1):
                text_preview = (item.get('text', '')[:60] + '...') if len(item.get('text', '')) > 60 else item.get('text', '')
                reason = item.get('cleanup_reason', 'Unknown')
                console.print(f"{i}. {text_preview}")
                console.print(f"   Reason: {reason}")

            if len(custom_candidates) > 5:
                console.print(f"... and {len(custom_candidates) - 5} more items")

            if Confirm.ask(f"\nRemove {len(custom_candidates)} items?", default=False):
                self._execute_cleanup(custom_candidates, "custom rule matches")

        except Exception as e:
            console.print(f"❌ Custom cleanup failed: {e}")

    def _apply_custom_cleanup_rules(self, min_len: int, max_len: int, max_hashtags: int, max_urls: int, keywords: str) -> List[Dict]:
        """Apply custom cleanup rules."""
        import re
        candidates = []
        posts = [item for item in self.current_data if item.get('type') == 'post']

        keywords_list = [k.strip().lower() for k in keywords.split(',') if k.strip()] if keywords else []

        for post in posts:
            text = post.get('text', '')
            matched = False
            reasons = []

            # Check text length
            if min_len > 0 and len(text) < min_len:
                reasons.append(f"Too short (< {min_len} chars)")
                matched = True

            if max_len > 0 and len(text) > max_len:
                reasons.append(f"Too long (> {max_len} chars)")
                matched = True

            # Check hashtags
            if max_hashtags > 0:
                hashtags = re.findall(r'#\w+', text)
                if len(hashtags) > max_hashtags:
                    reasons.append(f"Too many hashtags ({len(hashtags)} > {max_hashtags})")
                    matched = True

            # Check URLs
            if max_urls > 0:
                urls = re.findall(r'http[s]?://\S+', text)
                if len(urls) > max_urls:
                    reasons.append(f"Too many URLs ({len(urls)} > {max_urls})")
                    matched = True

            # Check keywords
            if keywords_list:
                text_lower = text.lower()
                found_keywords = [kw for kw in keywords_list if kw in text_lower]
                if found_keywords:
                    reasons.append(f"Contains keywords: {', '.join(found_keywords)}")
                    matched = True

            if matched:
                post['cleanup_reason'] = "; ".join(reasons)
                candidates.append(post)

        return candidates

    def _execute_cleanup(self, items_to_remove: List[Dict], description: str):
        """Execute the cleanup by removing items."""
        console.print(f"\n⚠️ This will remove {len(items_to_remove)} {description} from your data")
        console.print("💡 This operation modifies your loaded data - export to make permanent")

        if not Confirm.ask("Are you absolutely sure?", default=False):
            console.print("❌ Cleanup cancelled")
            return

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task(f"🗑️ Removing {description}...", total=len(items_to_remove))

                # Create a set of items to remove for faster lookup
                items_to_remove_set = set()
                for item in items_to_remove:
                    # Use a combination of fields as identifier
                    identifier = f"{item.get('uri', '')}{item.get('text', '')}{item.get('created_at', '')}"
                    items_to_remove_set.add(identifier)

                # Filter out items to remove
                original_count = len(self.current_data)
                filtered_data = []

                for item in self.current_data:
                    identifier = f"{item.get('uri', '')}{item.get('text', '')}{item.get('created_at', '')}"
                    if identifier not in items_to_remove_set:
                        filtered_data.append(item)
                    else:
                        progress.advance(task)

                self.current_data = filtered_data
                removed_count = original_count - len(self.current_data)

                progress.update(task, description=f"✅ Removed {removed_count} items")

            console.print(f"✅ Successfully removed {removed_count} {description}")
            console.print(f"📊 Remaining items: {len(self.current_data)}")
            console.print("💾 Remember to export your cleaned data to save changes")

        except Exception as e:
            console.print(f"❌ Cleanup execution failed: {e}")

    def _export_cleanup_results(self):
        """Export cleanup results."""
        if not self._ensure_data_loaded():
            return

        console.print(Rule("💾 Export Cleanup Results", style="green"))

        export_what = Prompt.ask(
            "What to export",
            choices=["cleaned_data", "cleanup_candidates", "both"],
            default="cleaned_data"
        )

        export_format = Prompt.ask(
            "Export format",
            choices=["json", "csv"],
            default="json"
        )

        base_filename = Prompt.ask(
            "Base filename",
            default=f"skymarshal_cleanup_{int(datetime.now().timestamp())}"
        )

        try:
            with Status("💾 [bold blue]Exporting cleanup results...[/bold blue]", console=console):
                exported_files = []

                if export_what in ["cleaned_data", "both"]:
                    if export_format == "json":
                        cleaned_filename = f"{base_filename}_cleaned.json"
                        with open(cleaned_filename, 'w', encoding='utf-8') as f:
                            json.dump(self.current_data, f, indent=2, ensure_ascii=False)
                        exported_files.append(cleaned_filename)
                    else:  # CSV
                        cleaned_filename = f"{base_filename}_cleaned.csv"
                        self._export_to_csv(self.current_data, cleaned_filename)
                        exported_files.append(cleaned_filename)

                if export_what in ["cleanup_candidates", "both"] and self.cleanup_candidates:
                    if export_format == "json":
                        candidates_filename = f"{base_filename}_candidates.json"
                        candidates_data = {
                            'account': self.auth_manager.current_handle,
                            'exported_at': datetime.now().isoformat(),
                            'total_candidates': len(self.cleanup_candidates),
                            'candidates': self.cleanup_candidates
                        }
                        with open(candidates_filename, 'w', encoding='utf-8') as f:
                            json.dump(candidates_data, f, indent=2, ensure_ascii=False)
                        exported_files.append(candidates_filename)
                    else:  # CSV
                        candidates_filename = f"{base_filename}_candidates.csv"
                        self._export_to_csv(self.cleanup_candidates, candidates_filename)
                        exported_files.append(candidates_filename)

            console.print(f"✅ Exported {len(exported_files)} files:")
            for filename in exported_files:
                file_size = Path(filename).stat().st_size
                console.print(f"   📄 {filename} ({file_size:,} bytes)")

        except Exception as e:
            console.print(f"❌ Export failed: {e}")

    def _export_to_csv(self, data: List[Dict], filename: str):
        """Export data to CSV format."""
        import csv

        if not data:
            return

        with open(filename, 'w', newline='', encoding='utf-8') as f:
            # Use common fields
            fieldnames = ['type', 'text', 'created_at', 'likes', 'reposts', 'replies', 'cleanup_reason']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for item in data:
                row = {}
                for field in fieldnames:
                    row[field] = item.get(field, '')
                writer.writerow(row)

    def _show_help(self):
        """Show help information."""
        console.print(Rule("❓ Content Cleanup Help", style="red"))

        help_content = """
[bold red]Content Cleanup Overview[/bold red]
This tool helps you clean up your Bluesky content by identifying and removing
unwanted items like duplicates, spam, low-quality posts, and old content.

[bold cyan]Cleanup Categories[/bold cyan]
• [bold]Duplicates[/bold]: Identical content posted multiple times
• [bold]Dead Posts[/bold]: Posts with zero engagement after specified time
• [bold]Bot Content[/bold]: Automated or spam-like posts (excessive URLs/hashtags)
• [bold]Old Content[/bold]: Content older than specified age
• [bold]Low Quality[/bold]: Very short posts or minimal content
• [bold]Custom Rules[/bold]: User-defined criteria for cleanup

[bold yellow]Safety Features[/bold yellow]
• [bold]Preview Mode[/bold]: See what will be removed before confirmation
• [bold]Multiple Confirmations[/bold]: Prevent accidental deletions
• [bold]In-Memory Operations[/bold]: Changes only affect loaded data until exported
• [bold]Backup Reminders[/bold]: Always backup before major cleanup operations

[bold green]Cleanup Process[/bold green]
1. [bold]Analysis[/bold]: Tool scans your data for cleanup candidates
2. [bold]Review[/bold]: Preview what will be removed and why
3. [bold]Confirmation[/bold]: Multiple confirmations before removal
4. [bold]Execution[/bold]: Items removed from loaded data
5. [bold]Export[/bold]: Save cleaned data to make changes permanent

[bold blue]Best Practices[/bold blue]
• Start with "Find Cleanup Candidates" to get overview
• Review each category carefully before removal
• Use conservative settings initially
• Export cleaned data to save changes
• Keep backups of original data

[bold magenta]Custom Rules Examples[/bold magenta]
• Remove posts shorter than 20 characters
• Remove posts with more than 5 hashtags
• Remove posts containing specific keywords
• Remove posts with multiple URLs

[bold red]⚠️ Important Notes[/bold red]
• Cleanup operations modify your loaded data only
• Export cleaned data to make changes permanent
• Original files remain unchanged until overwritten
• Always backup important data before cleanup
        """

        console.print(Panel(help_content, title="❓ Help", style="red"))

if __name__ == "__main__":
    app = ContentCleanupLoner()
    app.run()