# Archival Note: Bluesky Standalone Scripts
**Date:** November 18, 2025  
**Archived From:** `/home/coolhand/projects/tools_bluesky/bluesky_tools/`  
**Reason:** Superseded by skymarshal or other tools

---

## Scripts Archived (3)

### 1. bluesky_cleaner.py (45KB)
**Purpose:** Clean/delete Bluesky content, bot detection  
**Superseded By:** **skymarshal** (PyPI package v0.0.46)  
**Reason:** Skymarshal provides comprehensive cleanup features with:
- Safe deletion workflows
- Bot detection
- Batch operations
- Better error handling
- Maintained and tested

**Active Alternative:**
```bash
pip install skymarshal
python -m skymarshal
```

---

### 2. bluesky_post_import_cli.py (4KB)
**Purpose:** Import/export Bluesky posts  
**Superseded By:** **skymarshal** CAR file features  
**Reason:** Skymarshal handles:
- CAR file export (complete account backup)
- JSON export
- Import functionality
- Comprehensive data management

**Active Alternative:**
```bash
pip install skymarshal
# Use export/import features in interactive mode
```

---

### 3. vibe_check_posts.py (23KB)
**Purpose:** Basic sentiment/vibe analysis of posts  
**Superseded By:** **vibeagain.py** (in same directory)  
**Reason:** vibeagain.py is:
- Much more comprehensive (171KB vs 23KB)
- Enhanced analytics
- Better maintained
- Superset of functionality

**Active Alternative:**
```bash
cd /home/coolhand/projects/tools_bluesky/bluesky_tools
python vibeagain.py
```

---

## Active Scripts (Still in bluesky_tools/)

### Keep These ✅

1. **vibeagain.py** (171KB)
   - Advanced sentiment/vibe analysis
   - Most comprehensive analytics
   - Unique algorithms

2. **bluevibes.py** (4KB)
   - CLI for bluevibes service
   - Complements web interface

3. **pull_and_rank_posts.py** (50KB)
   - Post ranking and analysis
   - May have unique features

4. **bluesky_follower_ranker.py** (37KB)
   - Follower ranking (check if superseded by bluevibes service)

---

## How to Revive

If archived scripts had unique features:

1. **Check for unique functionality:**
   ```bash
   cd archive-20251118
   grep -A10 "def unique_function" bluesky_cleaner.py
   ```

2. **Extract useful code:**
   - Copy unique functions
   - Integrate into skymarshal or active scripts
   - Add tests

3. **Or use directly:**
   ```bash
   python archive-20251118/bluesky_cleaner.py
   ```

**Assessment:** Unlikely needed - skymarshal is comprehensive

---

## Migration Guide

### If You Were Using bluesky_cleaner.py

**Old:**
```bash
python bluesky_cleaner.py --username your.handle --password your_password
```

**New:**
```bash
pip install skymarshal
python -m skymarshal
# Navigate to deletion features in interactive menu
```

---

### If You Were Using bluesky_post_import_cli.py

**Old:**
```bash
python bluesky_post_import_cli.py --export posts.json
```

**New:**
```bash
python -m skymarshal
# Use export features for JSON or CAR files
```

---

### If You Were Using vibe_check_posts.py

**Old:**
```bash
python vibe_check_posts.py --analyze
```

**New:**
```bash
python vibeagain.py  # Enhanced version with more features
```

---

## Database Files

**Kept in parent directory:**
- `bluesky_profiles.db` - Shared SQLite database
- `bluesky_reports/` - Historical report data

**Reason:** Still used by active scripts

---

## References

- **Primary Tool:** [skymarshal on PyPI](https://pypi.org/project/skymarshal/)
- **Bluevibes Service:** `/projects/social/bluevibes/` (port 5012)
- **Tool Hierarchy:** [/tools_bluesky/TOOL_HIERARCHY.md](../TOOL_HIERARCHY.md)
- **Consolidation Analysis:** [/tools_bluesky/BLUESKY_SCRIPTS_CONSOLIDATION.md](../BLUESKY_SCRIPTS_CONSOLIDATION.md)

---

**Archived By:** Claude AI Assistant  
**Archival Date:** November 18, 2025  
**Safe to Delete:** After 30-day retention period (December 18, 2025)  
**Restore Location:** Git history preserves all code

**Status:** ✅ Archived - Use skymarshal, vibeagain.py, or bluevibes instead

