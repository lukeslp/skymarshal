"""
Banner display module for Skymarshal.

File Purpose: ASCII art banner display and system initialization sequence
Primary Functions/Classes: show_banner(), show_startup_sequence()
Inputs and Outputs (I/O): Displays ASCII art and loading messages to console, no file I/O
"""

import time

from rich.align import Align
from rich.text import Text

from . import __version__
from .models import console


def get_ascii_art():
    """Get the ASCII art from ascii.nfo verbatim."""
    return """⠀⠀⠀⠀⠀⠀⠀⠀⢠⡖⠀⠀⢀⣠⡤⠶⠶⢦⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⡄⠀⣰⢻⣇⡴⠛⠉⠀⡀⠀⠀⠀⠈⠳⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⢀⣷⢠⡏⢸⢏⠄⠀⡔⠉⣀⡴⢋⣁⣐⣢⡈⢷⡀⠀⠀⠀⠀⠀⠀⠀
⢀⣀⣀⡀⢸⡟⣿⠀⠈⢸⣀⣮⣤⣤⣟⣰⣷⣶⣶⣌⡙⠦⣝⠲⣤⣤⡀⠀⠀⠀
⣞⠀⢄⠉⠻⢧⡈⠀⠀⢸⣿⣿⣿⠟⠉⠉⠉⢉⣙⢻⣖⡂⠈⠉⠉⠉⠀⠀⠀⠀
⢹⡄⠀⠑⣄⠀⠈⠳⣤⣾⣿⣿⠃⠖⠒⣄⠀⡧⢾⡏⢻⡗⠂⠀⠀⠀⠀⠀⠀⠀
⠀⢳⡀⠀⢸⠳⣄⠀⢸⢿⣿⢿⡀⡚🟠⣿⠀⠀⣘🟠⣷⣤⣀⠀⠀⠀⠀⠀⠀
⠀⠀⢷⡀⠘⣧⡸⠃⠀⣼⠋⣸⠁⠀⠒⠋⢀⡰⠁⠀⡼⠁⠀⠉⠛⢦⡀⠀⠀⠀
⠀⠀⣸⠁⠀⡼⠁⠴⢾⡇⢀⡏⠀⠀⠤⠖⢫⡇⠀⢠⠃⠀⠀⣀⣀⣀⠿⢦⡀⠀
⠀⠀⢹⡀⠀⠁⠀⣾⡿⢁⡞⠀⠀⠀⠀⠀⢸⡅⠀⠘⡄⠀⢸⠁⡶⡄⢺⣳⠹⣆
⠀⠀⠀⠓⠦⣶⠋⠀⠇⣸⠁⠀⠀⢸⡀⠀⠈⡇⠀⠀⢧⠀⠸⡄⠙⠋⠀⠀⠀⣿
⠀⠀⠀⠀⢰⣣⠀⠀⠀⣿⠀⠀⠀⠈⣇⠀⠀⢳⠀⠀⠈⢧⡀⢱⣄⠀⠀⠀⢀⡿
⠀⠀⠀⠀⣸⠃⠀⠀⠀⢹⡄⠀⠀⠀⠘⢦⣄⡠⠷⡖⠲⠚⣍⠙⢏⠓⠦⠴⠛⠁
⠀⠀⠀⢠⠏⡀⠀⠀⠀⠀⠙⠳⠤⠤⠴⠋⠣⡀⠀⠘⠀⠑⣈⣧⡜⣧⠀⠀⠀⠀
⠀⠀⠀⣾⣾⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠱⣄⢀⣆⠀⢹⠑⢴⢸⡆⠀⠀⠀
⠀⠀∢⡏⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠛⠼⣄⣸⡤⠎⢀⡇⠀⠀⠀
⠀⠀⠀⢸⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣀⣠⠄⢀⠀⠀⠀⠀⢀⡤⠟⠀⠀⠀⠀
⠀⠀⠀⡟⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠁⠐⠛⣺⢿⣾⡤⠴⠚⠋⠀⠀⠀⠀⠀⠀
⠀⠀⠀⢧⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣠⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠈⠳⣦⡀⣄⣀⠀⠀⠀⢻⣖⠛⠋⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠙⠿⠉⠉⠉⠉⠉⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀"""


def get_banner_text():
    return "SKYMARSHAL"


def show_banner(console_override=None):
    display_console = console_override or console
    display_console.clear()
    ascii_art = get_ascii_art()
    ascii_text = Text(ascii_art, style="cyan")
    display_console.print(Align.center(ascii_text))
    display_console.print()
    banner_text = get_banner_text()
    banner = Text(banner_text, style="bold bright_white")
    display_console.print(Align.center(banner))
    tagline = Text(
        "Manage • Analyze • Clean up your social media", style="italic dim white"
    )
    display_console.print(Align.center(tagline))
    display_console.print()
    version_text = Text(
        f"v{__version__} • Luke • ",
        style="dim bright_white link https://lukesteuber.com",
    )
    version_text.append(
        "@lukesteuber.com",
        style="dim bright_blue link https://bsky.app/profile/lukesteuber.com",
    )
    display_console.print(Align.center(version_text))
    display_console.print()


def show_ascii_header_only(console_override=None):
    """Display just the ASCII art and banner text without clearing screen."""
    display_console = console_override or console
    ascii_art = get_ascii_art()
    ascii_text = Text(ascii_art, style="cyan")
    display_console.print(Align.center(ascii_text))
    display_console.print()
    banner_text = get_banner_text()
    banner = Text(banner_text, style="bold bright_white")
    display_console.print(Align.center(banner))
    display_console.print()


def show_startup_sequence(console_override=None):
    display_console = console_override or console
    display_console.clear()
    show_banner(display_console)


if __name__ == "__main__":
    show_startup_sequence()
