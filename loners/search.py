#!/usr/bin/env python3
"""Find, filter, and manage content via the search flow."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loners.common import init_manager


def main() -> None:
    manager = init_manager()
    manager.handle_search_analyze()


if __name__ == "__main__":
    main()
