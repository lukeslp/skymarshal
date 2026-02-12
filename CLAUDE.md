# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Reference

### Unified Backend (primary — serves the React client)
```bash
source .venv/bin/activate
python unified_app.py                    # Dev server on port 5090
python unified_app.py --port 5050        # Production port
./start.sh                               # Production (activates venv, port 5050)
```

### CLI (interactive terminal tool)
```bash
make run                   # Recommended — python -m skymarshal
python -m skymarshal       # Direct module execution
```

### Legacy Web Interfaces (standalone Flask dashboards)
```bash
python skymarshal/web/lite_app.py        # Port 5050, serves at /skymarshal/
python skymarshal/web/app.py             # Port 5051, extended interface
```

### Development
```bash
make dev                   # Install with dev dependencies
make test                  # pytest
make format                # Black + isort
make lint                  # flake8 + mypy
make check-all             # All quality checks
```

### Testing
```bash
pytest                                              # Full suite
pytest tests/unit/ -v                               # Unit tests only
pytest tests/integration/ -v                        # Integration tests
pytest tests/unit/test_auth.py::TestAuthManager -v  # Single class
pytest -m "not performance"                         # Skip slow tests
```

Custom markers auto-applied from directory (`unit/`, `integration/`) and name (`performance`/`perf`). Additional markers: `auth`, `api`.

## Architecture

Skymarshal has two roles:

1. **Unified Backend** — Flask + Flask-SocketIO server (`unified_app.py`) powering the React Bluesky client at `/home/coolhand/html/bluesky/unified/`. This is the production service (port 5050). It exposes 35 REST API routes across 7 blueprints plus real-time Socket.IO events.

2. **CLI Toolkit** — Interactive Rich terminal UI (`skymarshal/app.py`) and standalone web dashboards (`web/lite_app.py`, `web/app.py`) for content management. Published to PyPI as `skymarshal` v0.1.0.

### Unified Backend Architecture

```
unified_app.py → create_app() in skymarshal/api/__init__.py
  │
  ├── Flask app factory
  │   ├── CORS (localhost:5086, dr.eamer.dev, d.reamwalker.com)
  │   ├── Flask-SocketIO (threading async mode)
  │   ├── Global JSON error handlers (404, 500)
  │   └── /health endpoint
  │
  ├── 7 Blueprints:
  │   ├── /api/auth/*         auth.py        Login/logout/session
  │   ├── /api/content/*      content.py     Load, search, delete, export, share
  │   ├── /api/analytics/*    analytics.py   Sentiment, engagement, followers, posts
  │   ├── /api/network/*      network.py     Graph fetch jobs + NetworkX analysis
  │   ├── /api/profile/*      profile.py     Profile data, bot detection
  │   ├── /api/cleanup/*      cleanup.py     Following cleanup + unfollow
  │   └── /api/firehose/*     firehose.py    Stats, start/stop, recent posts
  │
  └── Socket.IO events:
      ├── firehose:post       Real-time Bluesky posts from Jetstream
      ├── firehose:stats      Live post rate + sentiment stats (1/sec)
      ├── job:progress        Network fetch progress updates
      └── connect/disconnect  Connection lifecycle
```

### Auth Pattern

Every blueprint duplicates the same auth pattern (not shared):

```python
def _require_service() -> ContentService | None:
    token = session.get("api_token")
    if not token:
        return None
    return get_services().get(token)
```

Per-session `ContentService` instances stored in `_services: Dict[str, ContentService]` (in `api/__init__.py`), keyed by session token. Public endpoints (stats, recent) skip auth. Protected endpoints (start/stop, delete, network fetch) check `_is_authenticated()`.

### React Frontend Integration

The React app lives at `/home/coolhand/html/bluesky/unified/`. Key integration points:

- **Vite proxy** (`unified/app/vite.config.ts`): Dev server on 5086 proxies `/api/*` and `/socket.io` to Flask on 5090
- **API client** (`unified/app/src/lib/skymarshal-api.ts`): TypeScript client for all Flask endpoints
- **Socket.IO hook** (`unified/app/src/hooks/useSocket.ts`): Auto-detects dev (default `/socket.io`) vs prod (`/skymarshal/socket.io`) path
- **Dual backend**: React talks to `bsky.social/xrpc` directly for feed/compose/chat, to Flask only for power tools

### Domain Layer

```
skymarshal/
├── api/                    # Flask blueprints (unified backend)
│   ├── __init__.py         # App factory, SocketIO init, services dict
│   ├── auth.py             # Login/logout/session routes
│   ├── content.py          # Content CRUD, search, export, share
│   ├── analytics.py        # Engagement/sentiment/follower analysis
│   ├── network.py          # Graph jobs + NetworkX analytics
│   ├── profile.py          # Profile endpoints, bot detection
│   ├── cleanup.py          # Following cleanup workflow
│   └── firehose.py         # Firehose control + SocketIO connect handler
│
├── firehose/               # Real-time Jetstream client (ported from Node.js)
│   ├── jetstream.py        # WebSocket client (websocket-client, sync)
│   ├── sentiment.py        # VADER sentiment analysis
│   └── features.py         # Feature extraction (hashtags, media, language)
│
├── network/                # Graph analytics (ported from blueballs/FastAPI)
│   ├── fetcher.py          # Follower/following fetch with pagination
│   ├── analysis.py         # Louvain, PageRank, centrality (NetworkX)
│   ├── client.py           # Rate-limited Bluesky API client
│   └── cache.py            # Filesystem cache with TTL
│
├── analytics/              # Content analysis
│   ├── follower_analyzer.py  # Follower ranking, bot detection
│   ├── post_analyzer.py      # Post engagement scoring
│   └── content_analyzer.py   # LLM-powered content analysis
│
├── services/               # Service layer (wraps domain managers)
│   ├── content_service.py  # ContentService — unified API for workflows
│   └── analytics.py        # ContentAnalytics — sentiment, time patterns
│
├── cleanup/                # Account management
│   ├── following_cleaner.py  # Detect + unfollow inactive/bot accounts
│   └── post_importer.py      # Import posts from external sources
│
├── web/                    # Legacy standalone Flask dashboards
│   ├── lite_app.py         # Primary dashboard (port 5050, /skymarshal/)
│   ├── app.py              # Extended interface (port 5051)
│   ├── dependencies.py     # Request-scoped dependency injection
│   ├── session_manager.py  # SessionManager + UserSession dataclass
│   └── share_manager.py    # SharedPostManager (SQLite permalinks)
│
├── auth.py                 # AuthManager — AT Protocol authentication
├── data_manager.py         # DataManager — CAR/JSON I/O
├── search.py               # SearchManager — filtering
├── deletion.py             # DeletionManager — safe deletion with confirmations
├── settings.py             # SettingsManager — user preferences
├── models.py               # ContentItem, SearchFilters, UserSettings, enums
├── bot_detection.py        # BotDetector — follower ratio heuristics
├── engagement_cache.py     # SQLite cache with TTL
├── ui.py                   # UIManager — Rich terminal output
├── app.py                  # CLI entry point (InteractiveCARInspector)
└── egonet/                 # Ego network visualization (separate Flask app)
```

## Key Dependencies

| Package | Purpose | Notes |
|---------|---------|-------|
| `flask-socketio` | Real-time WebSocket events | Threading async mode (not eventlet) |
| `websocket-client` | Jetstream WebSocket client | Sync library — NOT `websockets` (async) |
| `vaderSentiment` | Sentiment analysis | NOT `textblob` — lighter, social-media-optimized |
| `networkx` | Graph analytics | Louvain, PageRank, centrality |
| `aiohttp` | Async HTTP | Required by analytics modules (FollowerAnalyzer, FollowingCleaner) |
| `eventlet` | Async support | Available but SocketIO uses threading mode |
| `atproto` | AT Protocol client | Bluesky authentication and data access |
| `httpx` | HTTP client | AT Protocol API calls |
| `rich` | Terminal UI | CLI interface rendering |

## Porting Notes

Two major modules were ported from external projects:

### Firehose (from Node.js)
- **Source**: `/home/coolhand/html/firehose/server/` (TypeScript)
- **Target**: `skymarshal/firehose/`
- Conversions: `ws` WebSocket → `websocket-client` (sync), npm `sentiment` → `vaderSentiment`, Socket.IO → Flask-SocketIO
- Jetstream URI: `wss://jetstream2.us-east.bsky.network/subscribe`
- Auto-reconnect on WebSocket failure (5-second delay)

### Network (from blueballs/FastAPI)
- **Source**: `/home/coolhand/projects/blueballs/backend/app/` (Python/FastAPI)
- **Target**: `skymarshal/network/`
- Conversions: `asyncio.Lock` → `threading.Lock`, `asyncio.Semaphore` → `ThreadPoolExecutor`, `httpx.AsyncClient` → `requests.Session`
- Algorithms preserved: Louvain community detection, PageRank, betweenness centrality, 10-color palette

## Deployment

- **Production port**: 5050 (via `start.sh`)
- **Dev port**: 5090 (default in `unified_app.py`)
- **Caddy routes**: `/bluesky/unified/api/*` and `/bluesky/unified/socket.io/*` → port 5050
- **Service manager**: `sm start skymarshal` / `sm stop skymarshal`
- **Health endpoint**: `GET /health` returns `{"status": "ok", "service": "skymarshal-unified"}`
- **Venv**: `.venv/` (not `venv/`)

## AT Protocol

- **Library**: `atproto>=0.0.46`
- **CAR Files**: Binary account backups with CBOR encoding
- **URI Format**: `at://did:plc:*/collection/rkey`
- **Collections**: `app.bsky.feed.post`, `app.bsky.feed.like`, `app.bsky.feed.repost`
- **Handle Format**: `username.bsky.social` (auto-normalized from `@username`)

## File Locations

```
~/.skymarshal/
├── cars/                    # CAR backup files
├── json/                    # JSON exports
├── engagement_cache.db      # SQLite engagement cache
└── shared_posts.db          # SQLite shared post permalinks

~/.car_inspector_settings.json  # User settings (legacy name, still active)
```

## Testing Infrastructure

Fixtures in `tests/conftest.py`:
- `mock_auth`: Mock `AuthManager` with standard handle/DID
- `mock_settings`: Default `UserSettings` from mock data
- `skymarshal_dirs`: Temp directory structure
- `sample_content_items`: Mixed content dataset

Mock data factory in `tests/fixtures/mock_data.py`: `create_mock_content_item()`, `create_mock_posts_dataset(n)`, `create_mixed_content_dataset()`.

## Code Style

- Python 3.9+, type hints encouraged
- Black (88 char), isort (black profile)
- Rich console for terminal output
- mypy: `check_untyped_defs = true`, `disallow_untyped_defs = false`
