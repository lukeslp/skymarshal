# CLAUDE.md

Guidance for contributors working inside the `loners/` directory.

## Current Philosophy

All supported loner scripts now wrap the main `InteractiveContentManager` so they stay in sync with Skymarshal’s core logic. Each entrypoint simply bootstraps the manager, shows the banner, and calls the relevant handler (`handle_authentication`, `handle_data_management`, etc.). This eliminates the drift that came from copying large chunks of code into the loners directory.

Legacy utilities (`analyze.py`, `find_bots.py`, `cleanup.py`, `system_info.py`) are kept as informational shims that point folks back to the consolidated flows. Do not reintroduce the old copies of business logic here—extend the main package instead and reuse it from the scripts.

## Supported Workflows

```bash
python auth.py            # Login / logout helpers
python data_management.py # API downloads, backup import, file cleanup
python search.py          # Search, filters, exports, deletions (full flow)
python stats.py           # Loads data if needed then shows quick stats
python export.py          # Alias – jumps into search/export flow
python delete.py          # Safe deletion flow (requires loaded data)
python nuke.py            # Nuclear delete with warnings
python settings.py        # Interactive settings editor
python help.py            # Rich help viewer
python run.py             # Menu launcher for the items above + legacy stubs
```

## Key Paths

```
~/.skymarshal/
├── backups/   # CAR backups
└── json/      # Exported data

~/.car_inspector_settings.json  # Persisted settings (historical filename)
```

## Development Tips

- Make changes to the core managers in `skymarshal/` and expose new behaviour through the existing handlers rather than forking logic in loners.
- If you need a brand new loner, create a tiny wrapper that imports `init_manager()` from `loners.common` and calls the appropriate method on `InteractiveContentManager`.
- Keep console output short and rely on the main handlers for Rich UI elements.
- Python 3.9+ is required (matches the project baseline).

## Dependencies

The loners do not declare extra dependencies; they rely on whatever the main package uses (primarily `rich` and `atproto`). Installing the project in editable mode (`pip install -e .[dev]`) is sufficient.
