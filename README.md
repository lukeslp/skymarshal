# Skymarshal

Your personal Bluesky content command center — manage, analyze, and clean up your social media presence with ease.

# THIS IS A WORK IN PROGRESS. 
## Non-critical functions may be buggy or broken. 
### [Bluesky: @lukesteuber.com](https://bluesky.app/profile/lukesteuber.com)
### [lukesteuber.com](https://lukesteuber.com)

<br>

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
![License](https://img.shields.io/badge/license-MIT-green)
[![AT Protocol](https://img.shields.io/badge/AT%20Protocol-Compatible-green.svg)](https://atproto.com/)

## Development Log

> Status snapshot for **Skymarshal**. See [CHANGELOG](./CHANGELOG.md) for full history.

### Completed
- [x] **Secure auth**
  - Session-based login with Bluesky credentials
  - No password storage; temporary session tokens only
  - Handle normalization and guardrails to restrict access to own content
- [x] **CAR processing, download, and backup**
  - Create and import CAR archives (with resume + progress)
  - Integrity checks and local backup directory structure
  - Graceful handling of empty/partial CARs
- [x] **⚡ Engagement cache optimization** (NEW in v0.2.0)
  - 75% reduction in API calls via increased batch size (25 → 100)
  - 90% reduction on repeat loads via SQLite caching
  - Intelligent TTL based on post age
  - See [CACHE_OPTIMIZATION.md](./CACHE_OPTIMIZATION.md) for details

### 🧪 In Testing
- [ ] **Follower/Following reconciliation**
  - Diff local vs live graph; handle suspended/deleted accounts
  - Optional CSV/JSON export of deltas
- [ ] **Flask web interface (read-only MVP)**
  - Auth handshake, backup trigger, basic search/view of items
  - Simple analytics cards (top posts, dead threads)

### 🔧 Notes
- CLI currently menu-driven; subcommands on the roadmap
- Destructive ops remain gated behind explicit confirm flows
- Large accounts: prefer CAR workflows for speed and stability
- **Performance**: New caching system makes skymarshal 10x faster on large accounts

## What Skymarshal Does For You

### Keep Your Account Secure
- Log in safely with your existing Bluesky credentials
- Your data stays private and local to your computer
- No passwords stored - only temporary session access
- Access only your own content with built-in user protection

### Get Your Data When You Need It
- Download all your posts, likes, and reposts in minutes
- See real-time progress so you know exactly what's happening
- Pick up where you left off if something interrupts the process
- Choose what content to download - posts only, everything, or custom selections

### Find What You're Looking For
- Search through thousands of posts instantly using keywords or dates
- Discover your most and least popular content automatically
- Filter by engagement levels to find your hits and misses
- Get personalized categories based on your actual performance (not generic thresholds)

### Clean Up Your Profile Safely
- Preview exactly what will be deleted before you commit
- Delete one post at a time, in batches, or everything at once
- Get multiple confirmation prompts so you never delete by accident
- See progress bars during deletion so you know it's working

### Understand Your Bluesky Performance
- See which posts resonated with your audience and which didn't
- Understand your engagement patterns over time
- Identify your "dead threads" that got no interaction
- Discover your "bangers" that performed above average
- Track your posting habits and peak activity times

## Quick Start

### Installation

#### From PyPI (Recommended)

```bash
# Install via pip
pip install skymarshal

# Or in a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install skymarshal
```

#### From Source

```bash
# Clone the repository
git clone https://github.com/lukeslp/skymarshal.git
cd skymarshal

# (Recommended) Create and activate a virtualenv
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install (development mode)
pip install -e .

# Or install with dev extras
pip install -e ".[dev]"
```

### Usage

Skymarshal currently runs as an interactive terminal app. Start it and follow the guided menus.

```bash
# Easiest way
skymarshal

# Or via Python module
python -m skymarshal

# Or with the Makefile helper
make run
```

What you can do from the menus:
- Authenticate with Bluesky
- Create and process complete backups (CAR files)
- Import existing backups and export to JSON/CSV
- Search and filter by keywords, content types, and engagement
- Review stats and analytics
- Safely delete content with multiple confirmation flows

## Feature Reference

Skymarshal exposes all functionality through the interactive UI. A direct subcommand-style CLI is on the roadmap; until then, use the menus for these capabilities:

- Authentication: login/logout, handle normalization
- Data: create backups (CAR), import/process backups, export JSON/CSV
- Search & Analyze: filters, engagement scoring, dead thread detection
- Content Operations: delete by criteria with review/confirm/batch modes
- Statistics: content overview, engagement metrics, temporal breakdowns

## Safety Features

All destructive operations include multiple safety layers:
- Confirmation Prompts: Multiple verification steps
- Dry-run Modes: Preview operations without execution
- Progress Tracking: Real-time feedback with error handling
- Individual Approval: Review each item before deletion
- Batch Processing: Handle large operations safely
- Undo Capabilities: Temporary backups before permanent changes

## Architecture

Skymarshal uses a modular architecture with clear separation of concerns:

### Core Modules
- **`app.py`** - Main application controller and CLI orchestration
- **`models.py`** - Data structures (`ContentItem`, `UserSettings`, `SearchFilters`)
- **`auth.py`** - Authentication and session management (`AuthManager`)
- **`ui.py`** - User interface components and Rich displays (`UIManager`)
- **`data_manager.py`** - Data export/import and file operations (`DataManager`)
- **`search.py`** - Content search and filtering engine (`SearchManager`)
- **`deletion.py`** - Safe deletion workflows (`DeletionManager`)
- **`settings.py`** - User settings persistence (`SettingsManager`)
- **`help.py`** - Help system and documentation (`HelpManager`)
- **`banner.py`** - Startup sequences and visual elements

### Data Flow
1. **Authentication** → Validate Bluesky credentials
2. **Data Loading** → Download/import content from multiple sources
3. **Analysis** → Search, filter, and analyze content
4. **Operations** → Safe deletion with multiple confirmation modes
5. **Export** → Save results in various formats

## Troubleshooting

### Installation Issues

**Entry point issues** (editable installs during development):
```bash
# If the skymarshal command isn’t found, use module execution
python -m skymarshal

# Or use the Makefile
make run
```

**Multiple Python Versions**:
```bash
# Use the same Python for install and execution
python -m pip install -e .
python -m skymarshal
```

### Common Issues

| Issue | Solution |
|-------|----------|
| **"Module not found"** | Use `python -m skymarshal` instead of `skymarshal` command |
| **CBOR decoding errors** | Install libipld: `pip install libipld` |
| **Authentication failures** | Check handle format: `username.bsky.social` (not `@username`) |
| **File access denied** | Each user's data is isolated by handle for security |
| **Empty CAR import** | Some CAR files lack commit records - app handles this automatically |
| **Deletion failures** | Fixed in latest version - update your installation |

### Data & File Locations

- **Settings**: `~/.car_inspector_settings.json`
- **CAR Files**: `~/.skymarshal/cars/`
- **JSON Exports**: `~/.skymarshal/json/`

### Performance Tips

- **Large datasets**: Use CAR files for faster processing
- **Slow downloads**: CAR downloads are typically faster than API calls
- **Memory usage**: Process data in batches for large accounts
- **Rate limiting**: Built-in delays respect Bluesky API limits
- **⚡ NEW - Engagement cache**: Automatically caches engagement data for 90% faster repeat loads
  - First load: 75% fewer API calls (batch size 100 vs 25)
  - Subsequent loads: Uses local cache (near-instant)
  - See [CACHE_OPTIMIZATION.md](./CACHE_OPTIMIZATION.md) for details

## Development

### Prerequisites
- Python 3.8 or higher
- Git
- pip (or pipenv/poetry)

### Development Setup

```bash
# Clone and setup
git clone https://github.com/lukeslp/skymarshal.git
cd skymarshal

# Create virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# Run the application
make run
```

### Development Commands

```bash
# Code quality
make format          # Format with black + isort
make lint           # Run flake8 + mypy
make test           # Run pytest

# Build and distribution
make build          # Build distribution packages
make clean          # Clean build artifacts

# All-in-one development check
make check-all      # Format + lint + test
```

### Project Structure

```
skymarshal/
├── skymarshal/           # Main package
│   ├── app.py            # Main application controller
│   ├── models.py         # Data structures and enums
│   ├── auth.py           # Authentication management
│   ├── ui.py             # User interface components
│   ├── data_manager.py   # Data operations
│   ├── search.py         # Search and filtering
│   ├── deletion.py       # Safe deletion workflows
│   ├── settings.py       # Settings management
│   ├── help.py           # Help system
│   └── banner.py         # Startup sequences
├── tests/                # Test suite
├── internal/             # Internal docs, prototypes, and build artifacts
├── Makefile             # Development commands
├── pyproject.toml       # Project configuration
└── requirements*.txt    # Dependencies
```

### Contributing

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Make your changes** following the code style guidelines
4. **Run tests**: `make test`
5. **Format code**: `make format`
6. **Commit changes**: `git commit -m 'Add amazing feature'`
7. **Push to branch**: `git push origin feature/amazing-feature`
8. **Open a Pull Request**

### Code Style

- **Formatting**: Black (88 character line length)
- **Import sorting**: isort with black-compatible profile
- **Type hints**: Encouraged for all functions
- **Documentation**: Comprehensive docstrings for all modules
- **Testing**: pytest for unit and integration tests

## Documentation

- **[Architecture Guide](ARCHITECTURE.md)** - Detailed system design and component relationships
- **[API Reference](API.md)** - Complete CLI command documentation
- **[Contributing Guide](CONTRIBUTING.md)** - Guidelines for contributors
- **[Changelog](CHANGELOG.md)** - Version history and changes
  
For development setup and best practices, see the [Contributing Guide](CONTRIBUTING.md).

## Contributing

Contributions are welcome! See the [Contributing Guide](CONTRIBUTING.md) for:
- Code style and standards
- Testing requirements
- Pull request process
- Issue reporting

## License

MIT License. See [LICENSE](LICENSE) for details.

## Maintainer

Luke Steuber — [dr.eamer.dev](https://dr.eamer.dev)
Website: [dr.eamer.dev](https://dr.eamer.dev)
Bluesky: [@dr.eamer.dev](https://bsky.app/profile/dr.eamer.dev)
GitHub: [github.com/lukeslp](https://github.com/lukeslp)

---

## Acknowledgments

- **AT Protocol Team** for the excellent `atproto` Python library
- **Rich Library** for beautiful terminal interfaces
- **Bluesky Team** for building the decentralized social web
- **Open Source Community** for inspiration and collaboration

---


