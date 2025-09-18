#!/usr/bin/env python3
"""Standalone help viewer."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loners.common import init_manager


def main() -> None:
    manager = init_manager()
    manager.help_manager.show_help()


if __name__ == "__main__":
    main()
