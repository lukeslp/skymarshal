# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is the `site_gpt5` subdirectory within the Skymarshal project, containing web-based interfaces for Bluesky social media data analysis and engagement hydration. It provides Flask web applications that integrate with the main Skymarshal library to offer user-friendly web interfaces for downloading, processing, and analyzing Bluesky content.

## Development Commands

### Running Web Applications
```bash
# Full-featured Flask app (integrates with Skymarshal core)
python app.py                          # Default port 5003
PORT=5000 python app.py                # Custom port

# Simple streaming Flask app (standalone)
python web_simple.py                   # Default port 5006
echo "5007" > .env.port                # Set custom port via file
python web_simple.py

# CLI hydration script (standalone)
python hydrate_last_500.py <handle> <password> --limit 50 --out results.json
```

### Dependencies
```bash
pip install flask>=3.0.0 atproto>=0.0.46 rich>=13.0.0
```

## Architecture Overview

### Core Applications

**1. app.py - Full Skymarshal Integration**
- **Purpose**: Complete web interface using Skymarshal's manager pattern
- **Features**: Authentication, CAR file download/processing, engagement hydration, statistics display
- **Integration**: Uses `AuthManager`, `DataManager`, `UserSettings` from main Skymarshal
- **Authentication**: Supports both full authentication and guest mode (read-only)
- **Data Flow**: Login → Download CAR → Import & Process → Hydrate Engagement → Display Stats

**2. web_simple.py - Standalone Streaming Interface**
- **Purpose**: Lightweight real-time hydration interface
- **Features**: Server-Sent Events for live progress, direct API hydration
- **Dependencies**: Minimal - only `atproto`, `flask`, and `improved_hydration.py`
- **User Experience**: Real-time streaming of hydration progress with immediate feedback

**3. hydrate_last_500.py - CLI Tool**
- **Purpose**: Command-line batch hydration utility
- **Features**: Fetches up to 500 posts, hydrates all engagement metrics, saves JSON export
- **Usage Pattern**: Direct CLI execution with handle/password arguments

### Data Processing Architecture

**Hydration Engine (`improved_hydration.py`)**
- **Public API Integration**: Uses Bluesky's public AppView endpoints (no auth required for reads)
- **Endpoints Used**:
  - `app.bsky.feed.getPosts` - Basic post data
  - `app.bsky.feed.getLikes` - Paginated likes counting
  - `app.bsky.feed.getRepostedBy` - Paginated reposts counting  
  - `app.bsky.feed.getQuotes` - Paginated quotes counting
  - `app.bsky.feed.getPostThread` - Thread traversal for reply counting
- **Resilience**: Exponential backoff, timeout handling, automatic retries
- **Rate Limiting**: Configurable delays between requests (default 0.4s)

**Web-Safe Hydration (`app.py:_web_safe_hydrate`)**
- **Adaptive Strategy**: Small datasets use exact endpoints, large datasets use optimized batch processing
- **Performance Optimization**: Single-pass algorithms for 10K+ items
- **Authentication Recovery**: Automatic session rebuilding on auth failures
- **Budget Control**: Time-limited hydration with configurable timeout (`SKY_HYDRATE_BUDGET_S`)

### Integration Patterns

**Skymarshal Core Integration (app.py)**
```python
# Manager pattern usage
from skymarshal.auth import AuthManager
from skymarshal.data_manager import DataManager  
from skymarshal.models import UserSettings, ContentItem
```

**Session Management**
- **Flask Sessions**: Persistent authentication across page loads
- **In-Memory Store**: `_auth_by_sid` maps session IDs to `AuthManager` instances
- **Session Recovery**: Automatic reconstruction from stored session payloads
- **Guest Mode**: Read-only access for failed authentication with public client

**Data Persistence**
- **CAR Files**: Binary AT Protocol format in `~/.skymarshal/cars/`
- **JSON Exports**: Processed data in `~/.skymarshal/json/`
- **Temporary Files**: Web results in `tmp/` directory
- **Settings**: User preferences in `~/.car_inspector_settings.json`

## Key Implementation Details

### Environment Configuration
```bash
# app.py configuration
SKYM_SECRET=<flask_secret_key>          # Session encryption key
SKY_FAST_HYDRATE=1                      # Enable optimized hydration for large datasets
SKY_HYDRATE_BUDGET_S=10                 # Hydration timeout in seconds

# web_simple.py configuration  
PORT=5006                               # Default port
.env.port                               # Port file override
```

### Authentication Modes

**Full Authentication Mode**
- Uses Bluesky app passwords for full API access
- Enables CAR file download, private data access
- Persistent session management with automatic refresh

**Guest Mode**  
- Fallback for invalid credentials
- Read-only access using public AppView endpoints
- Limited to publicly available engagement data

### Data Flow Architecture

**app.py Processing Pipeline**
1. **Authentication**: `AuthManager` handles Bluesky login/session management
2. **CAR Download**: `DataManager.download_car()` fetches complete account backup
3. **Import**: `DataManager.import_car_replace()` processes CAR into JSON
4. **Hydration**: `_web_safe_hydrate()` enriches with engagement metrics
5. **Export**: Save hydrated data with engagement scores and quote counts

**web_simple.py Streaming Pipeline**  
1. **Authentication**: Direct `atproto.Client` login
2. **Post Fetching**: `_list_last_posts()` retrieves recent non-reply posts
3. **Real-time Hydration**: Server-Sent Events stream progress updates
4. **Export**: JSON file with hydrated engagement data

### Performance Optimizations

**Smart Dataset Handling**
- **Small Datasets (≤50 items)**: Direct exact endpoint calls for precision
- **Large Datasets (>50 items)**: Batch processing with optional fast path
- **Fast Hydrate Mode**: `SKY_FAST_HYDRATE=1` enables `get_posts` bulk fetching

**Rate Limiting & Resilience**
- **Exponential Backoff**: Automatic retry with increasing delays
- **Timeout Management**: Short HTTP timeouts (3s) to prevent hangs
- **Graceful Degradation**: Fallback to public endpoints on auth failures

**Memory Efficiency**
- **Single-Pass Processing**: Minimizes memory footprint for large datasets
- **Streaming Output**: Real-time progress without buffering full results
- **Batch Processing**: Configurable chunk sizes for API calls

## File Structure

```
site_gpt5/
├── app.py                     # Full Skymarshal web interface
├── web_simple.py             # Simple streaming interface  
├── hydrate_last_500.py       # CLI hydration tool
├── improved_hydration.py     # Core hydration engine
├── requirements.txt          # Dependencies
├── templates/
│   ├── index.html           # Full interface template
│   └── simple.html          # Streaming interface template
├── static/
│   └── simple.css           # Shared styles
└── tmp/                     # Temporary JSON exports
    └── hydrated_*.json      # Generated hydration results
```

## Development Patterns

### Adding New Web Features
1. **Choose Base**: Use `app.py` for Skymarshal integration, `web_simple.py` for standalone features
2. **Authentication**: Leverage existing session management patterns
3. **Data Processing**: Use `improved_hydration.py` for consistent engagement processing
4. **Error Handling**: Implement graceful fallbacks for auth/network failures
5. **Performance**: Consider dataset size for optimization strategy selection

### Testing Hydration Features
- **Small Datasets**: Test exact endpoint accuracy with ≤50 items
- **Large Datasets**: Test batch processing performance with 100+ items  
- **Rate Limiting**: Verify backoff behavior under API pressure
- **Authentication**: Test both full auth and guest mode fallbacks

### Frontend Integration
- **Server-Sent Events**: Use for real-time progress streaming
- **Progressive Enhancement**: Ensure functionality without JavaScript
- **Responsive Design**: Templates support light/dark mode via `color-scheme`
- **Error Display**: Consistent error messaging patterns across interfaces

## Important Notes

### AT Protocol Integration
- **URI Format**: `at://did:plc:*/collection/rkey` for all content operations
- **Collections**: `app.bsky.feed.post`, `app.bsky.feed.like`, `app.bsky.feed.repost` 
- **Public Endpoints**: Most hydration works without authentication via AppView
- **Rate Limits**: Built-in delays and retry logic for API compliance

### Security Considerations
- **Session Security**: `SESSION_COOKIE_HTTPONLY=True`, secure session keys
- **File Access**: Restricted to user's own data directories
- **Password Handling**: App passwords only, no credential storage
- **Guest Mode**: Safe fallback for authentication failures

### Performance Characteristics
- **Small Scale**: Sub-second processing for ≤50 posts
- **Large Scale**: Optimized for 10K+ item datasets with time budgets
- **Memory Usage**: Streaming processing prevents memory exhaustion
- **Network Efficiency**: Batched API calls with intelligent retry logic