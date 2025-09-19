# Repository Guidelines

## Project Structure & Module Organization
`skymarshal/` hosts the CLI: `app.py` orchestrates menus and hands work to modules like `auth.py`, `data_manager.py`, and `deletion.py`. Shared CLI copy sits in `templates/`; the optional Flask UI lives in `web/`. Tests live in `tests/` with dedicated `unit/`, `integration/`, and reusable `fixtures/`. Automation scripts stay in `scripts/`, while `internal/` is for design references that should not ship. Generated artefacts such as `dist/` and `skymarshal.egg-info/` can be recreated and should not be patched.

## Build, Test, and Development Commands
- `python -m venv .venv && source .venv/bin/activate`: create and enter the virtualenv.
- `make dev` or `pip install -e ".[dev]"`: install editable packages plus tooling.
- `make run` or `python -m skymarshal`: launch the CLI locally.
- `make test`: run the full Pytest suite; prefer this before commits.
- `make lint`: execute flake8 and mypy; keep the repo warning-free.
- `make format`: run Black and isort; apply before opening review.

## Coding Style & Naming Conventions
Use four-space indentation and keep lines within Black’s 88-character limit. Imports are auto-arranged by isort using the Black profile. Type hints are expected for new or changed functions so mypy’s strict equality checks pass. Favor `snake_case` for functions, modules, and CLI command IDs, `PascalCase` for classes and dataclasses, and place user-facing copy in `templates/` for reuse.

## Testing Guidelines
Pytest is the required runner. Use `pytest` for the complete suite, or target `pytest tests/unit` and `pytest tests/integration` when iterating. Extend `tests/fixtures/` to mock Bluesky traffic rather than calling live services. Every bug fix should carry a regression test, and CAR ingestion or deletion changes need integration coverage. When core modules move, check coverage with `pytest --cov=skymarshal`.

## Commit & Pull Request Guidelines
Repository history mixes imperative subjects and Conventional prefixes (e.g., `feat:`). Keep subjects under 72 characters and add focused bodies when context helps. Group related changes per commit. Pull requests should summarize behavior shifts, list manual verification steps (`pytest`, CLI walkthroughs), link issues, and attach screenshots or terminal captures when output changes. Wait for CI to pass before requesting review.

## Security & Configuration Tips
Never commit Bluesky credentials, CAR archives, or user exports. Settings persist through `SettingsManager`; redact local paths or tokens from logs before sharing. Route new settings through the existing JSON workflow and preserve the multi-step confirmations that guard destructive tasks.
