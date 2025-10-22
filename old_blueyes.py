"""Interactive CLI for BlueFlyer.

Uses [rich](https://rich.readthedocs.io/en/stable/prompt.html) for a simple
menu driven interface.
"""
from __future__ import annotations

import getpass
from typing import Optional

from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from rich.progress import Progress

from bluesky_client import BlueskyClient

console = Console()


def login(client: BlueskyClient) -> bool:
    """Prompt for credentials and login."""
    identifier = Prompt.ask("Bluesky handle", default="")
    password = getpass.getpass("App password: ")
    return client.login(identifier, password)


def show_profile(client: BlueskyClient, handle: str) -> None:
    """Display profile info in a table."""
    profile = client.get_profile_summary(handle)
    prof = profile.get("profile", {})
    table = Table(title=f"Profile: {prof.get('displayName', handle)}")
    table.add_column("Field")
    table.add_column("Value")
    for key in ["handle", "followersCount", "followsCount", "postsCount"]:
        table.add_row(key, str(prof.get(key, "")))
    console.print(table)


def follower_analysis(client: BlueskyClient, handle: str, count: int = 20) -> None:
    """Run follower ranking with live progress."""
    with Progress() as progress:
        task = progress.add_task("Processing", total=100)
        result = client.get_top_followers(handle, count=count)
        while result["progress"]["status"] not in {"complete", "failed"}:
            progress.update(task, completed=result["progress"].get("percentage_complete", 0))
            result = client.progress_data
        progress.update(task, completed=100)
    top = result.get("top", [])
    table = Table(title="Top Followers")
    table.add_column("Handle")
    table.add_column("Followers")
    for fol in top:
        table.add_row(fol.get("handle", ""), str(fol.get("followersCount", 0)))
    console.print(table)


def sentiment(client: BlueskyClient, handle: str, posts: int = 20) -> None:
    """Analyze recent posts sentiment."""
    with Progress() as progress:
        task = progress.add_task("Analyzing", total=100)
        result = client.analyze_recent_posts_sentiment(handle, limit=posts)
        while result["progress"]["status"] not in {"complete", "failed"}:
            progress.update(task, completed=result["progress"].get("percentage_complete", 0))
            result = client.sentiment_progress
        progress.update(task, completed=100)
    summary = result.get("summary", {})
    console.print(f"Average sentiment: {summary.get('average_sentiment',0):.2f}")


def main() -> None:
    client = BlueskyClient()
    while True:
        console.print("[bold cyan]BlueFlyer CLI[/bold cyan]")
        console.print("1. Login")
        console.print("2. Search profiles")
        console.print("3. View profile")
        console.print("4. Follower analysis")
        console.print("5. Sentiment analysis")
        console.print("0. Exit")
        choice = Prompt.ask("Select an option", choices=["0", "1", "2", "3", "4", "5"], default="0")
        if choice == "0":
            break
        if choice == "1":
            if login(client):
                console.print("[green]Logged in successfully[/green]")
            else:
                console.print("[red]Login failed[/red]")
        elif choice == "2":
            query = Prompt.ask("Search query")
            results = client.search_profiles(query)
            table = Table(title="Results")
            table.add_column("Handle")
            table.add_column("Name")
            for actor in results.get("actors", []):
                table.add_row(actor.get("handle", ""), actor.get("displayName", ""))
            console.print(table)
        elif choice == "3":
            handle = Prompt.ask("Handle")
            show_profile(client, handle)
        elif choice == "4":
            handle = Prompt.ask("Handle")
            follower_analysis(client, handle)
        elif choice == "5":
            handle = Prompt.ask("Handle")
            sentiment(client, handle)


if __name__ == "__main__":
    main()
