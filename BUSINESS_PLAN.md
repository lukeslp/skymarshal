# skymarshal (CLI) — Business Plan

> Generated: 2026-05-08 · Mode: --full · Verdict: **OSS-only, idealize for quality**

## Decision (2026-05-08)

Luke's call after reading the council: keep skymarshal-cli **open-source-only**. No commercial tier, no paid API spinoff, no funnel role for a paid product. Bluesky users won't pay; the cynic seat had the right read. The plan below documents the analysis the council ran and is preserved for reference, but pricing tables, GTM channels, and B2B positioning are no longer in scope. **In scope:** finish polishing the CLI as a defensible OSS portfolio piece — fix the security/reliability items in `.nextup.json` (Werkzeug debug, egonet bind, atproto+httpx pins, deletion 429-backoff, license-classifier), tighten the test matrix, retire legacy `web/app.py`, and let it stand on its own.

## Verdict

skymarshal-cli is not a paid product on its own and should not be sold. The audience that pip-installs a Python CLI for Bluesky management is too small (135 monthly PyPI downloads, 1 GitHub star, 4.12% line coverage), too DIY (these users already wrote their own atproto scripts), and culturally allergic to paying when free tools like Sky Follower Bridge and Bluesky Helper exist. The right call is to keep the CLI free, MIT, and visible as a credibility artifact behind the web product (skymarshal.blue) and as the developer-facing seam for a future Bluescreen-as-API offering. The `unified_app.py` skeleton plus `skymarshal/api/` blueprints (about 1,400 LOC of clean Flask app-factory work) is a reasonable seed for a paid hosted API SKU eventually, but it is not a paid CLI tier and it is not a primary monetization push. Kill the commercial intent on this surface if PyPI cumulative downloads stay under 800 by day 90 with zero external contributors; freeze it as portfolio.

## What This Is

- Python 3.9-3.12 menu-driven Bluesky CLI on PyPI as `skymarshal-cli` v0.1.2 (135 monthly downloads, 21 weekly, 5 daily).
- Modules: `auth.py`, `data_manager.py` (1,922 LOC), `search.py`, `deletion.py`, `analytics/`, `cleanup/`, `engagement_cache.py`, plus an in-tree Flask + SocketIO web layer at `unified_app.py` + `skymarshal/api/` (blueprinted, about 1,400 LOC) and a legacy `web/app.py` (2,294 LOC) slated for deletion.
- Distribution: PyPI + GitHub `lukeslp/skymarshal` (MIT, 111 commits). No telemetry, no CI matrix, no monetization wiring (zero stripe/patreon/sponsor hits in source).
- Local-only data model: CAR backups in `~/.skymarshal/cars/`, settings at `~/.car_inspector_settings.json` (50+ hardcoded references project-wide).
- 35 known scout findings in `.nextup.json`: 5 high-severity (broken `get_database_path()` crashes cleanup/analytics, Werkzeug `debug=True` default in `unified_app.py` with `allow_unsafe_werkzeug=True`, raw `Progress(...)` crashes in non-terminal contexts, unbounded `_services` dict leak, mutable-default in `SearchFilters.keywords`).

## Audience & Beachhead

The CLI's audience is **Python-comfortable Bluesky power users who already script the AT Protocol**: maybe a few hundred people globally. They will not pay. The right beachhead is therefore not a buyer pool but a **trust-building cohort**: AT Proto Developer Discord regulars, indie Bluesky tool builders, accessibility tooling authors, and journalists who write CLIs as part of their workflow. The CLI's job is to convince this cohort that the brand is technically credible enough to pay for the web product (skymarshal.blue) or the future Bluescreen API (see `~/servers/skymarshal-web/BUSINESS_PLAN.md`).

## Positioning (Dunford)

> For developers and Bluesky power users who want to manage their account from the terminal, skymarshal-cli is the open-source Bluesky toolkit that, unlike one-off atproto scripts, gives you safe-deletion workflows, CAR backups with resume, engagement-cache acceleration, and a session-aware menu UI without writing your own AT Protocol client. Free, MIT, no telemetry. The point isn't to sell this; the point is to prove I ship Bluesky tooling that doesn't break.

## Job to Be Done

The honest JTBD: "I want to back up and prune my Bluesky presence safely from the terminal because I distrust browser-based tools with destructive actions on my account." This is a real job, but the population that hires for it is small. The README oversells "manage your Bluesky presence from the command line" — the CLI is best at backup, safe-delete, and engagement analytics, not at composition or graph management.

## Pricing

**Free, MIT, no paid tier.** Comparable set: Sky Follower Bridge (free), Bluesky Helper (free), the unscoped `bsky-cli` packages (free, lower-level), the `atproto` Python SDK itself (free). Adding a paid tier here is rent extraction over a free market. Any paid evolution should happen as a **separate hosted API product** (Bluescreen-as-API) priced per call or per seat, not as a CLI Pro upsell.

## GTM (Bullseye, 3 channels)

1. **AT Protocol Developer Discord** + the bsky.app developer channels. Post: "I built skymarshal-cli for safe-delete + CAR backups; here's the engagement-cache architecture writeup." Earn one mention from a Bluesky core dev or PDS implementer.
2. **Hacker News Show HN** with the cache article: "Caching Bluesky engagement made my CLI 10x faster on large accounts." Technical, single-author, MIT — the HN sweet spot. The CLI's 111 commits and clean modular structure is the credibility proof.
3. **GitHub Awesome-Bluesky list inclusion** + **PyPI keyword discoverability** (already includes `bluesky`, `at-protocol`, `cli-tool`, `content-management`).

**Channels to AVOID:** Twitter/X ads (hostile audience), Mastodon (anti-promo culture, low conversion to non-Masto tools), TikTok/Instagram (wrong demographic), Buffer-style SEO (loses to Buffer on search intent).

## Legal Posture

| Posture | Status |
|---|---|
| Open-source as-is | YELLOW (license-metadata bug: `pyproject.toml` classifier says `License :: Public Domain`, LICENSE file is MIT) |
| Sell as-is | RED (no pricing, no entitlement, no telemetry, no support pipeline) |
| Sell with disclaimers + ToS/AUP | RED (paid CLI not viable per verdict) |
| Enterprise/edu/gov | RED |

**Required mitigations:**
1. Fix `pyproject.toml` license classifier (`License :: Public Domain` → `License :: OSI Approved :: MIT License`) so PyPI metadata matches LICENSE file.
2. Disable Werkzeug `debug=True` default in `unified_app.py`; remove `allow_unsafe_werkzeug=True`.
3. Bind embedded `egonet/app.py` to `127.0.0.1`, not `0.0.0.0` (RCE-shaped on every laptop today).
4. Pin `atproto<0.1` and `httpx<0.28.0` upper bounds in both `pyproject.toml` and `requirements.txt` (atproto historically required `httpx<0.28`).
5. Resolve flask version mismatch (pyproject says `>=2.3.0`, requirements says `>=3.0.0`).
6. Add opt-in Sentry telemetry behind `SKYMARSHAL_TELEMETRY=1` (free tier, traceback-only, no PII).

## Maintenance Cost

**About 180-260 hours/year** at current PyPI scale (50-500 active users). Breakdown: 80h incident triage on the four `get_database_path()` and Progress crashes; 60h dependency churn (atproto + httpx + flask 2/3 split + eventlet/threading drift); 40h release mechanics (PyPI rebuild + README/yank hygiene); 40h refactor cleanup forced by the legacy `web/app.py` shadow.

**What breaks first after 6 weeks untouched:** atproto SDK ships a minor that nudges `httpx>=0.28`; `pip install skymarshal-cli` resolves the new atproto, blows past the unpinned ceiling, and `skymarshal auth` raises ImportError on import. Secondary: any cleanup/analytics call crashes on broken `get_database_path()` (4 confirmed call sites in `cleanup/post_importer.py`, `cleanup/following_cleaner.py`, `analytics/post_analyzer.py`, `analytics/follower_analyzer.py`).

**Debt items that block any paid story** (numbered, all fixable):
1. `get_database_path()` crashes (4 call sites; about 3 hours to fix).
2. Werkzeug `debug=True` default + `allow_unsafe_werkzeug=True` in `unified_app.py` (CVE-shaped if exposed).
3. `_services` dict leak in `skymarshal/api/__init__.py` (auth-bleed across tenants in any multi-user deployment; capped at 50 entries, but never evicted).
4. Raw `Progress(...)` in `deletion.py:46-53,86-95` (crashes in web/API contexts).
5. Bare `except` + no rate-limit handling in `deletion.py:56-75` (a 50k-post nuke hits Bluesky's ~5,000-write/hr limit at item 5,001 and burns the next 45,000 URIs hammering 429s; user sees "5,000 deleted, 45,000 errors").
6. `engagement_cache.db` missing `PRAGMA journal_mode=WAL` + `busy_timeout` (corruption risk on second terminal; this is a quadrant-Inadvertent + already in `.nextup.json` as a TODO).

Total: items 1-4 fit in **2-3 focused days**; items 5-6 are about a day each. Underwater within one quarter if Luke ships paid features without paying down 1-4 first.

## Kill Criteria

- **Day 30:** PyPI cumulative downloads under 250 from baseline. Signal: PyPI is the wrong discovery surface; rethink distribution.
- **Day 60:** Zero external GitHub contributors AND zero adoption signals from AT Proto Discord. Signal: developer audience does not exist at scale.
- **Day 90:** PyPI cumulative downloads under 800 AND no inbound from skymarshal.blue users requesting CLI features. Signal: sunset commercial intent, freeze as portfolio.
- **Bluesky-side:** Bluesky ships a native CLI or a first-party `bsky-cli` with feature parity. Signal: CLI no longer differentiated; archive.
- **Solo-maintainer:** Sustained over 4 hours/week of CLI-specific support inbox. Signal: maintenance cost exceeds portfolio value; freeze.

If any two of these fire by day 60, sunset the CLI as a "live" project and keep it as a frozen MIT repo.

## 30/60/90 Day Plan

- **0-30 days:** Fix the four high-severity scout items (broken `get_database_path`, Werkzeug debug default, `_services` leak, raw Progress in non-terminal). Pin `atproto` + `httpx` upper bounds. Fix the `pyproject.toml` license classifier. Bind `egonet/app.py` to localhost. Republish as 0.1.3 with a clean changelog. Time budget: 3 focused days.
- **30-60 days:** Add opt-in Sentry telemetry (`SKYMARSHAL_TELEMETRY=1`). Add a CI install-smoke matrix (Python 3.9-3.12 × Linux/macOS-Intel/macOS-ARM). SQLite WAL + busy_timeout on `engagement_cache.db`. Rate-limit handling with exponential backoff in `deletion.py`. Decide whether `unified_app.py` skeleton becomes the seed of a hosted API SKU (separate decision; see `skymarshal-web/BUSINESS_PLAN.md`).
- **60-90 days:** Either (a) merge `unified_app.py` into the skymarshal-web codebase as the Bluescreen-API backend, consolidate, and delete legacy `web/app.py`; or (b) freeze the CLI at 0.1.4, archive the embedded web layer, and let it run as a portfolio piece. The decision turns on whether the skymarshal-web B2B trial converts (see that plan's day-60 gate).

## Risks Not Yet Assessed

- **Numerical financial model:** the "180-260h/yr" maintenance number is bottom-up estimation, not a calibrated model with Luke's hourly opportunity cost.
- **Customer interviews:** zero data from actual CLI users about whether they would pay, what they would pay for, or what they currently use. Recommend a 2-week PyPI survey before day 90.
- **Market sizing:** "few hundred globally" for the Python-CLI-Bluesky audience is a guess, not measured.
- **Cross-cutting brand risk:** if Skydio sends a C&D over the `skymarshal` mark, the CLI rename cost is folded into the joint pitch (see skymarshal-web plan).
