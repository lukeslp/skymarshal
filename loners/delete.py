#!/usr/bin/env python3
"""Safe deletion helper that reuses the main interactive workflows."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loners.common import init_manager
from skymarshal.models import console


def main() -> None:
    manager = init_manager()
    if not manager.current_data:
        console.print("[dim]No data loaded yet – opening data management first...[/]")
        manager.handle_data_management()
    if not manager.current_data:
        console.print("[yellow]Nothing to delete. Import data before running this tool.[/]")
        return

    manager.handle_delete_content()


if __name__ == "__main__":
    main()
