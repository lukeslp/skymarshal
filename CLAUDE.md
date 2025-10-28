# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

Skymarshal is a comprehensive Bluesky content management tool for analyzing, filtering, and cleaning up social media presence. It provides both interactive CLI and web interfaces for managing posts, likes, and reposts using the AT Protocol.

## Development Commands

### Essential Commands
```bash
# Development setup
make dev                    # Install with development dependencies
make install               # Install in editable mode

# Running the application
make run                   # Reliable execution (handles entry point issues)
python -m skymarshal       # Direct module execution (PREFERRED)
skymarshal                 # Entry point (may fail in dev environments)

# Web Interface
cd skymarshal/web
python run.py              # Full web interface on port 5051
python lite_app.py         # Lightweight interface on port 5050

# Testing
make test                  # Run full test suite with pytest
python -m pytest tests/unit/ -v          # Unit tests only
python -m pytest tests/integration/ -v   # Integration tests only
python -m pytest -m "not performance"    # Skip slow performance tests
python -m pytest tests/unit/test_auth.py::TestAuthManager::test_normalize_handle -v  # Single test

# Code Quality
make format                # Format with black + isort
make lint                  # Run flake8 + mypy
make clean                 # Clean build artifacts
make check-all             # All-in-one: format + lint + test

# Distribution
make build                 # Build distribution packages
make publish-test          # Publish to Test PyPI
make publish               # Publish to PyPI
make setup-dist            # Set up for distribution (run tests, build, check)
make test-install          # Test package installation
make clean-dist            # Clean distribution artifacts
```

### Additional Commands Available
```bash
# Makefile help
make help                  # Show all available commands with descriptions

# Development utilities
make clean                 # Clean build artifacts and __pycache__
```

### Testing Framework
- **63+ comprehensive tests** across unit and integration categories
- **Pytest with custom fixtures** for AT Protocol mocking
- **Markers**: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.performance`
- **Mock data generators** in `tests/fixtures/mock_data.py`
- **Authentication mocking** with realistic AT Protocol responses

## Architecture Overview

### Manager Pattern Design
The application follows a **modular manager pattern** where each functional area is encapsulated in a dedicated manager class:

```
InteractiveContentManager (app.py)
├── AuthManager (auth.py) - Authentication & session management
├── UIManager (ui.py) - Rich terminal interface components
├── DataManager (data_manager.py) - File operations & API data handling
├── SearchManager (search.py) - Content filtering & search engine
├── DeletionManager (deletion.py) - Safe deletion workflows
├── SettingsManager (settings.py) - User preferences & persistence
├── HelpManager (help.py) - Context-aware help system
└── EngagementCache (engagement_cache.py) - SQLite-based caching

Services Layer (NEW in v0.2.0+)
└── ContentService (services/content_service.py) - Unified API for web/CLI
    ├── login() - Authentication
    ├── ensure_content_loaded() - Data loading with caching
    ├── search() - Unified search interface
    └── delete() - Safe deletion with cache updates
```

### Web Interface Architecture

**Two Flask-based web applications** (`skymarshal/web/`):

**1. Full Interface (app.py - port 5051)** - Comprehensive workflow:
```
Skymarshal Full Web (app.py)
├── Routes:
│   ├── /login - Authentication
│   ├── /setup - CAR download & data selection
│   ├── /dashboard - Main interface with search/stats
│   ├── /search - Content filtering API
│   ├── /delete - Bulk deletion API
│   └── /nuke - Nuclear delete with multiple confirmations
├── Real-time Features:
│   ├── Server-Sent Events (SSE) for progress tracking
│   ├── CAR download progress streaming
│   └── Data processing progress updates
├── Features:
│   ├── Complete CAR file processing workflow
│   ├── Content type selection (posts/likes/reposts)
│   ├── Engagement analytics and overview cards
│   └── Advanced filtering and bulk operations
└── Security:
    ├── Session-based authentication (no password storage)
    ├── User data isolation by handle
    └── Multiple confirmation layers for deletion
```

**2. Lightweight Interface (lite_app.py - port 5050)** - Streamlined for quick operations:
```
Litemarshal (lite_app.py)
├── Routes:
│   ├── /login - Quick authentication
│   ├── /dashboard - Immediate search interface
│   ├── /search - Fast content filtering
│   └── /delete - Direct deletion with confirmation
├── Focus:
│   ├── **PRIMARY GOAL**: Search and delete posts/replies
│   ├── Minimal workflow: login → search → delete
│   ├── Lightweight UI with dark theme
│   └── No CAR processing - loads existing data only
└── Use Case:
    └── Quick cleanup operations without full setup workflow
```

**Key Differences**:
- **Full (app.py)**: Complete data management, CAR downloads, analytics
- **Lite (lite_app.py)**: Fast search and deletion only, assumes data already loaded

**Templates**:
- `base.html` - Navigation and layout
- `login.html` - Authentication page
- `setup.html` - CAR download and data selection (with SSE progress)
- `dashboard.html` - Main interface with search and results
- `nuke.html` - ⚠️ Nuclear delete with triple confirmation

### Core Data Structures (models.py)
- **`ContentItem`**: Represents Bluesky content (posts, likes, reposts) with engagement metadata
- **`UserSettings`**: User preferences including batch sizes, API limits, engagement thresholds, cache settings
- **`SearchFilters`**: Comprehensive filtering criteria for content search
- **`SearchRequest`** (services): Structured search parameters for web/API
- **`SearchResult`** (services): Serialized content for UI consumers
- **Enums**: `DeleteMode`, `ContentType` for type-safe operations
- **Utilities**: `parse_datetime()`, `merge_content_items()`, engagement score calculation with LRU cache

### Data Flow Architecture
1. **Authentication** (AuthManager) → Validate Bluesky credentials with session management
2. **Data Loading** (DataManager) → Download/import from CAR files, JSON exports, or direct API
3. **Caching** (EngagementCache) → 90% reduction in API calls via SQLite cache
4. **Analysis** (SearchManager + UIManager) → Filter, search, and compute statistics
5. **Operations** (DeletionManager) → Safe deletion with multiple confirmation modes
6. **Export** (DataManager) → Save results in JSON/CSV formats

### AT Protocol Integration
- **CAR File Processing**: Complete Bluesky account backups with CBOR decoding
- **API Operations**: `atproto` library for posts, likes, reposts via `com.atproto.repo.*`
- **Rate Limiting**: Built-in delays and batch processing respect API limits
- **Handle Normalization**: Automatic conversion of `@username` to `username.bsky.social`

### Performance Optimizations (v0.2.0+)

**⚡ Engagement Cache System** (see [CACHE_OPTIMIZATION.md](./CACHE_OPTIMIZATION.md)):
- **SQLite caching** at `~/.skymarshal/engagement_cache.db`
- **75% reduction in API calls** (batch size 25 → 100)
- **90% reduction on repeat loads** via local cache
- **Intelligent TTL**: 1h (fresh posts), 6h (week-old), 24h (old posts)
- **Automatic expiration** and cleanup
- **Enabled by default** with user toggle in settings

Recent optimizations for large datasets (10K+ items):
- **Single-pass statistics computation** (6x faster than previous implementation)
- **Combined filtering engine** (4x faster for complex searches)
- **LRU-cached engagement calculations** with 10,000 item capacity
- **Memory-efficient merging** with single-pass categorization
- **Batch processing** with configurable worker limits

## Key Implementation Details

### Interactive vs Web Modes
- **CLI Interface**: Rich-based interactive menu system (primary)
- **Web Interface**: Flask app with SSE for real-time updates
- **Service Layer**: Shared business logic via `ContentService`
- **Navigation**: Comprehensive back/forward navigation with context-aware help

### Authentication System
- **Session Management**: Persistent authentication with re-auth flows
- **Security**: User data isolation by handle, secure file access validation
- **Error Handling**: Automatic retry with user-friendly error messages
- **Web Sessions**: Flask session cookies with secure configuration

### Content Management Workflow
1. **Data Source Priority**:
   - CAR file download & processing (recommended - fastest)
   - Load existing JSON/CAR files
   - Direct API download (slowest, rate-limited)
2. **Analysis Phase**: Filter by engagement, keywords, content type, date ranges
3. **Safety Features**: Multiple deletion confirmation modes (all-at-once, individual, batch)

### Nuclear Delete Feature (NEW)
**Endpoint**: `/nuke` (GET/POST)

**Safety Confirmations**:
1. Type exact phrase: `DELETE ALL {handle}`
2. Check final confirmation checkbox
3. Browser confirmation dialog
4. Displays total counts before execution

**Implementation** (`skymarshal/web/app.py:1383-1498`):
- Loads all content for authenticated user
- Validates exact confirmation phrase
- Requires checkbox confirmation
- Uses `DeletionManager.delete_items_batch()` with `DeleteMode.ALL_AT_ONCE`
- Clears session data after successful deletion

### File System Structure
```
~/.skymarshal/
├── engagement_cache.db    # SQLite engagement cache (NEW in v0.2.0)
├── backups/               # CAR file backups (binary AT Protocol format)
├── cars/                  # Alternative CAR file location
└── json/                  # JSON exports for analysis

~/.car_inspector_settings.json  # User settings (legacy filename)
```

### Configuration and Settings
- **User Settings**: Batch sizes (1-100), API limits, engagement thresholds, cache toggle
- **Performance Tuning**: Worker counts, page sizes, fetch order (newest/oldest)
- **Engagement Scoring**: Weighted formula: `likes + (2 × reposts) + (2.5 × replies)` (see `models.py:calculate_engagement_score`)
- **Cache Settings**: `engagement_cache_enabled` (default: True), `hydrate_batch_size` (default: 100)

## Development Guidelines

### Code Style and Standards
- **Python 3.9+** (minimum version from pyproject.toml) with type hints encouraged
- **Black formatting** (88 character line length)
- **isort** with black-compatible profile
- **MyPy type checking** with moderate strictness (defined in pyproject.toml)
- **Flake8** for linting with default configuration
- **Rich console** for all UI output (shared instance in `models.console`)

### Testing Approach
- **Unit Tests**: Manager classes tested in isolation with comprehensive mocking
- **Integration Tests**: End-to-end workflows with file system operations
- **Performance Tests**: Large dataset handling (marked separately)
- **AT Protocol Mocking**: Realistic API responses for authentication and data operations
- **Service Layer Tests**: `tests/unit/test_content_service.py` for unified API

### Entry Point Issues
Due to editable installs in development environments:
- **Prefer**: `make run` or `python -m skymarshal`
- **Avoid**: Direct `skymarshal` command during development
- **Production**: Entry point works correctly in distributed packages

### Error Handling Patterns
- **Rich-formatted errors** for user-facing messages
- **Silent failures** with graceful degradation where appropriate
- **Progress tracking** with error recovery for long operations
- **Authentication validation** with automatic retry flows

### Working with the Service Layer
The `ContentService` class (introduced for web interface) provides a unified API:

```python
from skymarshal.services import ContentService, SearchRequest

# Initialize service
service = ContentService(
    settings_path=Path.home() / ".car_inspector_settings.json",
    storage_root=Path.home() / ".skymarshal"
)

# Authentication
service.login(handle="user.bsky.social", password="app-password")

# Load content (with automatic caching)
items = service.ensure_content_loaded(
    categories=["posts", "likes"],
    limit=1000
)

# Search with filters
request = SearchRequest(
    keyword="bluesky",
    min_engagement=10,
    content_types=["posts"]
)
results, total = service.search(request)

# Delete content
deleted_count, errors = service.delete(uris=[item.uri for item in results])
```

## Important Notes

### AT Protocol Specifics
- **URI Format**: `at://did:plc:*/collection/rkey` for all content operations
- **Collections**: `app.bsky.feed.post`, `app.bsky.feed.like`, `app.bsky.feed.repost`
- **CAR Files**: Binary format containing complete account history with CBOR encoding
- **Rate Limits**: Respected through batch processing and built-in delays
- **Batch Limit**: 100 items per `get_posts` call (Bluesky API maximum)

### Security Considerations
- **User Data Isolation**: Each handle's data is strictly separated
- **File Access Validation**: Users can only access their own data files
- **Authentication Security**: Passwords never stored, sessions managed securely
- **Safe Deletion**: Multiple confirmation layers prevent accidental data loss
- **Web Sessions**: Secure cookie settings, HTTPONLY, SameSite=Lax

### Performance Considerations
- **Large Datasets**: Optimized for accounts with 10K+ items
- **Memory Management**: Single-pass algorithms minimize memory footprint
- **Caching**: LRU cache for frequently computed values (engagement scores)
- **Batch Processing**: Configurable batch sizes for different operations
- **SQLite Cache**: Persistent engagement data reduces API load by 90%

### Production Deployment with Systemd

**Current Deployment**: Both web interfaces run as systemd services at **dr.eamer.dev**

#### Systemd Services

**Skymarshal Service** (Full Interface):
```bash
# Service management
sudo systemctl status skymarshal      # Check status
sudo systemctl restart skymarshal     # Restart service
sudo systemctl stop skymarshal        # Stop service
sudo systemctl start skymarshal       # Start service

# View logs
sudo journalctl -u skymarshal -f      # Follow logs in real-time
sudo journalctl -u skymarshal -n 50   # View last 50 lines

# Service details
# - Port: 5051
# - URL: https://dr.eamer.dev/skymarshal/
# - Config: /etc/systemd/system/skymarshal.service
# - User: coolhand
# - WorkingDirectory: /home/coolhand/projects/tools_bluesky/skymarshal
```

**Litemarshal Service** (Lightweight Interface):
```bash
# Service management
sudo systemctl status litemarshal
sudo systemctl restart litemarshal
sudo systemctl stop litemarshal
sudo systemctl start litemarshal

# View logs
sudo journalctl -u litemarshal -f
sudo journalctl -u litemarshal -n 50

# Service details
# - Port: 5050
# - URL: https://dr.eamer.dev/litemarshal/
# - Config: /etc/systemd/system/litemarshal.service
```

#### Caddy Reverse Proxy Configuration

Located at `/etc/caddy/Caddyfile`:
```caddyfile
# Litemarshal
handle_path /litemarshal* {
    reverse_proxy localhost:5050
}

# Skymarshal
handle_path /skymarshal/* {
    reverse_proxy localhost:5051
}
```

To reload Caddy after config changes:
```bash
sudo systemctl reload caddy
sudo systemctl status caddy
```

#### Flask Configuration for Subpath Deployment

Both apps use `PrefixMiddleware` to handle subpath routing:

**Skymarshal** (`skymarshal/web/app.py`):
- `APPLICATION_ROOT = '/skymarshal'` - Handles subpath deployment
- Session cookie path set to `/skymarshal`

**Litemarshal** (`skymarshal/web/lite_app.py`):
- `PrefixMiddleware` with prefix `/litemarshal`
- Session cookie path set to `/litemarshal`

Both use:
- `ProxyFix` middleware for proper header handling behind reverse proxy
- Session-based authentication with secure cookies
- HTTPONLY and SameSite=Lax cookie settings

#### Troubleshooting Production Deployment

**Services won't start**:
```bash
# Check service status
sudo systemctl status skymarshal litemarshal

# Reload systemd daemon after changes
sudo systemctl daemon-reload
sudo systemctl restart skymarshal litemarshal
```

**URL not accessible**:
```bash
# Test direct port access
curl -I http://localhost:5050/
curl -I http://localhost:5051/

# Test through proxy
curl -I https://dr.eamer.dev/litemarshal/
curl -I https://dr.eamer.dev/skymarshal/
```

**Password Authentication**:
- Both apps accept app passwords (recommended) and regular passwords (with warning)
- App passwords: 19-character format `xxxx-xxxx-xxxx-xxxx`
- Regular passwords show security warning but work

#### Production Recommendations

For production deployment, consider:

1. **Use Gunicorn instead of Flask dev server**:
   ```bash
   # In systemd service file:
   ExecStart=/usr/bin/gunicorn -w 4 -b 0.0.0.0:5051 \
       --chdir /path/to/skymarshal/web app:app
   ```

2. **Enable HTTPS session cookies** (already behind HTTPS proxy):
   ```python
   app.config['SESSION_COOKIE_SECURE'] = True
   ```

3. **Set up log rotation** for journald logs

4. **Monitor service health** with monitoring tools

5. **Regular security audits** for password handling

See [SYSTEMD_SETUP.md](./SYSTEMD_SETUP.md) for complete deployment documentation.

## Common Development Patterns

### Adding New Manager Classes
When creating a new manager, follow this pattern:
1. Inherit from base class if applicable
2. Accept `console` parameter for UI consistency
3. Use `@staticmethod` for pure utility functions
4. Add comprehensive error handling with Rich formatting
5. Include type hints for all parameters and returns

### Working with AT Protocol Data
- **Content URIs**: Always use format `at://did:plc:{identifier}/{collection}/{rkey}`
- **Error Handling**: Wrap atproto calls with try/except for network failures
- **Rate Limiting**: Use built-in delays between API calls (see `data_manager.py`)
- **Authentication**: Check `self.auth_manager.client` before API operations

### Testing New Features
1. Add unit tests in `tests/unit/test_{module}.py`
2. Use existing mock fixtures from `tests/fixtures/mock_data.py`
3. Add integration tests for end-to-end workflows
4. Mark performance tests with `@pytest.mark.performance`
5. Run targeted tests: `pytest tests/unit/test_module.py::TestClass::test_method -v`

### Adding Web Interface Features
1. Add route in `skymarshal/web/app.py`
2. Use `@login_required` decorator for authenticated routes
3. Leverage existing managers via helper functions (`get_auth_manager()`, etc.)
4. Return JSON for API endpoints, templates for pages
5. Add corresponding template in `skymarshal/web/templates/`
6. Use SSE for long-running operations

## Loners Subdirectory

The `loners/` directory contains standalone Python scripts that extract specific functionality from the main Skymarshal application. Each script can be run independently:

### Loners Scripts
```bash
# Core scripts (run from loners/ directory)
python run.py             # Menu-driven launcher for all scripts
python auth.py            # Authentication management
python search.py          # Search & filter content
python stats.py           # Statistics & analytics
python delete.py          # Content deletion (with safety checks)
python export.py          # Data export in various formats
python settings.py        # Settings management
python data_management.py # File operations & backup management
python system_info.py     # System status & diagnostics
python nuke.py            # Nuclear delete (⚠️ DANGER - delete ALL content)

# Analysis tools
python analyze.py         # Content analysis
python find_bots.py       # Bot detection
python cleanup.py         # Cleanup operations
python ratio_analysis.py  # Engagement ratio analysis
python inactive_detection.py  # Inactive user detection
```

### Loners Architecture
- **Standalone**: Each script is independent and self-contained
- **Focused**: Single responsibility per script
- **CLI-based**: Direct command-line interfaces vs main app's interactive menus
- **Shared utilities**: Common functions in `common.py`
- **Separate settings**: May use different configuration approaches than main app

## Documentation Files

Comprehensive documentation is available in the repository:

- **[README.md](README.md)** - Quick start, features, installation
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Detailed system design and patterns
- **[DEVELOPMENT.md](DEVELOPMENT.md)** - Development setup and workflows
- **[CACHE_OPTIMIZATION.md](CACHE_OPTIMIZATION.md)** - Performance improvements in v0.2.0
- **[API.md](API.md)** - Complete CLI command documentation
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Contribution guidelines
- **[CHANGELOG.md](CHANGELOG.md)** - Version history
- **[skymarshal/web/README.md](skymarshal/web/README.md)** - Web interface documentation

## Recent Changes & Next Steps

### Completed Features (v0.2.0+)
- ✅ SQLite engagement cache (90% API call reduction)
- ✅ Increased batch size to 100 (75% API call reduction)
- ✅ Flask web interface with SSE progress tracking
- ✅ Service layer for unified CLI/web API
- ✅ **Nuclear delete** with triple confirmation
- ✅ CAR file download and processing with resume capability
- ✅ Real-time progress tracking for web interface

### In Testing
- [ ] Follower/Following reconciliation
  - Diff local vs live graph
  - Handle suspended/deleted accounts
  - CSV/JSON export of deltas
- [ ] Bot detection and cleanup features
- [ ] Advanced analytics and reporting

### Known Issues
- Entry point may fail in editable installs (use `python -m skymarshal`)
- Some DEBUG logging statements remain in web app (cleanup pending)
- CAR processing requires sufficient disk space for large accounts

### Priority Next Steps
Based on documentation review:
1. **Test CAR file download and processing** end-to-end workflow
2. **Implement follower/following ranking** from `bluesky_tools/`
3. **Add cleanup features** for inactive accounts and bot detection
4. **Proper logging system** to replace DEBUG print statements
5. **Web interface polish** and additional safety features
