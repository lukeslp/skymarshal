"""
Skymarshal User Interface Components

File Purpose: Rich-based UI components for interactive menus, tables, and displays
Primary Functions/Classes: UIManager
Inputs and Outputs (I/O): User input via prompts, visual output via Rich console

This module provides all user interface functionality including menu systems, data tables,
progress displays, help screens, and interactive prompts for the Skymarshal application.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from .models import (
    ContentItem,
    ContentType,
    DeleteMode,
    SearchFilters,
    UserSettings,
    calculate_engagement_score,
    console,
)


class UIManager:
    """Manages all user interface operations."""

    def __init__(self, settings: UserSettings):
        self.settings = settings

    def show_main_menu(
        self,
        is_authenticated: bool,
        current_handle: Optional[str],
        current_data_file: Optional[Path],
        data_count: int,
    ) -> str:
        """Display main menu and get user choice."""
        # Display authentication and status information FIRST (above menu options)
        status_items = []
        if is_authenticated:
            if current_handle:
                status_items.append(f"[green]Authenticated[/] as @{current_handle}")
            else:
                status_items.append("[green]Authenticated[/]")
        else:
            status_items.append("[red]Not authenticated[/]")

        if current_data_file:
            status_items.append(f"[bright_cyan]Data:[/] {current_data_file.name}")
            status_items.append(f"[cyan]Items:[/] {data_count}")
        else:
            status_items.append("[dim]No data loaded[/]")

        console.print(
            Panel(" | ".join(status_items), title="Status", border_style="dim")
        )
        console.print()

        # Now display the menu options using new prompt system
        console.print(Rule("[bright_cyan]Main Menu[/]", style="bright_cyan"))

        choices = {
            "1": ("search", "Find and manage content (search, analyze, delete)"),
            "2": ("stats", "View statistics and engagement insights"),
            "3": ("data", "Make fresh backup or manage files"),
            "4": ("auth", "Login to Bluesky or check auth status"),
            "5": ("followers", "Follower analysis & ranking"),
            "s": ("settings", "Settings"),
            "?": ("help", "Help"),
            "q": ("quit", "Quit"),
        }

        choice, action = self.prompt_with_choices(
            "Select option",
            choices=choices,
            default="1",
            context="main_menu",
            allow_navigation=False,  # Main menu doesn't need back
        )

        return choice

    def display_stats(
        self,
        current_data: List[ContentItem],
        mode: str = "compact",
        data_file_name: Optional[str] = None,
        high_engagement_threshold: int = 20,
    ):
        """Display statistics in compact or full mode.

        Args:
            current_data: List of content items to analyze
            mode: "compact" for data loading screens, "full" for comprehensive stats
            data_file_name: Optional filename to show in title (full mode only)
            high_engagement_threshold: Threshold for high engagement classification
        """
        if not current_data:
            console.print("No data loaded")
            return

        # Compute with a short spinner to indicate work in big datasets
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
            console=console,
        ) as progress:
            task = progress.add_task("Computing statistics...", total=1)

            total_items = len(current_data)
            posts = [item for item in current_data if item.content_type == "post"]
            replies = [item for item in current_data if item.content_type == "reply"]
            repost_items = [
                item for item in current_data if item.content_type == "repost"
            ]
            like_items = [item for item in current_data if item.content_type == "like"]

            pr_items = posts + replies

            # Compute totals only over posts/replies
            total_likes = sum(int(it.like_count or 0) for it in pr_items)
            total_reposts = sum(int(it.repost_count or 0) for it in pr_items)
            total_replies = sum(int(it.reply_count or 0) for it in pr_items)
            total_engagement = sum(
                calculate_engagement_score(
                    int(it.like_count or 0),
                    int(it.repost_count or 0),
                    int(it.reply_count or 0),
                )
                for it in pr_items
            )

            # Averages are per post/reply, not per total items
            avg_engagement = (total_engagement / len(pr_items)) if pr_items else 0
            avg_likes = (total_likes / len(pr_items)) if pr_items else 0
            dead_threads = [
                it
                for it in pr_items
                if it.like_count == 0 and it.repost_count == 0 and it.reply_count == 0
            ]
            high_engagement = [
                it
                for it in pr_items
                if calculate_engagement_score(
                    int(it.like_count or 0),
                    int(it.repost_count or 0),
                    int(it.reply_count or 0),
                )
                >= high_engagement_threshold
            ]

            progress.update(task, completed=1)

        if mode == "compact":
            # Compact display for data loading screens
            console.print(Rule("Data Overview", style="bright_cyan"))

            table = Table(show_header=True, box=None)
            table.add_column("Metric", style="bold", width=20)
            table.add_column("Count", style="cyan", width=8)
            table.add_column("Details", style="dim", width=25)

            table.add_row("Total Items", str(total_items), "All content")
            table.add_row("Posts", str(len(posts)), "Original posts")
            table.add_row("Replies", str(len(replies)), "Comments/replies")
            table.add_row("Reposts", str(len(repost_items)), "Your repost actions")
            table.add_row("Likes", str(len(like_items)), "Your like actions")

            if pr_items:
                table.add_row("", "", "")
                table.add_row(
                    "Avg Engagement",
                    f"{avg_engagement:.1f}",
                    f"Across {len(pr_items)} posts/replies",
                )
                table.add_row(
                    "Avg Likes (posts/replies)",
                    f"{avg_likes:.1f}",
                    "Baseline for categories",
                )
                table.add_row(
                    "High Engagement",
                    str(len(high_engagement)),
                    f"{high_engagement_threshold}+ engagement score",
                )
                table.add_row("Dead Threads", str(len(dead_threads)), "0 engagement")

            console.print(table)

        elif mode == "full":
            # Full comprehensive statistics display
            title = f"Statistics for {data_file_name or 'Current Data'}"
            stats_table = Table(title=title)
            stats_table.add_column("Metric", style="bold")
            stats_table.add_column("Value", style="bright_white")
            stats_table.add_column("Details", style="dim")

            # Basic counts
            stats_table.add_row("Total Items", str(total_items), "Everything")
            stats_table.add_row("Posts", str(len(posts)), "Posts")
            stats_table.add_row("Replies", str(len(replies)), "Comments/replies")
            stats_table.add_row(
                "Reposts", str(len(repost_items)), "Your repost actions"
            )
            stats_table.add_row("Likes", str(len(like_items)), "Your like actions")

            # Engagement totals
            stats_table.add_row("", "", "")
            denom = max(1, len(pr_items))
            stats_table.add_row(
                "Total Likes",
                str(total_likes),
                f"Avg: {total_likes/denom:.1f} per post/reply",
            )
            stats_table.add_row(
                "Total Reposts (on posts)",
                str(total_reposts),
                f"Avg: {total_reposts/denom:.1f} per post/reply",
            )
            stats_table.add_row(
                "Total Replies",
                str(total_replies),
                f"Avg: {total_replies/denom:.1f} per post/reply",
            )
            stats_table.add_row(
                "Total Engagement",
                f"{int(total_engagement)}",
                f"Avg: {avg_engagement:.1f} per post/reply",
            )
            stats_table.add_row(
                "Avg Likes (posts/replies)",
                f"{avg_likes:.1f}",
                "Baseline for categories",
            )

            # Engagement analysis & categories
            stats_table.add_row("", "", "")
            stats_table.add_row(
                "High Engagement",
                str(len(high_engagement)),
                f"{high_engagement_threshold}+ engagement score",
            )

            # Likes-based categories (based on runtime avg) - only for posts, not replies
            avg_likes_runtime = (
                getattr(self.settings, "avg_likes_per_post", avg_likes) or avg_likes
            )
            # Clamp thresholds to sensible minimums when average is near zero
            half = max(0.0, avg_likes_runtime * 0.5)
            one_half = max(1.0, avg_likes_runtime * 1.5)
            double = max(1.0, avg_likes_runtime * 2.0)
            
            # Dead threads: posts and replies with 0 engagement
            cat_dead = [it for it in pr_items if (it.like_count or 0) == 0]
            
            # Performance categories: posts only
            posts_only = [it for it in pr_items if it.content_type == "post"]
            cat_bomber = [it for it in posts_only if 0 < (it.like_count or 0) <= half]
            cat_mid = [it for it in posts_only if half < (it.like_count or 0) <= one_half]
            cat_banger = [it for it in posts_only if (it.like_count or 0) >= double]
            cat_viral = [it for it in posts_only if (it.like_count or 0) >= 2000]
            stats_table.add_row("", "", "")
            stats_table.add_row("Dead Threads", str(len(cat_dead)), "0 likes")
            stats_table.add_row("Bombers (posts)", str(len(cat_bomber)), f"≤ {half:.1f} likes")
            stats_table.add_row(
                "Mid (posts)", str(len(cat_mid)), f"~ avg ({avg_likes_runtime:.1f})"
            )
            stats_table.add_row(
                "Bangers (posts)", str(len(cat_banger)), f"≥ {double:.1f} likes"
            )
            stats_table.add_row("Viral (posts)", str(len(cat_viral)), "≥ 2000 likes")

            console.print(stats_table)
            console.print()

    def display_search_results(self, items: List[ContentItem], limit: int = 10):
        """Display search results in a table."""
        if not items:
            console.print("No results to display")
            return

        console.print(f"Results (showing {min(len(items), limit)} of {len(items)})")
        console.print()

        table = Table(show_header=True)
        table.add_column("Type", style="cyan", width=6)
        table.add_column("Preview", style="white", width=40)
        table.add_column("Likes", style="red", width=4)
        table.add_column("Reposts", style="blue", width=4)
        table.add_column("Replies", style="yellow", width=4)
        table.add_column("Engagement", style="green", width=6)
        table.add_column("Date", style="dim", width=10)

        for item in items[:limit]:
            if item.content_type == "like":
                subj = (item.raw_data or {}).get("subject_uri")
                text_preview = f"Liked: {subj}" if subj else "Like"
            elif item.content_type == "repost":
                subj = (item.raw_data or {}).get("subject_uri")
                text_preview = f"Repost: {subj}" if subj else "Repost"
            else:
                text_preview = (
                    (item.text[:35] + "...")
                    if item.text and len(item.text) > 35
                    else (item.text or "")
                )

            created = item.created_at[:10] if item.created_at else ""

            if (
                item.content_type == "repost"
                and self.settings.use_subject_engagement_for_reposts
            ):
                subj_likes = (item.raw_data or {}).get("subject_like_count", 0)
                subj_reposts = (item.raw_data or {}).get("subject_repost_count", 0)
                subj_replies = (item.raw_data or {}).get("subject_reply_count", 0)
                eng = calculate_engagement_score(
                    int(subj_likes or 0), int(subj_reposts or 0), int(subj_replies or 0)
                )
                like_disp = str(subj_likes)
                repost_disp = str(subj_reposts)
                reply_disp = str(subj_replies)
                eng_disp = str(int(eng))
            else:
                like_disp = str(item.like_count)
                repost_disp = str(item.repost_count)
                reply_disp = str(item.reply_count)
                eng_disp = str(int(item.engagement_score))

            table.add_row(
                item.content_type,
                text_preview,
                like_disp,
                repost_disp,
                reply_disp,
                eng_disp,
                created,
            )

        console.print(table)

        if len(items) > limit:
            console.print()
            console.print(f"... and {len(items) - limit} more items")

    def display_single_item(self, item: ContentItem):
        """Display a single item with full details."""
        panel_content = []

        panel_content.append(f"[bold]Type:[/] {item.content_type}")
        panel_content.append(f"[bold]Created:[/] {item.created_at or 'Unknown'}")

        if (
            item.content_type == "repost"
            and self.settings.use_subject_engagement_for_reposts
        ):
            rd = item.raw_data or {}
            sl = rd.get("subject_like_count", 0)
            sr = rd.get("subject_repost_count", 0)
            srp = rd.get("subject_reply_count", 0)
            seng = calculate_engagement_score(int(sl or 0), int(sr or 0), int(srp or 0))
            panel_content.append(
                f"[bold]Subject Engagement:[/] Likes:{sl} Reposts:{sr} Replies:{srp} (Total: {int(seng)})"
            )
            subj = rd.get("subject_uri")
            if subj:
                panel_content.append(f"[bold]Subject:[/] {subj}")
        else:
            panel_content.append(
                f"[bold]Engagement:[/] Likes:{item.like_count} Reposts:{item.repost_count} Replies:{item.reply_count} (Total: {int(item.engagement_score)})"
            )

        panel_content.append("")

        if item.text:
            text_content = item.text[:200] + ("..." if len(item.text) > 200 else "")
            panel_content.append(f"[bold]Content:[/]")
            panel_content.append(text_content)
        else:
            panel_content.append("[dim]No text content[/]")

        console.print(
            Panel("\n".join(panel_content), title="Item Details", border_style="dim")
        )

    def select_categories_for_processing(
        self, default_selected: Optional[set] = None
    ) -> set:
        """Interactive toggle menu for categories to process (posts required; likes/reposts optional).

        Returns a set like {'posts','likes','reposts'} with 'posts' always included.
        """
        # Defaults: posts ON, likes/reposts OFF unless provided
        selected = {
            "posts": True,
            "likes": False,
            "reposts": False,
        }
        if default_selected:
            for key in ("posts", "likes", "reposts"):
                if key in default_selected:
                    selected[key] = True

        while True:
            console.print()
            console.print("Select categories to process from backup:")
            console.print()

            # Show current state with ASCII checkboxes (escape brackets for Rich)
            posts_check = "\\[x]" if selected["posts"] else "\\[ ]"
            likes_check = "\\[x]" if selected["likes"] else "\\[ ]"
            reposts_check = "\\[x]" if selected["reposts"] else "\\[ ]"

            console.print(f"  [1] {posts_check} Posts & Replies")
            console.print(f"  [2] {likes_check} Likes")
            console.print(f"  [3] {reposts_check} Reposts")
            console.print()
            console.print("  [Enter] Continue with selected categories")
            console.print()

            choice = Prompt.ask(
                "Toggle category (1/2/3) or press Enter to continue",
                choices=["1", "2", "3", ""],
                default="",
                show_choices=False,
            )

            if choice == "":
                # Ensure posts is always enabled
                if not selected["posts"]:
                    console.print(
                        "[yellow]Posts & replies are required; enabling automatically[/yellow]"
                    )
                    selected["posts"] = True

                # Show what will be processed
                selected_categories = [k for k, v in selected.items() if v]
                category_names = {
                    "posts": "Posts & Replies",
                    "likes": "Likes",
                    "reposts": "Reposts",
                }
                selected_names = [category_names[cat] for cat in selected_categories]
                console.print(f"Processing: {', '.join(selected_names)}")
                break
            elif choice == "1":
                # Posts can be toggled but will be re-enabled if turned off
                old_state = selected["posts"]
                selected["posts"] = not selected["posts"]
                if not selected["posts"]:
                    console.print(
                        "[yellow]Posts & Replies cannot be disabled (required)[/yellow]"
                    )
                    selected["posts"] = True
                else:
                    action = "enabled" if not old_state else "disabled"
                    console.print(f"Posts & Replies {action}")
            elif choice == "2":
                selected["likes"] = not selected["likes"]
                action = "enabled" if selected["likes"] else "disabled"
                console.print(f"Likes {action}")
            elif choice == "3":
                selected["reposts"] = not selected["reposts"]
                action = "enabled" if selected["reposts"] else "disabled"
                console.print(f"Reposts {action}")

        return {k for k, v in selected.items() if v}

    def show_file_picker(self, existing_files: List[Path]) -> Optional[Path]:
        """Show file picker and return selected file or None if cancelled."""
        if not existing_files:
            console.print("[dim]No files found[/]")
            return None

        console.print()
        console.print(Rule("[bright_cyan]Select Data File[/]", style="bright_cyan"))

        total = len(existing_files)
        if total <= 10:
            # Build choices for new prompt system
            file_choices = {}
            for idx, file_path in enumerate(existing_files, 1):
                stat = file_path.stat()
                size = f"{stat.st_size / 1024:.1f} KB"
                modified = datetime.fromtimestamp(stat.st_mtime).strftime(
                    "%Y-%m-%d %H:%M"
                )
                description = f"{file_path.name} [dim white]({size}, {modified})[/]"
                file_choices[str(idx)] = (file_path, description)

            # Add back option
            file_choices["b"] = (None, "Back")

            selected_path, action = self.prompt_with_choices(
                "Select file",
                choices=file_choices,
                default="b",
                context="file_selection",
                allow_navigation=False,  # Back is built into choices
            )

            if action == "back" or selected_path is None:
                return None
            return selected_path

        page_size = max(1, self.settings.file_list_page_size)
        page = 0

        while True:
            start = page * page_size
            end = min(start + page_size, total)
            page_files = list(enumerate(existing_files[start:end], start=start + 1))

            table = Table(show_header=True)
            table.add_column("#", style="bold", width=3)
            table.add_column("File", style="cyan")
            table.add_column("Size", style="dim", width=8)
            table.add_column("Modified", style="dim", width=16)

            for idx, file_path in page_files:
                stat = file_path.stat()
                size = f"{stat.st_size / 1024:.1f} KB"
                modified = datetime.fromtimestamp(stat.st_mtime).strftime(
                    "%Y-%m-%d %H:%M"
                )
                table.add_row(str(idx), file_path.name, size, modified)

            console.print(table)
            console.print(f"Page {page + 1} of {((total - 1) // page_size) + 1}")
            console.print()

            if page > 0:
                console.print("[p] Previous page")
            if end < total:
                console.print("[n] Next page")
            console.print()
            console.print("(b) Back")
            console.print()

            prompt_choices = ["n", "p", "b"] + [str(i) for i, _ in page_files]
            choice = Prompt.ask(
                "Select file # or navigate",
                choices=prompt_choices,
                default="b",
                show_choices=False,
            )

            if choice == "b":
                return None
            if choice == "n" and end < total:
                page += 1
                console.print()
                continue
            if choice == "p" and page > 0:
                page -= 1
                console.print()
                continue

            sel = int(choice)
            if 1 <= sel <= total:
                return existing_files[sel - 1]

    def select_deletion_mode(self, item_count: int) -> DeleteMode:
        """Select how to handle deletions."""
        console.print(
            Rule("[bright_red]Deletion Mode Selection[/]", style="bright_red")
        )

        mode_choices = {
            "1": (DeleteMode.ALL_AT_ONCE, f"Delete all {item_count} items at once"),
            "2": (DeleteMode.INDIVIDUAL, "Review and approve each item individually"),
            "3": (DeleteMode.BATCH, "Delete in batches (approve groups of items)"),
            "4": (DeleteMode.CANCEL, "Cancel deletion"),
        }

        mode, action = self.prompt_with_choices(
            "Select deletion mode",
            choices=mode_choices,
            default="4",  # Default to cancel for safety
            context="deletion_mode",
            allow_navigation=True,
        )

        if action == "back":
            return DeleteMode.CANCEL

        return mode

    def show_legend_help(self):
        """Display terminology and emoji legend."""
        console.print(Rule("Terminology & Legend", style="bright_blue"))
        console.print()

        legend = Table(show_header=False)
        legend.add_column("Symbol", style="bold", width=14)
        legend.add_column("Meaning", style="cyan")

        legend.add_row("Type", "post | reply | repost | like (content category)")
        legend.add_row("Preview", "Text snippet or subject URI for likes/reposts")
        legend.add_row("Likes", "Like count on the post/reply")
        legend.add_row("Reposts", "Repost count on the post/reply")
        legend.add_row("Replies", "Reply count on the post/reply")
        legend.add_row("Engagement", "Engagement = likes + 2×reposts + 2.5×replies")
        legend.add_row("Date", "Created date (UTC)")
        legend.add_row(
            "Repost rows", "Display subject post's counters (not your action's)"
        )
        legend.add_row(
            "Self-repost",
            "Your repost of your own post; counts toward the post's reposts",
        )

        console.print(legend)
        console.print()
        console.print("Notes:")
        console.print(
            "• Repost items show the subject's engagement. Your repost action has no counters."
        )
        console.print(
            "• Stats aggregate engagement only from posts/replies, not likes/reposts."
        )
        self.pause()

    def pause(self):
        """Pause for user to read output."""
        console.print()
        # Normalize pause behavior to use the unified navigation menu style
        while True:
            nav = self.pause_with_navigation(
                "menu", allow_help=False, allow_back=False, allow_main=False
            )
            if nav == "continue":
                break

    def pause_with_navigation(
        self,
        context: str = "menu",
        allow_help: bool = True,
        allow_back: bool = True,
        allow_main: bool = True,
    ) -> str:
        """Enhanced pause with navigation options.

        Returns:
            'continue' - normal continue
            'help' - user wants help
            'back' - user wants to go back
            'main' - user wants main menu
            'refresh' - user wants to refresh data
        """
        console.print()

        # Use key-driven options consistently (no Enter-based prompts)
        options = ["**c**ontinue"]
        choices = ["c"]

        if allow_help:
            options.append("**?** - Help")
            choices.append("?")

        if allow_back:
            options.append("**b**ack")
            choices.append("b")

        if allow_main:
            options.append("**m**ain menu")
            choices.append("m")

        # Add refresh option for data-related contexts
        if context in ["search", "stats", "results", "delete"]:
            options.append("**r**efresh data")
            choices.append("r")

        from rich.markdown import Markdown

        console.print(Markdown(f"*{' | '.join(options)}*"))

        choice = Prompt.ask("", choices=choices, default="c", show_choices=False)

        if choice == "?":
            return "help"
        elif choice == "b":
            return "back"
        elif choice == "m":
            return "main"
        elif choice == "r":
            return "refresh"
        else:
            return "continue"

    def input_with_navigation(
        self,
        prompt: str,
        password: bool = False,
        context: str = "input",
        allow_help: bool = True,
        allow_back: bool = True,
    ) -> tuple[str, str]:
        """Input with navigation options.

        Returns:
            (value, action) where action is 'continue', 'back', 'main', or 'help'
        """
        while True:
            console.print(prompt, style="bold", end="")

            if password:
                value = console.input(password=True)
            else:
                value = console.input()

            if value.strip():
                return value, "continue"

            # If empty input, show navigation options
            nav_choice = self.pause_with_navigation(
                context, allow_help=allow_help, allow_back=allow_back, allow_main=True
            )

            if nav_choice == "help":
                # Show context-appropriate help
                if context == "handle":
                    console.print("\n**Handle Help**")
                    console.print("Enter your Bluesky handle (username):")
                    console.print("• With @: @username.bsky.social")
                    console.print("• Without @: username.bsky.social")
                    console.print("• Both formats work the same way")
                elif context == "password":
                    console.print("\n**Password Help**")
                    console.print("Use your Bluesky App Password.")
                    console.print("• Create in Bluesky Settings → App Passwords")
                    console.print("• Your password is not stored (session only)")
                else:
                    console.print(f"\n**{context.title()} Help**")
                    console.print(
                        "Enter the requested information, or use navigation options."
                    )
                continue
            elif nav_choice in ["back", "main"]:
                return "", nav_choice
            else:
                # Continue - show prompt again
                continue

    def show_system_info(self):
        """Deprecated: previously showed a system overview screen."""
        # Intentionally left as a no-op; retained for backward compatibility
        return

    def show_help_text(self, help_text: str):
        """Display formatted help text."""
        console.print(Markdown(help_text))
        nav_choice = self.pause_with_navigation(
            "help", allow_back=True, allow_main=True, allow_help=False
        )
        return nav_choice

    # ========== NEW UNIFIED PROMPT METHODS ==========

    def prompt_with_choices(
        self,
        prompt: str,
        choices: Dict[str, Tuple[str, str]],
        default: str = None,
        context: str = "menu",
        show_choices: bool = True,
        allow_navigation: bool = True,
    ) -> Tuple[str, str]:
        """
        Standardized choice prompt with navigation support.

        Args:
            prompt: The prompt text to display
            choices: Dict of {key: (value, description)}
            default: Default choice key
            context: Context for help system
            show_choices: Whether to display choices above prompt
            allow_navigation: Whether to allow back/main/help navigation

        Returns:
            (selected_value, action) where action is 'continue', 'back', 'main', or 'help'
        """
        while True:
            if show_choices:
                console.print()

                # Separate numbered and lettered options
                numbered_choices = {k: v for k, v in choices.items() if k.isdigit()}
                lettered_choices = {k: v for k, v in choices.items() if not k.isdigit()}

                # Display numbered options first
                for key, (_, description) in numbered_choices.items():
                    console.print(f"  [bold white]\\[{key}][/] {description}")

                # Add visual gap if we have both numbered and lettered options
                if numbered_choices and lettered_choices:
                    console.print()

                # Display lettered options
                for key, (_, description) in lettered_choices.items():
                    console.print(f"  [yellow]\\[{key}][/] {description}")

                console.print()

            # Build choice list including navigation options
            valid_choices = list(choices.keys())
            nav_options = []

            if allow_navigation:
                if context != "main_menu":  # Don't show back on main menu
                    nav_options.append("b")
                    console.print("  [yellow]\\[b][/] Back")
                if context not in ["main_menu", "help"]:
                    nav_options.append("?")
                    console.print("  [yellow]\\[?][/] Help")
                if nav_options:
                    console.print()

            # Use Rich's Prompt.ask with our choices
            choice = Prompt.ask(
                f"[bold white]{prompt}[/]",
                choices=valid_choices + nav_options,
                default=default,
                show_choices=False,
            )

            # Handle navigation choices
            if allow_navigation:
                if choice == "b" and "b" in nav_options:
                    return "", "back"
                elif choice == "?":
                    self._show_context_help(context)
                    continue  # Redisplay prompt

            # Return the selected value and continue action
            if choice in choices:
                return choices[choice][0], "continue"

            # Should not reach here with Prompt validation
            console.print("[red]Invalid choice[/]")

    def prompt_text(
        self,
        prompt: str,
        default: str = "",
        context: str = "input",
        validation_fn=None,
        password: bool = False,
        allow_navigation: bool = True,
    ) -> Tuple[str, str]:
        """
        Standardized text input with navigation support.

        Args:
            prompt: The prompt text (should end with : for inputs)
            default: Default value to show
            context: Context for help system
            validation_fn: Optional validation function that returns (is_valid, error_msg)
            password: Whether to mask input
            allow_navigation: Whether to allow back/main/help navigation

        Returns:
            (input_value, action) where action is 'continue', 'back', 'main', or 'help'
        """
        while True:
            # Use existing input_with_navigation if available, otherwise implement
            if password:
                if allow_navigation and hasattr(self, "input_with_navigation"):
                    value, action = self.input_with_navigation(
                        prompt, password=True, context=context
                    )
                    if action in ["back", "main"]:
                        return "", action
                else:
                    value = Prompt.ask(
                        f"[bold white]{prompt.rstrip()}[/] ",
                        password=True,
                        default=default,
                    )
                    action = "continue"
            else:
                if allow_navigation and hasattr(self, "input_with_navigation"):
                    value, action = self.input_with_navigation(prompt, context=context)
                    if action in ["back", "main"]:
                        return "", action
                else:
                    value = Prompt.ask(
                        f"[bold white]{prompt.rstrip()}[/] ", default=default
                    )
                    action = "continue"

            # Validate if function provided
            if validation_fn and value:
                is_valid, error_msg = validation_fn(value)
                if not is_valid:
                    console.print(f"[red]{error_msg}[/]")
                    continue

            return value, action

    def prompt_confirm(
        self,
        prompt: str,
        default: bool = False,
        context: str = "confirm",
        allow_navigation: bool = True,
    ) -> Tuple[bool, str]:
        """
        Standardized yes/no confirmation with navigation support.

        Args:
            prompt: The question to ask (should end with ?)
            default: Default value (True/False)
            context: Context for help system
            allow_navigation: Whether to allow back/main/help navigation

        Returns:
            (bool_value, action) where action is 'continue', 'back', 'main', or 'help'
        """
        while True:
            # Add navigation hint if allowed
            nav_hint = ""
            if allow_navigation and context != "main_menu":
                nav_hint = " [dim blue](or b=back, ?=help)[/]"

            # Show the confirm prompt
            response = Prompt.ask(
                f"[bold white]{prompt}[/]{nav_hint}",
                choices=["y", "n"] + (["b", "?"] if allow_navigation else []),
                default="y" if default else "n",
                show_choices=False,
            )

            # Handle navigation
            if allow_navigation:
                if response == "b":
                    return False, "back"
                elif response == "?":
                    self._show_context_help(context)
                    continue

            # Return boolean result
            return response == "y", "continue"

    def prompt_integer(
        self,
        prompt: str,
        default: int = None,
        min_val: int = None,
        max_val: int = None,
        context: str = "number",
        allow_navigation: bool = True,
    ) -> Tuple[int, str]:
        """
        Standardized integer input with validation and navigation.

        Args:
            prompt: The prompt text
            default: Default value
            min_val: Minimum allowed value
            max_val: Maximum allowed value
            context: Context for help system
            allow_navigation: Whether to allow back/main/help navigation

        Returns:
            (int_value, action) where action is 'continue', 'back', 'main', or 'help'
        """
        while True:
            # Get text input first
            value_str, action = self.prompt_text(
                prompt,
                default=str(default) if default is not None else "",
                context=context,
                allow_navigation=allow_navigation,
            )

            if action in ["back", "main"]:
                return 0, action

            # Try to convert to integer
            try:
                value = int(value_str)

                # Validate range
                if min_val is not None and value < min_val:
                    console.print(f"[red]Value must be at least {min_val}[/]")
                    continue
                if max_val is not None and value > max_val:
                    console.print(f"[red]Value must be at most {max_val}[/]")
                    continue

                return value, "continue"

            except ValueError:
                console.print(f"[red]Please enter a valid number[/]")
                continue

    def _show_context_help(self, context: str):
        """Show context-sensitive help for the current prompt."""
        help_texts = {
            "main_menu": "Select an option by entering its number or letter. Common options include search (1), stats (2), and settings (s).",
            "content_type": "Choose what type of content to search for. 'All' includes everything, or select specific types.",
            "keywords": "Enter words to search for in your content. Use commas to separate multiple keywords.",
            "batch_size": "Choose how many items to process at once. Larger batches are faster but show less detail.",
            "handle": "Enter your Bluesky username. You can include or omit the @ symbol.",
            "password": "Enter your Bluesky App Password (create in Bluesky Settings).",
            "delete_confirm": "This action will permanently delete files. Make sure you have backups if needed.",
            "download_limit": "Set how many items to download per category. Higher numbers take longer but get more data.",
            "file_selection": "Choose a file by entering its number. Use 'b' to go back without selecting.",
            "settings_menu": "Select a setting to modify by entering its number, or use 'b' to go back.",
        }

        help_text = help_texts.get(context, f"Help for {context}")
        console.print()
        console.print(
            Panel(help_text, title="[bright_blue]Help[/]", border_style="bright_blue")
        )
        console.print()

        # Pause to let user read
        Prompt.ask("[dim]Press Enter to continue[/]", show_choices=False)
