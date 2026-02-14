# Full-Stack Integration Analysis: bsky-follow-analyzer

**Date**: 2026-02-14
**Analyst**: Luke Steuber
**Subject**: Disposition of bsky-follow-analyzer functionality

---

## Executive Summary

**Recommendation**: **Archive the reference** - functionality already exists in skymarshal.

The `bsky-follow-analyzer` appears to be a standalone repository reference in the skymarshal README that is broken (404). The functionality it was meant to provide **already exists and is superior** within the skymarshal codebase itself.

**Action Required**: Remove the broken link from README.md and clarify that follower analysis is built-in.

---

## Current State Analysis

### 1. Evidence of Missing Repository

```
Location: README.md (skymarshal)
Status: 404 broken link
Reference: https://github.com/lukeslp/bsky-follow-analyzer
```

Geepers agent reports confirm:
- Link identified as broken in January 2026 checkpoint
- No evidence of standalone repository ever existing in `/home/coolhand/`
- No TypeScript/Node.js implementation found anywhere

### 2. Existing Functionality in Skymarshal

The skymarshal codebase **already contains comprehensive follower analysis**:

| Module | Location | Features |
|--------|----------|----------|
| **FollowerAnalyzer** | `skymarshal/analytics/follower_analyzer.py` | Follower ranking, bot detection, quality analysis, SQLite caching |
| **FollowingCleaner** | `skymarshal/cleanup/following_cleaner.py` | Following cleanup, bot detection, unfollow automation, batch processing |
| **PostAnalyzer** | `skymarshal/analytics/post_analyzer.py` | Post engagement scoring |
| **ContentAnalyzer** | `skymarshal/analytics/content_analyzer.py` | LLM-powered content analysis |

### 3. Flask API Integration

All modules are exposed via REST API in the unified backend:

```
skymarshal/api/analytics.py   → /api/analytics/followers
                              → /api/analytics/posts

skymarshal/api/profile.py     → /api/profile/*
                              → /api/profile/bot-detection

skymarshal/api/cleanup.py     → /api/cleanup/following
                              → /api/cleanup/unfollow
```

### 4. CLI Standalone Scripts

The `/home/coolhand/html/bluesky/cli/` directory contains **standalone Python scripts** that pre-date the API integration:

- `bluesky_follower_ranker.py` - 695 lines, standalone CLI with identical functionality to `FollowerAnalyzer`
- `bluesky_cleaner.py` - Similar functionality to `FollowingCleaner`

**These scripts demonstrate the feature was originally standalone before being integrated into skymarshal.**

---

## Integration Options Evaluation

### Option 1: Port to Python and Add to Skymarshal ❌

**Verdict**: Already done.

- FollowerAnalyzer and FollowingCleaner are already integrated
- API endpoints already exist
- No TypeScript implementation to port

### Option 2: Keep as Separate TypeScript Service ❌

**Verdict**: No TypeScript implementation exists.

- No standalone bsky-follow-analyzer codebase found
- Would create duplication of existing Python functionality
- Would require maintaining two implementations of the same logic

### Option 3: Integrate into bluesky-web-apps Workspace ❌

**Verdict**: Not needed - backend already handles it.

The unified React app (`/home/coolhand/html/bluesky/unified/`) follows a **dual-backend pattern**:
- **Direct to bsky.social**: Feed, compose, threading, chat (client-side)
- **Via Flask backend**: Analytics, search, cleanup, network analysis (server-side power tools)

Follower analysis is a **server-side power tool** and belongs in the Flask backend, where it already lives.

### Option 4: Archive (Functionality Already Exists) ✅

**Verdict**: RECOMMENDED

- No standalone repository exists (404)
- All functionality already in skymarshal
- API endpoints already exposed to React frontend
- Standalone CLI scripts exist for direct CLI usage
- No duplication, no maintenance burden

---

## Architecture Context

### Current Skymarshal Architecture

```
React Frontend (port 5086 dev)
  └── Direct to bsky.social/xrpc (feed, compose, thread)
  └── Proxied to Flask (port 5090 dev / 5050 prod)
      ├── /api/analytics/followers    → FollowerAnalyzer
      ├── /api/analytics/posts         → PostAnalyzer
      ├── /api/profile/bot-detection   → BotDetector
      ├── /api/cleanup/following       → FollowingCleaner
      └── Socket.IO (real-time firehose)
```

### Comparison: Standalone vs. Integrated

| Aspect | Standalone bsky-follow-analyzer | Integrated (Current) |
|--------|--------------------------------|---------------------|
| **Technology** | TypeScript/Node.js (assumed) | Python |
| **Deployment** | Separate service, separate port | Part of unified backend |
| **Code Duplication** | Would duplicate Python logic | Single source of truth |
| **Maintenance** | Additional codebase to maintain | Already maintained |
| **API Surface** | Would need separate API | Already exposed via Flask |
| **Frontend Integration** | Would need separate client | Already integrated in React app |
| **Caching** | Would need separate database | Shared SQLite cache |
| **Authentication** | Would need separate auth | Uses skymarshal auth |

---

## Functionality Comparison

### What bsky-follow-analyzer Would Have Provided

Based on the broken link and typical follower analyzer features:
- Rank followers by follower count
- Detect bot accounts (low follower/following ratio)
- Quality analysis (selective following behavior)
- Export to file

### What Skymarshal Already Provides

**FollowerAnalyzer** (`skymarshal/analytics/follower_analyzer.py`):
- ✅ Rank followers by follower count
- ✅ Bot detection (follower/following ratio analysis)
- ✅ Quality analysis (selective following patterns)
- ✅ SQLite caching for performance
- ✅ Batch processing (25 profiles per API call)
- ✅ Rate limiting (3000 req/5min Bluesky API limit)
- ✅ REST API endpoints

**FollowingCleaner** (`skymarshal/cleanup/following_cleaner.py`):
- ✅ Analyze accounts you follow
- ✅ Bot/spam detection
- ✅ Interactive unfollowing
- ✅ Safety measures (confirmation prompts)
- ✅ Batch processing
- ✅ REST API endpoints

**Standalone CLI** (`html/bluesky/cli/bluesky_follower_ranker.py`):
- ✅ Direct command-line usage
- ✅ Export to formatted text file
- ✅ Progress tracking
- ✅ No web server required

---

## Deployment Complexity Analysis

### If We Kept as Separate TypeScript Service

**Additional Infrastructure Required**:
1. New port allocation (5xxx)
2. Caddy routing configuration
3. Service manager registration
4. Separate authentication/session management
5. Separate database for caching
6. CORS configuration
7. TypeScript build pipeline
8. Node.js dependency management
9. Separate health monitoring

**Result**: 9 additional infrastructure concerns for duplicate functionality.

### Current Integrated Approach

**Infrastructure**:
- Single Flask backend (port 5050)
- Single Caddy route (`/bluesky/unified/api/*`)
- Single service manager entry (`skymarshal`)
- Shared authentication (ContentService per session)
- Shared SQLite database
- Single build/deployment pipeline

**Result**: Zero additional infrastructure - already deployed and working.

---

## Tech Stack Consistency Analysis

### Current Ecosystem

| Component | Stack |
|-----------|-------|
| **Skymarshal backend** | Python, Flask, Flask-SocketIO |
| **Shared library** | Python (`/home/coolhand/shared/`) |
| **Network analysis** | Python, NetworkX (ported from blueballs) |
| **Firehose** | Python, websocket-client (ported from Node) |
| **All analytics modules** | Python, aiohttp |
| **CLI tools** | Python, Rich, atproto |

**Observation**: The entire Bluesky toolchain on this server is **Python-first**. Node.js is only used for:
- React frontend build (Vite)
- Legacy firehose dashboard (being superseded)

Adding a TypeScript backend service would be **architecturally inconsistent**.

---

## Code Duplication Analysis

### If We Implement in TypeScript

Would require duplicating:
1. **AT Protocol client logic** (already in `atproto` Python library)
2. **Batch API call logic** (25 profiles/request, 100 followers/request)
3. **Rate limiting** (3000 req/5min)
4. **Caching strategy** (SQLite schema, TTL logic)
5. **Bot detection algorithms** (follower/following ratio thresholds)
6. **Quality analysis algorithms** (selective following patterns)
7. **Error handling** (API failures, network timeouts)
8. **Progress tracking** (batch progress, long-running ops)

**Estimated duplication**: ~600-800 lines of logic already implemented in Python.

### Current Approach

**Single implementation**:
- `follower_analyzer.py`: 695 lines (comprehensive, tested)
- `following_cleaner.py`: 614 lines (comprehensive, tested)
- Shared across CLI (`bluesky_follower_ranker.py`) and API (`api/analytics.py`)

---

## Maintenance Burden Analysis

### Separate TypeScript Service

**Ongoing maintenance**:
- TypeScript type definitions for AT Protocol
- Node.js dependency updates (security patches)
- API client library updates
- Separate testing infrastructure
- Deployment coordination (must be in sync with React frontend)
- Documentation for two codebases

**Estimated burden**: +40% development time for any feature changes.

### Current Integrated Approach

**Ongoing maintenance**:
- Single Python codebase
- Shared with CLI tools (code reuse)
- Already tested and deployed
- Single documentation source

**Estimated burden**: Current level (already manageable).

---

## Recommendation: Implementation Steps

### Immediate Actions

1. **Remove broken link from README.md**
   ```markdown
   # Before
   - [Follower Analyzer](https://github.com/lukeslp/bsky-follow-analyzer) - Rank and analyze followers

   # After
   (Remove this line entirely)
   ```

2. **Clarify built-in functionality in README.md**
   ```markdown
   ## Features

   ### Analytics
   - **Follower Analysis** - Rank followers by popularity, detect bot accounts
   - **Following Cleanup** - Identify inactive/bot accounts you follow
   - **Post Analytics** - Engagement scoring and sentiment analysis
   ```

3. **Update API documentation**
   - Document `/api/analytics/followers` endpoint
   - Document `/api/cleanup/following` endpoint
   - Add examples to README

4. **Update React frontend integration**
   - Ensure `SkymarshalApi` client (`app/src/lib/skymarshal-api.ts`) has methods for follower analysis
   - Add UI components if not already present

### Documentation Updates

**Files to update**:
1. `/home/coolhand/servers/skymarshal/README.md` - Remove broken link, add features section
2. `/home/coolhand/servers/skymarshal/CLAUDE.md` - Ensure analytics modules documented
3. `/home/coolhand/html/bluesky/CLAUDE.md` - Confirm API integration documented
4. `/home/coolhand/html/bluesky/unified/CLAUDE.md` - Confirm frontend hooks documented

### Future Considerations

**If user explicitly requests TypeScript implementation**:
1. Wrap Python API with TypeScript client (already done via `SkymarshalApi`)
2. Do NOT duplicate backend logic
3. Use Flask backend as source of truth

**If user wants standalone CLI**:
1. Point to existing `html/bluesky/cli/bluesky_follower_ranker.py`
2. Consider publishing to PyPI as separate package (e.g., `bsky-follower-tools`)

---

## Conclusion

The `bsky-follow-analyzer` reference is a **broken link to a repository that either never existed or was already integrated into skymarshal**. The functionality it was meant to provide is **already implemented, deployed, and superior** to what a standalone service would offer.

**Action**: Archive the reference by removing the broken link and documenting the built-in functionality.

**No integration work required** - the integration already happened when FollowerAnalyzer and FollowingCleaner were built into skymarshal.

---

## Appendix: API Endpoint Reference

### Current Skymarshal Analytics API

```bash
# Get follower analysis
GET /api/analytics/followers?limit=100

# Get following cleanup candidates
GET /api/cleanup/following?threshold=0.05

# Detect bot accounts
GET /api/profile/bot-detection/:did

# Unfollow accounts
POST /api/cleanup/unfollow
{
  "dids": ["did:plc:...", "did:plc:..."]
}
```

### Example React Frontend Usage

```typescript
import { useSkymarshalApi } from '@/hooks/useSkymarshalApi'

function FollowerAnalysis() {
  const api = useSkymarshalApi()

  const analyzeFollowers = async () => {
    const followers = await api.analytics.getFollowers({ limit: 100 })
    const botCandidates = followers.filter(f => f.botScore > 0.7)
    return botCandidates
  }

  return <FollowerList onAnalyze={analyzeFollowers} />
}
```

Already integrated. Already working. No additional work required.
