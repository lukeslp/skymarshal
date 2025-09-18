# Skymarshal Feature & API Reference

Complete documentation for Skymarshal’s interactive interface and programmatic API.

Note on interface: Skymarshal currently runs as an interactive CLI. The subcommand-style examples in this document are a roadmap and reflect planned direct commands. For now, all capabilities are accessible via the guided menus when you run `skymarshal` or `python -m skymarshal`.

## Table of Contents

- [Interactive Interface](#interactive-interface)
- [Planned Direct Subcommands](#planned-direct-subcommands)
- [Authentication Commands](#authentication-commands)
- [Data Management Commands](#data-management-commands)
- [Content Operations Commands](#content-operations-commands)
- [Analysis Commands](#analysis-commands)
- [Utility Commands](#utility-commands)
- [Programmatic API](#programmatic-api)
- [Error Codes](#error-codes)
- [Examples](#examples)

## Interactive Interface

### Basic Usage

```bash
# Start the interactive UI
python -m skymarshal

# Or with the entry point
skymarshal
```

Navigation keys (available on most screens):
- c — continue/confirm
- ? — contextual help
- b — back one screen
- m — return to main menu
- r — refresh data (where applicable)

### Interactive Menu System

The interactive mode presents a hierarchical menu system:

1. **Main Menu** - Primary navigation hub
2. **Search & Analyze** - Content search and filtering
3. **Statistics** - Data analytics and insights
4. **Data Management** - Import/export operations
5. **Authentication** - Login/logout management
6. **Settings** - User preferences
7. **Help** - Contextual help system

### Navigation Commands

- c — Continue/confirm
- ? — Show contextual help
- b — Go back one screen
- m — Return to main menu
- r — Refresh data (where applicable)
- q — Quit application

## Planned Direct Subcommands

The sections below document the planned subcommand-style interface. Today, use the interactive menus to perform these actions.

## Authentication Commands

### `login`

Authenticate with Bluesky using your credentials.

```bash
# Planned
python -m skymarshal login [options]
```

**Options:**
- `--handle <handle>` - Bluesky handle (e.g., `username.bsky.social`)
- `--password <password>` - Account password
- `--interactive` - Prompt for credentials interactively (default)

**Examples:**
```bash
# Interactive login
python -m skymarshal login

# Direct login
python -m skymarshal login --handle username.bsky.social --password mypassword
```

**Output:**
```
Authenticating with Bluesky...
Successfully authenticated as @username.bsky.social
```

### `logout`

Clear authentication session and logout.

```bash
# Planned
python -m skymarshal logout
```

**Output:**
```
Logging out...
Session cleared successfully
```

## Data Management Commands

### `download`

Download your content from Bluesky via API.

```bash
# Planned
python -m skymarshal download [options]
```

**Options:**
- `--limit <number>` - Maximum number of items to download
- `--content-type <type>` - Type of content to download (`posts`, `likes`, `reposts`)
- `--since <date>` - Download content since date (YYYY-MM-DD)
- `--until <date>` - Download content until date (YYYY-MM-DD)

**Examples:**
```bash
# Download all content
python -m skymarshal download

# Download last 100 posts
python -m skymarshal download --limit 100 --content-type posts

# Download content from last month
python -m skymarshal download --since 2024-01-01 --until 2024-01-31
```

### `download-car`

Download complete CAR backup file from Bluesky.

```bash
# Planned
python -m skymarshal download-car [options]
```

**Options:**
- `--output <file>` - Output file path
- `--auto-process` - Automatically process CAR file after download

**Examples:**
```bash
# Download CAR file
python -m skymarshal download-car

# Download with custom filename
python -m skymarshal download-car --output my_backup.car

# Download and process automatically
python -m skymarshal download-car --auto-process
```

### `import-car`

Import existing CAR file.

```bash
# Planned
python -m skymarshal import-car <file> [options]
```

**Arguments:**
- `<file>` - Path to CAR file

**Options:**
- `--validate` - Validate CAR file before import
- `--backup` - Create backup before import

**Examples:**
```bash
# Import CAR file
python -m skymarshal import-car backup.car

# Import with validation
python -m skymarshal import-car backup.car --validate
```

### `export-json`

Export current data to JSON format.

```bash
# Planned
python -m skymarshal export-json [options]
```

**Options:**
- `--output <file>` - Output file path
- `--filtered` - Export only filtered results
- `--pretty` - Pretty-print JSON output

**Examples:**
```bash
# Export all data
python -m skymarshal export-json

# Export with custom filename
python -m skymarshal export-json --output my_data.json

# Export filtered results
python -m skymarshal export-json --filtered --pretty
```

## Content Operations Commands

### `delete-uri`

Delete specific content by URI.

```bash
# Planned
python -m skymarshal delete-uri <uri> [options]
```

**Arguments:**
- `<uri>` - URI of content to delete

**Options:**
- `--confirm` - Skip confirmation prompt
- `--dry-run` - Preview deletion without executing

**Examples:**
```bash
# Delete specific post
python -m skymarshal delete-uri "at://did:plc:abc123/app.bsky.feed.post/xyz789"

# Dry run to preview
python -m skymarshal delete-uri "at://..." --dry-run
```

### `unlike`

Remove likes from your account.

```bash
# Planned
python -m skymarshal unlike [options]
```

**Options:**
- `--limit <number>` - Maximum number of likes to remove
- `--since <date>` - Remove likes since date
- `--confirm` - Skip confirmation prompt
- `--dry-run` - Preview operation without executing

**Examples:**
```bash
# Remove all likes
python -m skymarshal unlike

# Remove last 50 likes
python -m skymarshal unlike --limit 50

# Preview operation
python -m skymarshal unlike --dry-run
```

### `unrepost`

Remove reposts from your account.

```bash
# Planned
python -m skymarshal unrepost [options]
```

**Options:**
- `--limit <number>` - Maximum number of reposts to remove
- `--since <date>` - Remove reposts since date
- `--confirm` - Skip confirmation prompt
- `--dry-run` - Preview operation without executing

**Examples:**
```bash
# Remove all reposts
python -m skymarshal unrepost

# Remove recent reposts
python -m skymarshal unrepost --since 2024-01-01
```

### `nuke`

WARNING: Delete ALL content from your account.

```bash
# Planned
python -m skymarshal nuke [options]
```

**Options:**
- `--confirm` - Skip confirmation prompt
- `--dry-run` - Preview operation without executing
- `--backup` - Create backup before deletion

**Examples:**
```bash
# Nuclear option (use with extreme caution!)
python -m skymarshal nuke

# Preview what would be deleted
python -m skymarshal nuke --dry-run
```

## Analysis Commands

### `stats`

Show content statistics and analytics.

```bash
# Planned
python -m skymarshal stats [options]
```

**Options:**
- `--detailed` - Show detailed statistics
- `--export <file>` - Export statistics to file
- `--format <format>` - Output format (`table`, `json`, `csv`)

**Examples:**
```bash
# Show basic statistics
python -m skymarshal stats

# Show detailed statistics
python -m skymarshal stats --detailed

# Export statistics
python -m skymarshal stats --export stats.json --format json
```

### `search`

Interactive search and filtering.

```bash
# Planned
python -m skymarshal search [options]
```

**Options:**
- `--query <text>` - Search query
- `--content-type <type>` - Filter by content type
- `--min-engagement <score>` - Minimum engagement score
- `--since <date>` - Filter by date range
- `--export <file>` - Export results

**Examples:**
```bash
# Interactive search
python -m skymarshal search

# Search for specific text
python -m skymarshal search --query "python programming"

# Search with filters
python -m skymarshal search --content-type posts --min-engagement 10
```

### `dead-threads`

Find posts with no engagement (dead threads).

```bash
# Planned
python -m skymarshal dead-threads [options]
```

**Options:**
- `--threshold <score>` - Engagement threshold (default: 0)
- `--since <date>` - Filter by date range
- `--export <file>` - Export results
- `--delete` - Delete dead threads (with confirmation)

**Examples:**
```bash
# Find dead threads
python -m skymarshal dead-threads

# Find threads with very low engagement
python -m skymarshal dead-threads --threshold 1

# Export dead threads for review
python -m skymarshal dead-threads --export dead_threads.json
```

## Utility Commands

### `backup-car`

Create timestamped backup of current data.

```bash
# Planned
python -m skymarshal backup-car [options]
```

**Options:**
- `--output <file>` - Custom backup filename
- `--compress` - Compress backup file

**Examples:**
```bash
# Create automatic backup
python -m skymarshal backup-car

# Create custom backup
python -m skymarshal backup-car --output my_backup_2024.car
```

### `validate-data`

Validate current data integrity.

```bash
# Planned
python -m skymarshal validate-data [options]
```

**Options:**
- `--fix` - Attempt to fix validation errors
- `--detailed` - Show detailed validation report

**Examples:**
```bash
# Validate data
python -m skymarshal validate-data

# Validate and fix issues
python -m skymarshal validate-data --fix
```

## 🔌 Programmatic API

### Basic Usage

```python
from skymarshal import InteractiveCARInspector
from skymarshal.models import SearchFilters, ContentType

# Initialize application
app = InteractiveCARInspector()

# Authenticate
app.authenticate("username.bsky.social", "password")

# Download data
app.download_data()

# Search content
filters = SearchFilters(
    content_type=ContentType.POSTS,
    keyword="python",
    min_engagement_score=5
)
results = app.search_content(filters)

# Process results
for item in results:
    print(f"Post: {item.text[:100]}...")
    print(f"Engagement: {item.engagement_score}")
```

### Manager Classes

#### AuthManager

```python
from skymarshal.auth import AuthManager

auth_manager = AuthManager()

# Authenticate
success = auth_manager.authenticate_client("username.bsky.social", "password")

# Check authentication status
if auth_manager.is_authenticated():
    print(f"Authenticated as {auth_manager.current_handle}")

# Normalize handle
normalized = auth_manager.normalize_handle("@username")
# Returns: "username.bsky.social"
```

#### DataManager

```python
from skymarshal.data_manager import DataManager

data_manager = DataManager()

# Download data
data_manager.download_data(limit=100)

# Import CAR file
data_manager.import_car_file("backup.car")

# Export to JSON
data_manager.export_to_json("output.json")
```

#### SearchManager

```python
from skymarshal.search import SearchManager
from skymarshal.models import SearchFilters, ContentType

search_manager = SearchManager()

# Build search filters
filters = SearchFilters(
    content_type=ContentType.POSTS,
    keyword="python",
    min_engagement_score=10,
    date_range=("2024-01-01", "2024-12-31")
)

# Execute search
results = search_manager.search_content(filters)

# Get engagement statistics
stats = search_manager.get_engagement_stats(results)
```

#### DeletionManager

```python
from skymarshal.deletion import DeletionManager
from skymarshal.models import DeleteMode

deletion_manager = DeletionManager()

# Delete content with confirmation
items_to_delete = [item1, item2, item3]
success = deletion_manager.delete_content(items_to_delete, DeleteMode.INDIVIDUAL)

# Dry run (preview only)
preview = deletion_manager.preview_deletion(items_to_delete)
```

## Error Codes

| Code | Description | Solution |
|------|-------------|----------|
| `AUTH_001` | Authentication failed | Check credentials and handle format |
| `AUTH_002` | Session expired | Re-authenticate with `login` command |
| `DATA_001` | File not found | Check file path and permissions |
| `DATA_002` | Invalid file format | Ensure file is valid JSON or CAR format |
| `API_001` | Rate limit exceeded | Wait and retry, or use CAR download |
| `API_002` | Network error | Check internet connection |
| `DEL_001` | Deletion failed | Check content URI and permissions |
| `DEL_002` | Confirmation required | Provide confirmation or use `--confirm` |

## Examples

Note: These examples illustrate the planned direct subcommand interface. Today, use the interactive UI to perform the same actions via menus.

### Complete Workflow Example

```bash
# 1. Authenticate
python -m skymarshal login

# 2. Download data
python -m skymarshal download-car --auto-process

# 3. Analyze content
python -m skymarshal stats --detailed

# 4. Find dead threads
python -m skymarshal dead-threads --threshold 0

# 5. Search for specific content
python -m skymarshal search --query "python" --min-engagement 5

# 6. Export results
python -m skymarshal export-json --output analysis.json
```

### Batch Operations Example

```bash
# Remove old likes
python -m skymarshal unlike --since 2023-01-01 --limit 100

# Remove old reposts
python -m skymarshal unrepost --since 2023-01-01 --limit 50

# Clean up dead threads
python -m skymarshal dead-threads --threshold 0 --delete
```

### Automation Example

```bash
#!/bin/bash
# Daily cleanup script

# Authenticate
python -m skymarshal login --handle $BSKY_HANDLE --password $BSKY_PASSWORD

# Download fresh data
python -m skymarshal download-car --auto-process

# Find and remove dead threads
python -m skymarshal dead-threads --threshold 0 --delete --confirm

# Export statistics
python -m skymarshal stats --export daily_stats_$(date +%Y%m%d).json

echo "Daily cleanup completed"
```

---

For more examples and advanced usage patterns, see the [Architecture Guide](ARCHITECTURE.md).
