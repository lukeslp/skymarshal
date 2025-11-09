#!/usr/bin/env python3
"""
XAI BlueSky Web Application & Interactive CLI

PATCH: DIDs are never modified or suffixed. All BlueSkyAPI calls are now safe for both handles and DIDs. See bluevibes_core.py for details.
Accessibility: All outputs are screen-reader friendly; errors are explicit.

- Imports BlueSkyAPI, CLIFormatter, and console from bluevibes_core.py
- Default: Launches interactive, menu-driven CLI (main_menu from bluevibes_cli.py)
- If subcommands are given, runs argparse CLI
- All DB files are named `.bluevibes.db` (in home or working dir)
- Embedding functionality (for chat/semantic search) is integrated and uses `.bluevibes*.pkl` filenames

Usage:
    python bluevibes.py         # Launches interactive CLI
    python bluevibes.py <args>  # (future) Subcommands

"""

from __future__ import annotations

import requests
import json
import os
from typing import Optional
from bluevibes_core import BlueSkyAPI

# -----------------------------------------------------------------------------
# Configuration (override via environment variables)
DEFAULT_ENDPOINT = os.environ.get("OLLAMA_ENDPOINT", "http://localhost:11434/api")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:1b")
# -----------------------------------------------------------------------------


class OllamaChat:
    """Minimal chat wrapper for an Ollama-compatible endpoint."""

    # Using configurable endpoint
    ENDPOINT = DEFAULT_ENDPOINT

    def __init__(
        self, model: "Optional[str]" = None, endpoint: "Optional[str]" = None
    ) -> None:
        """Create a new chat helper.

        Args:
            model: Optional model name override.
            endpoint: Optional API endpoint override.
        """
        # Allow overrides from args or env vars
        self.endpoint = (
            endpoint or os.environ.get("OLLAMA_ENDPOINT") or DEFAULT_ENDPOINT
        )
        self.model = model or os.environ.get("OLLAMA_MODEL") or DEFAULT_MODEL
        self.history = []

    def select_tool(self, user_prompt: str) -> dict:
        """Choose whether to respond with Bash or Python code.

        Args:
            user_prompt: The user's request.

        Returns:
            The assistant's reply describing the tool and code snippet.
        """
        # Build a plain-text prompt for non-chat model
        system = 'You are an assistant that receives a single natural-language prompt. Decide whether to use a shell command or Python snippet to fulfill it. Respond with a JSON object: {"tool":"bash"|"python", "code":"..."}. Do not include any additional text.'

        # Try OpenAI-compatible chat endpoint
        url = f"{self.endpoint}/v1/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
        }
        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        # Extract assistant content
        choices = data.get("choices", [])
        if not choices:
            raise ValueError(f"No choices in response: {resp.text}")
        content = choices[0].get("message", {}).get("content", "")
        try:
            result = json.loads(content)
            return result
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON from model: {content}")


def main():
    # Authenticate and launch the interactive CLI
    from bluevibes_cli import main_menu

    bsky = BlueSkyAPI()
    try:
        bsky.authenticate_bsky()
        print(f"[green]Authenticated as {bsky.current_user_handle}[/green]")
    except Exception as e:
        print(f"[yellow]Warning: Could not authenticate: {e}[/yellow]")
    try:
        main_menu(bsky)
    except KeyboardInterrupt:
        print("\n[cyan]Goodbye![/cyan]")


if __name__ == "__main__":
    main()
