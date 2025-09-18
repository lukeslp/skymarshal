#!/usr/bin/env python3
"""Launcher for the supported loner entrypoints."""

import subprocess
import sys
from pathlib import Path
from typing import Dict, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.prompt import Prompt
from rich.rule import Rule

console = Console()

SUPPORTED_SCRIPTS: Dict[str, Tuple[str, str]] = {
    "1": ("auth.py", "Authentication"),
    "2": ("data_management.py", "Data Management"),
    "3": ("search.py", "Search & Export"),
    "4": ("stats.py", "Quick Stats"),
    "5": ("delete.py", "Content Deletion"),
    "6": ("nuke.py", "Nuclear Delete"),
    "7": ("settings.py", "Settings Editor"),
    "8": ("help.py", "Help & Documentation"),
}

LEGACY_SCRIPTS: Dict[str, str] = {
    "a": "analyze.py",
    "b": "find_bots.py",
    "c": "cleanup.py",
    "d": "system_info.py",
}


def show_banner() -> None:
    banner = """
    ╔══════════════════════════════════════════════════════════════╗
    ║                    SKYMARSHAL LONERS                        ║
    ║            Focused entrypoints for common workflows         ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    console.print(banner, style="bright_cyan")


def launch_script(script_name: str) -> None:
    script_path = Path(__file__).parent / script_name
    subprocess.run([sys.executable, str(script_path)], check=False)


def main() -> None:
    show_banner()

    while True:
        console.print(Rule("Supported Workflows", style="bright_blue"))
        for key, (script, title) in SUPPORTED_SCRIPTS.items():
            console.print(f"  [{key}] {title}")
        if LEGACY_SCRIPTS:
            console.print()
            console.print("Legacy stubs:")
            for key, script in LEGACY_SCRIPTS.items():
                console.print(f"  [{key}] {script} (informational)")
        console.print()
        console.print("  [q] Quit")
        console.print()

        choice = Prompt.ask(
            "Select option",
            choices=list(SUPPORTED_SCRIPTS.keys()) + list(LEGACY_SCRIPTS.keys()) + ["q"],
            default="1",
            show_choices=False,
        )

        if choice == "q":
            console.print("Goodbye!")
            break

        if choice in SUPPORTED_SCRIPTS:
            launch_script(SUPPORTED_SCRIPTS[choice][0])
        elif choice in LEGACY_SCRIPTS:
            launch_script(LEGACY_SCRIPTS[choice])

        console.print()


if __name__ == "__main__":
    main()
