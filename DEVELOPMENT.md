# Skymarshal Development Guide

Comprehensive guide for developing, testing, and contributing to Skymarshal.

## Table of Contents

- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Development Workflow](#development-workflow)
- [Code Style Guidelines](#code-style-guidelines)
- [Testing Strategy](#testing-strategy)
- [Debugging](#debugging)
- [Performance Optimization](#performance-optimization)
- [Release Process](#release-process)
- [Troubleshooting](#troubleshooting)

## Development Setup

### Prerequisites

- **Python 3.8+** (tested on 3.8, 3.9, 3.10, 3.11, 3.12)
- **Git** for version control
- **pip** or **pipenv** for dependency management
- **Bluesky account** for testing (optional but recommended)

### Initial Setup

```bash
# Clone the repository
git clone https://github.com/lukeslp/skymarshal.git
cd skymarshal

# Create virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# Verify installation
python - <<'PY'
import skymarshal as sm
print(f"Skymarshal version: {sm.__version__}")
PY
```

### Development Dependencies

The `[dev]` extra includes all development tools:

```bash
# Install development dependencies
pip install -e ".[dev]"
```

**Included packages:**
- `pytest>=7.0.0` - Testing framework
- `pytest-cov>=4.0.0` - Coverage reporting
- `black>=23.0.0` - Code formatting
- `isort>=5.12.0` - Import sorting
- `flake8>=6.0.0` - Linting
- `mypy>=1.0.0` - Type checking
- `build>=0.10.0` - Package building
- `twine>=4.0.0` - Package uploading

### Known Issues & Workarounds

#### Entry Point Issues (Development Only)

On systems with multiple Python installations, pip may generate entry point scripts with incorrect shebangs. This is a [known limitation](https://github.com/pypa/pip/issues/4368) of pip's script generation.

**Workarounds:**
```bash
# Use module execution (recommended)
python -m skymarshal

# Use Makefile
make run
```

**Note**: This only affects editable installs during development, not the final distributed package.

## Project Structure

### Directory Layout

```
skymarshal/
├── skymarshal/              # Main package directory
│   ├── __init__.py          # Package initialization
│   ├── __main__.py          # Module entry point
│   ├── app.py               # Main application controller
│   ├── models.py            # Data structures and enums
│   ├── auth.py              # Authentication management
│   ├── ui.py                # User interface components
│   ├── data_manager.py      # Data operations
│   ├── search.py            # Search and filtering
│   ├── deletion.py          # Safe deletion workflows
│   ├── settings.py          # Settings management
│   ├── help.py              # Help system
│   └── banner.py            # Startup sequences
├── tests/                   # Test suite
├── docs/                    # Documentation
├── Makefile                 # Development commands
├── pyproject.toml          # Project configuration
├── requirements.txt         # Core dependencies
├── requirements-dev.txt     # Development dependencies
└── README.md               # Project overview
```

### Module Responsibilities

| Module | Purpose | Key Classes |
|--------|---------|-------------|
| `app.py` | Application orchestration | `InteractiveCARInspector` |
| `models.py` | Data structures | `ContentItem`, `UserSettings`, `SearchFilters` |
| `auth.py` | Authentication | `AuthManager` |
| `ui.py` | User interface | `UIManager` |
| `data_manager.py` | Data operations | `DataManager` |
| `search.py` | Search/filtering | `SearchManager` |
| `deletion.py` | Safe deletion | `DeletionManager` |
| `settings.py` | Settings | `SettingsManager` |
| `help.py` | Help system | `HelpManager` |
| `banner.py` | Startup UI | Various display functions |

## Development Workflow

### Daily Development Commands

```bash
# Start development session
make run                    # Run application

# Code quality checks
make format                 # Format code (black + isort)
make lint                   # Run linting (flake8 + mypy)
make test                   # Run tests
make check-all              # All quality checks

# Build and distribution
make build                  # Build packages
make clean                  # Clean artifacts
```

### Feature Development Process

1. **Create feature branch**
   ```bash
   git checkout -b feature/amazing-feature
   ```

2. **Implement changes**
   - Follow code style guidelines
   - Add comprehensive docstrings
   - Include type hints
   - Write tests for new functionality

3. **Test your changes**
   ```bash
   make test                # Run all tests
   make lint                # Check code quality
   make format              # Format code
   ```

4. **Commit changes**
   ```bash
   git add .
   git commit -m "feat: add amazing feature"
   ```

5. **Push and create PR**
   ```bash
   git push origin feature/amazing-feature
   # Create pull request on GitHub
   ```

### Code Review Process

- **Automated Checks**: All PRs must pass CI checks
- **Code Review**: At least one reviewer required
- **Testing**: New features must include tests
- **Documentation**: Update docs for user-facing changes

## Code Style Guidelines

### Formatting Standards

**Black Configuration** (88 character line length):
```bash
black skymarshal/
```

**Import Sorting** (isort with black-compatible profile):
```bash
isort skymarshal/
```

**Type Hints** (encouraged for all functions):
```python
def process_content(self, items: List[ContentItem]) -> Dict[str, Any]:
    """Process content items and return statistics."""
    # Implementation...
```

### Documentation Standards

**Module Docstrings**:
```python
"""
Skymarshal Module Name

File Purpose: Brief description of module purpose
Primary Functions/Classes: List main components
Inputs and Outputs (I/O): Describe data flow

Detailed description of module functionality and usage.
"""
```

**Function Docstrings**:
```python
def authenticate_client(self, handle: str, password: str) -> bool:
    """
    Authenticate client for API operations.
    
    Args:
        handle: Bluesky handle (e.g., 'username.bsky.social')
        password: Account password
        
    Returns:
        True if authentication successful, False otherwise
        
    Raises:
        AuthenticationError: If credentials are invalid
    """
```

### Naming Conventions

- **Modules**: `snake_case` (e.g., `data_manager.py`)
- **Classes**: `PascalCase` (e.g., `AuthManager`)
- **Functions**: `snake_case` (e.g., `authenticate_client`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_TIMEOUT`)
- **Private methods**: `_leading_underscore` (e.g., `_validate_input`)

## 🧪 Testing Strategy

### Test Structure

```
tests/
├── unit/                   # Unit tests
│   ├── test_auth.py       # Authentication tests
│   ├── test_data_manager.py # Data management tests
│   └── test_search.py     # Search functionality tests
├── integration/            # Integration tests
│   ├── test_workflows.py  # End-to-end workflows
│   └── test_api.py        # API integration tests
├── fixtures/              # Test data and fixtures
└── conftest.py           # Pytest configuration
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_auth.py

# Run with coverage
pytest --cov=skymarshal

# Run with verbose output
pytest -v

# Run specific test
pytest tests/unit/test_auth.py::test_authenticate_client_success
```

### Test Categories

**Unit Tests**:
- Test individual components in isolation
- Mock external dependencies
- Fast execution (< 1 second per test)

**Integration Tests**:
- Test component interactions
- Use real data when possible
- Test complete workflows

**End-to-End Tests**:
- Test complete user workflows
- Use real Bluesky API (with test account)
- Validate actual functionality

### Mocking Strategy

```python
# Mock external APIs
@patch('skymarshal.auth.Client')
def test_authenticate_client_success(mock_client):
    """Test successful authentication."""
    mock_client.return_value.login.return_value = MockProfile()
    
    auth_manager = AuthManager()
    result = auth_manager.authenticate_client("test.bsky.social", "password")
    
    assert result is True
    assert auth_manager.is_authenticated() is True
```

## Debugging

### Debug Mode

```bash
# Run with debug output
python -m skymarshal --verbose

# Enable debug logging
export SKYMARSHAL_DEBUG=1
python -m skymarshal
```

### Common Debug Scenarios

**Authentication Issues**:
```python
# Add debug logging to auth.py
import logging
logging.basicConfig(level=logging.DEBUG)

# Check client state
print(f"Client: {self.client}")
print(f"Handle: {self.current_handle}")
print(f"DID: {self.current_did}")
```

**Data Processing Issues**:
```python
# Debug data loading
def debug_data_loading(self, data):
    print(f"Data type: {type(data)}")
    print(f"Data length: {len(data) if hasattr(data, '__len__') else 'N/A'}")
    print(f"First item: {data[0] if data else 'Empty'}")
```

**UI Issues**:
```python
# Debug Rich rendering
from rich.console import Console
console = Console()
console.print("Debug: UI component rendered")
```

### Performance Debugging

```python
import time
import cProfile

# Time function execution
start_time = time.time()
result = expensive_function()
end_time = time.time()
print(f"Execution time: {end_time - start_time:.2f} seconds")

# Profile function
cProfile.run('expensive_function()')
```

## Performance Optimization

### Profiling

```bash
# Install profiling tools
pip install line_profiler memory_profiler

# Profile specific functions
kernprof -l -v skymarshal/app.py
```

### Optimization Strategies

**Memory Optimization**:
- Use generators for large datasets
- Process data in chunks
- Clear unused variables
- Use `__slots__` for data classes

**CPU Optimization**:
- Cache expensive computations
- Use appropriate data structures
- Minimize API calls
- Parallelize independent operations

**I/O Optimization**:
- Batch file operations
- Use async I/O where possible
- Compress data storage
- Cache frequently accessed data

### Performance Monitoring

```python
# Add performance metrics
import time
from functools import wraps

def time_function(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        print(f"{func.__name__} took {end_time - start_time:.2f} seconds")
        return result
    return wrapper

@time_function
def slow_operation():
    # Implementation...
```

## Release Process

### Version Management

**Semantic Versioning** (MAJOR.MINOR.PATCH):
- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Checklist

1. **Update Version**
   ```bash
   # Update pyproject.toml
   version = "0.2.0"
   ```

2. **Update Changelog**
   ```bash
   # Add entries to CHANGELOG.md
   ## [0.2.0] - 2024-01-15
   ### Added
   - New feature X
   ### Changed
   - Improved Y
   ### Fixed
   - Bug fix Z
   ```

3. **Run Full Test Suite**
   ```bash
   make check-all
   pytest --cov=skymarshal
   ```

4. **Build Packages**
   ```bash
   make clean-dist
   make setup-dist
   ```

5. **Test Installation**
   ```bash
   make test-install
   ```

6. **Create Git Tag**
   ```bash
   git tag v0.2.0
   git push origin v0.2.0
   ```

7. **Upload to PyPI**
   ```bash
   # Test PyPI first
   make publish-test
   
   # Production PyPI
   make publish
   ```

### Distribution Setup

**Automated Distribution**: The project includes GitHub Actions workflows for automated publishing.

**Manual Distribution**: Use the provided scripts and Makefile commands:

```bash
# Complete distribution setup
make setup-dist

# Test on Test PyPI
make publish-test

# Publish to PyPI
make publish
```

**Conda Distribution**: See the internal distribution guide at `internal/DISTRIBUTION.md` for conda-forge submission process.

### Automated Releases

**GitHub Actions** (future enhancement):
```yaml
name: Release
on:
  push:
    tags:
      - 'v*'
jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build and publish
        run: |
          pip install build twine
          python -m build
          python -m twine upload dist/*
```

## Troubleshooting

### Common Development Issues

**Import Errors**:
```bash
# Ensure package is installed in development mode
pip install -e .

# Check Python path
python -c "import sys; print(sys.path)"
```

**Test Failures**:
```bash
# Run tests with verbose output
pytest -v -s

# Run specific test with debugging
pytest tests/unit/test_auth.py::test_authenticate_client_success -v -s
```

**Build Issues**:
```bash
# Clean and rebuild
make clean
make build

# Check build configuration
python -m build --help
```

**Dependency Issues**:
```bash
# Update dependencies
pip install -e ".[dev]" --upgrade

# Check for conflicts
pip check
```

### Environment Issues

**Multiple Python Versions**:
```bash
# Use specific Python version
python3.9 -m pip install -e .
python3.9 -m skymarshal
```

**Virtual Environment Issues**:
```bash
# Recreate virtual environment
rm -rf .venv
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

**Permission Issues**:
```bash
# Fix file permissions
chmod +x bin/skymarshal  # If bin directory exists
```

### Getting Help

- **GitHub Issues**: Report bugs and request features
- **Discussions**: Ask questions and share ideas
- **Documentation**: Check existing docs first
- **Code Review**: Ask for review on PRs

---

This development guide provides comprehensive information for contributing to Skymarshal. For additional help, see the [Contributing Guide](CONTRIBUTING.md) and [Architecture Guide](ARCHITECTURE.md).
