"""
Skymarshal Settings Management

File Purpose: User settings persistence, validation, and interactive configuration
Primary Functions/Classes: SettingsManager
Inputs and Outputs (I/O): Settings file I/O, user preference validation

This module handles all user settings including persistence to disk, interactive configuration
menus, validation of user inputs, and default value management for the application.
"""

import json
from pathlib import Path
from typing import Any

from rich.prompt import Prompt
from rich.rule import Rule
from rich.table import Table

from .models import UserSettings, console


class SettingsManager:
    """Manages user settings and preferences."""

    def __init__(self, settings_file: Path):
        self.settings_file = settings_file
        self.settings = self._load_user_settings()

    def _load_user_settings(self) -> UserSettings:
        """Load settings from file or create defaults."""
        try:
            if self.settings_file.exists():
                with open(self.settings_file, "r") as f:
                    data = json.load(f)
                base = UserSettings()
                for k, v in data.items():
                    if hasattr(base, k):
                        setattr(base, k, v)
                return base
        except Exception:
            pass
        return UserSettings()

    def save_user_settings(self):
        """Save current settings to file."""
        try:
            data = {
                "download_limit_default": self.settings.download_limit_default,
                "default_categories": self.settings.default_categories,
                "records_page_size": self.settings.records_page_size,
                "hydrate_batch_size": self.settings.hydrate_batch_size,
                "category_workers": self.settings.category_workers,
                "file_list_page_size": self.settings.file_list_page_size,
                "high_engagement_threshold": self.settings.high_engagement_threshold,
                "use_subject_engagement_for_reposts": self.settings.use_subject_engagement_for_reposts,
                "fetch_order": self.settings.fetch_order,
            }
            with open(self.settings_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            console.print(f"[yellow]Warning: failed to save settings: {e}[/yellow]")

    def handle_settings(self):
        """Interactive settings management."""
        console.print(Rule("Settings", style="bright_magenta"))
        console.print()

        def show_table():
            tbl = Table(show_header=True)
            tbl.add_column("#", width=3)
            tbl.add_column("Setting", style="bold")
            tbl.add_column("Value", style="cyan")

            keys = [
                (
                    "Default download limit (per category)",
                    "download_limit_default",
                    str(self.settings.download_limit_default),
                ),
                (
                    "Default categories to fetch",
                    "default_categories",
                    ",".join(self.settings.default_categories),
                ),
                (
                    "API page size (listRecords)",
                    "records_page_size",
                    str(self.settings.records_page_size),
                ),
                (
                    "Update batch size for engagement info (get_posts)",
                    "hydrate_batch_size",
                    str(self.settings.hydrate_batch_size),
                ),
                (
                    "Parallel category workers",
                    "category_workers",
                    str(self.settings.category_workers),
                ),
                (
                    "File picker page size",
                    "file_list_page_size",
                    str(self.settings.file_list_page_size),
                ),
                (
                    "High engagement threshold",
                    "high_engagement_threshold",
                    str(self.settings.high_engagement_threshold),
                ),
                (
                    "Use subject engagement for reposts",
                    "use_subject_engagement_for_reposts",
                    "on" if self.settings.use_subject_engagement_for_reposts else "off",
                ),
                (
                    "Fetch order for data (newest|oldest)",
                    "fetch_order",
                    self.settings.fetch_order,
                ),
            ]

            for i, (label, _, v) in enumerate(keys, 1):
                tbl.add_row(str(i), label, v)

            console.print(tbl)
            return keys

        keys = show_table()
        console.print("Enter the # to edit, **?** for help, or **b** to go back")

        while True:
            choice = Prompt.ask(
                "[bold white]Choose setting[/]",
                choices=[str(i) for i in range(1, len(keys) + 1)] + ["b", "?"],
                default="b",
            )
            if choice == "b":
                break
            elif choice == "?":
                self._show_settings_help()
                keys = show_table()
                continue

            idx = int(choice) - 1
            label, key, current_val = keys[idx]
            new_val = Prompt.ask(
                f"[bold white]New value for {label}:[/] ", default=current_val
            )

            try:
                self._update_setting(key, new_val)
                self.save_user_settings()
                console.print("Saved")
            except Exception as e:
                console.print(f"Invalid value: {e}")

            console.print()
            keys = show_table()

    def _show_settings_help(self):
        """Show help for settings management."""
        console.print("\nSettings Help")
        console.print()
        console.print("**Performance Settings:**")
        console.print(
            "• **Download Limit**: Default number of items to download per category"
        )
        console.print("• **Records Page Size**: Items per page in API requests (1-100)")
        console.print(
            "• **Update Batch Size**: Records processed in each batch (1-25) when refreshing engagement info"
        )
        console.print(
            "• **Category Workers**: Parallel downloads for faster processing"
        )
        console.print()
        console.print("**Display Settings:**")
        console.print("• **File List Page Size**: Files shown per page in file picker")
        console.print(
            "• **High Engagement Threshold**: Score to consider content 'high engagement'"
        )
        console.print("• **Fetch Order**: Whether to download newest or oldest first")
        console.print()
        console.print("**Content Settings:**")
        console.print(
            "• **Default Categories**: What to download (posts,likes,reposts or 'all')"
        )
        console.print()
        console.print("Tip: Lower batch sizes use less memory but may be slower")
        console.print(
            "Tip: Higher worker counts speed up downloads but use more resources"
        )
        console.print()

    def _update_setting(self, key: str, new_val: str):
        """Update a specific setting with validation."""
        if key in (
            "download_limit_default",
            "records_page_size",
            "hydrate_batch_size",
            "category_workers",
            "file_list_page_size",
            "high_engagement_threshold",
        ):
            val = int(new_val)
            if key == "records_page_size":
                val = max(1, min(100, val))
            if key == "hydrate_batch_size":
                val = max(1, min(25, val))
            setattr(self.settings, key, val)
        elif key == "default_categories":
            parts = [p.strip().lower() for p in new_val.split(",") if p.strip()]
            valid = {"posts", "likes", "reposts"}
            if parts == ["all"] or not parts:
                self.settings.default_categories = ["posts", "likes", "reposts"]
            else:
                self.settings.default_categories = [p for p in parts if p in valid] or [
                    "posts",
                    "likes",
                    "reposts",
                ]
        elif key == "use_subject_engagement_for_reposts":
            val = new_val.strip().lower()
            self.settings.use_subject_engagement_for_reposts = val in (
                "on",
                "true",
                "yes",
                "y",
                "1",
            )
        elif key == "fetch_order":
            val = new_val.strip().lower()
            if val not in ("newest", "oldest"):
                raise ValueError("must be 'newest' or 'oldest'")
            self.settings.fetch_order = val
        else:
            setattr(self.settings, key, new_val)
