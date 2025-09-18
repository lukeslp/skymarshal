# Skymarshal Development Makefile

.PHONY: install dev run clean test lint format help

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install in editable mode
	python -m pip install -e .

dev:  ## Install with development dependencies
	python -m pip install -e ".[dev]"

run:  ## Run skymarshal (works regardless of entry point issues)
	python -m skymarshal

test:  ## Run tests
	python -m pytest

lint:  ## Run linting
	python -m flake8 skymarshal/
	python -m mypy skymarshal/

format:  ## Format code
	python -m black skymarshal/
	python -m isort skymarshal/

clean:  ## Clean build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build:  ## Build distribution packages
	python -m build

publish-test:  ## Publish to Test PyPI
	python -m twine upload --repository testpypi dist/*

publish:  ## Publish to PyPI
	python -m twine upload dist/*

setup-dist:  ## Set up for distribution (run tests, build, check)
	python scripts/setup_distribution.py

test-install:  ## Test package installation
	pip install dist/*.whl
	python - <<'PY'
import skymarshal as sm
print(f"Installed Skymarshal version: {sm.__version__}")
PY

clean-dist:  ## Clean distribution artifacts
	rm -rf build/ dist/ *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
