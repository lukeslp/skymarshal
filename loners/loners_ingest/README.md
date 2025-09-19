# Skymarshal Loners - Individual CLI Scripts

This folder contains standalone Python scripts that extract specific functionality from the main Skymarshal application. Each script can be run independently and focuses on a particular aspect of Bluesky content management.

## 📁 Available Scripts

### 🚀 `setup.py` - Initial Setup & Data Processing
**Purpose**: Download and process Bluesky data for analysis
- Authenticate with Bluesky
- Download complete backup (.car file) or API data
- Process CAR files into usable JSON format
- Set up local data structure

**Usage**: `python setup.py`

### 🔐 `auth.py` - Authentication Management
**Purpose**: Handle Bluesky authentication and session management
- Login/logout functionality
- Switch between accounts
- Test API connections
- View authentication status

**Usage**: `python auth.py`

### 🔍 `search.py` - Search & Filter Content
**Purpose**: Advanced search and filtering capabilities
- Load and search through downloaded data
- Filter by keywords, engagement levels, content types
- Sort results by various criteria
- Export search results

**Usage**: `python search.py`

### 📊 `stats.py` - Statistics & Analytics
**Purpose**: Comprehensive analytics and statistics
- Basic content statistics
- Engagement breakdown analysis
- Temporal analysis (hour/day/month patterns)
- Top content identification
- Dead threads analysis
- Content distribution analysis

**Usage**: `python stats.py`

### 🗑️ `delete.py` - Content Deletion
**Purpose**: Safe content deletion with multiple approval modes
- Load data and build deletion filters
- Multiple deletion modes (bulk, individual, batch)
- Comprehensive safety checks and confirmations
- Preview before deletion

**Usage**: `python delete.py`

### 💾 `export.py` - Data Export
**Purpose**: Export data in various formats
- Filter content for export
- Export to JSON, CSV, or Markdown formats
- Comprehensive data export with metadata

**Usage**: `python export.py`

### ⚙️ `settings.py` - Settings Management
**Purpose**: Manage user preferences and configuration
- View and edit current settings
- Reset settings to defaults
- Export/import settings backups
- Settings help and documentation

**Usage**: `python settings.py`

### ❓ `help.py` - Help & Documentation
**Purpose**: Comprehensive help and documentation
- Getting started guide
- Authentication help
- Search and filter help
- Deletion help
- Statistics help
- Terminology and legend
- Tips and tricks
- Troubleshooting guide

**Usage**: `python help.py`

### 📁 `data_management.py` - Data Management
**Purpose**: File operations, backup management, and data cleanup
- Data overview and file status
- Download CAR backups and API data
- Process CAR files into JSON format
- Backup and organize files
- Clear local data
- File details and diagnostics

**Usage**: `python data_management.py`

### ℹ️ `system_info.py` - System Information
**Purpose**: System status and diagnostic information
- System overview and hardware info
- Skymarshal application status
- Data files status
- Settings status
- Dependencies status
- Network connectivity
- Diagnostic information

**Usage**: `python system_info.py`

### 💥 `nuke.py` - Nuclear Delete
**Purpose**: Delete ALL content with multiple safety confirmations
- Interactive nuclear deletion with multiple confirmations
- Select specific collections to delete (posts, likes, reposts)
- Create backup before deletion
- Multiple safety checks and warnings
- Comprehensive confirmation process

**Usage**: `python nuke.py`

### 📊 `analyze.py` - Account Analysis
**Purpose**: Comprehensive analysis of your Bluesky account
- Basic account statistics and engagement metrics
- Content timeline analysis and posting patterns
- Content quality analysis with recommendations
- Follower growth analysis based on activity trends
- Export analysis results in multiple formats

**Usage**: `python analyze.py`

### 🤖 `find_bots.py` - Bot Detection
**Purpose**: Identify potential bot accounts in your data
- Quick bot scan using standard criteria
- Detailed bot analysis with confidence scoring
- Custom detection rules with user-defined parameters
- Bot pattern analysis and statistical insights
- Export bot results and remove bot content

**Usage**: `python find_bots.py`

### 🧹 `cleanup.py` - Content Cleanup
**Purpose**: Clean up unwanted content and spam
- Find cleanup candidates (duplicates, dead posts, bot content)
- Remove duplicate content with safety checks
- Clean up posts with no engagement
- Remove bot-like content and spam
- Custom cleanup rules with user-defined criteria
- Export cleanup results and cleaned data

**Usage**: `python cleanup.py`

## 🚀 Quick Start

1. **First Time Setup**:
   ```bash
   python setup.py
   ```
   This will authenticate you with Bluesky and download/process your data.

2. **Explore Your Data**:
   ```bash
   python stats.py    # View analytics
   python search.py   # Search and filter content
   ```

3. **Export Data**:
   ```bash
   python export.py   # Export in various formats
   ```

4. **Manage Content**:
   ```bash
   python delete.py   # Delete content (with safety checks)
   ```

5. **Configure Settings**:
   ```bash
   python settings.py # Manage preferences
   ```

6. **Get Help**:
   ```bash
   python help.py     # Comprehensive help
   ```

7. **Manage Files**:
   ```bash
   python data_management.py  # File operations
   ```

8. **System Status**:
   ```bash
   python system_info.py      # System information
   ```

9. **Nuclear Delete** (⚠️ DANGER):
   ```bash
   python nuke.py             # Delete ALL content
   ```

10. **Account Analysis**:
    ```bash
    python analyze.py          # Analyze your account
    ```

11. **Bot Detection**:
    ```bash
    python find_bots.py        # Find potential bots
    ```

12. **Content Cleanup**:
    ```bash
    python cleanup.py          # Clean up unwanted content
    ```

## 📋 Prerequisites

- Python 3.8 or higher
- Skymarshal dependencies installed (`pip install -e ..`)
- Bluesky account credentials

## 🔧 Configuration

All scripts use the same configuration system as the main Skymarshal application:
- Settings file: `~/.car_inspector_settings.json`
- Data directory: `~/.skymarshal/`
- CAR files: `~/.skymarshal/cars/`
- JSON files: `~/.skymarshal/json/`

## 🛡️ Safety Features

- **Authentication Required**: All destructive operations require authentication
- **Multiple Confirmations**: Deletion operations have multiple safety checks
- **Preview Before Action**: See what will be affected before proceeding
- **Dry-run Capabilities**: Preview operations without execution
- **Comprehensive Error Handling**: Graceful failure with helpful error messages

## 📚 Usage Examples

### Download and Process Data
```bash
python setup.py
# Follow prompts to authenticate and download data
```

### Search for Specific Content
```bash
python search.py
# Load data file → Build search filters → View results
```

### Analyze Engagement Patterns
```bash
python stats.py
# Load data → View temporal analysis → See engagement breakdown
```

### Export Filtered Data
```bash
python export.py
# Load data → Apply filters → Export to JSON/CSV/Markdown
```

### Delete Low-Engagement Content
```bash
python delete.py
# Load data → Filter for dead threads → Choose deletion mode → Execute
```

## 🔄 Workflow Integration

These scripts are designed to work together:

1. **Setup** → Download and process your data
2. **Stats** → Understand your content patterns
3. **Search** → Find specific content
4. **Export** → Save filtered results
5. **Delete** → Remove unwanted content
6. **Settings** → Configure preferences
7. **Help** → Get assistance and documentation
8. **Data Management** → Organize and maintain files
9. **System Info** → Monitor system status
10. **Nuclear Delete** → Delete ALL content (⚠️ DANGER)

## ⚠️ Important Notes

- **Backup First**: Always backup your data before deletion operations
- **Authentication**: Some operations require fresh authentication
- **Data Freshness**: After deletions, refresh your local data to see current state
- **Rate Limits**: Scripts respect Bluesky API rate limits

## 🐛 Troubleshooting

- **Import Errors**: Make sure you're running from the `loners/` directory
- **Authentication Issues**: Use `auth.py` to test and manage authentication
- **Data Not Found**: Run `setup.py` first to download and process data
- **Permission Errors**: Ensure you have write access to `~/.skymarshal/`

## 📖 Documentation

For detailed documentation, see the main Skymarshal documentation:
- [README.md](../README.md) - Main project documentation
- [ARCHITECTURE.md](../ARCHITECTURE.md) - System architecture
- [API.md](../API.md) - API reference

## 🤝 Contributing

These scripts are extracted from the main Skymarshal codebase. To contribute:
1. Make changes to the main Skymarshal modules
2. Update the corresponding loner script
3. Test both the main application and individual scripts
4. Submit pull requests to the main repository