# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Reference

### Running the Application
```bash
# CLI (interactive menu)
make run                   # Recommended - handles entry point issues
python -m skymarshal       # Direct module execution

# Web Interface (lite version - main dashboard)
python skymarshal/web/lite_app.py    # Port 5050

# Web Interface (full version)
python skymarshal/web/app.py         # Port 5051

# Loners (standalone scripts)
cd loners && python run.py           # Menu-driven launcher
```

### Development Commands
```bash
make dev                   # Install with dev dependencies
make test                  # Run pytest suite
make format                # Black + isort
make lint                  # flake8 + mypy
make check-all             # All quality checks
make build                 # Build distribution packages
```

### Testing
```bash
pytest                                              # Full suite
pytest tests/unit/ -v                               # Unit tests only
pytest tests/integration/ -v                        # Integration tests
pytest tests/unit/test_auth.py::TestAuthManager -v  # Single class
pytest -m "not performance"                         # Skip slow tests
```

## Architecture Overview

Skymarshal is a Bluesky content management toolkit with three interfaces:
- **CLI**: Interactive Rich-based terminal UI (`skymarshal/app.py`)
- **Web Lite**: Streamlined Flask dashboard for search/delete (`skymarshal/web/lite_app.py`)
- **Web Full**: Complete Flask interface with CAR processing (`skymarshal/web/app.py`)

### Manager Pattern
```
InteractiveCARInspector (app.py)
├── AuthManager (auth.py)        # Bluesky authentication & sessions
├── UIManager (ui.py)            # Rich terminal components
├── DataManager (data_manager.py)# CAR files, JSON export/import
├── SearchManager (search.py)    # Content filtering & statistics
├── DeletionManager (deletion.py)# Safe deletion with confirmations
├── SettingsManager (settings.py)# User preferences
└── HelpManager (help.py)        # Context-aware documentation
```

### Data Flow
1. **Auth** → Bluesky credentials validation via AT Protocol
2. **Load** → CAR file download/import or direct API fetch
3. **Analyze** → Filter by engagement, keywords, dates, content type
4. **Act** → Delete with multiple safety confirmation modes
5. **Export** → JSON/CSV output

### Key Data Structures (`models.py`)
- `ContentItem`: Posts/likes/reposts with engagement metadata
- `UserSettings`: Batch sizes, API limits, thresholds
- `SearchFilters`: Comprehensive filtering criteria
- `DeleteMode`, `ContentType`: Type-safe enums

## Project Layout

```
skymarshal/
├── skymarshal/              # Core CLI package
│   ├── app.py               # Main controller (72K)
│   ├── models.py            # Data structures
│   ├── auth.py              # AT Protocol auth
│   ├── data_manager.py      # CAR/JSON operations (74K)
│   ├── search.py            # Filter engine (35K)
│   ├── deletion.py          # Safe deletion workflows
│   ├── ui.py                # Rich terminal UI (40K)
│   └── web/                 # Flask web interfaces
│       ├── lite_app.py      # Streamlined dashboard (port 5050)
│       ├── app.py           # Full interface (port 5051)
│       └── templates/       # Jinja2 templates
├── loners/                  # Standalone CLI scripts
├── bluevibes/               # Profile viewer subproject
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── Makefile                 # Dev commands
└── pyproject.toml           # Build config
```

## Subprojects

### Loners (`loners/`)
Standalone scripts for specific operations. Run from loners directory:
```bash
python search.py          # Search & filter
python stats.py           # Analytics
python delete.py          # Safe deletion
python nuke.py            # Delete ALL (dangerous)
python export.py          # Data export
```

### Bluevibes (`bluevibes/`)
Separate Flask app for Bluesky profile viewing and network analysis.

## AT Protocol Integration

- **Library**: `atproto>=0.0.46`
- **CAR Files**: Binary account backups with CBOR encoding
- **URI Format**: `at://did:plc:*/collection/rkey`
- **Collections**: `app.bsky.feed.post`, `app.bsky.feed.like`, `app.bsky.feed.repost`
- **Handle Format**: `username.bsky.social` (auto-normalized from `@username`)

## File Locations

```
~/.skymarshal/
├── cars/                    # CAR backup files
└── json/                    # JSON exports

~/.car_inspector_settings.json  # User settings (legacy name)
```

## Performance Notes

Optimized for large datasets (10K+ items):
- Single-pass statistics computation
- LRU-cached engagement scores (10K capacity)
- Batch processing with configurable sizes
- Engagement formula: `likes + (2 × reposts) + (2.5 × replies)`

## Code Style

- Python 3.9+ with type hints encouraged
- Black (88 char), isort (black profile)
- Rich console for all terminal output
- Pytest with unit/integration/performance markers

## Web Interface Notes

### Lite App (Port 5050)
Primary web dashboard at `/skymarshal/` path. Features:
- Quick filters: bangers, dead threads, old posts
- Bulk delete with confirmation
- Real-time search

### Full App (Port 5051)
Extended interface with CAR download/processing, setup wizard, and analytics.

### Templates Structure
- `lite_dashboard.html`: Main search/results interface
- `hub.html`: Navigation hub
- `dashboard.html`: Full analytics dashboard
- `cleanup_*.html`: Cleanup workflows

## Safety Features

All destructive operations include:
- Multiple confirmation prompts
- Dry-run preview modes
- Progress tracking with error recovery
- User data isolation by handle
