#!/usr/bin/env python3
"""Quick statistics helper that reuses the main application flow."""

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

    if manager.current_data:
        manager.handle_quick_stats()
    else:
        console.print("[yellow]No dataset available. Run data_management.py to import content first.[/]")


if __name__ == "__main__":
    main()
