#!/usr/bin/env python3
"""
Skymarshal Help System Script

This script provides comprehensive help and documentation for Skymarshal.
It offers context-aware help covering all aspects of the application.

Usage: python help.py
"""

import os
import sys
from pathlib import Path

# Add parent directory to path to import skymarshal modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.rule import Rule
from rich.markdown import Markdown

# Import from skymarshal
from skymarshal.models import UserSettings
from skymarshal.ui import UIManager
from skymarshal.help import HelpManager

console = Console()

class HelpScript:
    """Standalone help system functionality."""
    
    def __init__(self):
        self.settings_file = Path.home() / '.car_inspector_settings.json'
        self.settings = self._load_settings()
        self.ui = UIManager(self.settings)
        self.help_manager = HelpManager(self.ui)
    
    def _load_settings(self) -> UserSettings:
        """Load user settings or create defaults."""
        try:
            if self.settings_file.exists():
                import json
                with open(self.settings_file, 'r') as f:
                    data = json.load(f)
                base = UserSettings()
                for k, v in data.items():
                    if hasattr(base, k):
                        setattr(base, k, v)
                return base
        except Exception:
            pass
        return UserSettings()
    
    def show_getting_started(self):
        """Show getting started guide."""
        console.print(Rule("Getting Started", style="bright_green"))
        console.print()
        
        help_text = """
# Getting Started with Skymarshal

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

## Workflow Overview

1. **Setup** → Download and process your Bluesky data
2. **Stats** → Understand your content patterns and engagement
3. **Search** → Find specific content using filters
4. **Export** → Save filtered results in various formats
5. **Delete** → Remove unwanted content (with safety checks)

## Next Steps

- Try the individual loner scripts for specific tasks
- Use the main application for comprehensive workflows
- Check the help system for detailed information
        """
        
        console.print(Panel(help_text, title="Getting Started Guide", border_style="green"))
        console.print()
    
    def show_authentication_help(self):
        """Show authentication help."""
        console.print(Rule("Authentication Help", style="bright_blue"))
        console.print()
        
        help_text = """
# Authentication

## How Login Works

- Your credentials are used to authenticate with Bluesky's AT Protocol
- Session information is kept in memory only (not saved to disk for security)
- Passwords are never stored, only session tokens

## Re-authentication

Since sessions are not saved between app launches, you'll need to login each time you start the application. This ensures maximum security of your credentials.

Some operations may also require re-authentication during the session:
- API-heavy operations if the session expires
- Certain deletion operations for security

## Troubleshooting Login

- Make sure your handle is correct (e.g., `username.bsky.social`)
- Use your account password, not app-specific passwords
- Check your internet connection
- Verify your account isn't restricted

## Security Notes

- Credentials are never saved to disk
- Sessions are temporary and expire automatically
- All API calls use secure HTTPS connections
- Your data remains private and local
        """
        
        console.print(Panel(help_text, title="Authentication Help", border_style="blue"))
        console.print()
    
    def show_search_help(self):
        """Show search help."""
        console.print(Rule("Search & Filter Help", style="bright_yellow"))
        console.print()
        
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

## Engagement Scoring

**Total Engagement = Likes + (Reposts × 2) + (Replies × 3)**

Reposts and replies are weighted higher because they represent stronger engagement.

## Advanced Search

- Combine keyword and engagement filters
- Use date ranges for temporal analysis
- Export results for external analysis
- Preview before taking action
        """
        
        console.print(Panel(help_text, title="Search & Filter Help", border_style="yellow"))
        console.print()
    
    def show_deletion_help(self):
        """Show deletion help."""
        console.print(Rule("Content Deletion Help", style="bright_red"))
        console.print()
        
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
- Operations make real API calls to Bluesky
- Rate limiting prevents API errors
- Failed deletions are reported

## Best Practices

- Always preview before deleting
- Start with small batches
- Use individual approval for sensitive content
- Keep backups before major deletions
- Test with dry-run mode first
        """
        
        console.print(Panel(help_text, title="Content Deletion Help", border_style="red"))
        console.print()
    
    def show_statistics_help(self):
        """Show statistics help."""
        console.print(Rule("Statistics Help", style="bright_cyan"))
        console.print()
        
        help_text = """
# Understanding Statistics

## Engagement Scoring

**Total Engagement = Likes + (Reposts × 2) + (Replies × 3)**

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

## Temporal Analysis

- Hour of day patterns show when your audience is active
- Day of week patterns reveal weekly engagement trends
- Monthly trends help track long-term performance

## Content Distribution

- See breakdown of posts vs replies vs reposts vs likes
- Understand your content creation patterns
- Identify areas for improvement
        """
        
        console.print(Panel(help_text, title="Statistics Help", border_style="cyan"))
        console.print()
    
    def show_terminology_help(self):
        """Show terminology and legend."""
        console.print(Rule("Terminology & Legend", style="bright_magenta"))
        console.print()
        
        help_text = """
# Terminology & Legend

## Content Types

- **Post**: Original content you created
- **Reply**: Comments/replies to other posts
- **Repost**: Sharing someone else's post
- **Like**: Expressing approval of a post

## Engagement Metrics

- **Likes**: Number of people who liked the post
- **Reposts**: Number of times the post was shared
- **Replies**: Number of comments on the post
- **Engagement Score**: Weighted total (likes + reposts×2 + replies×3)

## Data Files

- **CAR File**: Complete backup in AT Protocol format
- **JSON File**: Processed data in readable format
- **Export**: Saved search results or filtered data

## Interface Elements

- **URI**: Unique identifier for each piece of content
- **CID**: Content identifier in the AT Protocol
- **DID**: Decentralized identifier for your account
- **Handle**: Your username (e.g., username.bsky.social)

## Status Indicators

- Success/Complete
- Error/Failed
- Warning/Caution
- In Progress
- Statistics/Data
- Search/Filter
- Delete/Remove
- Save/Export
        """
        
        console.print(Panel(help_text, title="Terminology & Legend", border_style="magenta"))
        console.print()
    
    def show_tips_and_tricks(self):
        """Show tips and tricks."""
        console.print(Rule("Tips & Tricks", style="bright_green"))
        console.print()
        
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

## Performance Tips

- Limit data downloads to what you need
- Use filters to reduce result sets
- Process deletions in batches for large sets
- Clear old data files periodically

## Troubleshooting

- Check authentication if operations fail
- Verify data files exist and are readable
- Use dry-run modes to test operations
- Check network connection for API calls
        """
        
        console.print(Panel(help_text, title="Tips & Tricks", border_style="green"))
        console.print()
    
    def show_troubleshooting_help(self):
        """Show troubleshooting help."""
        console.print(Rule("Troubleshooting", style="bright_red"))
        console.print()
        
        help_text = """
# Troubleshooting

## Common Issues

### Authentication Problems
- **Wrong credentials**: Double-check handle and password
- **Network issues**: Check internet connection
- **Rate limiting**: Wait and try again

### Data Loading Issues
- **File not found**: Use Data Management to select/download
- **Empty results**: Check if data file has content
- **Parsing errors**: File may be corrupted, re-download

### Deletion Problems
- **Authentication expired**: Re-login before deletion
- **API errors**: Check rate limits, network connection
- **Partial failures**: Some items may fail, others succeed

## Performance Tips

- Limit data downloads to what you need (max 100 posts)
- Use filters to reduce result sets
- Process deletions in batches for large sets

## Getting Help

- Check this help system first
- Review error messages carefully
- Note exact steps that caused issues
- Consider network and API status

## Error Messages

- **"Not authenticated"**: Login required
- **"No data loaded"**: Load a data file first
- **"File not found"**: Check file path and permissions
- **"API error"**: Check network and try again

## Data Recovery

- CAR files contain complete backups
- JSON files can be re-exported
- Settings can be reset to defaults
- Always backup before major operations
        """
        
        console.print(Panel(help_text, title="Troubleshooting Guide", border_style="red"))
        console.print()
    
    def show_about_skymarshal(self):
        """Show information about Skymarshal."""
        console.print(Rule("About Skymarshal", style="bright_blue"))
        console.print()
        
        help_text = """
# About Skymarshal

## What is Skymarshal?

Skymarshal is a comprehensive command-line tool for managing Bluesky social media content. It provides interactive and programmatic interfaces for downloading, analyzing, filtering, and safely deleting Bluesky posts, likes, and reposts using the AT Protocol.

## Key Features

- **Complete Data Management**: Download and process your entire Bluesky history
- **Advanced Search**: Find content by keywords, engagement, date ranges
- **Safe Deletion**: Multiple approval modes with comprehensive safety checks
- **Rich Analytics**: Detailed statistics and engagement analysis
- **Flexible Export**: Save data in JSON, CSV, and Markdown formats
- **Individual Scripts**: Standalone tools for specific tasks

## Architecture

- **Manager Pattern**: Modular design with dedicated managers for each function
- **AT Protocol Integration**: Direct integration with Bluesky's protocol
- **Rich UI**: Beautiful terminal interface with progress indicators
- **Safety First**: Multiple confirmation layers and dry-run capabilities

## Data Storage

- **Settings**: ~/.car_inspector_settings.json
- **Data Directory**: ~/.skymarshal/
- **CAR Files**: ~/.skymarshal/cars/ (complete backups)
- **JSON Files**: ~/.skymarshal/json/ (processed data)

## Safety & Security

- Credentials never saved to disk
- Multiple confirmation prompts
- Preview before action
- Comprehensive error handling
- Rate limiting compliance
        """
        
        console.print(Panel(help_text, title="About Skymarshal", border_style="blue"))
        console.print()
    
    def show_menu(self):
        """Display main menu."""
        console.print(Rule("Help & Documentation", style="bright_blue"))
        console.print()
        
        options = {
            "1": ("Getting Started", self.show_getting_started),
            "2": ("Authentication Help", self.show_authentication_help),
            "3": ("Search & Filter Help", self.show_search_help),
            "4": ("Content Deletion Help", self.show_deletion_help),
            "5": ("Statistics Help", self.show_statistics_help),
            "6": ("Terminology & Legend", self.show_terminology_help),
            "7": ("Tips & Tricks", self.show_tips_and_tricks),
            "8": ("Troubleshooting", self.show_troubleshooting_help),
            "9": ("About Skymarshal", self.show_about_skymarshal),
            "q": ("Quit", None)
        }
        
        console.print("Help Topics:")
        for key, (desc, _) in options.items():
            console.print(f"  [{key}] {desc}")
        console.print()
        
        choice = Prompt.ask("Select help topic", choices=list(options.keys()), default="1", show_choices=False)
        
        if choice == "q":
            return False
        
        if choice in options:
            _, func = options[choice]
            if func:
                func()
                console.print()
                if not Confirm.ask("Continue?", default=True):
                    return False
        
        return True
    
    def run(self):
        """Run the help script."""
        console.print()
        console.print("Skymarshal Help & Documentation")
        console.print("=" * 50)
        console.print()
        
        try:
            while True:
                if not self.show_menu():
                    break
                console.print()
        except KeyboardInterrupt:
            console.print("\nGoodbye!")
        except Exception as e:
            console.print(f"\nUnexpected error: {e}")

def main():
    """Main entry point."""
    help_script = HelpScript()
    help_script.run()

if __name__ == "__main__":
    main()
