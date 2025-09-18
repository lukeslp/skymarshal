# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is the **Loners** directory within the Skymarshal project. It contains standalone Python scripts that extract specific functionality from the main Skymarshal application. Each script can be run independently and focuses on a particular aspect of Bluesky content management.

The loners are designed as individual CLI scripts that provide focused functionality without requiring the full interactive interface of the main Skymarshal application.

## Development Commands

### Running Individual Scripts
```bash
# Run from the loners directory
python setup.py           # Initial setup & data processing
python auth.py            # Authentication management
python search.py          # Search & filter content
python stats.py           # Statistics & analytics
python delete.py          # Content deletion (with safety checks)
python export.py          # Data export in various formats
python settings.py        # Settings management
python help.py            # Help & documentation
python data_management.py # File operations & backup management
python system_info.py     # System status & diagnostics
python nuke.py            # Nuclear delete (⚠️ DANGER - delete ALL content)

# Universal launcher
python run.py             # Menu-driven launcher for all scripts
```

### Development Prerequisites
```bash
# Install from parent skymarshal directory
cd ../..
make dev                  # Install with development dependencies
# or
pip install -e ".[dev]"
```

### Dependencies and Path Management
All loner scripts automatically add the parent skymarshal directory to the Python path:
```python
sys.path.insert(0, str(Path(__file__).parent.parent))
```
This allows importing from the main `skymarshal` package.

## Architecture Overview

### Script Design Pattern
Each loner script follows a consistent pattern:

1. **Path Setup**: Add parent directory to sys.path for skymarshal imports
2. **Manager Initialization**: Create instances of required manager classes
3. **Settings Management**: Load/save user settings from `~/.car_inspector_settings.json`
4. **Rich Console Interface**: Use Rich library for terminal UI
5. **Error Handling**: Comprehensive error handling with user-friendly messages

### Core Dependencies
- **atproto** (>=0.0.46) - Bluesky AT Protocol client
- **rich** (>=13.0.0) - Terminal UI framework
- **click** (>=8.0.0) - Command-line interface framework

### Shared Manager Classes
All scripts import and use manager classes from the main skymarshal package:

- **`AuthManager`** - Authentication and session management
- **`DataManager`** - File operations, CAR processing, data export/import
- **`UIManager`** - Rich-based terminal interface components
- **`SearchManager`** - Content filtering and search functionality
- **`DeletionManager`** - Safe deletion workflows with multiple confirmation modes
- **`SettingsManager`** - User preferences persistence
- **`HelpManager`** - Context-aware help system

### Data Flow Architecture

1. **Authentication First**: All scripts validate authentication before data operations
2. **Settings Loading**: User preferences loaded from JSON settings file
3. **Data Sources**: Scripts can work with:
   - CAR backup files (`~/.skymarshal/cars/`)
   - JSON export files (`~/.skymarshal/json/`)
   - Direct API data (with rate limiting)
4. **Processing**: Manager classes handle business logic
5. **Output**: Rich-formatted terminal output with progress tracking

## Key Implementation Details

### File System Layout
```
~/.skymarshal/
├── cars/           # CAR backup files (binary AT Protocol format)
└── json/           # JSON exports for analysis

~/.car_inspector_settings.json  # User settings (legacy filename)
```

### Script Categories and Workflow

#### Setup Flow
1. **`setup.py`** - Initial data download and processing
2. **`data_management.py`** - File organization and backup management

#### Analysis Flow
3. **`stats.py`** - Content analytics and engagement patterns
4. **`search.py`** - Advanced filtering and content discovery

#### Action Flow
5. **`export.py`** - Data export in multiple formats
6. **`delete.py`** - Safe content removal with confirmations
7. **`nuke.py`** - Complete content deletion (⚠️ DANGER)

#### Support Flow
8. **`auth.py`** - Authentication troubleshooting
9. **`settings.py`** - Configuration management
10. **`help.py`** - Comprehensive documentation
11. **`system_info.py`** - Diagnostic information

### Common Script Structure
```python
#!/usr/bin/env python3
# Path setup for skymarshal imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Rich console and skymarshal imports
from rich.console import Console
from skymarshal.models import UserSettings
from skymarshal.auth import AuthManager
# ... other managers

class ScriptManager:
    def __init__(self):
        # Settings and manager initialization
        self.settings_file = Path.home() / '.car_inspector_settings.json'
        self.settings = self._load_settings()
        self.ui = UIManager(self.settings)
        self.auth = AuthManager(self.ui)
        # ... other manager instances
```

### Safety Features
- **Authentication Required**: All destructive operations require active authentication
- **Multiple Confirmations**: Deletion operations have layered safety checks
- **Preview Before Action**: Users can see what will be affected before proceeding
- **Error Recovery**: Graceful handling of API errors and network issues
- **Rate Limiting**: Built-in delays respect Bluesky API limits

### AT Protocol Integration
- **CAR File Processing**: Complete account backups with CBOR decoding
- **Handle Normalization**: Automatic conversion of `@username` to `username.bsky.social`
- **URI Format**: `at://did:plc:*/collection/rkey` for content operations
- **Collections**: `app.bsky.feed.post`, `app.bsky.feed.like`, `app.bsky.feed.repost`

## Testing and Quality

### Testing Framework
Tests are located in the parent directory (`../../tests/`):
```bash
cd ../..
make test                 # Run full test suite
python -m pytest tests/unit/ -v          # Unit tests only
python -m pytest tests/integration/ -v   # Integration tests
```

### Code Quality Tools
```bash
cd ../..
make format              # Black + isort formatting
make lint                # flake8 + mypy linting
```

## Important Implementation Notes

### Entry Point Reliability
Due to development environment variations, prefer direct Python execution:
```bash
# Reliable execution methods
python script_name.py
python run.py            # Universal launcher

# May fail in development
skymarshal               # Entry point may have incorrect shebang
```

### Import Path Management
All scripts handle the import path automatically, but they must be run from the `loners/` directory to ensure proper module resolution.

### Settings Persistence
User settings are shared between all scripts and the main Skymarshal application, stored in `~/.car_inspector_settings.json` with the following structure:
- Download limits and batch sizes
- Default content categories
- Performance tuning parameters
- Engagement thresholds

### Error Handling Philosophy
Scripts prioritize user-friendly error messages over technical details, with comprehensive error recovery and graceful degradation when possible.