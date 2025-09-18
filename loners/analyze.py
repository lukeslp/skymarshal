#!/usr/bin/env python3
"""Legacy analyze entrypoint – directs contributors to the consolidated flows."""

from skymarshal.models import console


def main() -> None:
    console.print("[yellow]Account analysis now lives inside search.py and stats.py.[/]")
    console.print("[dim]Run those scripts to load data, view insights, and export results.[/]")


if __name__ == "__main__":
    main()
