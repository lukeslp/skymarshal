#!/usr/bin/env python3
"""Standalone authentication flow for Skymarshal."""

import sys
from pathlib import Path

# Ensure the project root is on sys.path when executed directly
sys.path.insert(0, str(Path(__file__).parent.parent))

from loners.common import init_manager
from skymarshal.models import console


def main() -> None:
    """Kick off the authentication handler."""
    manager = init_manager()
    manager.handle_authentication()
    console.print()
    console.print("[dim]Use this shell to verify or refresh your session before other loners.[/]")


if __name__ == "__main__":
    main()
