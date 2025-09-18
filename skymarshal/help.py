"""
Skymarshal Help System and Documentation

File Purpose: Comprehensive help system with interactive documentation
Primary Functions/Classes: HelpManager
Inputs and Outputs (I/O): User help requests, formatted help content display

This module provides extensive help documentation covering all aspects of the Skymarshal
application including getting started guides, feature explanations, and troubleshooting.
"""

from rich.prompt import Prompt
from rich.rule import Rule

from .models import console
from .ui import UIManager


class HelpManager:
    """Manages help system and documentation."""

    def __init__(self, ui_manager: UIManager):
        self.ui = ui_manager

    def show_help(self):
        """Show comprehensive help."""
        console.print(Rule("Help & Documentation", style="bright_blue"))
        console.print()

        help_sections = {
            "1": ("Getting Started", self._show_getting_started_help),
            "2": ("Authentication", self._show_auth_help),
            "3": ("Search & Filter", self._show_search_help),
            "4": ("Content Deletion", self._show_deletion_help),
            "5": ("Understanding Statistics", self._show_stats_help),
            "6": ("Terminology & Legend", self.ui.show_legend_help),
            "7": ("Tips & Tricks", self._show_tips_help),
            "8": ("Troubleshooting", self._show_troubleshooting_help),
        }

        console.print("Help Topics:")
        for key, (title, _) in help_sections.items():
            console.print(f"  [{key}] {title}")
        console.print("  (b) Back to main menu")
        console.print()

        choice = Prompt.ask(
            "Select help topic",
            choices=list(help_sections.keys()) + ["b"],
            default="1",
            show_choices=False,
        )

        if choice in help_sections:
            _, help_func = help_sections[choice]
            nav_choice = help_func()
            if nav_choice == "back":
                return
            elif nav_choice == "main":
                return

    def _show_getting_started_help(self):
        """Show getting started help."""
        help_text = """
# Getting Started

## Quick Start Steps

1. **Authentication**: Login with your Bluesky credentials
2. **Load Data**: Download your posts or select existing data file
3. **Explore**: Use search to find specific content
4. **Manage**: Delete unwanted posts safely

## First Time Setup

- Go to "Authentication" and login with your Bluesky handle and password
- Use "Data Management" to download your posts (up to 100 per download)
- Start with "Search & Analyze" to explore your content

## Safety Features

- All operations show previews before executing
- Dry-run modes for testing
- Multiple confirmation steps for deletions
- Individual approval options
        """
        return self.ui.show_help_text(help_text)

    def _show_auth_help(self):
        """Show authentication help."""
        help_text = """
# Authentication

## How Login Works

- Use a Bluesky App Password to connect to Bluesky
- Session information is kept in memory only (not saved to disk for security)
- Passwords are never stored, only login session tokens

## Re-authentication

Since sessions are not saved between app launches, you'll need to login each time you start the application. This ensures maximum security of your credentials.

Some operations may also require re-authentication during the session:
- Heavy data operations if the session expires
- Certain deletion operations for security

## Troubleshooting Login

- Make sure your handle is correct (e.g., `username.bsky.social`)
- Use a Bluesky App Password (create in Bluesky Settings → App Passwords)
- Check your internet connection
- Verify your account isn't restricted

        """
        return self.ui.show_help_text(help_text)

    def _show_search_help(self):
        """Show search help."""
        help_text = """
# Search & Filter

## Filter Types

### Content Type
- **All**: Everything (posts + replies)
- **Posts**: Original posts only
- **Replies**: Comments/replies only

### Engagement Filters
- **Presets**: Quick common filters (dead threads, popular, etc.)
- **Custom**: Set exact thresholds for likes, reposts, replies

## Engagement Presets

- **Dead threads**: 0 likes, 0 reposts, 0 replies
- **Low engagement**: Under 5 total engagement
- **High engagement**: 20+ total engagement
- **Popular posts**: 10+ likes
- **Controversial**: Many replies, few likes

## Search Tips

- Use keywords to find specific topics
- Combine multiple filters for precise results
- Start broad, then refine your search
- Use stats view to understand your data first

        """
        return self.ui.show_help_text(help_text)

    def _show_deletion_help(self):
        """Show deletion help."""
        help_text = """
# Content Deletion

## Deletion Modes

### All at Once
- Delete everything matching your criteria
- Single confirmation for entire batch
- Fastest for large deletions

### Individual Approval
- Review each item before deletion
- See full content and engagement
- Most control, but slower

### Batch Processing
- Review and approve groups of items
- Balance between speed and control
- Configurable batch sizes

## Safety Features

- Multiple confirmation prompts
- Preview before deletion
- Real-time progress tracking
- Error handling with reporting

## Important Notes

- Deletions are **permanent** and cannot be undone
- Operations make real calls to Bluesky
- Built-in delays prevent errors
- Failed deletions are reported

        """
        return self.ui.show_help_text(help_text)

    def _show_stats_help(self):
        """Show stats help."""
        help_text = """
# Understanding Statistics

## Engagement Scoring

**Total Engagement = Likes + (Reposts × 2) + (Replies × 2.5)**

Reposts and replies are weighted higher because they represent stronger engagement.

## Key Metrics

- **Average Likes**: Total likes / total posts (baseline for categories)
- **Dead Threads**: Posts with 0 engagement (candidates for deletion)
- **Average Engagement**: Total engagement / total posts
- **High Engagement**: Posts with 20+ engagement score

## Likes-based Categories

- Dead Thread: 0 likes
- Bomber: ≤ 0.5 × your average likes
- Mid: ~ your average likes (0.5× to 1.5×)
- Banger: ≥ 2 × your average likes
- Viral: ≥ 2000 likes (absolute threshold)

## Using Stats for Cleanup

- High percentage of dead threads? Consider cleanup
- Low average engagement? Review content strategy
- Few high-engagement posts? Identify what works

        """
        return self.ui.show_help_text(help_text)

    def _show_tips_help(self):
        """Show tips and tricks."""
        help_text = """
# Tips & Tricks

## Efficient Workflows

1. **Start with Stats**: Understand your content distribution
2. **Use Presets**: Quick filters for common cleanup tasks
3. **Preview First**: Always review before deleting
4. **Batch Process**: Balance speed and control

## Content Cleanup Strategy

- Delete dead threads first (0 engagement)
- Review low-engagement content (1-5 engagement)
- Keep high-performing content for reference
- Consider content age in decision making

## Advanced Usage

- Use keyword filters to find outdated topics
- Combine engagement and keyword filters
- Export results for external analysis
- Use individual review for sensitive content

## Data Management

- Download data regularly for analysis
- Keep backups before major cleanup operations
- Monitor engagement patterns over time
- Use stats to guide content strategy

        """
        return self.ui.show_help_text(help_text)

    def _show_troubleshooting_help(self):
        """Show troubleshooting help."""
        help_text = """
# Troubleshooting

## Common Issues

### Authentication Problems
- **Wrong credentials**: Double-check handle and password
- **Network issues**: Check internet connection
- **Too many attempts**: Wait and try again

### Data Loading Issues
- **File not found**: Use Data Management to select/download
- **Empty results**: Check if data file has content
- **File errors**: File may be corrupted, re-download

### Deletion Problems
- **Authentication expired**: Re-login before deletion
- **Connection errors**: Check network connection
- **Partial failures**: Some items may fail, others succeed

## Performance Tips

- Download only what you need (reasonable limits)
- Use filters to reduce result sets
- Process deletions in batches for large sets

## Getting Help

- Check this help system first
- Review error messages carefully
- Note exact steps that caused issues
- Consider network connection status

        """
        return self.ui.show_help_text(help_text)
