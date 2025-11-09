# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a collection of Bluesky (AT Protocol) tools for social media management, content analysis, and account cleanup. The repository contains multiple independent projects with different approaches and feature sets, all focused on Bluesky social network interactions.

## Project Structure

The repository is organized into distinct sub-projects:

### Main Projects

1. **skymarshal/** - Comprehensive content management CLI tool (PRIMARY PROJECT)
   - Interactive terminal app for managing Bluesky posts, likes, and reposts
   - CAR file processing and AT Protocol integration
   - Advanced search, filtering, and safe deletion workflows
   - Published to PyPI as `skymarshal`

2. **blueeyes/** - Multi-implementation Bluesky manager collection
   - `claude/bluesky_manager/` - Advanced modular implementation with FastAPI web interface
   - `claude/tests/` - Comprehensive test suite
   - Bot detection, analytics, and bulk operations
   - Multiple authentication and storage backends

3. **bluesky_tools/** - Standalone utility scripts
   - `bluesky_cleaner.py` - Bot/spam account cleanup with ratio analysis
   - `bluesky_follower_ranker.py` - Follower ranking and influence metrics
   - `pull_and_rank_posts.py` - Post analytics and ranking
   - `vibe_check_posts.py` - Content sentiment/vibe analysis
   - Individual scripts with SQLite databases

4. **bluevibes/** - Flask web profile viewer
   - Web application for searching and viewing Bluesky profiles
   - Profile data, posts, followers/following display
   - Uses Flask with responsive design

5. **bluesky/** - Simple HTML/JavaScript frontend
   - Static web interface for Bluesky browsing
   - Client-side only implementation

## Development Commands

### Skymarshal (Primary Project)

Navigate to `skymarshal/` directory:

```bash
# Installation & Setup
make dev                    # Install with development dependencies
make install               # Install in editable mode
python -m pip install skymarshal  # Install from PyPI

# Running
make run                   # Reliable execution (handles entry point issues)
python -m skymarshal       # Direct module execution
skymarshal                 # Entry point (may fail in dev environments)

# Testing
make test                  # Run full test suite (63+ tests)
python -m pytest tests/unit/ -v          # Unit tests only
python -m pytest tests/integration/ -v   # Integration tests
python -m pytest -m "not performance"    # Skip performance tests
python -m pytest tests/unit/test_auth.py::TestAuthManager::test_normalize_handle -v  # Single test

# Code Quality
make format                # Format with black + isort
make lint                  # Run flake8 + mypy
make check-all             # Format + lint + test
make clean                 # Clean build artifacts

# Distribution
make build                 # Build distribution packages
make publish-test          # Publish to Test PyPI
make publish               # Publish to PyPI
```

### Blueeyes/Bluesky Manager

Navigate to `blueeyes/claude/bluesky_manager/` directory:

```bash
# Installation & Setup
make quickstart            # Complete setup for new users
make dev-install          # Install development dependencies
pip install -r requirements-basic.txt  # Basic CLI dependencies
pip install -r requirements.txt        # Full dependencies with web

# Testing
make test                  # Run all tests
make test-unit             # Unit tests only
make test-integration      # Integration tests only
make test-cov              # Tests with coverage report

# Code Quality
make format                # Format code (black, isort)
make lint                  # Run linting (flake8, pylint)
make type-check            # Run mypy type checking
make check-all             # Run all quality checks + tests
make security-check        # Security analysis (bandit, safety)

# Running
./bsky --help              # CLI help (after chmod +x bsky)
make run-cli               # Run CLI in development mode
make run-web               # Run web server (http://localhost:8000)
make run-web-prod          # Run production web server
python -m bluesky_manager.cli.main  # Direct module execution

# Database
make db-init               # Initialize database tables
make db-migrate            # Run database migrations
make db-reset              # Drop and recreate tables
```

### Bluesky Tools (Standalone Scripts)

Navigate to `bluesky_tools/` directory:

```bash
# Run individual scripts directly
python bluesky_cleaner.py --username your.handle --password your_password
python bluesky_follower_ranker.py --username your.handle
python pull_and_rank_posts.py
python vibe_check_posts.py

# Each script maintains its own SQLite database
# Database: bluesky_profiles.db (shared across some scripts)
```

### Bluevibes (Flask Web App)

Navigate to `bluevibes/` directory:

```bash
# Installation
pip install -r requirements.txt

# Running
python run.py              # Start Flask development server
# Access at http://localhost:5000

# Environment variables (optional)
export FLASK_DEBUG=true
export BSKY_IDENTIFIER=your.handle
export BSKY_PASSWORD=your_password
```

## Architecture Overview

### Skymarshal Architecture (Primary)

**Manager Pattern Design** - Modular managers for each functional area:

```
InteractiveContentManager (app.py)
├── AuthManager (auth.py) - Authentication & session management
├── UIManager (ui.py) - Rich terminal interface components
├── DataManager (data_manager.py) - File operations & API data
├── SearchManager (search.py) - Content filtering & search
├── DeletionManager (deletion.py) - Safe deletion workflows
├── SettingsManager (settings.py) - User preferences
└── HelpManager (help.py) - Context-aware help system
```

**Core Data Structures** (models.py):
- `ContentItem` - Represents posts, likes, reposts with engagement metadata
- `UserSettings` - User preferences (batch sizes, API limits, thresholds)
- `SearchFilters` - Comprehensive filtering criteria
- Enums: `DeleteMode`, `ContentType` for type-safe operations

**AT Protocol Integration**:
- CAR file processing with CBOR decoding
- atproto library for `com.atproto.repo.*` operations
- Built-in rate limiting and batch processing
- Handle normalization (`@username` → `username.bsky.social`)

**Performance Optimizations** (10K+ items):
- Single-pass statistics computation (6x faster)
- Combined filtering engine (4x faster)
- LRU-cached engagement calculations (10,000 item capacity)
- Batch processing with configurable worker limits

### Blueeyes/Bluesky Manager Architecture

**Layered Architecture** with separation of concerns:

- `core/` - Business logic
  - `client.py` - BlueskySocialManager (AT Protocol wrapper)
  - `analytics.py` - BotDetectionEngine (multi-signal analysis)
  - `operations.py` - Bulk operations with rate limiting
  - `security.py` - Authentication and credential management

- `cli/` - Click-based command-line interface
  - `main.py` - CLI entry point with command groups
  - `commands/` - Individual command modules (auth, followers, manage, analytics)
  - `interactive.py` - Interactive menu mode

- `web/` - FastAPI web application
  - `app.py` - FastAPI application with WebSocket support
  - `api/` - REST API endpoints by domain
  - Real-time progress tracking via WebSocket

- `storage/` - Data persistence
  - `models.py` - SQLAlchemy database models
  - `cache.py` - Redis caching layer
  - `migrations/` - Database schema migrations

**Bot Detection System**:
- Multi-signal analysis: follower ratios, account age, profile completeness
- Username patterns, activity patterns, bio content analysis
- Scoring: 0.0-0.2 (likely human) to 0.7-1.0 (highly suspicious)

**Rate Limiting** respects Bluesky API:
- 5,000 points per hour (follows/unfollows = 1 point)
- 35,000 points per day
- 3,000 requests per 5 minutes

### Bluesky Tools Architecture

**Standalone Scripts** - Each script is independent:
- Direct CLI interfaces with argument parsing
- Individual SQLite databases for caching
- Shared database: `bluesky_profiles.db`
- Focus on specific tasks (cleaning, ranking, analysis)

## Key Technologies

### Common Stack Across Projects
- **Python 3.9+** with type hints
- **atproto** library for AT Protocol/Bluesky API
- **Rich** for terminal formatting and progress bars
- **SQLite/PostgreSQL** for data persistence
- **Redis** for caching (blueeyes only)

### Web Frameworks
- **FastAPI** (blueeyes/bluesky_manager) - Modern async web framework
- **Flask** (bluevibes) - Lightweight web application
- **Click** (blueeyes) - CLI framework
- **Rich** (skymarshal, blueeyes) - Terminal UI

### Testing & Quality
- **pytest** with asyncio support
- **black** (88 or 100 char line length)
- **isort** with black-compatible profile
- **mypy** for type checking
- **flake8** for linting

## Important Implementation Notes

### AT Protocol Specifics
- **URI Format**: `at://did:plc:*/collection/rkey`
- **Collections**: `app.bsky.feed.post`, `app.bsky.feed.like`, `app.bsky.feed.repost`
- **CAR Files**: Binary format with complete account history (CBOR encoding)
- **Rate Limits**: All projects include built-in rate limiting

### Security Patterns
- **Encrypted credential storage** (Fernet/bcrypt in blueeyes)
- **Session-based authentication** (no password persistence)
- **User data isolation** by handle
- **JWT authentication** (blueeyes web interface)
- **Input validation** and sanitization

### Data Management
- **File Locations**:
  - Skymarshal: `~/.skymarshal/` (backups/, cars/, json/)
  - Skymarshal settings: `~/.car_inspector_settings.json`
  - Bluesky Tools: Local `bluesky_profiles.db`
  - Blueeyes: Configurable via `.env`

### Entry Point Issues
- **Development**: Use `make run` or `python -m module_name`
- **Production**: Entry points work correctly in distributed packages
- **Avoid**: Direct command calls in editable installs

## Testing Strategy

### Skymarshal Testing
- **63+ comprehensive tests** across unit and integration
- **Markers**: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.performance`
- **Mock fixtures** in `tests/fixtures/mock_data.py`
- **AT Protocol mocking** with realistic responses

### Blueeyes Testing
- **Unit tests** for individual components with mocking
- **Integration tests** for API endpoints and workflows
- **Security tests** for authentication and validation
- **Coverage reporting** available

## Configuration

### Environment Variables

Common across projects:
```bash
# Bluesky Authentication
BLUESKY_USERNAME=your.handle.bsky.social
BLUESKY_PASSWORD=your_password
BSKY_IDENTIFIER=your.handle
BSKY_PASSWORD=your_password

# Database (blueeyes)
DATABASE_URL=postgresql://user:password@localhost:5432/bluesky_manager
REDIS_URL=redis://localhost:6379

# API Settings (blueeyes)
API_RATE_LIMIT_PER_HOUR=4500
API_BATCH_SIZE=10

# Security (blueeyes)
JWT_SECRET_KEY=your-jwt-secret-key
JWT_EXPIRATION_HOURS=24

# Flask (bluevibes)
FLASK_DEBUG=true
FLASK_SECRET_KEY=your_secret_key
```

## Key Development Patterns

### Adding Features to Skymarshal
1. Create new manager class inheriting from base (if applicable)
2. Accept `console` parameter for UI consistency
3. Use `@staticmethod` for pure utility functions
4. Add comprehensive error handling with Rich formatting
5. Include type hints for all parameters and returns
6. Add tests in `tests/unit/test_{module}.py`

### Working with AT Protocol
- **Content URIs**: Always use `at://did:plc:{id}/{collection}/{rkey}` format
- **Error Handling**: Wrap atproto calls with try/except for network failures
- **Rate Limiting**: Use built-in delays between API calls
- **Authentication**: Check client exists before API operations

### Code Style Standards

**Black formatting** (varies by project):
```toml
# Skymarshal
line-length = 88
target-version = ['py39']

# Blueeyes/Bluesky Manager
line-length = 100
target-version = ['py39']
```

**Type checking**:
- Skymarshal: Moderate strictness, optional for many functions
- Blueeyes: Strict mode with `disallow_untyped_defs = true`

## Project Status

- **skymarshal**: Published to PyPI, actively maintained
- **blueeyes/bluesky_manager**: Comprehensive features, well-tested
- **bluesky_tools**: Collection of working standalone utilities
- **bluevibes**: Functional Flask web viewer
- **bluesky**: Static HTML demo

## Common Workflows

### Initial Setup (Any Project)
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Navigate to specific project
cd skymarshal  # or blueeyes/claude/bluesky_manager, etc.

# Install dependencies
pip install -r requirements.txt
# or
make dev-install
```

### Running Tests
```bash
# Skymarshal
cd skymarshal && make test

# Blueeyes
cd blueeyes/claude/bluesky_manager && make test

# Specific test
pytest tests/unit/test_module.py::TestClass::test_method -v
```

### Code Quality Checks
```bash
# Format code
make format  # or: black . && isort .

# Lint
make lint  # or: flake8 && mypy .

# All checks
make check-all
```
