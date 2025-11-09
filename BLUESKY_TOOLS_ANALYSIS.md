# Bluesky Tools Analysis & Integration Plan

## Overview

This document analyzes all existing Bluesky tools across the `tools_bluesky` directory and provides a comprehensive plan for idealizing, merging, and building interfaces for each tool category.

## 🔍 Existing Tools Analysis

### 1. **bluesky_tools/** - Standalone CLI Scripts

#### A. **bluesky_cleaner.py** - Following Cleanup Tool
**Purpose**: Analyzes accounts you follow to identify potential bots/spam accounts
**Key Features**:
- Analyzes follower-to-following ratios
- Interactive unfollowing with individual review or bulk options
- Smart caching system (SQLite database)
- Safety measures to prevent accidental mass unfollowing
- Batch processing (25 profiles per request)
- Rate limiting (3000 req/5min)

**Core Class**: `BlueskyFollowingCleaner`
**Database**: `bluesky_profiles.db`

#### B. **bluesky_follower_ranker.py** - Follower Analysis Tool
**Purpose**: Ranks a Bluesky user's followers from most followed to least followed
**Key Features**:
- Standard follower ranking by follower count
- Bot indicator analysis (low follower/following ratio)
- Quality follower analysis (selective following behavior)
- Smart caching system for fast subsequent runs
- Export to formatted text file with multiple analyses
- Unlimited follower analysis (no artificial caps)

**Core Class**: `BlueskyFollowerRanker`
**Database**: `bluesky_profiles.db` (shared)

#### C. **pull_and_rank_posts.py** - Post Analysis Tool
**Purpose**: Fetches and analyzes all posts for a given Bluesky user
**Key Features**:
- Parallelized, paginated fetching for posts (concurrency for speed)
- Deduplication by post URI
- Batch upserts for posts and profiles
- WAL mode, PRAGMAs, and indexes for DB performance
- Accessible CLI output and error messages
- Lists top N most liked posts

**Core Class**: `PostFetcher`
**Database**: SQLite with posts and profiles tables

#### D. **vibe_check_posts.py** - AI Content Analysis Tool
**Purpose**: Performs AI-powered "vibe check" and summary on user's posts
**Key Features**:
- Authenticates with BlueSky API using XAI credentials/endpoints
- Leverages optimized post fetching logic with DB caching
- Performs efficient bulk checks to avoid unnecessary API calls
- Stores posts and profiles in local SQLite DB
- Uses XAI model for content analysis and summarization
- CLI usage with multiple analysis options

**Dependencies**: `bluevibes_db.py`, `bluevibes_ai.py`
**Database**: `.bluevibes.db`

#### E. **bluesky_post_import_cli.py** - Post Import Tool
**Purpose**: Simple post import and storage tool
**Key Features**:
- Prompts for BlueSky username and password (password masked)
- Authenticates with BlueSky API
- Fetches the last 50 posts for the authenticated user
- Stores posts in database with deduplication (using URI)
- Displays each post with confirmation if newly saved or already present

### 2. **bluevibes/** - Flask Web Profile Viewer

**Purpose**: Web application for searching and viewing Bluesky profiles
**Key Features**:
- User authentication with Bluesky credentials
- Profile searching by username or display name
- Profile viewing with detailed information
- Recent posts with images and interaction stats
- Followers and following lists
- Direct profile access via handle
- Responsive design for desktop and mobile
- CLI interface using Rich

**Core Components**:
- `src/app.py` - Flask web application
- `src/bluesky_client.py` - Bluesky API client
- `src/cli.py` - Command-line interface
- Templates for web interface

### 3. **blueeyes/claude/bluesky_manager/** - Advanced Modular Implementation

**Purpose**: Comprehensive Bluesky social media management tool
**Key Features**:
- Modular architecture with separate CLI, web, core, and storage modules
- FastAPI web application with real-time WebSocket support
- Advanced bot detection using multiple algorithms
- PostgreSQL database with Redis caching
- Comprehensive testing with unit and integration tests
- Professional tooling with Poetry, pre-commit hooks, and CI/CD

**Core Modules**:
- `core/` - Business logic (client, analytics, operations, security)
- `cli/` - Command-line interface with interactive mode
- `web/` - FastAPI web application with API endpoints
- `storage/` - Database models, caching, and migrations
- `tests/` - Comprehensive test suite

### 4. **bluesky/** - Static HTML/JavaScript Frontend

**Purpose**: Static web interface for Bluesky browsing
**Key Features**:
- Client-side only implementation
- HTML/CSS/JavaScript frontend
- Static asset management

## 🎯 Tool Categories & Integration Strategy

### Category 1: **Analytics & Ranking Tools**
- `bluesky_follower_ranker.py`
- `pull_and_rank_posts.py`
- `vibe_check_posts.py`

**Integration Plan**: Create `skymarshal/analytics/` module with:
- `FollowerAnalyzer` - Based on bluesky_follower_ranker.py
- `PostAnalyzer` - Based on pull_and_rank_posts.py
- `ContentAnalyzer` - Based on vibe_check_posts.py

### Category 2: **Cleanup & Management Tools**
- `bluesky_cleaner.py`
- `bluesky_post_import_cli.py`

**Integration Plan**: Create `skymarshal/cleanup/` module with:
- `FollowingCleaner` - Based on bluesky_cleaner.py
- `PostImporter` - Based on bluesky_post_import_cli.py

### Category 3: **Profile & Social Tools**
- `bluevibes/` (Flask web viewer)
- `blueeyes/claude/bluesky_manager/` (Advanced implementation)

**Integration Plan**: 
- Merge bluevibes functionality into Skymarshal web interface
- Extract useful components from blueeyes for Skymarshal modules

### Category 4: **Static Frontend**
- `bluesky/` (Static HTML/JS)

**Integration Plan**: Use as reference for modern frontend components

## 🏗️ Unified Architecture Design

### Core Principles
1. **Modular Design**: Each tool becomes a focused module
2. **Shared Services**: Common authentication, caching, and database services
3. **Unified Web Interface**: Single dashboard with tool categories
4. **Progressive Enhancement**: CLI → Web → Advanced features
5. **Accessibility First**: All interfaces must be accessible

### Proposed Module Structure
```
skymarshal/
├── analytics/           # Analytics & ranking tools
│   ├── follower_analyzer.py
│   ├── post_analyzer.py
│   ├── content_analyzer.py
│   └── __init__.py
├── cleanup/            # Cleanup & management tools
│   ├── following_cleaner.py
│   ├── post_importer.py
│   └── __init__.py
├── social/             # Social & profile tools
│   ├── profile_viewer.py
│   ├── relationship_manager.py
│   └── __init__.py
├── web/                # Enhanced web interface
│   ├── analytics_dashboard.html
│   ├── cleanup_dashboard.html
│   ├── social_dashboard.html
│   └── unified_dashboard.html
└── services/           # Shared services
    ├── analytics_service.py
    ├── cleanup_service.py
    └── social_service.py
```

## 🚀 Implementation Plan

### Phase 1: Core Module Integration
1. **Create analytics module** from existing ranking tools
2. **Create cleanup module** from existing cleanup tools
3. **Integrate shared services** (auth, caching, database)
4. **Update Skymarshal CLI** to include new modules

### Phase 2: Web Interface Enhancement
1. **Create analytics dashboard** for ranking and analysis tools
2. **Create cleanup dashboard** for management tools
3. **Create social dashboard** for profile and relationship tools
4. **Create unified dashboard** showing all available tools

### Phase 3: Advanced Features
1. **Real-time updates** using WebSocket/SSE
2. **Advanced filtering and search** across all tools
3. **Export functionality** for all analysis results
4. **API endpoints** for external integrations

### Phase 4: Optimization & Polish
1. **Performance optimization** for large datasets
2. **Accessibility improvements** across all interfaces
3. **Mobile responsiveness** for all web interfaces
4. **Comprehensive testing** and documentation

## 🔧 Technical Implementation Details

### Database Schema Updates
```sql
-- Analytics tables
CREATE TABLE follower_analyses (
    id INTEGER PRIMARY KEY,
    user_did TEXT NOT NULL,
    analysis_type TEXT NOT NULL,
    results TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE post_analyses (
    id INTEGER PRIMARY KEY,
    user_did TEXT NOT NULL,
    analysis_type TEXT NOT NULL,
    results TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Cleanup tables
CREATE TABLE cleanup_operations (
    id INTEGER PRIMARY KEY,
    user_did TEXT NOT NULL,
    operation_type TEXT NOT NULL,
    target_dids TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Web Interface Routes
```python
# Analytics routes
@app.route('/analytics/followers')
@app.route('/analytics/posts')
@app.route('/analytics/content')

# Cleanup routes
@app.route('/cleanup/following')
@app.route('/cleanup/posts')

# Social routes
@app.route('/social/profiles')
@app.route('/social/relationships')

# Unified dashboard
@app.route('/dashboard')
```

### API Endpoints
```python
# Analytics API
/api/analytics/followers/rank
/api/analytics/posts/analyze
/api/analytics/content/vibe-check

# Cleanup API
/api/cleanup/following/analyze
/api/cleanup/following/unfollow
/api/cleanup/posts/import

# Social API
/api/social/profiles/search
/api/social/profiles/view
/api/social/relationships/analyze
```

## 📊 Benefits of Integration

### For Users
1. **Single Interface**: All Bluesky tools in one place
2. **Consistent Experience**: Unified design and interaction patterns
3. **Shared Data**: Analytics and cleanup tools can share cached data
4. **Progressive Workflow**: Start with simple tools, progress to advanced features

### For Developers
1. **Code Reuse**: Shared authentication, caching, and database services
2. **Maintainability**: Centralized codebase with clear module boundaries
3. **Extensibility**: Easy to add new tools following established patterns
4. **Testing**: Comprehensive test suite across all modules

### For Performance
1. **Shared Caching**: All tools benefit from shared profile and post caches
2. **Batch Operations**: Combined operations reduce API calls
3. **Database Optimization**: Single database with optimized queries
4. **Memory Efficiency**: Shared data structures and services

## 🎯 Next Steps

1. **Start with analytics module** - Most mature and well-tested tools
2. **Create web interfaces** for each tool category
3. **Integrate shared services** for authentication and caching
4. **Build unified dashboard** showing all available tools
5. **Add advanced features** like real-time updates and API endpoints

This integration will create a comprehensive Bluesky management platform that combines the best features of all existing tools while providing a unified, accessible, and maintainable interface.