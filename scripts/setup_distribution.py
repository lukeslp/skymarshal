#!/usr/bin/env python3
"""
Skymarshal Distribution Setup Script

This script helps set up the project for PyPI and Conda distribution.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"{description}...")
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print(f"{description} completed")
        return result
    except subprocess.CalledProcessError as e:
        print(f"{description} failed:")
        print(f"   Command: {cmd}")
        print(f"   Error: {e.stderr}")
        sys.exit(1)

def check_requirements():
    """Check if we're in the right directory and have required tools."""
    if not Path("pyproject.toml").exists():
        print("Error: Please run this script from the project root directory")
        sys.exit(1)
    
    # Check Python version
    python_version = sys.version_info
    print(f"Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    if python_version < (3, 8):
        print("Error: Python 3.8 or higher is required")
        sys.exit(1)

def install_dependencies():
    """Install build dependencies."""
    run_command("pip install --upgrade pip", "Upgrading pip")
    run_command("pip install build twine", "Installing build dependencies")

def clean_builds():
    """Clean previous builds."""
    print("Cleaning previous builds...")
    dirs_to_clean = ["build", "dist"]
    for dir_name in dirs_to_clean:
        if Path(dir_name).exists():
            shutil.rmtree(dir_name)
            print(f"   Removed {dir_name}/")
    
    # Clean egg-info directories
    for egg_info in Path(".").glob("*.egg-info"):
        shutil.rmtree(egg_info)
        print(f"   Removed {egg_info}/")

def run_tests():
    """Run tests and quality checks."""
    run_command("pip install -e \".[dev]\"", "Installing development dependencies")
    run_command("pytest --cov=skymarshal", "Running tests")
    run_command("flake8 skymarshal/", "Running flake8 linting")
    run_command("mypy skymarshal/", "Running mypy type checking")
    run_command("black --check skymarshal/", "Checking code formatting")
    run_command("isort --check-only skymarshal/", "Checking import sorting")

def build_package():
    """Build the package."""
    run_command("python -m build", "Building package")
    run_command("twine check dist/*", "Checking package")

def show_results():
    """Show build results and next steps."""
    print("\nDistribution setup complete.")
    print("\nBuilt packages:")
    
    dist_dir = Path("dist")
    if dist_dir.exists():
        for file in dist_dir.iterdir():
            size = file.stat().st_size
            print(f"   {file.name} ({size:,} bytes)")
    
    print("\nNext steps:")
    print("1. Test the package: pip install dist/*.whl")
    print("2. Upload to Test PyPI: twine upload --repository testpypi dist/*")
    print("3. Upload to PyPI: twine upload dist/*")
    print("4. Submit to conda-forge: https://github.com/conda-forge/staged-recipes")
    print("\nFor more information, see DEVELOPMENT.md")

def main():
    """Main setup process."""
    print("Setting up Skymarshal for distribution...")
    
    check_requirements()
    install_dependencies()
    clean_builds()
    run_tests()
    build_package()
    show_results()

if __name__ == "__main__":
    main()
