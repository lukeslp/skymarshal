# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) + [Semver](https://semver.org/).

## [Unreleased]

### Added
- Documentation (README, ARCHITECTURE, API)
- Progress indicators for JSON load, engagement hydration, CAR decode
- CAR-first data loading (single download vs paginated API)
- Selective engagement hydration (only fetches recent posts, caches old)
- Parallel repost hydration (was sequential)

### Changed
- CAR download is now the default data path (faster for large accounts)
- Cache TTL for posts >90 days bumped to 7 days (engagement is frozen by then)
- Debug mode off by default in production
- Session service pool capped at 50 (was unbounded)

### Removed
- LLM content analyzer (external API calls to xAI/OpenAI stripped out)
- Temp files and stale audit docs

## [0.2.0] - 2025-10-22

### Added - Performance Optimization

- **Engagement cache**: SQLite-based caching for engagement data
  - 90-95% fewer API calls on repeat loads
  - TTL based on post age (1h recent, 6h mid, 24h old)
  - Batch operations, auto-expiration, stats

- **Test suite**: `tests/unit/test_engagement_cache.py` — 15 cases, full coverage

### Changed

- Batch size increased 25 → 100 items per API call (75% fewer calls)
- Cache settings persist across sessions
- Data manager checks cache before hitting API

### Performance

| Scenario | Before | After |
|----------|--------|-------|
| 1k posts, first load | 40 API calls, ~12s | 10 calls, ~3s |
| 1k posts, repeat | 40 calls, ~12s | 0-2 calls, ~0.5s |
| 10k posts, repeat | 400 calls, ~120s | 0-20 calls, ~4s |

## [0.1.0] - 2024-01-15

### Added
- CLI-based Bluesky content management (interactive menus)
- Auth: session management, handle normalization, user isolation
- Data: CAR download/import, JSON export, merge/dedup
- Search: keyword, date, engagement filters, dead thread detection
- Deletion: multi-mode (all/individual/batch), dry-run, progress tracking
- Rich terminal UI with progress bars and contextual help
- Safety: confirmation prompts, data isolation, undo via backups

### Fixed
- Login message formatting (f-string)
- Reposts pagination ('list' object not callable)
- CAR import without commit records
- CBOR decode for atproto >= 0.0.26
- Deletion list access syntax
- Self-repost detection URI parsing

## [0.0.1] - 2024-01-01

- Initial project setup and package structure

---

Maintainer: Luke Steuber — [dr.eamer.dev](https://dr.eamer.dev)
