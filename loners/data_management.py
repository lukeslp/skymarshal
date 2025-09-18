#!/usr/bin/env python3
"""Standalone data management entrypoint."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loners.common import init_manager
from skymarshal.models import console


def main() -> None:
    manager = init_manager()
    manager.handle_data_management()
    console.print()
    console.print("[dim]Tip: follow with search.py to work with freshly loaded data.[/]")


if __name__ == "__main__":
    main()
