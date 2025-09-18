#!/usr/bin/env python3
"""Placeholder notice for retired system info tooling."""

from skymarshal.models import console


def main() -> None:
    console.print("[yellow]System diagnostics are no longer shipped with loners.[/]")
    console.print("[dim]Use your OS tools or extend the main CLI if deeper checks are required.[/]")


if __name__ == "__main__":
    main()
