# Project Consolidation Tasks

## Phase 1: Verify Bluevibes
- [x] Check bluevibes CLI works (`python -m src.cli`)
- [x] Check bluevibes web GUI works (`python run.py`)
- [x] Fix any issues found (import fix, added __init__.py)

## Phase 2: Verify Blueeyes
- [x] Check blueeyes CLI works (broken due to keyring issues)
- [x] Check blueeyes web/main works (N/A - broken)
- [x] Decision: Archive as-is, not worth fixing

## Phase 3: Archive & Cleanup
- [x] Archive `blueeyes/` → `archive/blueeyes/`
- [x] Archive other scraps (`bluesky/`, old docs)
- [x] Archive `bluesky_tools/` → `archive/bluesky_tools/`

## Phase 4: Final Structure
- [x] Verify skymarshal still works (CLI + web)
- [ ] Update any hardcoded paths (defer - do after move)
- [x] Document final structure

