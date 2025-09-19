# Skymarshal Loners

Note on archival variants
- Historical variants are consolidated under `loners/internal/`:
  - `loners/internal/loners` (from `internal/loners`)
  - `loners/internal/bluefly/loners` (from `internal/bluefly/loners`)
- Treat these as reference only; do not import from them at runtime. Migrate any needed code into the main `loners/` package with tests.

Standalone entrypoints for focused workflows built on top of the main Skymarshal CLI. Each script bootstraps the same `InteractiveContentManager` used by the core app so you can jump directly to a task without navigating the full menu.

## Supported Scripts

| Script | Purpose | Quick Start |
| --- | --- | --- |
| `auth.py` | Log in/out and verify the current Bluesky session | `python auth.py` |
| `data_management.py` | Download API data, import backups, or clear local files | `python data_management.py` |
| `search.py` | Filter, analyze, and export content in one flow | `python search.py` |
| `stats.py` | Load data (if needed) then show the quick stats dashboard | `python stats.py` |
| `export.py` | Alias for the search flow, convenient when you only need exports | `python export.py` |
| `delete.py` | Load data and run the guided deletion experience | `python delete.py` |
| `nuke.py` | Run the guarded "nuclear" delete flow with all confirmations | `python nuke.py` |
| `settings.py` | Edit persisted preferences (`~/.car_inspector_settings.json`) | `python settings.py` |
| `help.py` | Open the Rich-based help viewer | `python help.py` |

## Legacy Stubs

The older `analyze.py`, `find_bots.py`, `cleanup.py`, and `system_info.py` scripts are now informational shims. They explain where the functionality moved (typically into `search.py` + `delete.py`) so contributors are not surprised when invoking them.

## Usage Notes

- Python 3.9+ is required, matching the main project target.
- All scripts rely on the primary data directories:
  - Settings file: `~/.car_inspector_settings.json`
  - Data root: `~/.skymarshal/`
  - Backups (.car): `~/.skymarshal/backups/`
  - Processed JSON exports: `~/.skymarshal/json/`
- The flows automatically clear the console and reuse the Skymarshal banner for continuity with the main CLI.
- Authentication, data downloads, and destructive actions mirror the safeguards used in `skymarshal` itself (re-auth prompts, previews, and confirmations).

## Launcher

`run.py` provides a simple menu over the supported scripts plus the legacy stubs. Launch it with:

```bash
python run.py
```

Pick a number to execute the workflow you need. Each script exits back to the launcher when finished.
