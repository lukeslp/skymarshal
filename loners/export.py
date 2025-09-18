#!/usr/bin/env python3
"""Export filtered datasets via the search flow."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loners.common import init_manager
from skymarshal.models import console


def main() -> None:
    manager = init_manager()
    if not manager.current_data:
        console.print("[dim]Loading data before export...[/]")
        manager.handle_data_management()
    if manager.current_data:
        manager.handle_search_analyze()
    else:
        console.print("[yellow]Nothing to export yet. Import data first.[/]")


if __name__ == "__main__":
    main()
