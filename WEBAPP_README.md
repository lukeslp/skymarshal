# Skymarshal Web Application

A simple, single-page Flask web application that provides an intuitive interface for Bluesky account analysis.

## Features

🔐 **Simple Authentication** - Login with your Bluesky credentials  
📥 **Automatic Data Download** - Downloads your complete account backup (.car file)  
🔍 **Data Processing** - Extracts and processes posts, likes, and reposts  
💫 **Engagement Enrichment** - Adds engagement scores and categorization  
📊 **Comprehensive Analytics** - Detailed statistics and insights  
🎨 **Modern UI** - Clean, responsive interface with visual charts  

## Quick Start

### Option 1: Using the Startup Script (Recommended)
```bash
# From the skymarshal directory
./start_webapp.sh
```

### Option 2: Manual Setup
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install flask atproto rich

# Start the application
python webapp.py
```

## Usage

1. **Start the Application**
   - Run `./start_webapp.sh` or `python webapp.py`
   - Open http://localhost:5000 in your browser

2. **Authenticate**
   - Enter your Bluesky handle (username.bsky.social or @username)
   - Enter your Bluesky password
   - Click "Authenticate & Continue"

3. **Process Data**
   - Click "Download & Analyze Data" on the dashboard
   - Wait for processing to complete (may take several minutes for large accounts)

4. **View Statistics**
   - Explore comprehensive analytics including:
     - Account overview (posts, likes, reposts)
     - Engagement distribution and patterns
     - Recent activity trends
     - Content quality metrics
     - Top performing posts

## What Gets Analyzed?

### 📝 Posts
- Text content analysis
- Engagement metrics (likes, reposts, replies)
- Posting patterns and timing
- Content quality assessment

### ❤️ Likes
- Like counts and patterns
- Content preferences
- Interaction behaviors

### 🔁 Reposts
- Sharing behavior analysis
- Content amplification patterns
- Community engagement metrics

## Data Processing Pipeline

1. **Authentication** - Secure login with Bluesky credentials
2. **Download** - Fetches complete account backup (.car file)
3. **Extraction** - Processes CAR file to extract posts, likes, reposts
4. **Enrichment** - Adds engagement scores using weighted formula:
   - `engagement_score = likes + (2 × reposts) + (2.5 × replies)`
5. **Categorization** - Classifies content by engagement level:
   - Dead (0 interactions)
   - Low (1-2 interactions)
   - Medium (3-10 interactions)
   - High (11-50 interactions)
   - Viral (50+ interactions)
6. **Analytics** - Generates comprehensive statistics and insights

## Security & Privacy

- 🔒 **No Data Storage** - Credentials are used only for authentication
- 🏠 **Local Processing** - All data processing happens on your machine
- 🔐 **Session-Based** - No persistent storage of credentials
- 🛡️ **File Isolation** - Users can only access their own data files

## Technical Details

### Architecture
- **Backend**: Flask web framework
- **Data Processing**: Integrates with existing Skymarshal managers
- **Authentication**: Uses Skymarshal's AuthManager
- **File Management**: Leverages Skymarshal's DataManager
- **UI**: Responsive HTML/CSS with JavaScript enhancements

### File Structure
```
webapp.py              # Main Flask application
templates/
  ├── base.html        # Base template with styling
  ├── login.html       # Authentication page
  ├── dashboard.html   # Main dashboard
  └── statistics.html  # Analytics display
start_webapp.sh        # Startup script
venv/                  # Virtual environment
```

### Dependencies
- `flask>=3.0.0` - Web framework
- `atproto>=0.0.46` - Bluesky/AT Protocol client
- `rich>=13.0.0` - Terminal UI (used by Skymarshal managers)

## Integration with Skymarshal

The web application reuses existing Skymarshal components:

- **AuthManager** - Handles Bluesky authentication and session management
- **DataManager** - Downloads CAR files and processes account data
- **UIManager** - Provides UI utilities (adapted for web)
- **UserSettings** - Manages user preferences and configurations

This ensures consistency with the CLI tool and leverages battle-tested code.

## Performance Notes

- **Large Accounts**: Accounts with 10K+ items may take several minutes to process
- **Memory Usage**: Single-pass algorithms minimize memory footprint
- **Caching**: LRU cache for frequently computed engagement scores
- **Batch Processing**: Configurable batch sizes for different operations

## Troubleshooting

### Common Issues

**Flask not found**
```bash
# Ensure you're in the virtual environment
source venv/bin/activate
pip install flask
```

**Authentication fails**
- Verify your Bluesky credentials
- Check network connectivity
- Ensure Bluesky services are operational

**Processing hangs**
- Large accounts require patience (10K+ items = several minutes)
- Check terminal for error messages
- Restart if stuck for >10 minutes

**No statistics displayed**
- Ensure data processing completed successfully
- Check for error messages in browser console
- Try processing data again

### Development

To run in development mode:
```bash
source venv/bin/activate
export FLASK_ENV=development
python webapp.py
```

## Comparison with CLI Tool

| Feature | Web App | CLI Tool |
|---------|---------|----------|
| **Interface** | Web browser | Terminal |
| **Authentication** | Simple form | Interactive prompts |
| **Data Processing** | One-click | Menu-driven |
| **Statistics** | Visual charts | Rich tables |
| **Export** | Print-friendly | JSON/CSV/TXT |
| **Usability** | Point-and-click | Power users |
| **Deployment** | Local server | Direct execution |

## Future Enhancements

Potential improvements for future versions:

- 📈 Interactive charts with Chart.js or D3.js
- 🔍 Advanced filtering and search capabilities
- 📤 Direct export functionality (JSON, CSV)
- 📱 Mobile-responsive design improvements
- 🔄 Real-time processing updates via WebSockets
- 👥 Multi-user support with proper session management
- 🎨 Customizable themes and dashboards
- 📊 Historical trend analysis
- 🤖 Bot detection integration
- 🌐 Deployment guides for cloud platforms

## License

This web application is part of the Skymarshal project and follows the same licensing terms.