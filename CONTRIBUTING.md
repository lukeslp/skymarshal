# Contributing to Skymarshal

Thank you for your interest in contributing to Skymarshal! This guide will help you get started with contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Types of Contributions](#types-of-contributions)
- [Development Process](#development-process)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Testing Requirements](#testing-requirements)
- [Documentation Guidelines](#documentation-guidelines)
- [Issue Reporting](#issue-reporting)
- [Community Guidelines](#community-guidelines)

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inclusive environment for all contributors, regardless of:

- Age, body size, disability, ethnicity, gender identity and expression
- Level of experience, nationality, personal appearance, race, religion
- Sexual identity and orientation, socioeconomic status, or technical background

### Expected Behavior

- **Be respectful** and inclusive in all interactions
- **Be constructive** in feedback and discussions
- **Be collaborative** and help others learn and grow
- **Be patient** with newcomers and different experience levels
- **Be professional** in all communications

### Unacceptable Behavior

- Harassment, discrimination, or exclusionary behavior
- Trolling, insulting, or derogatory comments
- Personal attacks or political discussions
- Public or private harassment
- Publishing private information without permission
- Any conduct that would be inappropriate in a professional setting

### Enforcement

Instances of unacceptable behavior may be reported to the project maintainers. All complaints will be reviewed and investigated promptly and fairly.

## Getting Started

### Prerequisites

- **Python 3.8+** installed on your system
- **Git** for version control
- **GitHub account** for contributing
- **Basic understanding** of Python and command-line tools

### Initial Setup

1. **Fork the repository**
   ```bash
   # Go to https://github.com/lukeslp/skymarshal and click "Fork"
   ```

2. **Clone your fork**
   ```bash
   git clone https://github.com/YOUR_USERNAME/skymarshal.git
   cd skymarshal
   ```

3. **Add upstream remote**
   ```bash
   git remote add upstream https://github.com/lukeslp/skymarshal.git
   ```

4. **Set up development environment**
   ```bash
   # Create virtual environment
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   
   # Install in development mode
   pip install -e ".[dev]"
   ```

5. **Verify setup**
   ```bash
   python - <<'PY'
   import skymarshal as sm
   print(f"Skymarshal version: {sm.__version__}")
   PY
   make test
   ```

## Types of Contributions

### Bug Reports

**Before reporting a bug:**
1. Check if the issue already exists
2. Try the latest version
3. Check the [troubleshooting guide](README.md#troubleshooting)

**When reporting a bug:**
- Use the bug report template
- Include steps to reproduce
- Provide system information (OS, Python version)
- Include error messages and logs
- Describe expected vs actual behavior

### Feature Requests

**Before requesting a feature:**
1. Check if the feature already exists
2. Consider if it aligns with project goals
3. Check if it's already planned

**When requesting a feature:**
- Use the feature request template
- Describe the problem it solves
- Provide use cases and examples
- Consider implementation complexity
- Be open to discussion and alternatives

### Code Contributions

**Types of code contributions:**
- **Bug fixes** - Fix existing issues
- **New features** - Add new functionality
- **Improvements** - Enhance existing features
- **Documentation** - Improve docs and examples
- **Tests** - Add or improve test coverage
- **Refactoring** - Improve code structure

### Documentation Contributions

**Types of documentation:**
- **User guides** - Help users understand features
- **API documentation** - Document functions and classes
- **Examples** - Provide usage examples
- **Tutorials** - Step-by-step guides
- **Translation** - Translate docs to other languages

## Development Process

### Branch Strategy

**Branch naming conventions:**
- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation changes
- `refactor/description` - Code refactoring
- `test/description` - Test improvements

**Examples:**
```bash
git checkout -b feature/car-file-validation
git checkout -b fix/authentication-timeout
git checkout -b docs/api-reference-update
```

### Commit Message Format

We use [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**
```bash
git commit -m "feat(auth): add session timeout handling"
git commit -m "fix(ui): resolve menu navigation issue"
git commit -m "docs(api): update command reference"
git commit -m "test(data): add CAR file validation tests"
```

### Development Workflow

1. **Create feature branch**
   ```bash
   git checkout -b feature/amazing-feature
   ```

2. **Make changes**
   - Write code following style guidelines
   - Add tests for new functionality
   - Update documentation as needed

3. **Test your changes**
   ```bash
   make test                # Run tests
   make lint                # Check code quality
   make format              # Format code
   ```

4. **Commit changes**
   ```bash
   git add .
   git commit -m "feat: add amazing feature"
   ```

5. **Push to your fork**
   ```bash
   git push origin feature/amazing-feature
   ```

6. **Create pull request**
   - Go to your fork on GitHub
   - Click "New Pull Request"
   - Fill out the PR template
   - Request review from maintainers

## Pull Request Process

### Before Submitting

- [ ] **Tests pass** - All tests must pass
- [ ] **Code quality** - Code follows style guidelines
- [ ] **Documentation** - Update docs for user-facing changes
- [ ] **Commit messages** - Use conventional commit format
- [ ] **Single responsibility** - PR focuses on one change
- [ ] **Backward compatibility** - Don't break existing functionality

### PR Template

When creating a pull request, please include:

**Description:**
- What does this PR do?
- Why is this change needed?
- How does it work?

**Type of Change:**
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

**Testing:**
- [ ] Tests added/updated
- [ ] Manual testing performed
- [ ] All tests pass

**Checklist:**
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No breaking changes (or documented)

### Review Process

1. **Automated Checks**
   - CI/CD pipeline runs tests
   - Code quality checks
   - Security scans

2. **Code Review**
   - At least one maintainer review required
   - Address feedback promptly
   - Make requested changes

3. **Approval**
   - Maintainer approves PR
   - PR is merged
   - Feature is included in next release

### After Merging

- **Clean up** - Delete feature branch
- **Update** - Pull latest changes from upstream
- **Celebrate** - Your contribution is now part of Skymarshal!

## License for Contributions

By contributing to this repository, you agree that your contributions are released under the CC0 1.0 Universal (public domain) dedication, consistent with the project’s [LICENSE](LICENSE).

## Coding Standards

### Code Style

**Formatting:**
- Use **Black** with 88 character line length
- Use **isort** for import sorting
- Follow **PEP 8** guidelines

**Type Hints:**
```python
def process_content(self, items: List[ContentItem]) -> Dict[str, Any]:
    """Process content items and return statistics."""
    # Implementation...
```

**Documentation:**
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

### Code Organization

**Module Structure:**
```python
"""
Module docstring with purpose and overview.
"""

# Standard library imports
import os
import sys
from typing import List, Dict, Any

# Third-party imports
from rich.console import Console
from atproto import Client

# Local imports
from .models import ContentItem
from .auth import AuthManager

# Module-level constants
DEFAULT_TIMEOUT = 30

# Classes and functions
class ExampleClass:
    """Class docstring."""
    
    def __init__(self):
        """Initialize class."""
        pass
    
    def public_method(self) -> str:
        """Public method docstring."""
        return self._private_method()
    
    def _private_method(self) -> str:
        """Private method docstring."""
        return "example"
```

## 🧪 Testing Requirements

### Test Coverage

- **New features** must include tests
- **Bug fixes** must include regression tests
- **Aim for 80%+ coverage** on new code
- **Test edge cases** and error conditions

### Test Structure

```python
# tests/unit/test_auth.py
import pytest
from unittest.mock import patch, Mock
from skymarshal.auth import AuthManager

class TestAuthManager:
    """Test cases for AuthManager class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.auth_manager = AuthManager()
    
    def test_authenticate_client_success(self):
        """Test successful authentication."""
        with patch('skymarshal.auth.Client') as mock_client:
            mock_client.return_value.login.return_value = MockProfile()
            
            result = self.auth_manager.authenticate_client(
                "test.bsky.social", "password"
            )
            
            assert result is True
            assert self.auth_manager.is_authenticated() is True
    
    def test_authenticate_client_failure(self):
        """Test authentication failure."""
        with patch('skymarshal.auth.Client') as mock_client:
            mock_client.return_value.login.side_effect = Exception("Auth failed")
            
            result = self.auth_manager.authenticate_client(
                "test.bsky.social", "wrong_password"
            )
            
            assert result is False
            assert not self.auth_manager.is_authenticated()
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
pytest tests/unit/test_auth.py::TestAuthManager::test_authenticate_client_success
```

## Documentation Guidelines

### User Documentation

**README Updates:**
- Update feature lists
- Add new command examples
- Update installation instructions
- Include troubleshooting info

**API Documentation:**
- Document new commands
- Update command reference
- Provide usage examples
- Include error codes

### Code Documentation

**Module Docstrings:**
```python
"""
Skymarshal Module Name

File Purpose: Brief description of module purpose
Primary Functions/Classes: List main components
Inputs and Outputs (I/O): Describe data flow

Detailed description of module functionality and usage.
"""
```

**Function Docstrings:**
```python
def example_function(param1: str, param2: int) -> bool:
    """
    Brief description of what the function does.
    
    Args:
        param1: Description of first parameter
        param2: Description of second parameter
        
    Returns:
        Description of return value
        
    Raises:
        ValueError: When invalid input is provided
        
    Example:
        >>> result = example_function("test", 42)
        >>> print(result)
        True
    """
```

### Documentation Standards

- **Clear and concise** language
- **Complete examples** for new features
- **Up-to-date** information
- **Consistent** formatting and style
- **Accessible** to users of all skill levels

## Issue Reporting

### Before Creating an Issue

1. **Search existing issues** - Check if your issue already exists
2. **Check documentation** - Review README and troubleshooting guide
3. **Try latest version** - Ensure you're using the most recent release
4. **Reproduce the issue** - Confirm the problem exists

### Creating a Good Issue

**Bug Report Template:**
```markdown
## Bug Description
Brief description of the bug.

## Steps to Reproduce
1. Go to '...'
2. Click on '....'
3. Scroll down to '....'
4. See error

## Expected Behavior
What you expected to happen.

## Actual Behavior
What actually happened.

## Environment
- OS: [e.g., macOS 13.0, Windows 10, Ubuntu 20.04]
- Python Version: [e.g., 3.9.7]
- Skymarshal Version: [e.g., 0.1.0]

## Additional Context
Any other context about the problem.
```

**Feature Request Template:**
```markdown
## Feature Description
Brief description of the feature.

## Problem Statement
What problem does this feature solve?

## Proposed Solution
How should this feature work?

## Alternatives Considered
What other solutions have you considered?

## Additional Context
Any other context or screenshots about the feature request.
```

### Issue Labels

We use labels to categorize issues:

- `bug` - Something isn't working
- `enhancement` - New feature or request
- `documentation` - Improvements to documentation
- `good first issue` - Good for newcomers
- `help wanted` - Extra attention needed
- `question` - Further information is requested

## Community Guidelines

### Getting Help

**Where to ask questions:**
- **GitHub Discussions** - General questions and ideas
- **GitHub Issues** - Bug reports and feature requests
- **Code Review** - Questions about specific changes

**How to ask good questions:**
- **Be specific** about your problem
- **Provide context** and examples
- **Show what you've tried** already
- **Be patient** for responses

### Providing Help

**How to help others:**
- **Answer questions** in discussions
- **Review pull requests** constructively
- **Share knowledge** and best practices
- **Welcome newcomers** and help them get started

### Recognition

**Contributor recognition:**
- **Contributors list** in README
- **Release notes** mention significant contributions
- **GitHub contributor badges** for active contributors
- **Special thanks** for major contributions

## Recognition

### Contributor Levels

**First-time Contributors:**
- Welcome message
- Special badge
- Mentorship available

**Regular Contributors:**
- Contributor badge
- Priority in issue assignment
- Direct communication with maintainers

**Core Contributors:**
- Maintainer status consideration
- Release management access
- Project decision input

### How to Get Recognized

- **Consistent contributions** over time
- **High-quality code** and documentation
- **Helpful community** participation
- **Mentoring** other contributors
- **Project leadership** and initiative

## Contact

**Project Maintainer:**
- **Luke Steuber** - [@lukesteuber.com](https://bsky.app/profile/lukesteuber.com)
- **Email** - [luke@lukesteuber.com](mailto:luke@lukesteuber.com)
- **GitHub** - [@lukeslp](https://github.com/lukeslp)

**Community Channels:**
- **GitHub Discussions** - General discussion
- **GitHub Issues** - Bug reports and features
- **Email** - Direct contact for sensitive issues

---

Thank you for contributing to Skymarshal! Your contributions help make Bluesky content management better for everyone.
