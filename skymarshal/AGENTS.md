# Repository Guidelines

## Project Structure & Module Organization
Skymarshal CLI lives in `skymarshal/` with `app.py` orchestrating menus and delegating to `auth.py`, `data_manager.py`, and `deletion.py`. Shared CLI copy stays in `templates/`, while the optional Flask UI resides in `web/`. Tests sit under `tests/` split into `unit/`, `integration/`, and reusable `fixtures/`; automation scripts live in `scripts/`, and design notes in `internal/` should never ship. Build artefacts such as `dist/` and `skymarshal.egg-info/` are reproducible outputs—do not edit them manually.

## Build, Test, and Development Commands
Bootstrap a virtualenv with `python -m venv .venv && source .venv/bin/activate`. Install development dependencies via `make dev` or `pip install -e ".[dev]"`. Run the CLI locally through `make run` or `python -m skymarshal`. Execute checks before merging: `make test` for the full pytest suite, `make lint` for flake8 plus mypy, and `make format` to apply Black and isort.

## Coding Style & Naming Conventions
Use 4-space indentation and respect Black’s 88-character limit. Keep imports sorted with isort’s Black profile and avoid unused symbols. Provide type hints for any new or modified functions so mypy strict mode passes. Follow naming conventions: snake_case for functions, modules, and CLI command IDs; PascalCase for classes and dataclasses.

## Testing Guidelines
Pytest drives all tests; name files `test_*.py`. Run focused suites with `pytest tests/unit` or `pytest tests/integration` and use `tests/fixtures/` for Bluesky traffic mocks—never hit live services. Every bug fix requires a regression test, and CAR ingestion or deletion changes need integration coverage. Use `pytest --cov=skymarshal` to check coverage when touching core modules.

## Commit & Pull Request Guidelines
Write commits in imperative voice with optional Conventional prefixes such as `feat:` and keep subjects under 72 characters. Group related changes and avoid drive-by edits. PRs must summarize behavior changes, list verification steps (e.g., `pytest`, CLI walkthroughs), link relevant issues, and include screenshots or terminal captures when output changes. Wait for CI to pass before requesting review.

## Security & Configuration Tips
Never commit Bluesky credentials, CAR archives, or user exports. Persist settings through `SettingsManager` and scrub tokens or paths from logs before sharing. Route new settings through the existing JSON workflow and preserve multi-step confirmations for destructive operations.
