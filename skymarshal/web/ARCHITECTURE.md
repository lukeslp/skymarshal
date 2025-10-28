# Skymarshal Web Interface - Architecture & Implementation Guide

## Overview

The Skymarshal web interface provides a modern, accessible browser-based UI for managing Bluesky content. This document covers the architecture, design decisions, and implementation details.

## Architecture

### Core Principles

1. **Single Source of Truth**: Centralized session management eliminates scattered state
2. **Dependency Injection**: Request-scoped services reduce code duplication
3. **Progressive Enhancement**: Works without JavaScript, enhanced with it
4. **Accessibility First**: WCAG 2.1 AA compliant, keyboard navigable
5. **Performance**: Pagination, caching, and lazy loading for large datasets

### Layer Architecture

```
┌─────────────────────────────────────────┐
│         Templates (Jinja2)              │
│  - Base layout, dashboard, setup, etc.  │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│          Routes (Flask)                 │
│  - HTTP endpoints, form handling        │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│       Dependencies (DI Layer)           │
│  - get_auth_manager()                   │
│  - get_data_manager()                   │
│  - get_content_service()                │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│      Services & Managers                │
│  - ContentService (unified API)         │
│  - DataManager, SearchManager, etc.     │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│       Models & Core Logic               │
│  - ContentItem, UserSettings, etc.      │
└─────────────────────────────────────────┘
```

## Key Components

### 1. Session Management (`session_manager.py`)

**Purpose**: Centralized user session state management

**Before (scattered state)**:
```python
# State was scattered across:
session['json_path']         # Flask session
progress_data[session_id]    # Global dict
auth_storage[session_id]     # Another global dict
# Plus complex fallback logic in get_json_path()
```

**After (unified)**:
```python
# Single source of truth
session_mgr = SessionManager()
user_session = session_mgr.get_session(session_id)
user_session.json_path  # Clear, deterministic access
```

**Features**:
- Automatic cleanup of expired sessions (24h TTL)
- Thread-safe operations with locking
- Simple API: create, get, save, clear
- Session statistics for monitoring

**Usage**:
```python
# Create new session on login
session = session_mgr.create_session(
    handle=user_handle,
    auth_manager=auth_mgr,
    used_regular_password=False
)

# Get session in routes
user_session = session_mgr.get_session(session_id)
if user_session:
    data_path = user_session.json_path
```

### 2. Dependency Injection (`dependencies.py`)

**Purpose**: Eliminate manager recreation in every route

**Before (repeated pattern)**:
```python
@app.route('/search')
def search():
    # This pattern repeated 10+ times
    settings_file = Path.home() / ".car_inspector_settings.json"
    settings_manager = SettingsManager(settings_file)
    settings = settings_manager.settings
    
    auth_manager = get_auth_manager()
    data_manager = DataManager(
        auth_manager,
        settings,
        skymarshal_dir,
        backups_dir,
        json_dir
    )
    # ... actual logic
```

**After (DI pattern)**:
```python
@app.route('/search')
def search():
    # One line replaces 15+ lines
    service = get_content_service()
    # ... actual logic
```

**Available Dependencies**:
- `get_session_manager()` - App-wide SessionManager
- `get_user_session()` - Current UserSession
- `get_auth_manager()` - Current AuthManager
- `get_settings()` - UserSettings (request-scoped)
- `get_storage_paths()` - Standard directory paths
- `get_data_manager()` - DataManager (request-scoped)
- `get_search_manager()` - SearchManager (request-scoped)
- `get_deletion_manager()` - DeletionManager (request-scoped)
- `get_content_service()` - ContentService (request-scoped)
- `get_json_path()` - User's data file with intelligent fallback

**Request Scoping**: All managers are cached in Flask's `g` object for the request lifecycle, ensuring:
- No duplicate instantiation within a request
- Automatic cleanup after request
- Thread-safe per-request isolation

### 3. Content Service (`services/content_service.py`)

**Purpose**: Unified API for web and CLI

The ContentService provides a high-level interface that abstracts:
- Authentication workflows
- Data loading (CAR, JSON, API)
- Search and filtering
- Deletion with cache updates

**Key Methods**:
```python
service = ContentService()

# Authenticate
service.login(handle, password)

# Load content (with smart caching)
items = service.ensure_content_loaded(
    categories=['posts', 'likes'],
    limit=500
)

# Search
results, total = service.search(SearchRequest(
    keyword='bluesky',
    min_engagement=10
))

# Delete
deleted, errors = service.delete(uris=[...])

# Summary stats
stats = service.summarize()
```

## User Journeys

### 1. First-Time User Flow

```
┌────────────┐
│   Login    │ - Password validation & warnings
└─────┬──────┘   - Session creation
      │
      ↓
┌────────────┐
│   Setup    │ - 3-step wizard with visual progress
└─────┬──────┘   - Data source selection (CAR, JSON, API)
      │          - Real-time progress via SSE
      ↓
┌────────────┐
│ Dashboard  │ - Content overview
└─────┬──────┘   - Engagement analytics
      │          - Search interface
      ↓
┌────────────┐
│   Search   │ - Filters & presets
└─────┬──────┘   - Paginated results
      │
      ↓
┌────────────┐
│   Delete   │ - Bulk or individual
└────────────┘   - Multiple confirmations
```

### 2. Returning User Flow

```
┌────────────┐
│   Login    │ - Existing session detection
└─────┬──────┘   - Auto-redirect to dashboard
      │
      ↓
┌────────────┐
│ Dashboard  │ - Cached data loaded
└─────┬──────┘   - Recent searches available
      │
      ↓
    (Work)
```

## Security

### Authentication
- App password recommended (heuristic detection with warnings)
- Session-based auth (no password storage)
- 24-hour session expiration
- Secure session cookies (HTTPOnly, SameSite=Lax)

### Data Access
- User data isolation by handle
- Path validation for file access
- No shared data between users

### Deletion Safety
- Multiple confirmation layers:
  1. Selection review
  2. Modal confirmation
  3. Browser confirm dialog (for nuclear delete)
- Exact phrase matching for nuclear delete
- Rate limiting on delete endpoints (TODO)

## Performance Optimizations

### Current
1. **Engagement Score Caching**: LRU cache (10K items) for score calculations
2. **Request-Scoped Managers**: No duplicate instantiation
3. **SQLite Engagement Cache**: 90% reduction in API calls
4. **Batch Processing**: Configurable batch sizes for API calls

### Planned
1. **Pagination**: Server-side pagination for search results
2. **Client-Side Caching**: Service worker for search results
3. **Virtual Scrolling**: For large result sets
4. **Lazy Loading**: Defer non-critical resources

## Accessibility Features

### Current
- Semantic HTML throughout
- ARIA labels on interactive elements
- Focus management for modals
- Keyboard shortcuts (Escape to close modals)
- High contrast color scheme
- Responsive font sizing

### Planned (Phase 3)
- Full keyboard navigation (Tab, Arrow keys, Enter)
- Dark mode support
- Screen reader optimizations
- Skip links for navigation
- Focus visible states
- Reduced motion support

## Error Handling

### Patterns

1. **User-Friendly Messages**: Technical errors translated to actionable messages
2. **Graceful Degradation**: Features degrade when services unavailable
3. **Error Recovery**: Automatic retry with exponential backoff
4. **Logging**: Structured logging for debugging (without sensitive data)

### Example:
```python
try:
    items = data_manager.load_exported_data(json_path)
except FileNotFoundError:
    return jsonify({
        'success': False,
        'error': 'Data file not found. Please complete setup first.',
        'action': 'redirect_to_setup'
    }), 404
except Exception as e:
    current_app.logger.exception("Failed to load data")
    return jsonify({
        'success': False,
        'error': 'An unexpected error occurred. Please try again.',
        'support_code': generate_support_code()
    }), 500
```

## Testing Strategy

### Unit Tests
- Manager classes tested in isolation
- Mock dependencies with pytest fixtures
- Edge cases and error conditions

### Integration Tests
- End-to-end workflows
- Real file system operations (in temp directories)
- Mock AT Protocol API calls

### E2E Tests (Planned)
- Selenium for full browser testing
- Test critical user journeys
- Accessibility audit automation

## Development Workflow

### Local Development
```bash
# Start development server
cd skymarshal/web
python run.py

# Run tests
pytest tests/

# Format code
black skymarshal/
isort skymarshal/

# Type check
mypy skymarshal/
```

### Adding a New Route

1. **Define route** in `app.py`:
```python
@app.route('/my-feature', methods=['GET', 'POST'])
@login_required
def my_feature():
    # Use dependency injection
    service = get_content_service()
    user_session = get_user_session()
    
    # Your logic here
    
    return render_template('my_feature.html')
```

2. **Create template** in `templates/`:
```html
{% extends "base.html" %}
{% block content %}
    <!-- Your content -->
{% endblock %}
```

3. **Add tests** in `tests/`:
```python
def test_my_feature(client, authenticated_session):
    response = client.get('/my-feature')
    assert response.status_code == 200
```

4. **Update documentation** in this file

## Configuration

### Environment Variables
```bash
# Flask
FLASK_ENV=development
FLASK_DEBUG=true

# Skymarshal
SKYMARSHAL_USE_CAR=true           # Prefer CAR files
SKYMARSHAL_SESSION_TTL=86400      # Session timeout (seconds)

# Performance
SKYMARSHAL_PAGE_SIZE=50           # Results per page
SKYMARSHAL_CACHE_TTL=3600         # Cache timeout
```

### Settings File
User-specific settings stored in `~/.car_inspector_settings.json`:
```json
{
    "download_limit_default": 500,
    "default_categories": ["posts", "likes", "reposts"],
    "engagement_cache_enabled": true,
    "hydrate_batch_size": 100
}
```

## Deployment

### Production Checklist
- [ ] Set `SESSION_COOKIE_SECURE=True` (HTTPS only)
- [ ] Configure reverse proxy (Caddy/nginx)
- [ ] Set up process manager (systemd/pm2)
- [ ] Enable HTTPS at proxy level
- [ ] Configure CORS headers
- [ ] Set up monitoring (logs, metrics)
- [ ] Configure rate limiting
- [ ] Set up automated backups

### Example Systemd Service
```ini
[Unit]
Description=Skymarshal Web Interface
After=network.target

[Service]
Type=simple
User=skymarshal
WorkingDirectory=/opt/skymarshal
ExecStart=/opt/skymarshal/.venv/bin/python skymarshal/web/run.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Reverse Proxy (Caddy)
```
handle_path /skymarshal/* {
    reverse_proxy localhost:5051
}
```

## Troubleshooting

### Common Issues

**Session Lost on Refresh**
- Check browser cookies enabled
- Verify session cookie path matches app prefix
- Check for session expiration (24h default)

**Data Not Loading**
- Verify JSON file exists: `ls ~/.skymarshal/json/`
- Check file permissions
- Review logs for errors

**Slow Search Performance**
- Enable engagement cache in settings
- Reduce result limit
- Check available memory

**Authentication Failures**
- Ensure using app password (not main password)
- Verify handle format (username.bsky.social)
- Check network connectivity

## Future Enhancements

### Short Term (v0.3.0)
- [ ] Dark mode toggle
- [ ] Search presets
- [ ] Keyboard shortcuts
- [ ] Pagination
- [ ] Export filtered results

### Medium Term (v0.4.0)
- [ ] Scheduled deletion
- [ ] Content analytics dashboard
- [ ] Follow/unfollow management
- [ ] Bulk editing
- [ ] Content scheduling

### Long Term (v1.0.0)
- [ ] Multi-account support
- [ ] Team collaboration
- [ ] Advanced analytics
- [ ] API for integrations
- [ ] Mobile app

## Contributing

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for:
- Code style guidelines
- Pull request process
- Testing requirements
- Documentation standards

## License

See [LICENSE](../../LICENSE) for details.
