#!/usr/bin/env python3
"""Run the nuclear delete flow with standalone ergonomics."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loners.common import init_manager


def main() -> None:
    manager = init_manager()
    manager.handle_nuke()


if __name__ == "__main__":
    main()
