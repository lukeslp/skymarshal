# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Reference

### Running the Application
```bash
# CLI (interactive menu)
make run                   # Recommended - handles entry point issues
python -m skymarshal       # Direct module execution

# Web Interface (lite version - primary dashboard)
python skymarshal/web/lite_app.py    # Port 5050, serves at /skymarshal/

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
pytest -m unit                                      # Only unit-marked tests
pytest -m "auth"                                    # Only auth-related tests
```

Custom markers are auto-applied based on directory (`unit/`, `integration/`) and name (`performance`/`perf`). Additional markers: `auth`, `api`.

## Architecture Overview

Skymarshal is a Bluesky content management toolkit (published to PyPI as `skymarshal` v0.1.0) with three interfaces:
- **CLI**: Interactive Rich-based terminal UI (`skymarshal/app.py`)
- **Web Lite**: Primary Flask dashboard for search/delete/analytics (`skymarshal/web/lite_app.py`, port 5050)
- **Web Full**: Extended interface with CAR processing wizard (`skymarshal/web/app.py`, port 5051)

### Three-Layer Architecture

```
┌─────────────────────────────────────────────────────┐
│  Interfaces                                         │
│  ├── CLI: InteractiveCARInspector (app.py)          │
│  ├── Web Lite: Flask + PrefixMiddleware (lite_app)  │
│  └── Web Full: Flask + setup wizard (app.py)        │
├─────────────────────────────────────────────────────┤
│  Service Layer (services/)                          │
│  ├── ContentService: Unified API for all workflows  │
│  ├── ContentAnalytics: Sentiment, posting patterns  │
│  └── SearchRequest/SearchResult: Typed DTOs         │
├─────────────────────────────────────────────────────┤
│  Domain Managers                                    │
│  ├── AuthManager (auth.py)         # AT Protocol    │
│  ├── DataManager (data_manager.py) # CAR/JSON I/O   │
│  ├── SearchManager (search.py)     # Filtering      │
│  ├── DeletionManager (deletion.py) # Safe deletion  │
│  ├── SettingsManager (settings.py) # Preferences    │
│  ├── UIManager (ui.py)            # Rich terminal   │
│  └── HelpManager (help.py)        # Context docs    │
├─────────────────────────────────────────────────────┤
│  Supporting Modules                                 │
│  ├── analytics/    # FollowerAnalyzer, PostAnalyzer,│
│  │                 # ContentAnalyzer (LLM-powered)  │
│  ├── cleanup/      # FollowingCleaner, PostImporter │
│  ├── bot_detection # Follower ratio heuristics      │
│  ├── engagement_cache # SQLite cache with TTL       │
│  └── egonet/       # Network visualization Flask app│
└─────────────────────────────────────────────────────┘
```

### Service Layer Pattern

The `services/` package (`ContentService`) is the **primary abstraction** both CLI and web use. It wraps all domain managers into a single API:

```python
from skymarshal.services import ContentService, SearchRequest
service = ContentService(settings_path=..., storage_root=..., auth_manager=...)
results = service.search(SearchRequest(keyword="python", min_likes=5))
```

The web lite app stores `ContentService` instances per session in `_services: Dict[str, ContentService]`.

### Web Dependency Injection

`web/dependencies.py` provides Flask request-scoped (`flask.g`) dependency management. Instead of recreating managers per route, use:

```python
from skymarshal.web.dependencies import get_content_service, get_auth_manager, get_json_path
```

`get_json_path()` handles intelligent fallback for finding a user's data file (exact match → timestamped files → most recent).

### Web Subpath Routing

The lite app runs behind Caddy at `/skymarshal/` using `PrefixMiddleware` (defined inline in `lite_app.py`) that sets `SCRIPT_NAME` and strips the prefix from `PATH_INFO`. This is wrapped with `ProxyFix` for reverse proxy headers. All `url_for()` calls automatically include the prefix.

### Data Flow
1. **Auth** → Bluesky credentials validation via AT Protocol
2. **Load** → CAR file download/import or direct API fetch (configurable via `SKYMARSHAL_LITE_USE_CAR` env flag)
3. **Analyze** → Filter by engagement, keywords, dates, content type
4. **Act** → Delete with multiple safety confirmation modes
5. **Export** → JSON/CSV output, or share via `SharedPostManager` (SQLite-backed permalinks)

### Key Data Structures (`models.py`)
- `ContentItem`: Posts/likes/reposts with engagement metadata
- `UserSettings`: Batch sizes, API limits, thresholds
- `SearchFilters`: Comprehensive filtering criteria
- `DeleteMode`, `ContentType`: Type-safe enums
- `console`: Shared Rich console (auto-detects terminal vs web context)
- `safe_progress()`: Context manager for Rich Progress that degrades gracefully in non-terminal contexts
- `calculate_engagement_score()`: LRU-cached (10K) formula: `likes + (2 × reposts) + (2.5 × replies)`

## Modules Not Obvious From File Listing

### `analytics/` — Three analyzers
- `FollowerAnalyzer`: Follower ranking and engagement analysis
- `PostAnalyzer`: Post fetching, ranking, engagement scoring
- `ContentAnalyzer`: LLM-powered content analysis and "vibe checking"

### `cleanup/` — Account cleanup tools
- `FollowingCleaner`: Detect and unfollow inactive/bot accounts
- `PostImporter`: Import posts from external sources

### `engagement_cache.py` — SQLite Cache
Stores engagement data (likes, reposts, replies) with **configurable TTL based on post age**. Provides 90% reduction in API calls on repeat loads. Located at `~/.skymarshal/engagement_cache.db`.

### `web/session_manager.py` — Centralized Session State
`SessionManager` + `UserSession` dataclass replaces scattered Flask session/global dict storage. Thread-safe with `Lock`.

### `web/share_manager.py` — Post Permalinks
`SharedPostManager` generates 8-char hex share IDs for posts, stored in `~/.skymarshal/shared_posts.db`. Enables the `/share/<id>` route.

### `egonet/` — Network Visualization
Separate Flask app for ego network visualization. Uses environment-based Bluesky credentials (`BSKY_IDENTIFIER`, `BSKY_PASSWORD`). Hardcoded data directory at `/home/coolhand/html/bluesky/egonet-manager`.

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
├── json/                    # JSON exports (named <safe_handle>.json or timestamped)
├── engagement_cache.db      # SQLite engagement cache
└── shared_posts.db          # SQLite shared post permalinks

~/.car_inspector_settings.json  # User settings (legacy name, still active)
```

## Testing Infrastructure

Shared fixtures in `tests/conftest.py`:
- `mock_auth`: Mock `AuthManager` with standard handle/DID
- `mock_settings`: Default `UserSettings` from mock data
- `skymarshal_dirs`: Temp directory structure (`skymarshal_dir`, `cars_dir`, `json_dir`)
- `data_manager`: Pre-wired `DataManager` with mock auth/settings/dirs
- `sample_content_items`: Mixed content dataset (posts + likes + reposts)
- `content_type` (parametrized): `'post'`, `'like'`, `'repost'`
- `engagement_level` (parametrized): `0`, `1`, `5`, `50`

Mock data factory in `tests/fixtures/mock_data.py`: `create_mock_content_item()`, `create_mock_posts_dataset(n)`, `create_mixed_content_dataset()`, `create_large_dataset()`, `create_mock_atproto_profile()`, `create_mock_atproto_records_response()`.

## Code Style

- Python 3.9+ with type hints encouraged
- Black (88 char), isort (black profile)
- Rich console for all terminal output
- Pytest with unit/integration/performance markers
- `mypy` configured with `check_untyped_defs = true` but `disallow_untyped_defs = false`

## Safety Features

All destructive operations include:
- Multiple confirmation prompts
- Dry-run preview modes
- Progress tracking with error recovery
- User data isolation by handle
