# Repository Guidelines

## Project Structure & Module Organization
- `skymarshal/` contains the production Python package and CLI; core modules live beside reusable utilities, with automated suites under `skymarshal/tests/`.
- `bluevibes/` hosts the Flask profile viewer (`src/`, `templates/`, `static/`) plus a CLI entry point (`python -m src.cli`).
- `bluesky_tools/` holds standalone scripts that emit reports to `bluesky_reports/`; double-check each subfolder for a local `AGENTS.md` before editing.
- `bluesky/` serves the static marketing site with `assets/`, `scripts.js`, and `styles.css`; `blueeyes/` and archival data folders are read-mostly unless their own guides permit changes.

## Build, Test, and Development Commands
- `cd skymarshal && make dev` installs editable deps; follow with `make run` to exercise the CLI.
- `cd skymarshal && make test | make lint | make format` wrap `pytest`, `flake8`/`mypy`, and `black`/`isort` respectively.
- `cd bluevibes && python -m pip install -r requirements.txt` prepares the viewer; run `python run.py` for the Flask UI.
- Execute individual tooling scripts with `python bluesky_tools/<script>.py`; create virtualenvs locally to isolate deps.

## Coding Style & Naming Conventions
- Target Python 3.9+ with four-space indents, snake_case modules, and PascalCase classes.
- Run `make format` inside `skymarshal/` to apply `black`/`isort`; rely on `flake8` and `mypy` for linting.
- Front-end assets follow existing BEM-style CSS classes and modular JavaScript helpers in `bluesky/`.

## UX Agent Dispatch
- UX prototypes follow the dedicated playbook in `UX_AGENT.md`—read it before running the UX automation agent.
- Every prototype must be saved under `~/UX_TEST/<concept_slug>/` so it serves at `https://dr.eamer.dev/ux/<concept_slug>/`.
- Keep assets self-contained (relative paths only) and add a short `README.md` per concept describing scope, credentials, and review notes.

## Testing Guidelines
- Add focused `pytest` suites under `skymarshal/tests/` using `test_<feature>.py` filenames and fixtures for API calls.
- Verify Bluevibes features manually (UI + CLI) and note the steps in PR descriptions; provide sample outputs for `bluesky_tools` scripts instead of large artifacts.

## Commit & Pull Request Guidelines
- Write imperative commit titles ≈50 chars, e.g., `Fix: Update API routes`, and squash noisy commits before merging.
- PRs should summarize scope, link related issues, list validation commands (`make test`, manual UI steps), and attach screenshots or logs for user-facing changes.
- Confirm every nested `AGENTS.md` was honored, document skipped checks, and scrub credentials or personal data before submission.

## Security & Configuration Tips
- Store Bluesky credentials in environment variables or `.env` files ignored by Git.
- Review scripts for hard-coded handles or tokens, and prefer sample usernames when demonstrating API usage.
- Run `create_placeholders.sh` before publishing static assets so no local media leaks.
