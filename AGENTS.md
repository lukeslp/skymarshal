# Repository Guidelines

## Project Structure & Module Organization
- Source CLI in `skymarshal/`: `app.py` orchestrates menus and delegates to `auth.py`, `data_manager.py`, `deletion.py`.
- Shared CLI copy in `templates/`; optional Flask UI in `web/`.
- Tests in `tests/` with `unit/`, `integration/`, and reusable `fixtures/`.
- Automation in `scripts/`; design notes in `internal/` (do not ship).
- Generated artefacts like `dist/` and `skymarshal.egg-info/` are reproducible; don’t patch.

## Build, Test, and Development Commands
- Create venv: `python -m venv .venv && source .venv/bin/activate`.
- Install dev deps: `make dev` or `pip install -e ".[dev]"`.
- Run CLI: `make run` or `python -m skymarshal`.
- Test suite: `make test` (preferred before commits).
- Linting: `make lint` (flake8 + mypy). Formatting: `make format` (Black + isort).

## Coding Style & Naming Conventions
- 4-space indentation; Black’s 88-character line limit.
- isort with Black profile; keep imports clean and grouped.
- Type hints required for new/changed functions; pass mypy’s strict checks.
- Naming: `snake_case` for functions/modules/CLI command IDs; `PascalCase` for classes/dataclasses.
- Place user-facing copy in `templates/` for reuse.

## Testing Guidelines
- Runner: Pytest. Run all tests with `pytest` or targeted with `pytest tests/unit` and `pytest tests/integration`.
- Name tests `test_*.py`; prefer small, isolated cases.
- Use `tests/fixtures/` to mock Bluesky traffic—never hit live services.
- Every bug fix needs a regression test. CAR ingestion/deletion changes require integration coverage.
- For core module moves, check coverage: `pytest --cov=skymarshal`.

## Commit & Pull Request Guidelines
- Commit style mixes imperative and Conventional prefixes (e.g., `feat:`); keep subjects ≤72 chars with focused bodies.
- Group related changes per commit; avoid drive-by edits.
- PRs should summarize behavior changes, list verification steps (`pytest`, CLI walkthroughs), link issues, and include screenshots/terminal captures when output changes.
- Wait for CI to pass before requesting review.

## Security & Configuration Tips
- Never commit Bluesky credentials, CAR archives, or user exports.
- Settings persist via `SettingsManager`; redact tokens/paths from logs before sharing.
- Route new settings through the existing JSON workflow and preserve multi-step confirmations for destructive tasks.

