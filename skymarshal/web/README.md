# Skymarshal Web Interface

A Flask-based web interface for Skymarshal, providing a user-friendly way to manage your Bluesky content through a web browser.

## Features

- **Secure Authentication**: Login with your Bluesky credentials
- **CAR File Processing**: Download and process complete Bluesky archives
- **Content Selection**: Choose specific content types (posts, likes, reposts) and limits
- **Real-time Progress**: Visual feedback during data processing
- **Interactive Dashboard**: Overview cards showing engagement metrics and statistics
- **Advanced Search**: Filter content by keywords, dates, engagement levels, and more
- **Bulk Operations**: Select and delete multiple items with safety confirmations
- **Professional UI**: Clean, responsive design with progress indicators

## Installation

1. **Install Python dependencies**:
   ```bash
   cd skymarshal/web
   pip install -r requirements.txt
   ```

2. **Install Skymarshal dependencies** (if not already installed):
   ```bash
   cd ../..
   pip install -e ".[dev]"
   ```

## Running the Web App

```bash
cd skymarshal/web
python app.py
```

The web interface will be available at: http://localhost:5051

### Lightweight Interface

For a minimal workflow focused on login, search, and deletion you can start the
lite app:

```bash
cd skymarshal/web
python lite_app.py
```

This exposes a streamlined UI at http://localhost:5050 that mirrors the core
CLI flows with quick filters and bulk delete actions.

## Usage Flow

### 1. Authentication
- Navigate to the login page
- Enter your Bluesky handle (with or without `.bsky.social`)
- Use an app password from your Bluesky settings

### 2. Data Setup
- **Step 1**: Download your CAR file (complete Bluesky archive)
- **Step 2**: Select content types to analyze:
  - Posts (your original content)
  - Likes (content you've liked)
  - Reposts (content you've shared)
- Set limits for each type (0 = all content)

### 3. Dashboard & Analysis
- View overview cards with total counts and engagement metrics
- See engagement breakdowns (top posts, average, low engagement, dead threads)
- Access search and filtering tools

### 4. Search & Filter
- **Keyword search**: Find content containing specific text
- **Content type filters**: Posts, likes, or reposts
- **Date range**: Filter by creation date
- **Engagement range**: Filter by like/repost/reply counts
- **Media filters**: Content with images/videos
- **Reply filters**: Original posts vs replies

### 5. Content Management
- **View results**: See filtered content in a table format
- **Select items**: Individual checkboxes or select/deselect all
- **Bulk deletion**: Delete multiple items with confirmation
- **Individual deletion**: Delete single items with confirmation

## Security Features

- **Session-based authentication**: No passwords stored
- **User data isolation**: Each user can only access their own data
- **File access validation**: Secure file operations
- **Multiple confirmations**: Prevent accidental deletions

## File Structure

```
skymarshal/web/
├── app.py                    # Main Flask application
├── requirements.txt          # Python dependencies
├── static/
│   ├── css/style.css        # Styling and responsive design
│   └── js/main.js           # Utility functions
└── templates/
    ├── base.html            # Base template with navigation
    ├── login.html           # Authentication page
    ├── setup.html           # CAR download and content selection
    └── dashboard.html       # Main interface with search and results
```

## API Endpoints

- `GET /` - Redirect to login or dashboard
- `POST /login` - Authenticate user
- `GET /logout` - Clear session
- `GET /setup` - Data setup page
- `POST /download-car` - Stream CAR download progress
- `POST /process-data` - Stream data processing progress
- `GET /dashboard` - Main dashboard
- `POST /search` - Search and filter content
- `POST /delete` - Delete selected content

## Technical Details

### Real-time Updates
- Server-Sent Events (SSE) for progress updates during:
  - CAR file downloads
  - Data processing and engagement hydration
- No WebSocket required - uses standard HTTP streaming

### Data Processing
- Uses existing Skymarshal managers for all operations:
  - `AuthManager` for authentication
  - `DataManager` for CAR processing and data management  
  - `SearchManager` for filtering and statistics
  - `DeletionManager` for safe content removal

### Performance
- Batched processing for large datasets
- Progressive loading with visual feedback
- Optimized search results (limited to 100 items for UI performance)
- Efficient engagement score calculations with caching

### Error Handling
- Graceful degradation on API failures
- User-friendly error messages
- Automatic retry for authentication issues
- Progress recovery on connection issues

## Development

The web interface integrates seamlessly with the existing Skymarshal codebase, reusing all core functionality while providing a modern web-based user experience.

For development setup, see the main Skymarshal documentation in `CLAUDE.md`.
