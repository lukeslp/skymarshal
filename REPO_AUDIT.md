# Skymarshal Repository Audit

**Date**: 2026-02-14
**Auditor**: geepers_scout
**Scope**: Public GitHub repositories and local deployments

---

## Executive Summary

Two public repositories exist for skymarshal with **distinct but complementary purposes**. They are NOT redundant. Recommend keeping both public with documentation improvements.

### Key Findings

1. **skymarshal (Python)** - PyPI package v0.1.0, CLI tool + Flask backend
   - Local deployment: `/home/coolhand/servers/skymarshal/`
   - GitHub: https://github.com/lukeslp/skymarshal
   - Status: **KEEP PUBLIC** - Active production service

2. **skymarshal-js (TypeScript)** - npm package v2.3.0, comprehensive toolkit
   - No local deployment (library only)
   - GitHub: https://github.com/lukeslp/skymarshal-js
   - Status: **KEEP PUBLIC** - Active npm package with 2 stars

3. **@bluesky/skymarshal (workspace package)** - Internal only
   - Local: `/home/coolhand/html/bluesky/unified/packages/skymarshal/`
   - Status: Private workspace package for unified React app

---

## Repository Analysis

### 1. skymarshal (Python) - https://github.com/lukeslp/skymarshal

**Purpose**: Bluesky content management CLI and Flask backend
**Published**: PyPI as `skymarshal` v0.1.0
**Stars**: 1
**Last push**: 2026-02-14 (today - active development)

#### Local Deployment
- **Location**: `/home/coolhand/servers/skymarshal/`
- **Service**: Port 5050 (unified backend for React app)
- **Active**: Yes - powers `/bluesky/unified/` React app
- **Git remote**: Correctly linked to `lukeslp/skymarshal`

#### Architecture
- **CLI tool**: Rich terminal UI for content management
- **Flask backend**: 35 REST API routes + Socket.IO
  - 7 blueprints: auth, content, analytics, network, profile, cleanup, firehose
  - Real-time Jetstream integration (WebSocket → Flask-SocketIO)
  - Network analysis (ported from blueballs FastAPI)
- **Venv**: `.venv/` (correct)
- **Entry**: `unified_app.py` (production) or `python -m skymarshal` (CLI)

#### README Quality: **GOOD**
- ✅ Comprehensive feature list with clear categories
- ✅ Installation instructions (PyPI + source)
- ✅ Troubleshooting section
- ✅ Architecture overview
- ✅ Development commands (Makefile)
- ✅ Performance documentation (CACHE_OPTIMIZATION.md)
- ⚠️ "WORK IN PROGRESS" warning at top (should be removed or softened - v0.1.0 is published)
- ⚠️ License shows CC0 in PyPI but MIT in README (inconsistency)

#### Key Features
- CAR file processing (Content Addressable aRchives)
- Engagement cache with 90% reduction on repeat loads
- Multi-step confirmation flows for destructive actions
- SSE streaming for real-time generation
- Bot detection and analytics

#### Documentation Files
- `CLAUDE.md` - Architecture for agents
- `ARCHITECTURE.md` - System design
- `CACHE_OPTIMIZATION.md` - Performance details
- `API.md` - CLI reference
- `CONTRIBUTING.md` - Development guide
- `DEVELOPMENT.md` - Setup guide

---

### 2. skymarshal-js (TypeScript) - https://github.com/lukeslp/skymarshal-js

**Purpose**: Comprehensive AT Protocol toolkit for TypeScript/JavaScript
**Published**: npm as `skymarshal` v2.3.0
**Stars**: 2
**Last push**: 2026-02-13 (yesterday - active development)
**Lines of code**: ~13,265 lines TypeScript

#### Local Deployment
- **None** - This is a library-only package
- **NOT deployed locally** - No local clone found
- **Usage**: Referenced as workspace package in unified app (`@bluesky/skymarshal` - separate internal fork)

#### Architecture
- **12 managers**: Auth, Content, Network, Chat, Notifications, Profile, Post, Lists, Feeds, Media, Analytics, Search
- **4 services**: Backup (CAR), Vision (alt text), Sentiment (VADER), Jetstream (real-time)
- **Zero dependencies** except `@atproto/api` (peer dependency)
- **Pure TypeScript**: No NetworkX equivalent - native graph algorithms
- **Browser compatible**: IndexedDB, WebSocket, image processing

#### README Quality: **EXCELLENT**
- ✅ Clear quick start with comprehensive example
- ✅ Feature breakdown by version (v2.2.0 features highlighted)
- ✅ Subpath imports for tree-shaking
- ✅ Full TypeScript type exports
- ✅ Comparison table for analytics scoring
- ✅ Multiple usage patterns (EventEmitter + async iterators)
- ✅ Related projects section linking to Python version
- ✅ Vision service provider comparison table

#### Key Differentiators from Python Version
1. **Thread management** - Caching, flattening, URL parsing (v2.2.0)
2. **Graph analysis** - Pure TS (Louvain, PageRank, centrality) - no NetworkX
3. **Analytics utilities** - 9 bot detection signals, engagement scoring
4. **Deletion manager** - Safe workflows with backup (v2.2.0)
5. **Engagement manager** - Age-aware TTL caching (v2.2.0)
6. **Jetstream service** - Real-time streaming with async iterators
7. **Vision AI** - 4 providers (Ollama, OpenAI, Anthropic, xAI)

#### Documentation Files
- `README.md` - Comprehensive (530 lines)
- `CHANGELOG.md` - Version history
- `GRAPH_UTILITIES.md` - Graph analysis details
- `JETSTREAM_USAGE.md` - Real-time streaming guide
- `BOT_DETECTION_ENHANCEMENT.md` - Detection algorithms
- `FOLLOWER_RANKING.md` - Influence ranking
- `THREAD_PORT_SUMMARY.md` - Thread features
- `ERROR_HIERARCHY.md` - Error handling
- `TEST_STRATEGY.md` - Testing approach
- 20+ markdown files in total

---

## Redundancy Analysis

### Are they redundant?

**NO** - They serve different ecosystems:

| Aspect | skymarshal (Python) | skymarshal-js (TypeScript) |
|--------|---------------------|----------------------------|
| **Target** | CLI users, Flask backends | npm/browser developers |
| **Published** | PyPI | npm |
| **Use case** | Standalone tool, server backend | Library for Bluesky apps |
| **Deployment** | Port 5050 (dr.eamer.dev) | Library only |
| **Primary mode** | Interactive terminal + API | Programmatic integration |
| **Graph analysis** | NetworkX (via blueballs port) | Pure TypeScript |
| **Vision AI** | Shared library (xAI provider) | 4 providers built-in |
| **Jetstream** | WebSocket → Flask-SocketIO | Native WebSocket (browser-compatible) |
| **CAR support** | Yes (with SQLite cache) | Yes (BackupService) |

### Overlap Areas
Both implement:
- AT Protocol authentication
- Content fetching (posts, likes, reposts)
- CAR file processing
- Bot detection
- Engagement scoring
- Network analysis (different implementations)
- Deletion workflows
- Real-time firehose (Jetstream)

### Divergence
- **Python**: Flask backend powers React app, CLI for power users
- **TypeScript**: Library for developers building Bluesky apps

---

## Recommendation by Repository

### skymarshal (Python) - KEEP PUBLIC ✅

**Rationale**:
1. Published to PyPI (v0.1.0) - public package
2. Active production service (port 5050)
3. Unique CLI tool for non-developers
4. Flask backend architecture not replicated in JS version
5. 1 star - small but real usage

**Suggested Actions**:
1. **Update README**:
   - Remove or soften "WORK IN PROGRESS" warning (v0.1.0 is stable enough)
   - Clarify relationship to skymarshal-js in Related Projects section
   - Fix license inconsistency (CC0 in PyPI, MIT in README)
2. **Cross-reference**: Add note in README about TypeScript version for developers
3. **Badge**: Add PyPI version badge to match npm version badge in JS repo

**Priority**: Medium (documentation polish)

---

### skymarshal-js (TypeScript) - KEEP PUBLIC ✅

**Rationale**:
1. Published to npm (v2.3.0) - public package
2. 2 stars - more traction than Python version
3. Comprehensive toolkit for Bluesky app developers
4. Active development (push yesterday)
5. 13k+ lines of TypeScript - substantial investment
6. Zero dependencies design (except peer dep) - good for library adoption

**Suggested Actions**:
1. **README already excellent** - no major changes needed
2. **Cross-reference**: Ensure Python version is mentioned (already done in "Related Projects")
3. **Documentation**: Consider adding "Why two versions?" FAQ section
4. **Consider**: Add comparison table showing Python vs TypeScript use cases

**Priority**: Low (already well-documented)

---

## Internal Package Analysis

### @bluesky/skymarshal (workspace package) - PRIVATE ✅

**Location**: `/home/coolhand/html/bluesky/unified/packages/skymarshal/`
**Purpose**: Internal workspace package for unified React app
**Status**: Correctly private (not published)

**Relationship to public skymarshal-js**:
- **Separate codebase** - Not a clone of public npm package
- **Unified-specific**: Tailored for the unified app's needs
- **Different API surface**: `api.ts`, `SkymarshalCore.ts`, workspace-scoped types

**Recommendation**: Keep as-is (private workspace package)

---

## Archive Recommendation

### NONE - Do not archive either repository

Both serve active, distinct purposes:
1. **skymarshal (Python)**: Production service + CLI tool
2. **skymarshal-js (TypeScript)**: npm library for developers

Archiving either would break:
- PyPI/npm installations
- Production service (Python)
- Developer tooling (TypeScript)
- Cross-links between projects

---

## Summary Table

| Repository | Status | Local Deploy | Published | Stars | Recommendation |
|------------|--------|--------------|-----------|-------|----------------|
| **lukeslp/skymarshal** | Public | `/home/coolhand/servers/skymarshal/` | PyPI v0.1.0 | 1 | **Keep public** - Polish README |
| **lukeslp/skymarshal-js** | Public | None (library) | npm v2.3.0 | 2 | **Keep public** - Already excellent |
| **@bluesky/skymarshal** | Private | `/home/coolhand/html/bluesky/unified/packages/skymarshal/` | Not published | N/A | Keep private (internal) |

---

## Action Items

### High Priority
- [ ] Fix license inconsistency in Python version (CC0 vs MIT)
- [ ] Update Python README to remove/soften "WORK IN PROGRESS" warning

### Medium Priority
- [ ] Add PyPI version badge to Python README
- [ ] Add "Why two versions?" section to one or both READMEs
- [ ] Create comparison table showing Python vs TypeScript use cases

### Low Priority
- [ ] Consider unifying documentation style between repos
- [ ] Ensure cross-references are bidirectional and accurate

---

## Conclusion

The two skymarshal repositories are **complementary, not redundant**. They target different ecosystems (CLI/Flask vs npm/library) and should both remain public. The Python version needs minor documentation polish, while the TypeScript version is already well-documented.

**Final verdict**: Keep both public, improve Python README, celebrate the dual-language approach.
