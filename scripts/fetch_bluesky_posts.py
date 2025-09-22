#!/usr/bin/env python3
"""Download and hydrate the latest Bluesky posts for an authenticated user.

Steps performed:
1. Prompt for a handle and app password, then create a logged-in `atproto.Client`.
2. Page through the user's author feed until up to the requested number of posts are collected.
3. Hydrate each post by collecting likes, reposts, quote posts, and replies using the AppView endpoints.

The script is intentionally self-contained so it can be used as a starting point for
ad-hoc data pulls or further automation. See https://docs.bsky.app/docs/get-started
for additional details about the endpoints referenced here.
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from atproto import Client


@dataclass
class ActorSnapshot:
    """Minimal representation of an actor returned by engagement endpoints."""

    did: Optional[str]
    handle: Optional[str]
    display_name: Optional[str]


@dataclass
class PostHydration:
    """Serialized view of a post plus its engagement edges."""

    uri: str
    cid: Optional[str]
    indexed_at: Optional[str]
    text: Optional[str]
    author: ActorSnapshot
    like_count: int
    repost_count: int
    quote_count: int
    reply_count: int
    likes: List[ActorSnapshot] = field(default_factory=list)
    reposts: List[ActorSnapshot] = field(default_factory=list)
    quotes: List[Dict[str, Any]] = field(default_factory=list)
    replies: List[Dict[str, Any]] = field(default_factory=list)


def _actor_from_profile(profile: Any) -> ActorSnapshot:
    """Convert an actor-ish object (with attributes) into an ActorSnapshot."""

    if profile is None:
        return ActorSnapshot(did=None, handle=None, display_name=None)
    return ActorSnapshot(
        did=getattr(profile, "did", None),
        handle=getattr(profile, "handle", None),
        display_name=getattr(profile, "display_name", None),
    )


def _extract_text(record: Any) -> Optional[str]:
    """Best-effort extraction of post text from various record structures."""

    if record is None:
        return None
    if hasattr(record, "text"):
        return getattr(record, "text")
    if isinstance(record, dict):
        text = record.get("text")
        if text:
            return text
    return None


def _post_summary(post_view: Any) -> Dict[str, Any]:
    """Collapse a `PostView` object into a JSON-serializable dictionary."""

    author_snapshot = _actor_from_profile(getattr(post_view, "author", None))
    record = getattr(post_view, "record", None)
    indexed_at = getattr(post_view, "indexed_at", None)

    return {
        "uri": getattr(post_view, "uri", None),
        "cid": getattr(post_view, "cid", None),
        "indexed_at": indexed_at,
        "text": _extract_text(record),
        "author": asdict(author_snapshot),
    }


def fetch_recent_posts(client: Client, actor: str, limit: int) -> List[Any]:
    """Return up to ``limit`` posts for ``actor`` using get_author_feed."""

    posts: List[Any] = []
    cursor: Optional[str] = None

    while len(posts) < limit:
        page_limit = min(100, limit - len(posts))
        kwargs: Dict[str, Any] = {"actor": actor, "limit": page_limit}
        if cursor:
            kwargs["cursor"] = cursor

        response = client.get_author_feed(**kwargs)
        feed_items = getattr(response, "feed", None)
        if not feed_items:
            break

        for item in feed_items:
            post_view = getattr(item, "post", None)
            if post_view is None:
                continue
            posts.append(post_view)
            if len(posts) >= limit:
                break

        cursor = getattr(response, "cursor", None)
        if not cursor:
            break

    return posts


def _paginate_likes(client: Client, uri: str) -> List[ActorSnapshot]:
    likes: List[ActorSnapshot] = []
    cursor: Optional[str] = None

    while True:
        params: Dict[str, Any] = {"uri": uri, "limit": 100}
        if cursor:
            params["cursor"] = cursor

        response = client.get_likes(**params)
        batch = getattr(response, "likes", None)
        if not batch:
            break

        for like in batch:
            likes.append(_actor_from_profile(getattr(like, "actor", None)))

        cursor = getattr(response, "cursor", None)
        if not cursor:
            break

    return likes


def _paginate_reposts(client: Client, uri: str) -> List[ActorSnapshot]:
    reposts: List[ActorSnapshot] = []
    cursor: Optional[str] = None

    while True:
        params: Dict[str, Any] = {"uri": uri, "limit": 100}
        if cursor:
            params["cursor"] = cursor

        response = client.get_reposted_by(**params)
        batch = getattr(response, "reposted_by", None)
        if not batch:
            break

        for repost in batch:
            reposts.append(_actor_from_profile(getattr(repost, "actor", None)))

        cursor = getattr(response, "cursor", None)
        if not cursor:
            break

    return reposts


def _paginate_quotes(client: Client, uri: str) -> List[Dict[str, Any]]:
    quotes: List[Dict[str, Any]] = []
    cursor: Optional[str] = None

    while True:
        params: Dict[str, Any] = {"uri": uri, "limit": 100}
        if cursor:
            params["cursor"] = cursor

        response = client.app.bsky.feed.get_quotes(params)
        batch = getattr(response, "posts", None)
        if not batch:
            break

        for post_view in batch:
            quotes.append(_post_summary(post_view))

        cursor = getattr(response, "cursor", None)
        if not cursor:
            break

    return quotes


def _collect_replies(client: Client, uri: str) -> List[Dict[str, Any]]:
    replies: List[Dict[str, Any]] = []

    try:
        response = client.get_post_thread(uri=uri, depth=2, parent_height=0)
    except Exception as exc:  # pragma: no cover - defensive logging path
        print(f"Failed to get replies for {uri}: {exc}", file=sys.stderr)
        return replies

    thread = getattr(response, "thread", None)
    if thread is None:
        return replies

    def walk(node: Any) -> None:
        children: Optional[Iterable[Any]] = getattr(node, "replies", None)
        if not children:
            return
        for child in children:
            post_view = getattr(child, "post", None)
            if post_view is not None:
                replies.append(_post_summary(post_view))
            walk(child)

    walk(thread)
    return replies


def hydrate_post(client: Client, post_view: Any) -> PostHydration:
    uri = getattr(post_view, "uri", "")
    author_snapshot = _actor_from_profile(getattr(post_view, "author", None))
    record = getattr(post_view, "record", None)
    indexed_at = getattr(post_view, "indexed_at", None)

    likes = _paginate_likes(client, uri)
    reposts = _paginate_reposts(client, uri)
    quotes = _paginate_quotes(client, uri)
    replies = _collect_replies(client, uri)

    return PostHydration(
        uri=uri,
        cid=getattr(post_view, "cid", None),
        indexed_at=indexed_at,
        text=_extract_text(record),
        author=author_snapshot,
        like_count=len(likes),
        repost_count=len(reposts),
        quote_count=len(quotes),
        reply_count=len(replies),
        likes=likes,
        reposts=reposts,
        quotes=quotes,
        replies=replies,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch and hydrate recent Bluesky posts")
    parser.add_argument(
        "--handle",
        help="Bluesky handle to authenticate with (e.g. alice.bsky.social)",
    )
    parser.add_argument(
        "--app-password",
        dest="app_password",
        help="App-specific password. If omitted, the script prompts securely.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of recent posts to fetch (defaults to 10)",
    )
    parser.add_argument(
        "--output",
        help="Optional path to write JSON output. Defaults to stdout.",
    )
    parser.add_argument(
        "--sleep",
        dest="sleep_interval",
        type=float,
        default=0.2,
        help="Pause (seconds) between hydration calls to respect rate limits.",
    )
    return parser.parse_args()


def authenticate(handle: str, password: str) -> Client:
    client = Client()
    client.login(handle, password)
    return client


def main() -> int:
    args = parse_args()

    handle = args.handle or input("Bluesky handle: ").strip()
    if not handle:
        print("A handle is required.", file=sys.stderr)
        return 1

    password = args.app_password or getpass.getpass("App password: ")
    if not password:
        print("An app password is required.", file=sys.stderr)
        return 1

    try:
        client = authenticate(handle, password)
    except Exception as exc:  # pragma: no cover - interactive script
        print(f"Failed to authenticate: {exc}", file=sys.stderr)
        return 1

    limit = max(1, args.limit)
    print(f"Fetching up to {limit} posts for {handle}...", file=sys.stderr)

    posts = fetch_recent_posts(client, actor=handle, limit=limit)
    if not posts:
        print("No posts found for the requested handle.", file=sys.stderr)
        return 0

    hydrated: List[PostHydration] = []
    for index, post_view in enumerate(posts, start=1):
        print(f"Hydrating post {index}/{len(posts)}: {getattr(post_view, 'uri', 'unknown')}", file=sys.stderr)
        hydrated.append(hydrate_post(client, post_view))
        time.sleep(max(0.0, args.sleep_interval))

    output_payload = [asdict(item) for item in hydrated]

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle_file:
            json.dump(output_payload, handle_file, indent=2)
        print(f"Wrote hydrated data for {len(hydrated)} posts to {args.output}", file=sys.stderr)
    else:
        json.dump(output_payload, sys.stdout, indent=2)
        sys.stdout.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
