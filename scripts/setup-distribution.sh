#!/bin/bash

# Skymarshal Distribution Setup Script
# This script helps set up the project for PyPI and Conda distribution

set -e

echo "Setting up Skymarshal for distribution..."

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "Error: Please run this script from the project root directory"
    exit 1
fi

# Check Python version
python_version=$(python --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "🐍 Python version: $python_version"

# Install build dependencies
echo "Installing build dependencies..."
pip install --upgrade pip
pip install build twine

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf build/ dist/ *.egg-info/

# Run tests
echo "🧪 Running tests..."
pip install -e ".[dev]"
pytest --cov=skymarshal

# Run linting
echo "Running linting..."
flake8 skymarshal/
mypy skymarshal/

# Check formatting
echo "🎨 Checking code formatting..."
black --check skymarshal/
isort --check-only skymarshal/

# Build package
echo "🔨 Building package..."
python -m build

# Check package
echo "Checking package..."
twine check dist/*

echo ""
echo "Distribution setup complete."
echo ""
echo "Built packages:"
ls -la dist/
echo ""
echo "Next steps:"
echo "1. Test the package: pip install dist/*.whl"
echo "2. Upload to Test PyPI: twine upload --repository testpypi dist/*"
echo "3. Upload to PyPI: twine upload dist/*"
echo "4. Submit to conda-forge: https://github.com/conda-forge/staged-recipes"
echo ""
echo "For more information, see DEVELOPMENT.md"
