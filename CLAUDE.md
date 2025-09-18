# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

Skymarshal is a comprehensive command-line tool for managing Bluesky social media content. It provides interactive and programmatic interfaces for downloading, analyzing, filtering, and safely deleting Bluesky posts, likes, and reposts using the AT Protocol.

## Development Commands

### Essential Commands
```bash
# Development setup
make dev                    # Install with development dependencies
make install               # Install in editable mode

# Running the application
make run                   # Reliable execution (handles entry point issues)
python -m skymarshal       # Direct module execution
skymarshal                 # Entry point (may fail in dev environments)

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
```

### Testing Framework
- **63 comprehensive tests** across unit and integration categories
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
└── HelpManager (help.py) - Context-aware help system
```

### Core Data Structures (models.py)
- **`ContentItem`**: Represents Bluesky content (posts, likes, reposts) with engagement metadata
- **`UserSettings`**: User preferences including batch sizes, API limits, engagement thresholds
- **`SearchFilters`**: Comprehensive filtering criteria for content search
- **Enums**: `DeleteMode`, `ContentType` for type-safe operations
- **Utilities**: `parse_datetime()`, `merge_content_items()`, engagement score calculation with LRU cache

### Data Flow Architecture
1. **Authentication** (AuthManager) → Validate Bluesky credentials with session management
2. **Data Loading** (DataManager) → Download/import from CAR files, JSON exports, or direct API
3. **Analysis** (SearchManager + UIManager) → Filter, search, and compute statistics
4. **Operations** (DeletionManager) → Safe deletion with multiple confirmation modes
5. **Export** (DataManager) → Save results in JSON/CSV formats

### AT Protocol Integration
- **CAR File Processing**: Complete Bluesky account backups with CBOR decoding
- **API Operations**: `atproto` library for posts, likes, reposts via `com.atproto.repo.*`
- **Rate Limiting**: Built-in delays and batch processing respect API limits
- **Handle Normalization**: Automatic conversion of `@username` to `username.bsky.social`

### Performance Optimizations
Recent optimizations for large datasets (10K+ items):
- **Single-pass statistics computation** (6x faster than previous implementation)
- **Combined filtering engine** (4x faster for complex searches)
- **LRU-cached engagement calculations** with 10,000 item capacity
- **Memory-efficient merging** with single-pass categorization
- **Batch processing** with configurable worker limits

## Key Implementation Details

### Interactive vs CLI Modes
- **Primary Interface**: Rich-based interactive menu system
- **CLI Commands**: Available but limited; full CLI planned for future
- **Navigation**: Comprehensive back/forward navigation with context-aware help

### Authentication System
- **Session Management**: Persistent authentication with re-auth flows
- **Security**: User data isolation by handle, secure file access validation
- **Error Handling**: Automatic retry with user-friendly error messages

### Content Management Workflow
1. **Data Source Priority**:
   - CAR file download & processing (recommended - fastest)
   - Load existing JSON/CAR files
   - Direct API download (slowest, rate-limited)
2. **Analysis Phase**: Filter by engagement, keywords, content type, date ranges
3. **Safety Features**: Multiple deletion confirmation modes (all-at-once, individual, batch)

### File System Structure
```
~/.skymarshal/
├── cars/           # CAR file backups (binary AT Protocol format)
└── json/           # JSON exports for analysis

~/.car_inspector_settings.json  # User settings (legacy filename)
```

### Configuration and Settings
- **User Settings**: Batch sizes (1-100), API limits, engagement thresholds
- **Performance Tuning**: Worker counts, page sizes, fetch order (newest/oldest)
- **Engagement Scoring**: Weighted formula: `likes + (2 × reposts) + (3 × replies)`

## Development Guidelines

### Code Style and Standards
- **Python 3.8+** with type hints encouraged
- **Black formatting** (88 character line length)
- **isort** with black-compatible profile
- **MyPy type checking** with moderate strictness
- **Rich console** for all UI output (shared instance in `models.console`)

### Testing Approach
- **Unit Tests**: Manager classes tested in isolation with comprehensive mocking
- **Integration Tests**: End-to-end workflows with file system operations
- **Performance Tests**: Large dataset handling (marked separately)
- **AT Protocol Mocking**: Realistic API responses for authentication and data operations

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

## Important Notes

### AT Protocol Specifics
- **URI Format**: `at://did:plc:*/collection/rkey` for all content operations
- **Collections**: `app.bsky.feed.post`, `app.bsky.feed.like`, `app.bsky.feed.repost`
- **CAR Files**: Binary format containing complete account history with CBOR encoding
- **Rate Limits**: Respected through batch processing and built-in delays

### Security Considerations
- **User Data Isolation**: Each handle's data is strictly separated
- **File Access Validation**: Users can only access their own data files
- **Authentication Security**: Passwords never stored, sessions managed securely
- **Safe Deletion**: Multiple confirmation layers prevent accidental data loss

### Performance Considerations
- **Large Datasets**: Optimized for accounts with 10K+ items
- **Memory Management**: Single-pass algorithms minimize memory footprint
- **Caching**: LRU cache for frequently computed values (engagement scores)
- **Batch Processing**: Configurable batch sizes for different operations

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