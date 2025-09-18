"""Shared helpers for loner scripts.

These helpers wrap the main InteractiveContentManager so the standalone
entrypoints can reuse the same logic without maintaining their own copies.
"""

from __future__ import annotations

from typing import Optional

from skymarshal.app import InteractiveContentManager
from skymarshal.banner import show_banner
from skymarshal.models import console


def init_manager(show: bool = True) -> InteractiveContentManager:
    """Instantiate the interactive manager and optionally show the banner."""
    manager = InteractiveContentManager()
    if show:
        try:
            console.clear()
        except Exception:
            pass
        show_banner()
    return manager
