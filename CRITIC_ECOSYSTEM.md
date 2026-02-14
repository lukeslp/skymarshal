# CRITIC.md - Bluesky Repository Ecosystem

> Honest critique of repository fragmentation, architectural boundaries, and maintenance burden.
> Generated: 2026-02-14 by geepers_critic
>
> This isn't about code quality - it's about "does this structure make sense?"

## The Vibe Check

**First Impression**: You have 10 different repositories doing Bluesky things. Some are active. Some are archived. Some overlap completely. It's confusing.

**Would I use this?**: As a developer looking for Bluesky tools, I'd have no idea where to start. The fragmentation screams "exploratory phase that never got consolidated."

**Biggest Annoyance**: The fact that `blueballs` network analysis was ported INTO `skymarshal` but the original repo still exists with 3,300 lines of code that's now redundant.

---

## The Repository Landscape

### Active Public Repositories

| Repo | Purpose | Status | npm/PyPI Version | Last Push |
|------|---------|--------|------------------|-----------|
| `skymarshal` (Python) | CLI + unified backend | Active, published to PyPI | v0.1.0 | Active dev |
| `skymarshal-js` | TypeScript/JS toolkit | Active, published to npm | v2.3.0 | 2026-02-13 |
| `bluesky-tools` | Catch-all tools repo | Stale | - | 2025-12-15 |

### Active Private Repositories

| Repo | Purpose | Status | Last Push |
|------|---------|--------|-----------|
| `bluesky-web-apps` | React workspace monorepo | Active | 2026-02-14 (TODAY) |
| `blueflyer` | Accessible media poster with alt-text | Active | 2026-02-14 (TODAY) |
| `bluevibes` | Profile viewer + sentiment | Unclear | Unknown |
| `blueballs` | Network visualization (FastAPI + Svelte) | Legacy/ported | 2026-02-12 |
| `bluesky-cli` | CLI with LLM analysis | Unclear | 2025-12-21 |
| `bluesky-chat` | DM chat integration | Unknown | Unknown |

### Archived

| Repo | Purpose | Archived Date |
|------|---------|---------------|
| `bsky-follow-analyzer` | Following list audit | 2026-01-22 |

### Local-Only Directories (Not in Git Repos)

- `/home/coolhand/html/bluesky/` - Active development hub (unified client, post-visualizer, accordion, etc.)
- `/home/coolhand/projects/blueballs/` - 3,298 lines of FastAPI backend that's been ported to skymarshal
- `/home/coolhand/projects/bluevibes/` - Flask profile viewer, unclear relationship to other tools

---

## Architecture Smells

### ARCH-001: The Ghost of Blueballs
**What**: The `blueballs` repository (FastAPI + Svelte) contains network visualization code that was explicitly ported TO `skymarshal/network/` (1,223 lines). Yet the original 3,298-line codebase still exists.

**Why It's Bad**:
- Maintenance confusion: Which is the source of truth?
- Wasted disk space and cognitive overhead
- Documentation references both locations
- Users don't know which to use

**Better Approach**: Archive or delete `projects/blueballs/`. Update README to redirect to skymarshal.

**Effort to Fix**: 15 minutes (archive + README update)

---

### ARCH-002: Dual Skymarshal Packages
**What**: `skymarshal` (Python, PyPI v0.1.0) and `skymarshal-js` (TypeScript/JS, npm v2.3.0) are separate packages with unclear boundaries.

**Why It's Bad**:
- Naming collision causes confusion
- Users don't know which to install
- No clear explanation of when to use which
- Both claim to be "Bluesky content management toolkit"

**Better Approach**:
- Rename one (e.g., `skymarshal-py` and `skymarshal-js`)
- OR merge into monorepo with language-specific packages
- Document the relationship clearly in both READMEs

**Effort to Fix**: 2 hours (rename + republish + docs)

---

### ARCH-003: The "bluesky-tools" Black Hole
**What**: Public repo named `bluesky-tools` that hasn't been pushed to since 2025-12-15. Meanwhile, ALL active development happens in `/home/coolhand/html/bluesky/` which is part of the PRIVATE `bluesky-web-apps` monorepo.

**Why It's Bad**:
- Public repo is stale and misleading
- Active work is hidden in private repo
- GitHub presence doesn't match reality
- Contributors can't find the actual code

**Better Approach**:
- Archive `bluesky-tools` public repo with redirect notice
- Make `bluesky-web-apps` public (if desired for community contributions)
- OR mirror `/html/bluesky/` to `bluesky-tools` with automated sync

**Effort to Fix**: 30 minutes (archive + redirect)

---

### ARCH-004: Vibes Without Direction
**What**: `bluevibes` is a Flask profile viewer that overlaps with features in the unified client (profile viewing, sentiment analysis, follower lists).

**Why It's Bad**:
- Duplicate functionality
- No clear differentiation
- Maintenance burden (two codebases doing same thing)
- User confusion about which to use

**Better Approach**:
- Absorb unique features into unified client
- Archive `bluevibes`
- OR clearly document "lightweight standalone" vs "full-featured" distinction

**Effort to Fix**: 4 hours (feature extraction + archive)

---

### ARCH-005: CLI Tool Proliferation
**What**: THREE CLI tools exist:
1. `skymarshal` (Python, Rich terminal UI, published to PyPI)
2. `skymarshal-js` (TypeScript, published to npm)
3. `bluesky-cli` (private repo, "LLM-powered analysis")

**Why It's Bad**:
- Users don't know which to install
- Feature overlap (all do account management)
- Split development effort
- Inconsistent UX across tools

**Better Approach**: Consolidate into ONE canonical CLI per language:
- Python: `skymarshal` (already published, mature)
- TypeScript: `skymarshal-js` (already published)
- Archive: `bluesky-cli` (merge unique LLM features into skymarshal if valuable)

**Effort to Fix**: 6 hours (feature merge + deprecation notice)

---

### ARCH-006: The Express Server Ghost
**What**: `/home/coolhand/html/bluesky/unified/server/` contains a legacy Express + Socket.IO backend that has been REPLACED by the Flask backend at `/home/coolhand/servers/skymarshal/unified_app.py`. The Express directory still exists.

**Why It's Bad**:
- Dead code taking up space
- Confusing for new developers
- Git history noise
- Documentation references both

**Better Approach**: DELETE `/html/bluesky/unified/server/` entirely. The Flask backend is the source of truth.

**Effort to Fix**: 5 minutes (rm -rf + git commit)

---

### ARCH-007: Repository Sprawl Without Hub
**What**: 10 repositories with no central "start here" documentation explaining the ecosystem.

**Why It's Bad**:
- New users face choice paralysis
- No clear recommended path
- Discoverability is terrible
- Looks like abandoned experiments rather than cohesive tools

**Better Approach**: Create a hub repository (`bluesky-ecosystem` or pin `bluesky-web-apps`) with:
- Clear navigation: "Want CLI? Use skymarshal. Want web UI? Use unified client."
- Relationship diagram showing how pieces fit together
- Archive/deprecation notices for old repos

**Effort to Fix**: 2 hours (documentation)

---

## UX Friction Points

### UX-001: Where Do I Even Start?
**Where**: GitHub profile, documentation, search results

**The Problem**: A developer searching for "Bluesky tools by Luke Steuber" finds:
- 10 different repositories
- 3 named "bluesky-*" generically
- No clear hierarchy or recommended starting point
- Some public, some private, some archived

**Why It Matters**: First impression is "this person has a lot of unfinished projects" rather than "this is a cohesive ecosystem."

**Suggested Fix**:
- Create ONE public "hub" repo with clear navigation
- Pin it on GitHub profile
- Archive stale repos
- Document relationship between all active projects

---

### UX-002: Blueflyer in Isolation
**Where**: `blueflyer` repository (accessible media poster)

**The Problem**: This is a standalone PWA for posting media with alt-text. It's separate from the unified client, which also supports posting. Users have to know about BOTH tools and choose between them.

**Why It Matters**: Feature fragmentation. If unified client doesn't support accessible media posting, it should. If it does, why does blueflyer exist?

**Suggested Fix**:
- Integrate blueflyer's accessibility features into unified client
- Keep blueflyer as a lightweight alternative with clear positioning ("minimal PWA for quick posts")
- OR archive blueflyer if redundant

---

### UX-003: The Chat Mystery
**Where**: `bluesky-chat` private repository

**The Problem**: Listed in repo list but no description, no known purpose, no integration with other tools. Dead or alive?

**Fix**: Archive or document. Don't leave mystery repos lying around.

---

### UX-004: Public/Private Mismatch
**Where**: Active development in private repos while public repos go stale

**The Problem**:
- `bluesky-web-apps` (private) gets daily updates
- `bluesky-tools` (public) hasn't been touched in 2 months
- Contributors looking for your work can't find it

**Why It Matters**: Open source relies on discoverability. Hiding active work in private repos while maintaining stale public repos sends the wrong signal.

**Fix**: Either make active repos public or clearly mark public repos as "archived, see X for active development"

---

## Technical Debt Ledger

| ID | Type | Description | Pain Level | Fix Effort |
|----|------|-------------|------------|------------|
| TD-001 | Dead Code | Express server in `unified/server/` | 🔥 | 5 min |
| TD-002 | Duplication | Blueballs codebase (3,298 lines) duplicates skymarshal/network | 🔥🔥 | 15 min |
| TD-003 | Naming | `skymarshal` vs `skymarshal-js` collision | 🔥🔥 | 2 hours |
| TD-004 | Stale Repo | `bluesky-tools` public repo not updated | 🔥🔥 | 30 min |
| TD-005 | Feature Overlap | `bluevibes` vs unified client profile viewing | 🔥🔥🔥 | 4 hours |
| TD-006 | CLI Fragmentation | 3 different CLI tools | 🔥🔥🔥 | 6 hours |
| TD-007 | Documentation | No central hub explaining ecosystem | 🔥🔥🔥 | 2 hours |
| TD-008 | Visibility | Active work hidden in private repos | 🔥🔥 | 1 hour (policy decision) |
| TD-009 | Mystery Repos | `bluesky-chat` status unknown | 🔥 | 15 min |

**Total Debt Estimate**: 16 hours to pay down

---

## The Honest Summary

### What's Working
- Skymarshal (Python) is well-structured, published to PyPI, and actively maintained
- The unified React client at `/html/bluesky/unified/` is the real flagship
- Network analysis features (ported from blueballs) are working in production
- Flask + SocketIO backend successfully replaced the Express server
- You're actually building useful tools

### What's Not
- Too many repos doing overlapping things
- Public GitHub presence doesn't match reality (stale repos, private active work)
- No clear "start here" for new users
- Legacy codebases (blueballs, Express server) still exist after being replaced
- CLI tool proliferation (3 tools, unclear differentiation)
- `bluesky-tools` repo is abandoned but still public

### If I Had to Fix One Thing
**Archive or delete `projects/blueballs/` and `/html/bluesky/unified/server/`.** These are the clearest examples of dead code that causes confusion. The functionality exists elsewhere. Removing them would immediately reduce cognitive overhead.

---

## Priority Actions

### 1. Quick Wins (1 hour total)

**Delete dead code**:
```bash
# Delete legacy Express server
rm -rf /home/coolhand/html/bluesky/unified/server/
git commit -m "Remove legacy Express server (replaced by Flask backend)"

# Archive blueballs project
cd /home/coolhand/projects
mv blueballs blueballs-ARCHIVED-2026-02-14
echo "ARCHIVED: Network analysis moved to skymarshal/network/" > blueballs-ARCHIVED-2026-02-14/README.md
```

**Archive stale GitHub repos**:
- Archive `bluesky-tools` (public repo, stale since Dec 2025)
- Archive `bluesky-chat` (if unused)
- Add archive notice redirecting to active repos

---

### 2. Important (6 hours)

**Consolidate CLI tools**:
1. Audit `bluesky-cli` for unique features (LLM-powered analysis)
2. If valuable, merge into `skymarshal` (Python) as optional module
3. Archive `bluesky-cli` with migration guide
4. Document when to use `skymarshal` (Python) vs `skymarshal-js` (TypeScript)

**Clarify bluevibes**:
1. Document unique value proposition vs unified client
2. If redundant, archive and merge features
3. If distinct (e.g., "lightweight alternative"), update README to explain

**Clarify blueflyer**:
1. Test if unified client supports accessible media posting
2. If no, integrate blueflyer's alt-text features
3. If yes, position blueflyer as "minimal PWA" or archive

---

### 3. When You Have Time (3 hours)

**Create ecosystem hub**:
1. New public repo: `bluesky-ecosystem` or make `bluesky-web-apps` public
2. README with clear navigation:
   - **Web Apps**: `bluesky-web-apps` (unified client, visualizers)
   - **Python CLI**: `skymarshal` (PyPI)
   - **TypeScript SDK**: `skymarshal-js` (npm)
   - **Specialized Tools**: `blueflyer` (accessible posting, if kept)
3. Relationship diagram showing how pieces fit together
4. Archive notices for deprecated repos
5. Pin to GitHub profile
6. Cross-link from all active repos

**Rename for clarity** (optional):
- `skymarshal` → `skymarshal` (keep, it's on PyPI)
- `skymarshal-js` → `@skymarshal/js` or `skymarshal-node` (avoid naming collision)
- Update all documentation

---

## Consolidation Recommendations

### Archive Immediately ❌

- `bluesky-tools` (public, stale, replaced by bluesky-web-apps)
- `bluesky-chat` (if unused/unknown)
- `bsky-follow-analyzer` (already archived ✓)
- `/projects/blueballs/` (local, ported to skymarshal)
- `/html/bluesky/unified/server/` (local, replaced by Flask)

### Merge or Clarify 🔄

- `bluevibes` → Document differentiation OR merge into unified client
- `bluesky-cli` → Merge unique features into `skymarshal`, then archive
- `blueflyer` → Integrate into unified client OR position as lightweight alternative

### Keep (Legitimate Separation) ✅

- `skymarshal` (Python) - Mature CLI + backend, published to PyPI
- `skymarshal-js` (TypeScript) - npm package for JS developers (rename recommended)
- `bluesky-web-apps` (private monorepo) - Active development hub for web clients
- `blueflyer` - IF positioned as specialized accessible posting PWA distinct from unified client

### Make Public (Consider) 🌐

- `bluesky-web-apps` - This is where the real work happens, hiding it seems counterproductive
  - OR create public mirror of `/html/bluesky/` in `bluesky-tools`

---

## Architectural Boundaries That Make Sense

### By Language/Runtime
- **Python backend/CLI**: `skymarshal`
- **TypeScript/Node SDK**: `skymarshal-js` (renamed to avoid collision)
- **React web apps**: `bluesky-web-apps`

### By Use Case
- **Full-featured client**: Unified client (in bluesky-web-apps)
- **Content management**: Skymarshal CLI (Python)
- **Visualization**: Post-visualizer, network graphs (in bluesky-web-apps)
- **Accessibility**: Blueflyer (if distinct from unified client)
- **Developer SDK**: skymarshal-js (for external integrations)

### By Deployment Model
- **Self-hosted web**: Unified client + skymarshal backend
- **CLI tool**: skymarshal (Python) or skymarshal-js (Node)
- **PWA**: Blueflyer (if kept separate)

---

## The Brutal Truth

You have the bones of an excellent Bluesky ecosystem, but it's buried under:
- 3,300 lines of redundant network analysis code (blueballs repo after porting to skymarshal)
- 3 competing CLI tools with unclear differentiation
- A public repo (`bluesky-tools`) that's 2 months stale while active work happens in private
- Dead Express server code sitting next to production Flask code
- No clear entry point for users
- 10 repositories with overlapping functionality

**The fix is mechanical, not architectural.** Delete dead code, archive stale repos, document what remains. The underlying code is good. The organization is the problem.

---

## What Good Consolidation Looks Like

### GitHub Profile (Pinned Repos)
1. **bluesky-web-apps** (or public mirror) - "Full-featured Bluesky web client and tools"
2. **skymarshal** (Python) - "CLI and backend for Bluesky content management"
3. **skymarshal-js** (TypeScript) - "TypeScript SDK for Bluesky AT Protocol"
4. **blueflyer** (if kept) - "Accessible media posting PWA"

### Ecosystem README (in pinned hub repo)
```markdown
# Bluesky Ecosystem by Luke Steuber

## For Users
- **Web Interface**: [Unified Client](https://dr.eamer.dev/bluesky/unified/) - Full-featured Bluesky client
- **CLI Tool**: [skymarshal](https://pypi.org/project/skymarshal/) - Python CLI for content management

## For Developers
- **Python SDK**: [skymarshal](https://github.com/lukeslp/skymarshal) - Backend + CLI
- **TypeScript SDK**: [skymarshal-js](https://www.npmjs.com/package/skymarshal) - AT Protocol toolkit

## Specialized Tools
- **Accessible Posting**: [Blueflyer](https://dr.eamer.dev/bluesky/blueflyer/) - PWA with auto alt-text

## Archived Projects
- ~~bluesky-tools~~ → Superseded by bluesky-web-apps
- ~~blueballs~~ → Network analysis merged into skymarshal
- ~~bluesky-cli~~ → Features merged into skymarshal
```

---

## Conclusion: You Built It, Now Curate It

You've shipped a LOT of Bluesky functionality:
- Unified web client with feed, chat, analytics, firehose
- Python CLI with content management, follower analysis, cleanup
- TypeScript SDK published to npm
- Network visualization with 19 different layouts
- Post visualizer with D3 force graphs
- Accessible media posting PWA

The problem isn't what you've built. It's that it's scattered across 10 repositories with unclear boundaries, stale public presence, and no clear entry point.

**Next steps**:
1. Delete dead code (1 hour)
2. Archive redundant repos (1 hour)
3. Create ecosystem hub with clear navigation (2 hours)
4. Make active work visible (policy decision)

**Total consolidation effort**: 4-16 hours depending on scope

**Impact**: Users can actually find and use your tools. Contributors know where to send PRs. Your GitHub profile reflects reality instead of confusion.

---

*This critique is meant to make things better, not to discourage.*
*You've built a lot. Now it's time to curate.*
