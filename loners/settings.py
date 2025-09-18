#!/usr/bin/env python3
"""Interactive settings editor."""

from pathlib import Path

from skymarshal.settings import SettingsManager


def main() -> None:
    settings_file = Path.home() / ".car_inspector_settings.json"
    SettingsManager(settings_file).handle_settings()


if __name__ == "__main__":
    main()
