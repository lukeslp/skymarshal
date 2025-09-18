# Repository Guidelines

## Project Structure & Module Organization
The Python CLI lives in `skymarshal/`: `app.py` coordinates menus and delegates to modules such as `auth.py`, `data_manager.py`, and `deletion.py`. CLI copy sits in `templates/`; the experimental Flask surface is in `web/`. Tests live under `tests/` with `unit/`, `integration/`, and reusable `fixtures/`. Automation scripts stay in `scripts/`, while `internal/` houses design references that should not ship. Regenerated artefacts (`dist/`, `skymarshal.egg-info/`) are safe to delete instead of editing.

## Build, Test, and Development Commands
Spin up a virtualenv (`python -m venv .venv && source .venv/bin/activate`) before installing. Use `make dev` or `pip install -e ".[dev]"` for an editable environment with tooling. Launch the CLI via `make run` or `python -m skymarshal`. Run `make test` for Pytest, `make lint` for flake8 + mypy, and `make format` to apply Black and isort. Packaging helpers include `make build`, `python scripts/setup_distribution.py`, and `make clean` for a reset.

## Coding Style & Naming Conventions
Stick to Black’s 88-character line length and four-space indentation. isort (Black profile) enforces import grouping; avoid manual tweaks. Use explicit type hints when feasible—mypy is configured with strict-equality checks and warnings for unused ignores. Prefer `snake_case` for modules, functions, and CLI command ids, `PascalCase` for classes and dataclasses, and keep user-facing strings in `templates/` for consistency. Run Black, isort, and flake8 locally before raising a PR.

## Testing Guidelines
Pytest is the only supported runner. Execute `pytest` for the full suite or target `pytest tests/unit` and `pytest tests/integration` for scoped runs. Extend fixtures in `tests/fixtures/` to mock Bluesky traffic rather than hitting live services. Every bug fix needs a regression test, and features touching CAR ingestion or deletion flows should add integration coverage. Check coverage with `pytest --cov=skymarshal` when core modules change.

## Commit & Pull Request Guidelines
History mixes imperative subjects and Conventional-style prefixes (`feat: ...`). Mirror that tone with concise, present-tense summaries under 72 characters and optional body context. Group related work per commit. PRs should describe behavior changes, list manual verification steps (`pytest`, CLI walkthroughs), link issues, and attach screenshots or terminal captures when output shifts. Wait for checks to pass before requesting merge.

## Security & Configuration Tips
Never commit Bluesky credentials, CAR archives, or user exports. Configuration persists through `SettingsManager`; redact local paths or tokens from logs before sharing. Route new settings through the existing JSON workflow and preserve the multi-step confirmation UX around destructive actions.
