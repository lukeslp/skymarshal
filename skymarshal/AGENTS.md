# Repository Guidelines

## Project Structure & Module Organization
Source CLI code lives in `skymarshal/`, with `app.py` delegating into modules like `auth.py`, `data_manager.py`, and `deletion.py`; shared CLI copy lives under `templates/`, and the optional Flask UI is in `web/`. Tests are under `tests/` with `unit/`, `integration/`, and reusable fixtures in `tests/fixtures/`. Automation scripts reside in `scripts/`, and design or internal notes stay in `internal/` (do not ship). Generated artifacts such as `dist/` and `skymarshal.egg-info/` are reproducible and should never be hand-edited.

## Build, Test, and Development Commands
Create a virtualenv with `python -m venv .venv && source .venv/bin/activate`. Install dev dependencies via `make dev` or `pip install -e ".[dev]"`. Run the CLI with `make run` or `python -m skymarshal`. Use `make test` (pytest) for the full suite and `pytest tests/unit` or `pytest tests/integration` for scoped runs. Lint and type-check with `make lint` (flake8 + mypy). Apply formatting using `make format`, which runs Black and isort.

## Coding Style & Naming Conventions
Use Black’s defaults (4-space indentation, 88-char lines) and isort’s Black profile. Keep imports grouped and free of dead code. All new or modified functions need type hints that pass mypy’s strict configuration. Favor `snake_case` for functions, modules, and CLI command IDs; use `PascalCase` for classes and dataclasses. Place user-facing strings in `templates/` so both CLI and UI can reuse them.

## Testing Guidelines
Pytest is the runner, and fixtures in `tests/fixtures/` mock Bluesky traffic—never hit real services. Name cases `test_*.py`, keep them focused, and add regression coverage for every bug fix. CAR ingestion/deletion logic must have integration coverage (`pytest tests/integration`). For large refactors, confirm coverage with `pytest --cov=skymarshal` and include new tests before merging.

## Commit & Pull Request Guidelines
Commit subjects follow an imperative or Conventional prefix style (e.g., `feat: add timeline filters`) capped at 72 characters. Keep commits scoped to related changes. PRs should summarize behavior shifts, list verification steps (e.g., `pytest`, CLI walkthroughs), link tracking issues, and attach terminal captures or screenshots when user-visible output changes. Wait for CI to pass before requesting review.

## Security & Configuration Tips
Never commit Bluesky credentials, CAR archives, or user exports. Settings persist through `SettingsManager`; route changes via the JSON workflow and redact tokens or paths from logs. Preserve multi-step confirmations for destructive commands in `deletion.py` and related flows.
