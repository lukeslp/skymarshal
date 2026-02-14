# bsky-follow-analyzer Repository Analysis

## Overview

The **bsky-follow-analyzer** repository is a planned comprehensive **Bluesky Social Network Management Platform** - a unified web application designed to consolidate and expand functionality from multiple existing projects into a single, feature-rich platform for managing and analyzing Bluesky accounts.

## Functionality & Purpose

### Primary Goal
Transform the follow analyzer tool into a **multi-module platform** that handles:
1. **Network Analysis** - Graph operations, follower/following relationships, community detection
2. **Content Management** - Posts, likes, reposts, deletion, drafts, scheduling
3. **Analytics & Insights** - Engagement metrics, sentiment analysis, posting patterns, top performers
4. **Chat/DM Management** - Full messaging with reactions and conversation management
5. **Account Maintenance** - Cleanup, tagging, filtering, bot detection
6. **Backup & Recovery** - CAR file export/restore, data portability

## Relationship to Skymarshal

This repository is the **design specification** and **vision document** for an expanded version of skymarshal. Key connections:

### Current Skymarshal (what exists)
- Flask backend at port 5050 with 35 REST API routes
- React frontend for Bluesky unified client
- Follower analysis and network graph capabilities
- Batch unfollowing and account management
- AT Protocol integration

### bsky-follow-analyzer (what's planned)
- **Skymarshal 2.0**: Consolidation of 7+ related projects into one platform
- New npm package: `skymarshal-core` (TypeScript toolkit for Bluesky operations)
- Expanded feature set covering content creation, chat, backup, etc.
- Database schema for analytics, backups, interactions, and tags

## Source Projects Being Consolidated

| Project | Language | Key Contributions to Skymarshal |
|---------|----------|----------------------------------|
| **skymarshal** (Python CLI) | Python | Manager pattern, CAR processing, engagement cache, safe deletion |
| **skymarshal-js** | TypeScript | Auth manager, search/content models |
| **bluesky-tools** | Python | Follower ranking, ego networks, bot detection |
| **firehose** | TypeScript | Real-time streaming, sentiment (VADER), feature extraction |
| **bluesky-chat** | TypeScript | Full DM/chat API implementation with reactions |
| **BlueSky Manager (blueeyes)** | Python | Graph operations, batch analysis |
| **BlueDreams** (browser ext) | CSS/JS | UI patterns, metric hiding, transparency |

## Platform Architecture

### Core Technology Stack
- **Frontend**: React 19 + Tailwind CSS 4 + shadcn/ui (Radix UI)
- **Backend**: Express + tRPC or Flask
- **Database**: MySQL (configurable, can support SQLite for VPS)
- **Real-time**: Socket.IO (for firehose streaming)
- **Authentication**: Direct AT Protocol (no OAuth)
- **Charts**: Recharts for visualizations

### Package Structure
```
skymarshal-core (npm package)
├── types/
│   ├── content.ts         (Post, Like, Repost, ContentItem)
│   ├── profile.ts         (Profile, FollowRelation, NetworkAnalysis)
│   ├── engagement.ts      (EngagementStats, Sentiment)
│   └── search.ts          (SearchFilters, SortMode)
├── managers/
│   ├── AuthManager        (enhanced with profile ops)
│   ├── ContentManager     (NEW - posts, likes, reposts, deletion)
│   ├── NetworkManager     (NEW - ego networks, graph analysis)
│   ├── SearchManager      (enhanced filtering, ranking)
│   └── AnalyticsManager   (NEW - sentiment, trends, features)
├── services/
│   ├── api.ts            (AT Protocol wrappers)
│   ├── sentiment.ts      (VADER sentiment analysis)
│   └── features.ts       (Feature extraction)
└── utils/
    ├── engagement.ts     (Scoring functions)
    ├── pagination.ts     (Cursor-based pagination)
    ├── cache.ts          (TTL caching)
    └── datetime.ts       (Date utilities)
```

### Unified Database Schema
```
Core (existing):
- users (DID, handle, credentials)
- sessions (auth tokens)
- follow_analysis (followers, mutuals, blocking, muting)
- tags (user-defined categorization)

New Content Layer:
- posts (URI, CID, text, engagement, sentiment, metadata)
- likes (tracking user's liked posts)
- reposts (repost records)

Analytics Layer:
- engagement_stats (daily engagement metrics)
- backup_history (CAR file tracking)

Firehose Layer (optional):
- firehose_sessions (keyword monitoring)
- firehose_posts (real-time post capture)
```

## Key Features Being Planned

### Phase 1: Core Infrastructure (Current)
- [x] Bluesky authentication (handle + app password)
- [x] Following/follower fetching with pagination
- [x] Bot detection via ratio analysis
- [x] Interaction pattern detection
- [x] MySQL caching layer

### Phase 2: Enhanced Navigation (Sidebar)
- [ ] Collapsible module navigation
- [ ] Dashboard overview cards
- [ ] Breadcrumb navigation

### Phase 3: Content Management
- [ ] Posts viewer with engagement stats
- [ ] Likes/Reposts managers
- [ ] Bulk delete operations
- [ ] Draft & scheduled posts

### Phase 4: Analytics Dashboard
- [ ] Engagement trends charts
- [ ] Top performers list
- [ ] Dead threads detector
- [ ] Posting patterns heatmap

### Phase 5: Backup & Export
- [ ] CAR file download
- [ ] JSON/CSV export
- [ ] Backup scheduling
- [ ] Restore functionality

### Phase 6: Network Visualization (Optional)
- [ ] Ego network graphs
- [ ] Follow relationship visualization
- [ ] Community detection

### Phase 7: Firehose Integration (Optional)
- [ ] Real-time stream connection
- [ ] Keyword monitoring
- [ ] Sentiment analysis dashboard

## Comprehensive Feature Set

### Network Analysis
- Full following list with activity status
- Followers analysis with interaction tracking
- Mutual connections mapping
- Bot detection (follower/following ratios)
- Blocking & muting relationships
- One-way followers (following back analysis)
- Network graph visualization
- Community detection (Louvain algorithm)
- PageRank and centrality analysis

### Content Management
- Browse user's posts with engagement metrics
- Like/Repost management
- Safe bulk deletion with confirmation
- Post filtering (date range, engagement level)
- Keyword-based search
- Hashtag & mention extraction
- Media library management
- Draft posts & scheduling

### Analytics & Insights
- Engagement statistics (likes, reposts, replies)
- Top performing posts identification
- Dead thread detection
- Posting pattern analysis (time of day, days of week)
- Sentiment analysis (VADER-based)
- Audience insights & interaction matrix
- Hashtag & mention frequency

### Chat/DM Management
- Full conversation browsing
- Send/receive messages with reactions
- Delete messages with rollback
- Mute/unmute conversations
- Message search

### Account Tools
- Batch unfollowing with progress tracking
- Following cleanup (detect inactive/deleted accounts)
- Custom tag system for account categorization
- Predefined tags (Close Friends, Professional, Inactive, Consider Unfollowing)
- Bulk tag assignment
- Filter by tags

### Backup & Portability
- CAR file export for account backups
- JSON/CSV data export
- Scheduled backup jobs
- Restore from backup
- Data transparency dashboard

## npm Package: skymarshal-core

**Published as**: `skymarshal-core@2.0.0`

### Managers Exported

```typescript
// Authentication
export { AuthManager };

// Content operations
export { ContentManager };

// Network analysis
export { NetworkManager };

// Search & filtering
export { SearchManager };

// Analytics
export { AnalyticsManager };
```

### Usage Example

```typescript
import { AuthManager, ContentManager, NetworkManager } from 'skymarshal-core';

const auth = new AuthManager();
await auth.login('handle.bsky.social', 'app-password');

const content = new ContentManager(auth);
const posts = await content.getPosts({ limit: 500 });

const network = new NetworkManager(auth);
const analysis = await network.analyzeNetwork();
```

## Design Philosophy

1. **Direct AT Protocol**: No OAuth complexity, direct handle + app password authentication
2. **Type Safety**: Full TypeScript with comprehensive interfaces
3. **Reusability**: Extract and consolidate logic from 7+ projects
4. **Multi-user Support**: Database-backed sessions (not just client-side)
5. **VPS Deployment Ready**: Configurable DB (MySQL or SQLite)
6. **Performance**: Engagement caching with age-based TTL
7. **Transparency**: Clear data limitation notifications (30-day notification history limit)

## Comparison: Existing Features vs Planned Expansion

### Today (Current Skymarshal)
- Following list analysis
- Bot detection
- Batch unfollowing
- Following cleanup
- Network analysis basics
- CSV export

### Tomorrow (bsky-follow-analyzer vision)
- Everything above, PLUS:
- Full content management (posts, likes, reposts)
- Real-time analytics dashboard
- Sentiment analysis
- Engagement trend tracking
- Chat/DM management
- Backup/restore functionality
- Real-time firehose monitoring (optional)
- Customizable tagging system
- Drafts & scheduled posts
- Account organization tools

## Implementation Status

Currently in **design & architecture phase**:
- Architecture documents created (PLATFORM_ARCHITECTURE.md)
- Core package design specified (SKYMARSHAL_CORE_DESIGN.md)
- Feature roadmap documented (todo.md with 80+ tasks)
- Tech stack defined
- Database schema drafted

The `skymarshal-core` npm package referenced is a **planned dependency** to extract shared functionality from existing projects into a reusable TypeScript library.

## Key Dependencies

- `@atproto/api` - AT Protocol SDK
- `express` or `flask` - Backend framework
- `react 19` - UI framework
- `tailwindcss` - Styling
- `vaderSentiment` - Sentiment analysis
- `networkx` - Graph algorithms (Python)
- `recharts` - Data visualization
- `socket.io` - Real-time updates
- `drizzle-orm` - Database ORM

## Next Steps for Integration

1. **Extract shared logic** from 7+ projects into `skymarshal-core`
2. **Design unified database schema** supporting all features
3. **Implement expanded Flask/Express backend** with new endpoints
4. **Build enhanced React UI** with modular pages
5. **Add real-time capabilities** (Socket.IO for firehose)
6. **Publish `skymarshal-core` to npm** for reusability
7. **Deploy to VPS** with configurable database

## Summary

**bsky-follow-analyzer** is the codename for **Skymarshal 2.0** - an ambitious consolidation of 7+ Bluesky-related projects into a single, comprehensive platform for network analysis, content management, and account maintenance. It represents the vision to create the **most complete Bluesky power-user toolkit**, with full TypeScript tooling (`skymarshal-core`) for other developers to build with.
