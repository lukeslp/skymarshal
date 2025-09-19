"""Module entry point for loners.

Launches the loners launcher menu (loners/run.py).
Run with: python -m loners
"""

from . import run as _run


def main() -> None:
    _run.main()


if __name__ == "__main__":
    main()

