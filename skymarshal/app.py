"""
Skymarshal Main Application Controller

File Purpose: Primary application orchestration and interactive workflow management
Primary Functions/Classes: InteractiveContentManager, interactive commands
Inputs and Outputs (I/O): User interactions, file operations, API calls, Rich console output

This module serves as the main application controller, orchestrating all components including
authentication, data management, search operations, deletion workflows, and interactive commands.
It provides an interactive interface for comprehensive Bluesky content management.
"""

import json
from pathlib import Path
from typing import List, Optional

from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.rule import Rule

from .auth import AuthManager
from .banner import show_banner
from .data_manager import DataManager
from .deletion import DeletionManager
from .help import HelpManager
from .models import (
    ContentItem,
    DeleteMode,
    SearchFilters,
    console,
    parse_datetime,
)
from .search import SearchManager
from .settings import SettingsManager
from .ui import UIManager


class InteractiveContentManager:
    """Interactive tool for Bluesky content management."""

    def __init__(self):
        self.skymarshal_dir = Path.home() / ".skymarshal"
        self.backups_dir = self.skymarshal_dir / "backups"
        self.json_dir = self.skymarshal_dir / "json"

        self.skymarshal_dir.mkdir(exist_ok=True)
        self.backups_dir.mkdir(exist_ok=True)
        self.json_dir.mkdir(exist_ok=True)

        self.settings_file = Path.home() / ".car_inspector_settings.json"
        self.settings_manager = SettingsManager(self.settings_file)

        self.ui = UIManager(self.settings_manager.settings)
        self.auth = AuthManager(self.ui)
        self.data_manager = DataManager(
            self.auth,
            self.settings_manager.settings,
            self.skymarshal_dir,
            self.backups_dir,
            self.json_dir,
        )
        self.search_manager = SearchManager(self.auth, self.settings_manager.settings)
        self.deletion_manager = DeletionManager(
            self.auth, self.settings_manager.settings
        )
        self.help_manager = HelpManager(self.ui)

        self.current_data: List[ContentItem] = []
        self.current_data_file: Optional[Path] = None

    def handle_navigation_choice(self, nav_choice: str, context: str = "menu") -> str:
        """Handle navigation choice and return action.

        Returns:
            'continue' - stay in current screen
            'back' - go back one screen
            'main' - go to main menu
        """
        if nav_choice == "help":
            if context == "search":
                self.help_manager._show_search_help()
            elif context == "stats":
                self.help_manager._show_stats_help()
            elif context == "delete":
                self.help_manager._show_deletion_help()
            else:
                self.help_manager.show_help()

            # After help, we need to signal that the caller should redisplay content
            return "redisplay"
        elif nav_choice == "main":
            return "main"
        elif nav_choice == "refresh":
            console.print("Refreshing data...")
            if self.refresh_current_data():
                console.print("Data refreshed successfully.")
            else:
                console.print("Failed to refresh data")
            return "continue"
        elif nav_choice == "back":
            return "back"
        else:
            return "continue"

    def refresh_current_data(self) -> bool:
        """Refresh the current data by re-downloading and processing."""
        if not self.auth.current_handle:
            console.print("No authenticated user to refresh data for")
            return False

        try:
            # Download fresh backup and process it
            handle = self.auth.current_handle
            console.print(f"Downloading fresh backup for @{handle}...")
            backup_path = self.data_manager.download_backup(handle)
            if not backup_path:
                return False

            console.print("Processing backup...")
            # Replace existing data with fresh backup results to reflect current account state
            json_path = self.data_manager.import_backup_replace(backup_path, handle)
            if not json_path:
                return False

            # Load the fresh data
            return self.load_data_with_stats_and_navigation(json_path, "refresh")
        except Exception as e:
            console.print(f"Error refreshing data: {e}")
            return False

    def _clear_for_flow(self, title: str = None):
        """Clear the terminal and optionally show the banner and a section title."""
        try:
            console.clear()
        except Exception:
            pass
        show_banner()
        if title:
            console.print(Rule(title, style="dim"))

    def handle_authentication(self):
        """Handle authentication flow."""
        console.print(Rule("Authentication", style="bright_green"))
        console.print()

        if self.auth.is_authenticated():
            console.print("Logged in.")
            # console.print(f"👤 Handle: @{self.auth.current_handle}")
            # console.print(f"🆔 DID: {self.auth.current_did}")
            console.print()

            switch, switch_action = self.ui.prompt_confirm(
                "Switch accounts?", default=False, context="switch_accounts"
            )
            if switch_action == "back":
                return
            if switch:
                self.perform_login(force_new_login=True)
            else:
                console.print("Continuing with current session")
        else:
            # Require successful login here and re-prompt on failure
            while True:
                console.print("Authentication required")
                console.print()
                self.perform_login()
                if self.auth.is_authenticated():
                    break
                console.print("Authentication failed", style="red")
                retry, retry_action = self.ui.prompt_confirm(
                    "Try again?", default=True, context="retry_auth"
                )
                if retry_action == "back" or not retry:
                    return

        while True:
            nav_choice = self.ui.pause_with_navigation(
                "menu", allow_help=True, allow_back=True, allow_main=True
            )
            if nav_choice == "continue":
                break
            elif nav_choice in ["back", "main"]:
                return
            elif nav_choice == "help":
                self.help_manager.show_auth_help()

    def perform_login(self, force_new_login: bool = False):
        """Perform login process."""
        if force_new_login:
            # Clear existing authentication to force fresh login
            self.auth.logout()

        if self.auth.ensure_authentication():
            console.print(f"Logged in as @{self.auth.current_handle}.")
        else:
            # Silent here; outer flows will show a single concise failure
            pass

    def handle_data_management(self):
        """Handle data file management."""
        console.print(
            Rule("[bright_magenta]Data Management[/]", style="bright_magenta")
        )
        console.print()
        console.print("[dim]💡 Tip: API downloads provide complete engagement data (likes, reposts, replies)[/]")
        console.print("[dim]   CAR files are best used as backups for data preservation[/]")
        console.print()

        data_choices = {
            "1": ("download", "Download data from Bluesky API (recommended)"),
            "2": ("load", "Load previously saved data file"),
            "3": ("refresh", "Refresh engagement data for loaded content"),
            "4": ("backup_create", "Create backup (.car file) for data preservation"),
            "5": ("process", "Import from backup file (.car) - may lack engagement data"),
            "6": ("timestamp", "Create timestamped backup"),
            "7": ("clear", "Clear local data and backups"),
            "b": ("back", "Back to main menu"),
        }

        choice, action = self.ui.prompt_with_choices(
            "Data Management",
            choices=data_choices,
            default="1",
            context="data_management",
            allow_navigation=False,  # Back is built into choices
        )

        if choice == "download":
            # Primary option: Download fresh data from API
            result = self.download_data_flow()
            if result:
                return
        elif choice == "load":
            # Only show files belonging to current user
            existing_files = self.data_manager.get_user_files(
                self.auth.current_handle, "json"
            )
            if self._select_existing_file_with_navigation(existing_files):
                return
        elif choice == "refresh":
            # Refresh engagement data for currently loaded content
            if not self.current_data:
                console.print("[yellow]No data loaded to refresh[/]")
                console.print("Load some data first, then use this option to update engagement metrics")
            else:
                console.print(f"Refreshing engagement data for {len(self.current_data)} items...")
                try:
                    self.data_manager.hydrate_items(self.current_data)
                    console.print("[green]✓[/] Engagement data refreshed")
                except Exception as e:
                    console.print(f"[yellow]Warning: Refresh partially failed: {e}[/]")
        elif choice == "backup_create":
            # Create backup file for data preservation
            if self.auth.current_handle:
                handle = self.auth.current_handle
            else:
                while True:
                    handle, action = self.ui.input_with_navigation(
                        "Enter your handle for backup: @", context="handle"
                    )
                    if action in ["back", "main"]:
                        return
                    if handle:
                        handle = self.auth.normalize_handle(handle)
                        break
                    console.print("Handle is required")
            console.print("[yellow]Creating backup file...[/]")
            backup_path = self.data_manager.download_backup(handle)
            if backup_path:
                console.print(f"[green]✓[/] Backup saved: {backup_path.name}")
            else:
                console.print("[red]Backup failed[/]")
        elif choice == "process":
            # Import from backup - show warning about engagement data
            console.print("[yellow]⚠️  Warning: CAR file imports may have incomplete engagement data[/]")
            console.print("[yellow]   Consider downloading fresh API data instead for complete metrics[/]")
            console.print()
            if Confirm.ask("Continue with backup import?", default=False):
                self.import_backup_flow()
        elif choice == "timestamp":
            if self.auth.current_handle:
                handle = self.auth.current_handle
            else:
                handle, handle_action = self.ui.prompt_text(
                    "Handle to create backup for: @",
                    default="",
                    context="handle",
                )
                if handle_action == "back":
                    return
                if not handle:
                    console.print("Handle is required")
                    return
                handle = self.auth.normalize_handle(handle)
            self.data_manager.create_timestamped_backup(handle)
        elif choice == "clear":
            # Clear local data for current or entered handle
            if self.auth.current_handle:
                handle = self.auth.current_handle
            else:
                handle, action = self.ui.input_with_navigation(
                    "Handle to clear data for: @", context="handle"
                )
                if action in ["back", "main"]:
                    return
            handle = self.auth.normalize_handle(handle)
            console.print(
                Panel(
                    f"This will delete local data and backup files for @{handle}",
                    title="[red]Clear Local Data[/]",
                    border_style="red",
                )
            )
            proceed, confirm_action = self.ui.prompt_confirm(
                "Proceed with deleting files?",
                default=False,
                context="delete_confirm",
            )
            if confirm_action == "back":
                return
            if proceed:
                deleted = self.data_manager.clear_local_data(handle)
                if deleted:
                    console.print(f"Deleted {deleted} file(s)")
                    # Reset in-memory data if we just removed the loaded file
                    if (
                        self.current_data_file
                        and self.current_data_file.name.startswith(
                            handle.replace(".", "_")
                        )
                    ):
                        self.current_data = []
                        self.current_data_file = None
                else:
                    console.print("[dim]No files found to delete[/dim]")

    def _get_download_options(self):
        """Get backup options (consolidated function for both startup and main flows)."""
        # Allow any positive integer, or blank for "all"
        def _validate_limit(value: str):
            if value.strip() == "":
                return True, ""
            try:
                iv = int(value)
                if iv < 1:
                    return False, "Value must be at least 1"
                return True, ""
            except ValueError:
                return False, "Please enter a number or press Enter for all"

        value, limit_action = self.ui.prompt_text(
            "Number of items per category to backup: ",
            default="",
            context="download_limit",
            validation_fn=_validate_limit,
            allow_navigation=True,
        )
        if limit_action == "back":
            return None

        # Interpret blank as "all" with a very large cap to avoid None plumbing
        limit = 1_000_000_000 if value.strip() == "" else int(value)

        console.print("[dim]Will collect data in chunks for efficiency[/dim]")
        console.print()

        # Use the existing category selection method
        categories = self.ui.select_categories_for_processing()

        # Date range option
        use_date_range, date_action = self.ui.prompt_confirm(
            "Limit by date range?", default=False, context="date_range"
        )
        if date_action == "back":
            return None

        date_start = date_end = None
        if use_date_range:
            console.print("[bright_cyan]Date Range (YYYY-MM-DD or ISO8601)[/]")
            ds, ds_action = self.ui.prompt_text(
                "Start date:", default="", context="date_input"
            )
            if ds_action == "back":
                return None
            de, de_action = self.ui.prompt_text(
                "End date:", default="", context="date_input"
            )
            if de_action == "back":
                return None
            date_start = ds or None
            date_end = de or None

        return limit, categories, date_start, date_end

    def download_data_flow(self):
        """Handle fresh backup creation flow."""
        if not self.auth.is_authenticated():
            console.print("You need to be authenticated to create a backup")
            console.print("Go to Authentication menu first")
            return False

        console.print()
        console.print("Create Fresh Backup")
        console.print()

        # Use authenticated handle automatically
        handle = self.auth.current_handle
        if not handle:
            console.print("No authenticated handle found")
            return False

        console.print(f"Creating backup for authenticated user: @{handle}")

        # Get backup options using consolidated function
        download_options = self._get_download_options()
        if not download_options:
            return False

        limit, categories, date_start, date_end = download_options

        console.print("[yellow]Re-authentication required for API access[/]")
        password, password_action = self.ui.prompt_text(
            "App Password: ", password=True, context="password"
        )
        if password_action == "back":
            return False

        try:
            console.print()
            console.print("[bold cyan]Step 1:[/] Authenticating...")
            if not self.auth.authenticate_client(handle, password):
                console.print("[red]Authentication failed[/]")
                return False
            console.print("[green]✓[/] Authentication successful")
            
            console.print()
            console.print("[bold cyan]Step 2:[/] Downloading data from Bluesky...")
            export_path = self.data_manager.export_user_data(
                handle,
                limit,
                categories=categories,
                date_start=date_start,
                date_end=date_end,
                replace_existing=True,
            )
        except Exception as e:
            console.print(f"[red]Download error:[/] {e}")
            return False

        # Handle results
        if export_path:
            console.print()
            console.print(f"[green]✓[/] Data downloaded successfully: [cyan]{export_path.name}[/]")
            console.print()

            if self.load_data_with_stats_and_navigation(export_path, "data download"):
                return True
            return False
        else:
            console.print("[red]Download failed[/]")
            return False

    def download_backup_flow(self):
        """Create a complete backup file for a handle."""
        handle = Prompt.ask(
            "Handle to create complete backup for: @",
            default=self.auth.current_handle or "",
        )
        if not handle:
            console.print("Handle is required")
            return
        self.data_manager.download_backup(handle)

    def import_backup_flow(self):
        """Process existing backup files into readable format."""
        console.print("[yellow]⚠️  Backup Import Information:[/]")
        console.print("• Backup files preserve your content but may have zero engagement counts")
        console.print("• After importing, use 'Refresh engagement data' to get current metrics")
        console.print("• For best results, consider downloading fresh API data instead")
        console.print()
        
        # Only show backup files belonging to current user
        backup_files = self.data_manager.get_user_files(self.auth.current_handle, "backup")
        if not backup_files:
            console.print(f"No backup files found for @{self.auth.current_handle}")
            return

        console.print("Select backup to import:")
        selected_backup = self.ui.show_file_picker(backup_files)
        if selected_backup:
            console.print("Importing backup file...")
            imported_path = self.data_manager.import_backup_merge(selected_backup, self.auth.current_handle)
            if imported_path:
                console.print(f"[green]✓[/] Backup imported: {imported_path.name}")
                console.print("[dim]Tip: Use 'Refresh engagement data' to update likes/reposts/replies[/]")
            else:
                console.print("[red]Failed to import backup[/]")

    def handle_search_analyze(self):
        """Handle search, analyze, and manage content flow."""
        self._clear_for_flow("Find & Manage Content")

        if not self.current_data:
            console.print("No data loaded")
            console.print()
            if Confirm.ask("Do you want to load data first?"):
                self.handle_data_management()
                if not self.current_data:
                    return
            else:
                return

        while True:
            filters = self.search_manager.build_search_filters(self.ui)
            if filters is None:
                return  # User cancelled or asked for help

            with console.status("Searching..."):
                filtered_items = self.search_manager.search_content_with_filters(
                    self.current_data, filters
                )

            console.print()
            console.print(f"Found [bold green]{len(filtered_items)}[/] matching items")
            console.print()

            if not filtered_items:
                console.print("No items match your criteria")
                if Confirm.ask("Adjust filters and search again?", default=True):
                    continue
                else:
                    return

            if filtered_items:
                sort_opts = self.search_manager.get_sort_options()
                console.print("Sort by:")
                for k, (label, _) in sort_opts.items():
                    console.print(f"  [{k}] {label}")

                default_sort = (
                    "1"
                    if self.settings_manager.settings.fetch_order == "newest"
                    else "2"
                )
                chosen = Prompt.ask(
                    "Choose sort", choices=list(sort_opts.keys()), default=default_sort
                )
                _, mode = sort_opts[chosen]

                filtered_items = self.search_manager.sort_results(filtered_items, mode)

            # Display results table first, then menu options
            self.ui.display_search_results(filtered_items)
            console.print()
            self.handle_post_search_options(filtered_items, filters)
            break

    def handle_post_search_options(
        self, filtered_items: List[ContentItem], filters: SearchFilters
    ):
        """Handle options after search results."""
        console.print()
        console.print(Rule("[dim]Search Results Options[/]", style="dim"))

        result_choices = {
            "1": ("show_all", "Show all results - Display all matching items"),
            "2": ("export", "Export results - Save to JSON/CSV file"),
            "3": ("delete", "Delete results - Delete the matching items"),
            "4": ("refine", "Refine search - Modify search filters"),
            "5": ("legend", "Terminology legend - What the columns mean"),
            "6": ("back", "Back to menu - Return to main menu"),
        }

        choice, action = self.ui.prompt_with_choices(
            "Select option",
            choices=result_choices,
            default="1",
            context="search_results",
            allow_navigation=False,  # Back is built into choices
        )

        if choice == "show_all":
            self.ui.display_search_results(filtered_items, limit=len(filtered_items))
            while True:
                nav_choice = self.ui.pause_with_navigation("results")
                if nav_choice == "continue":
                    break
                else:
                    action = self.handle_navigation_choice(nav_choice, "search")
                    if action in ["back", "main"]:
                        return
                    elif action == "redisplay":
                        # Redisplay search results after help
                        self.ui.display_search_results(
                            filtered_items, limit=len(filtered_items)
                        )
        elif choice == "export":
            self.export_results(filtered_items)
        elif choice == "delete":
            self.handle_delete_content(filtered_items)
        elif choice == "refine":
            new_filters = self.search_manager.build_search_filters(self.ui)
            if new_filters is None:
                return  # User cancelled, return to previous menu

            with console.status("Searching..."):
                new_results = self.search_manager.search_content_with_filters(
                    self.current_data, new_filters
                )
            console.print(
                f"[bright_cyan]Found {len(new_results)} items with new filters[/]"
            )
            if new_results:
                self.ui.display_search_results(new_results)
                self.handle_post_search_options(new_results, new_filters)
        elif choice == "legend":
            self.ui.show_legend_help()
        elif choice == "back":
            return

    def handle_delete_content(self, items: List[ContentItem] = None):
        """Handle content deletion flow."""
        console.print(Rule("Delete Content", style="bright_red"))
        console.print()

        if items is None:
            if not self.current_data:
                console.print("No data loaded")
                if Confirm.ask("Load data first?"):
                    self.handle_data_management()
                    if not self.current_data:
                        return
                else:
                    return

            console.print("First, let's find what to delete")
            console.print()
            filters = self.search_manager.build_search_filters(self.ui)
            if filters is None:
                return  # User cancelled

            with console.status("Searching for items to delete..."):
                items = self.search_manager.search_content_with_filters(
                    self.current_data, filters
                )

            if not items:
                console.print("No items match your criteria")
                while True:
                    nav_choice = self.ui.pause_with_navigation("search")
                    if nav_choice == "continue":
                        return
                    else:
                        action = self.handle_navigation_choice(nav_choice, "search")
                        if action in ["back", "main"]:
                            return

        console.print(f"Found [bold red]{len(items)}[/] items to potentially delete")
        console.print()

        self.ui.display_search_results(items, limit=5)
        console.print()

        mode = self.ui.select_deletion_mode(len(items))

        if mode == DeleteMode.CANCEL:
            console.print("Deletion cancelled")
            return

        self.execute_deletion(items, mode)

    def execute_deletion(self, items: List[ContentItem], mode: DeleteMode):
        """Execute deletion with the selected mode."""
        if mode == DeleteMode.ALL_AT_ONCE:
            self.deletion_manager.delete_all_at_once(
                items, self.ui.display_search_results
            )
        elif mode == DeleteMode.INDIVIDUAL:
            self.deletion_manager.delete_individual_approval(
                items, self.ui.display_single_item
            )
        elif mode == DeleteMode.BATCH:
            self.deletion_manager.delete_batch_approval(
                items, self.ui.display_search_results
            )

    def handle_quick_stats(self):
        """Show quick statistics."""
        console.print(Rule("Quick Stats", style="bright_cyan"))
        console.print()

        if not self.current_data:
            console.print("No data loaded")
            if Confirm.ask("Load data first?"):
                self.handle_data_management()
                if not self.current_data:
                    return
            else:
                return

        # Use UIManager's unified statistics display
        data_file_name = self.current_data_file.name if self.current_data_file else None
        high_engagement_threshold = (
            self.settings_manager.settings.high_engagement_threshold
        )
        self.ui.display_stats(
            self.current_data,
            mode="full",
            data_file_name=data_file_name,
            high_engagement_threshold=high_engagement_threshold,
        )

        while True:
            nav_choice = self.ui.pause_with_navigation("stats")
            if nav_choice == "continue":
                break
            elif nav_choice == "refresh":
                if self.refresh_current_data():
                    console.print("Data refreshed successfully.")
                    # Redisplay stats with fresh data
                    self.ui.display_stats(
                        self.current_data,
                        mode="full",
                        data_file_name=data_file_name,
                        high_engagement_threshold=high_engagement_threshold,
                    )
                else:
                    console.print("Failed to refresh data")
            else:
                action = self.handle_navigation_choice(nav_choice, "stats")
                if action in ["back", "main"]:
                    return
                elif action == "redisplay":
                    # Redisplay stats after help
                    data_file_name = (
                        self.current_data_file.name if self.current_data_file else None
                    )
                    high_engagement_threshold = (
                        self.settings_manager.settings.high_engagement_threshold
                    )
                    self.ui.display_stats(
                        self.current_data,
                        mode="full",
                        data_file_name=data_file_name,
                        high_engagement_threshold=high_engagement_threshold,
                    )

        self._handle_quick_actions()

    def handle_nuke(self):
        """Interactive nuclear delete with multiple confirmations."""
        console.print(
            Panel(
                "WARNING: Delete ALL content (posts, likes, reposts)",
                title="NUKE",
                border_style="bright_red",
            )
        )

        valid = {
            "post": "app.bsky.feed.post",
            "like": "app.bsky.feed.like",
            "repost": "app.bsky.feed.repost",
        }
        console.print("Collections to delete (comma-separated): post, like, repost")
        inc = Prompt.ask("Include", default="post,like,repost")
        includes = {
            s.strip().lower() for s in inc.split(",") if s.strip().lower() in valid
        }

        if not includes:
            console.print("No valid collections selected")
            return

        if self.auth.current_handle:
            handle = self.auth.current_handle
        else:
            handle, action = self.ui.input_with_navigation(
                "Your handle: @", context="handle"
            )
            if action in ["back", "main"]:
                return

        if Confirm.ask("Create backup before deleting?", default=True):
            try:
                self.data_manager.create_timestamped_backup(handle)
            except Exception:
                console.print("[yellow]Backup failed or skipped[/yellow]")

        phrase = f"DELETE ALL {handle}"
        console.print(f"Type to confirm: [bold]{phrase}[/bold]")
        entered = Prompt.ask("Confirmation phrase")
        if entered != phrase:
            console.print("Confirmation failed. Aborting.")
            return

        entered_handle, action = self.ui.input_with_navigation(
            "Re-type your handle to confirm: @", context="handle"
        )
        if action in ["back", "main"]:
            return
        if entered_handle.strip().lower() != handle.strip().lower():
            console.print("Handle mismatch. Aborting.")
            return

        agree = Prompt.ask("Type 'I UNDERSTAND' to proceed", default="")
        if agree.strip() != "I UNDERSTAND":
            console.print("Confirmation failed. Aborting.")
            return

        if not Confirm.ask(
            "Final confirmation — proceed with nuclear delete?", default=False
        ):
            console.print("Cancelled")
            return

        total_deleted = 0
        total_matched = 0
        for key in includes:
            coll = valid[key]
            deleted, matched = self.deletion_manager.bulk_remove_by_collection(
                coll, dry_run=False
            )
            total_deleted += deleted
            total_matched += matched
            console.print(f"• {coll}: matched {matched} (deleted {deleted})")

        console.print(
            f"Nuclear delete complete. Deleted {total_deleted} records (matched {total_matched})."
        )
        while True:
            nav_choice = self.ui.pause_with_navigation("delete")
            if nav_choice == "continue":
                break
            else:
                action = self.handle_navigation_choice(nav_choice, "delete")
                if action in ["back", "main"]:
                    break

    def handle_startup_flow(self):
        """Handle startup flow with authentication-first approach."""
        # console.print("Welcome to Skymarshal!")
        # console.print()

        if not self.validate_and_ensure_authentication():
            console.print("Authentication required to continue")
            return False

        # Only show files belonging to the current authenticated user
        current_handle = self.auth.current_handle
        existing_json_files = self.data_manager.get_user_files(current_handle, "json")
        existing_backup_files = self.data_manager.get_user_files(current_handle, "backup")

        # console.print(f"Found {len(existing_json_files)} JSON file(s) and {len(existing_car_files)} CAR file(s)")
        # console.print()

        if not existing_json_files and not existing_backup_files:
            return self._handle_no_data_scenario()
        elif existing_json_files and not existing_backup_files:
            return self._handle_json_only_scenario(existing_json_files)
        elif not existing_json_files and existing_backup_files:
            return self._handle_backup_only_scenario(existing_backup_files)
        else:
            return self._handle_mixed_data_scenario(
                existing_json_files, existing_backup_files
            )

    def validate_and_ensure_authentication(self):
        """Always require fresh authentication on startup, re-prompting on failure."""
        return self.auth.validate_and_ensure_authentication_with_retry()

    def load_data_with_stats_and_navigation(
        self, file_path: Path, source_context: str = "loading"
    ) -> bool:
        """Load data, show stats, and handle navigation options."""
        # Validate file access before loading
        if not self.data_manager.validate_file_access(
            file_path, self.auth.current_handle
        ):
            return False

        try:
            # Provide user feedback while reading the data file
            with console.status("Loading data file..."):
                self.current_data = self.data_manager.load_exported_data(file_path)
            # Validate auth and update engagement counters when loaded from CAR-derived JSONs
            try:
                # Proactively validate token; prompt if expired before hydration
                if self.auth.client and self.auth.current_handle:
                    try:
                        self.auth.client.get_profile(self.auth.current_handle)
                    except Exception:
                        self.auth.ensure_authentication()
                self.data_manager.hydrate_items(self.current_data)
            except Exception as e:
                console.print(
                    f"[yellow]Warning: Could not update engagement data: {e}[/yellow]"
                )
                console.print("[dim]Engagement stats may be incomplete[/dim]")
            self.current_data_file = file_path
            console.print(
                f"Loaded {len(self.current_data)} items from {file_path.name}"
            )
            console.print()

            if self.current_data:
                # Update runtime averages in settings for likes and engagement
                pr_items = [
                    it
                    for it in self.current_data
                    if it.content_type in ("post", "reply")
                ]
                if pr_items:
                    total_likes = sum(int(it.like_count or 0) for it in pr_items)
                    total_eng = sum(
                        int(it.like_count or 0)
                        + 2 * int(it.repost_count or 0)
                        + 2.5 * int(it.reply_count or 0)
                        for it in pr_items
                    )
                    self.settings_manager.settings.avg_likes_per_post = (
                        total_likes / len(pr_items)
                    )
                    self.settings_manager.settings.avg_engagement_per_post = (
                        total_eng / len(pr_items)
                    )
                self.ui.display_stats(self.current_data, mode="compact")
                console.print()

                while True:
                    nav_choice = self.ui.pause_with_navigation(
                        "stats", allow_help=True, allow_back=True, allow_main=True
                    )
                    if nav_choice == "continue" or nav_choice == "main":
                        return True
                    elif nav_choice == "back":
                        return False
                    elif nav_choice == "help":
                        self.help_manager._show_stats_help()
                        # Redisplay the stats after help
                        console.print(
                            f"Loaded {len(self.current_data)} items from {self.current_data_file.name}"
                        )
                        console.print()
                        self.ui.display_stats(self.current_data, mode="compact")
                        console.print()
                        # Continue the navigation loop
                    elif nav_choice == "refresh":
                        if self.refresh_current_data():
                            console.print("Data refreshed successfully.")
                            # Redisplay stats with fresh data
                            self.ui.display_stats(self.current_data, mode="compact")
                            console.print()
                        else:
                            console.print("Failed to refresh data")
            else:
                console.print("No content found in this data file")
                console.print("This could mean:")
                console.print("   • The account has no posts, likes, or reposts yet")
                console.print("   • The data export was empty")
                console.print("   • Try creating some content on Bluesky first")
                return False

        except Exception as e:
            console.print(f"Error loading file: {e}")
            return False

    def export_results(self, items: List[ContentItem]):
        """Export search results."""
        console.print()
        console.print("Export Results")
        console.print()

        formats = {"1": ("json", "JSON format"), "2": ("csv", "CSV format")}

        console.print("Export format:")
        for key, (_, desc) in formats.items():
            console.print(f"  [{key}] {desc}")

        format_choice = Prompt.ask(
            "Select format",
            choices=list(formats.keys()),
            default="1",
            show_choices=False,
        )
        export_format, _ = formats[format_choice]

        filename = Prompt.ask("Filename (without extension)", default="search_results")

        # Always export to ~/skymarshal (non-hidden) for user convenience
        export_base = Path.home() / "skymarshal"
        try:
            export_base.mkdir(parents=True, exist_ok=True)
        except Exception:
            # Fallback to current working directory if home export path is not writable
            export_base = Path.cwd()
        export_path = export_base / f"{filename}.{export_format}"

        try:
            if export_format == "json":
                data = []
                for item in items:
                    data.append(
                        {
                            "uri": item.uri,
                            "cid": item.cid,
                            "type": item.content_type,
                            "text": item.text,
                            "created_at": item.created_at,
                            "engagement": {
                                "likes": item.like_count,
                                "reposts": item.repost_count,
                                "replies": item.reply_count,
                                "score": item.engagement_score,
                            },
                        }
                    )

                with open(export_path, "w") as f:
                    json.dump(data, f, indent=2)

            elif export_format == "csv":
                import csv

                with open(export_path, "w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(
                        [
                            "URI",
                            "Type",
                            "Text",
                            "Likes",
                            "Reposts",
                            "Replies",
                            "Engagement",
                            "Created",
                        ]
                    )

                    for item in items:
                        writer.writerow(
                            [
                                item.uri,
                                item.content_type,
                                item.text or "",
                                item.like_count,
                                item.repost_count,
                                item.reply_count,
                                item.engagement_score,
                                item.created_at or "",
                            ]
                        )

            console.print(f"Exported {len(items)} items to {export_path}")
            console.print("[dim]Note: Exports are saved to ~/skymarshal[/dim]")

        except Exception as e:
            console.print(f"Export failed: {e}")

        while True:
            nav_choice = self.ui.pause_with_navigation("results")
            if nav_choice == "continue":
                break
            else:
                action = self.handle_navigation_choice(nav_choice, "search")
                if action in ["back", "main"]:
                    break

    def run(self):
        """Main application loop."""
        try:
            show_banner()

            if not self.handle_startup_flow():
                console.print("[dim]Skipping startup — proceed via the main menu[/dim]")

            while True:
                try:
                    # Display ASCII header before main menu
                    show_banner()

                    choice = self.ui.show_main_menu(
                        self.auth.is_authenticated(),
                        self.auth.current_handle,
                        self.current_data_file,
                        len(self.current_data),
                    )
                except KeyboardInterrupt:
                    if Confirm.ask("Quit Skymarshal?", default=False):
                        console.print("Goodbye!")
                        break
                    else:
                        continue

                try:
                    if choice == "quit":
                        quit_confirm, quit_action = self.ui.prompt_confirm(
                            "Quit Skymarshal?", default=True, context="quit_confirm"
                        )
                        if quit_action == "back":
                            continue
                        if quit_confirm:
                            console.print("Goodbye!")
                            break
                        else:
                            continue
                    elif choice == "search":
                        self.handle_search_analyze()
                    elif choice == "stats":
                        self.handle_quick_stats()
                    elif choice == "data":
                        self.handle_data_management()
                    elif choice == "auth":
                        self.handle_authentication()
                    elif choice == "x":
                        self.handle_nuke()
                    elif choice == "settings":
                        self.settings_manager.handle_settings()
                    elif choice == "help":
                        self.help_manager.show_help()
                except KeyboardInterrupt:
                    console.print("[dim]Cancelled — returning to previous menu[/dim]")
                    continue

                console.print()

        except Exception as e:
            console.print(f"\nUnexpected error: {e}")
            console.print("Please report this issue if it persists.")

    def _select_existing_file_with_navigation(self, existing_files):
        """Select from existing data files with stats and navigation."""
        while True:
            selected_file = self.ui.show_file_picker(existing_files)
            if not selected_file:
                return False

            if self.load_data_with_stats_and_navigation(
                selected_file, "file selection"
            ):
                return True

    def _handle_no_data_scenario(self):
        """Handle case with no data or backup files - download backup, then select categories to process."""
        console.print(
            "No existing backups found. Creating fresh backup and processing..."
        )
        console.print()

        # Get handle
        if self.auth.current_handle:
            handle = self.auth.current_handle
        else:
            while True:
                handle, action = self.ui.input_with_navigation(
                    "Enter your handle: @", context="handle"
                )
                if action in ["back", "main"]:
                    return False
                if handle:
                    break
                console.print("Handle is required")

        handle = self.auth.normalize_handle(handle)

        # Step 1: Download complete backup (single efficient API call)
        console.print("Step 1: Creating complete backup...")
        backup_path = self.data_manager.download_backup(handle)
        if not backup_path:
            console.print("Failed to create backup")
            return False

        console.print("Complete backup created successfully")
        console.print()

        # Step 2: Category selection before processing (no limit/date prompts)
        categories = self.ui.select_categories_for_processing()

        # Step 3: Process backup into usable format (local operation, no API calls)
        console.print("Step 2: Processing backup into usable data...")
        imported_path = self.data_manager.import_backup_replace(
            backup_path, handle, categories=categories
        )
        if not imported_path:
            console.print("Failed to process backup")
            return False

        console.print("Data processed successfully.")
        console.print()

        # Step 4: Load and show stats
        return self.load_data_with_stats_and_navigation(imported_path, "startup")

    def _startup_download_fresh_data(self):
        """Download fresh data during startup with full control options."""
        console.print()
        console.print("Download Fresh Data")
        console.print()

        # Get handle
        if self.auth.current_handle:
            handle = self.auth.current_handle
        else:
            while True:
                handle, action = self.ui.input_with_navigation(
                    "Enter your handle to download data: @", context="handle"
                )
                if action in ["back", "main"]:
                    return False
                if handle:
                    break
                console.print("Handle is required")

        handle = self.auth.normalize_handle(handle)

        # Get download options with same controls as main flow
        download_options = self._get_download_options()
        if not download_options:
            return False

        limit, categories, date_start, date_end = download_options

        console.print("[yellow]Re-authentication required for API access[/]")
        password, password_action = self.ui.prompt_text(
            "App Password: ", password=True, context="password"
        )
        if password_action == "back":
            return False

        with console.status("Authenticating and downloading..."):
            try:
                if not self.auth.authenticate_client(handle, password):
                    return False

                export_path = self.data_manager.export_user_data(
                    handle,
                    limit,
                    categories=categories,
                    date_start=date_start,
                    date_end=date_end,
                    replace_existing=True,
                )
            except Exception as e:
                console.print(f"Download error: {e}")
                return False

        # Handle results outside the status context
        if export_path:
            console.print(f"Data downloaded successfully: {export_path.name}")
            console.print()
            return self.load_data_with_stats_and_navigation(export_path, "download")
        else:
            console.print("Download failed")
            return False

    def _startup_download_and_import_backup(self):
        """Download and import backup file during startup."""
        console.print()
        console.print("[yellow]Download & Process Backup[/]")
        console.print("[yellow]⚠️  Note: Backup files may have incomplete engagement data[/]")
        console.print("[yellow]   Use 'Refresh engagement data' after loading to get current metrics[/]")
        console.print()

        if self.auth.current_handle:
            handle = self.auth.current_handle
        else:
            while True:
                handle, action = self.ui.input_with_navigation(
                    "Enter your handle to download data: @", context="handle"
                )
                if action in ["back", "main"]:
                    return False
                if handle:
                    break
                console.print("Handle is required")
        handle = self.auth.normalize_handle(handle)
        console.print(f"Downloading backup for @{handle}...")
        backup_path = self.data_manager.download_backup(handle)

        if not backup_path:
            console.print("Failed to download backup file")
            return False

        console.print("Backup file downloaded successfully.")
        console.print()

        # Ask which categories to process from this backup
        console.print("Select which categories to process from the backup:")
        categories = self.ui.select_categories_for_processing()
        console.print("Importing data from backup file...")
        # Replace rather than merge to reflect current state after destructive ops
        imported_path = self.data_manager.import_backup_replace(
            backup_path, handle, categories=categories
        )
        if imported_path:
            console.print("Data imported successfully.")
            console.print()

            if self.load_data_with_stats_and_navigation(imported_path, "startup"):
                return True
            else:
                if Confirm.ask("Try a different setup option?", default=True):
                    return self._handle_no_data_scenario()
                return False
        else:
            console.print("Failed to import data")
            if Confirm.ask("Try downloading fresh data instead?", default=True):
                return self._handle_no_data_scenario()
            return False

    def _handle_json_only_scenario(self, existing_files):
        """Handle case with only JSON files available."""
        if len(existing_files) == 1:
            json_file = existing_files[0]
            console.print(f"Loading existing data: {json_file.name}")
            return self.load_data_with_stats_and_navigation(json_file, "data selection")
        else:
            console.print("Multiple data files found")
            return self._select_existing_file_with_navigation(existing_files)

    def _handle_backup_only_scenario(self, existing_files):
        """Handle case with only backup files available."""
        console.print("[bright_yellow]Only backup files found (no processed data)[/]")
        console.print("[yellow]⚠️  Note: Backup files may have incomplete engagement data[/]")
        console.print("[yellow]   Consider downloading fresh API data for complete metrics[/]")
        console.print()

        while True:
            backup_choices = {
                "1": ("api", "Download fresh data from Bluesky API (recommended)"),
                "2": ("backup", "Import existing backup file"),
            }
            
            choice, action = self.ui.prompt_with_choices(
                "Choose option",
                choices=backup_choices,
                default="1",
                context="backup_only",
                allow_navigation=False,
            )
            
            if choice == "api":
                return self._startup_download_fresh_data()
            elif choice == "backup":
                if len(existing_files) == 1:
                    backup_file = existing_files[0]
                    console.print(f"Found backup file: {backup_file.name}")
                    return self._import_backup_and_load_with_navigation(backup_file)
                else:
                    console.print("Multiple backup files found:")
                    selected_backup = self.ui.show_file_picker(existing_files)
                    if selected_backup:
                        return self._import_backup_and_load_with_navigation(selected_backup)
                    continue
            
            return False

    def _handle_mixed_data_scenario(self, json_files, backup_files):
        """Handle case with both data and backup files available."""
        while True:
            console.print(Rule("[bright_cyan]Data files found[/]", style="bright_cyan"))
            console.print("[dim]💡 API downloads provide the most accurate engagement data[/]")
            console.print()

            mixed_choices = {
                "1": ("download_fresh", "Download fresh data from Bluesky API (recommended)"),
                "2": ("json", "Load existing processed data"),
                "3": ("backup", "Import from existing backup file (may lack engagement data)"),
                "4": ("clear", "Clear local data and backups"),
                "q": ("quit", "Quit"),
            }

            choice, action = self.ui.prompt_with_choices(
                "Choose option",
                choices=mixed_choices,
                default="1",
                context="mixed_data",
                allow_navigation=False,
            )

            if choice == "download_fresh":
                # Fresh data download path (now primary option)
                return self._startup_download_fresh_data()
            elif choice == "json":
                return self._handle_json_only_scenario(json_files)
            elif choice == "backup":
                # Import an existing backup with warning
                console.print("[yellow]⚠️  Warning: Backup files may have incomplete engagement data[/]")
                console.print("[yellow]   Consider downloading fresh API data for complete metrics[/]")
                console.print()
                if Confirm.ask("Continue with backup import?", default=False):
                    return self._handle_backup_only_scenario(backup_files)
                continue
            elif choice == "clear":
                # Clear local data for current or entered handle
                if self.auth.current_handle:
                    handle = self.auth.current_handle
                else:
                    handle, action = self.ui.input_with_navigation(
                        "Handle to clear data for: @", context="handle"
                    )
                    if action in ["back", "main"]:
                        continue
                handle = self.auth.normalize_handle(handle)
                console.print(
                    Panel(
                        f"This will delete local data and backup files for @{handle}",
                        title="Clear Local Data",
                        border_style="red",
                    )
                )
                if Confirm.ask("Proceed with deleting local files?", default=False):
                    deleted = self.data_manager.clear_local_data(handle)
                    if deleted:
                        console.print(f"Deleted {deleted} local file(s)")
                        # Reset in-memory data if we just removed the loaded file
                        if (
                            self.current_data_file
                            and self.current_data_file.name.startswith(
                                handle.replace(".", "_")
                            )
                        ):
                            self.current_data = []
                            self.current_data_file = None
                    else:
                        console.print("[dim]Nothing was deleted[/dim]")
                # After clearing, refresh available files before showing menu again
                h = self.auth.current_handle or handle
                json_files = self.data_manager.get_user_files(h, "json")
                backup_files = self.data_manager.get_user_files(h, "backup")
                # If no files remain, fall back to no-data flow
                if not json_files and not backup_files:
                    return self._handle_no_data_scenario()
                console.print()
                continue
            elif choice == "quit":
                # Explicit quit only
                return False

    def _import_backup_and_load_with_navigation(self, backup_path):
        """Import a backup file and load with stats and navigation."""
        console.print(f"[yellow]⚠️  Importing backup file: {backup_path.name}[/]")
        console.print("[yellow]Note: Engagement data may be incomplete or zero[/]")
        console.print("[yellow]Use 'Refresh engagement data' after loading to get current metrics[/]")
        console.print()

        handle = self.auth.current_handle
        if not handle:
            name_parts = backup_path.stem.split("_")
            if name_parts and "." in name_parts[0]:
                handle = name_parts[0]

        if not handle:
            while True:
                handle, action = self.ui.input_with_navigation(
                    "Enter handle for this backup file: @", context="handle"
                )
                if action in ["back", "main"]:
                    return False
                if handle:
                    handle = self.auth.normalize_handle(handle)
                    break
                console.print("Handle is required")

        # Ask which categories to process from this backup
        console.print("Select which categories to process from the backup:")
        categories = self.ui.select_categories_for_processing()
        imported_path = self.data_manager.import_backup_merge(
            backup_path, handle, categories=categories
        )
        if imported_path:
            console.print("[green]✓[/] Backup file imported successfully.")
            console.print("[dim]Tip: Use Data Management > Refresh engagement data to update metrics[/]")
            console.print()
            return self.load_data_with_stats_and_navigation(imported_path, "Backup import")
        else:
            console.print("Failed to import backup file")
            return False

    def _handle_quick_actions(self):
        """Handle quick action options from stats view."""
        pr_items = [
            item for item in self.current_data if item.content_type in ("post", "reply")
        ]
        dead_threads = [
            it
            for it in pr_items
            if it.like_count == 0 and it.repost_count == 0 and it.reply_count == 0
        ]

        quick_actions = {
            "1": (
                "View dead threads",
                lambda: self._quick_view_dead_threads(dead_threads),
            ),
            "2": ("View top content", lambda: self._quick_view_top_content()),
            "3": ("Engagement breakdown", lambda: self._show_engagement_breakdown()),
            "4": ("Peak/low times", lambda: self._show_temporal_breakdown()),
        }

        console.print("Quick actions:")
        for key, (desc, _) in quick_actions.items():
            console.print(f"  [{key}] {desc}")
        console.print("  (b) Back to main menu")
        console.print()

        choice = Prompt.ask(
            "Select action",
            choices=list(quick_actions.keys()) + ["b"],
            default="1",
            show_choices=False,
        )

        if choice in quick_actions:
            _, action = quick_actions[choice]
            action()

    def _quick_view_dead_threads(self, dead_threads: List[ContentItem]):
        """Quick view of dead threads."""
        console.print()
        console.print(f"Dead Threads ({len(dead_threads)} items)")
        console.print()

        if dead_threads:
            self.ui.display_search_results(dead_threads, limit=10)
            console.print()

            if Confirm.ask("Delete these dead threads?"):
                self.handle_delete_content(dead_threads)
        else:
            console.print("No dead threads found.")

        while True:
            nav_choice = self.ui.pause_with_navigation("results")
            if nav_choice == "continue":
                break
            else:
                action = self.handle_navigation_choice(nav_choice, "search")
                if action in ["back", "main"]:
                    return
                elif action == "redisplay":
                    # Redisplay dead threads after help
                    console.print(f"Dead Threads ({len(dead_threads)} items)")
                    console.print()
                    if dead_threads:
                        self.ui.display_search_results(dead_threads, limit=10)
                        console.print()
                    else:
                        console.print("No dead threads found.")

    def _quick_view_top_content(self):
        """Show top performing content."""
        console.print()
        console.print("Top Content")
        console.print()

        sorted_items = sorted(
            self.current_data, key=lambda x: x.engagement_score, reverse=True
        )
        top_items = sorted_items[:10]

        self.ui.display_search_results(top_items)
        while True:
            nav_choice = self.ui.pause_with_navigation("results")
            if nav_choice == "continue":
                break
            else:
                action = self.handle_navigation_choice(nav_choice, "search")
                if action in ["back", "main"]:
                    return
                elif action == "redisplay":
                    # Redisplay top content after help
                    console.print()
                    console.print("Top Content")
                    console.print()
                    self.ui.display_search_results(top_items)

    def _show_engagement_breakdown(self):
        """Show detailed engagement breakdown."""
        console.print()
        console.print("Engagement Breakdown")
        console.print()

        ranges = [
            (0, 0, "Dead"),
            (0.1, 8, "Low"),
            (9, 25, "Medium"),
            (26, 100, "High"),
            (101, float("inf"), "Viral"),
        ]

        from rich.table import Table

        breakdown_table = Table()
        breakdown_table.add_column("Range", style="bold")
        breakdown_table.add_column("Count", style="bright_white")
        breakdown_table.add_column("Percentage", style="dim")

        total = len(self.current_data)

        for min_eng, max_eng, label in ranges:
            if max_eng == float("inf"):
                count = len(
                    [
                        item
                        for item in self.current_data
                        if item.engagement_score >= min_eng
                    ]
                )
            else:
                count = len(
                    [
                        item
                        for item in self.current_data
                        if min_eng <= item.engagement_score <= max_eng
                    ]
                )

            percentage = (count / total * 100) if total else 0
            breakdown_table.add_row(label, str(count), f"{percentage:.1f}%")

        console.print(breakdown_table)
        while True:
            nav_choice = self.ui.pause_with_navigation("stats")
            if nav_choice == "continue":
                break
            else:
                action = self.handle_navigation_choice(nav_choice, "stats")
                if action in ["back", "main"]:
                    return

    def _show_temporal_breakdown(self):
        """Show engagement by hour-of-day and day-of-week."""
        console.print()
        console.print("Temporal Engagement Breakdown")
        console.print()

        items = [
            it
            for it in self.current_data
            if it.content_type in ("post", "reply") and it.created_at
        ]
        if not items:
            console.print("[dim]No timestamped posts/replies to analyze[/dim]")
            return

        by_hour = {h: 0 for h in range(24)}
        by_day = {d: 0 for d in range(7)}

        for it in items:
            dt = parse_datetime(it.created_at)
            if not dt:
                continue
            # Use engagement_score if available and non-zero, otherwise calculate manually
            if hasattr(it, "engagement_score") and it.engagement_score > 0:
                eng = it.engagement_score
            else:
                eng = (
                    int(it.like_count or 0)
                    + 2 * int(it.repost_count or 0)
                    + 2.5 * int(it.reply_count or 0)
                )
            by_hour[dt.hour] += eng
            by_day[dt.weekday()] += eng

        hours_sorted = sorted(by_hour.items(), key=lambda kv: kv[1], reverse=True)
        top_hours = {h for h, _ in hours_sorted[:5]}
        bottom_hours = {h for h, _ in sorted(by_hour.items(), key=lambda kv: kv[1])[:5]}

        from rich.table import Table

        tbl = Table(title="By Hour of Day (all hours)")
        tbl.add_column("Hour", style="bold")
        tbl.add_column("Engagement", style="cyan")
        tbl.add_column("", style="green")

        for h in range(24):
            mark = ""
            style = None
            if h in top_hours:
                mark = "up"
                style = "bold green"
            elif h in bottom_hours:
                mark = "down"
                style = "dim"

            hr = f"{h:02d}:00"
            val = str(by_hour[h])

            if style:
                tbl.add_row(
                    f"[bold]{hr}[/bold]" if h in top_hours else hr,
                    f"[{style}]{val}[/{style}]",
                    mark,
                )
            else:
                tbl.add_row(hr, val, mark)

        console.print(tbl)
        console.print()

        dow_names = {
            0: "Mon",
            1: "Tue",
            2: "Wed",
            3: "Thu",
            4: "Fri",
            5: "Sat",
            6: "Sun",
        }
        tbl2 = Table(title="By Day of Week (all days)")
        tbl2.add_column("Day", style="bold")
        tbl2.add_column("Engagement", style="cyan")

        for d in range(7):
            tbl2.add_row(dow_names[d], str(by_day[d]))

        console.print(tbl2)
        while True:
            nav_choice = self.ui.pause_with_navigation("stats")
            if nav_choice == "continue":
                break
            else:
                action = self.handle_navigation_choice(nav_choice, "stats")
                if action in ["back", "main"]:
                    return


def cli():
    """Skymarshal — Bluesky Content Management Tool

    Interactive tool for managing your Bluesky content.

    Usage:
      - skymarshal            Launch interactive interface
      - skymarshal --help     Show this help and exit
    """
    import sys

    args = sys.argv[1:]
    if args:
        if len(args) == 1 and args[0] in {"-h", "--help"}:
            help_text = (
                "Skymarshal — Interactive Tool for Bluesky\n\n"
                "Usage:\n"
                "  skymarshal            Launch interactive interface\n"
                "  skymarshal --help     Show this help and exit\n\n"
                "Notes:\n"
                "  - Skymarshal is interactive-only; no other options are supported.\n"
                "  - Use the on-screen menus to access all features.\n"
            )
            console.print(help_text)
            return
        else:
            console.print("Unrecognized option(s). Skymarshal supports only --help.")
            console.print(
                "Run 'skymarshal' for the interactive interface, or 'skymarshal --help'."
            )
            sys.exit(2)

    # Launch interactive interface
    show_banner()
    inspector = InteractiveContentManager()
    inspector.run()


if __name__ == "__main__":
    cli()
