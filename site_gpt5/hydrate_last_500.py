#!/usr/bin/env python3
"""
Hydrate a user's last 500 Bluesky posts with engagement using official APIs.

Steps:
1) Log in (handle + app password)
2) Fetch last up to 500 posts from the user's repo (com.atproto.repo.listRecords)
   - Filters out replies; keeps original posts only
3) For each post, fetch:
   - Likes via app.bsky.feed.getLikes (paginated)
   - Reposts via app.bsky.feed.getRepostedBy (paginated)
   - Quotes via app.bsky.feed.getQuotes (paginated)
   - Replies via app.bsky.feed.getPostThread (depth=1), counting reply nodes
4) Save a JSON file with hydrated counts

Requires: pip install atproto requests
Docs: https://docs.bsky.app/docs/get-started
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

try:
    from atproto import Client
except ImportError:
    print("Missing dependency: pip install atproto requests")
    sys.exit(1)

APPVIEW = "https://public.api.bsky.app/xrpc"


@dataclass
class HydratedPost:
    uri: str
    cid: Optional[str]
    text: Optional[str]
    created_at: Optional[str]
    like_count: int = 0
    repost_count: int = 0
    reply_count: int = 0
    quote_count: int = 0


def get_profile_did(client: Client, handle: str) -> str:
    try:
        prof = client.get_profile(handle)
        return getattr(prof, "did", handle)
    except Exception:
        res = client.resolve_handle(handle)
        return getattr(res, "did", handle)


def list_last_posts(client: Client, did: str, limit: int = 500) -> List[Dict[str, Any]]:
    """List last posts (not replies) from the user's repo via listRecords."""
    posts: List[Dict[str, Any]] = []
    cursor: Optional[str] = None
    per_page = 100

    while len(posts) < limit:
        resp = client.com.atproto.repo.list_records(
            {
                "repo": did,
                "collection": "app.bsky.feed.post",
                "limit": min(per_page, limit - len(posts)),
                "cursor": cursor,
            }
        )
        records = getattr(resp, "records", []) or []
        if not records:
            break
        for rec in records:
            uri = getattr(rec, "uri", None)
            cid = getattr(rec, "cid", None)
            value = getattr(rec, "value", None) or {}
            text = getattr(value, "text", None) if hasattr(value, "text") else value.get("text") if isinstance(value, dict) else None
            created_at = (
                getattr(value, "created_at", None)
                if hasattr(value, "created_at")
                else value.get("createdAt") if isinstance(value, dict) else None
            )
            is_reply = False
            if hasattr(value, "reply"):
                is_reply = bool(getattr(value, "reply") or None)
            elif isinstance(value, dict):
                is_reply = value.get("reply") is not None
            if is_reply:
                continue  # keep only original posts
            if uri:
                posts.append({
                    "uri": uri,
                    "cid": cid,
                    "text": text,
                    "created_at": created_at,
                })
            if len(posts) >= limit:
                break
        cursor = getattr(resp, "cursor", None)
        if not cursor:
            break
    return posts


def _http_get(path: str, params: Dict[str, Any], timeout: float = 3.0) -> Optional[Dict[str, Any]]:
    url = f"{APPVIEW}/{path}"
    try:
        r = requests.get(url, params=params, timeout=timeout)
        if r.ok:
            return r.json()
    except Exception:
        return None
    return None


def _count_paginated(path: str, base_params: Dict[str, Any], items_key: str, max_pages: int = 50) -> int:
    total = 0
    cursor: Optional[str] = None
    pages = 0
    while pages < max_pages:
        params = dict(base_params)
        params["limit"] = 100
        if cursor:
            params["cursor"] = cursor
        data = _http_get(path, params)
        if not data or items_key not in data:
            break
        items = data.get(items_key, []) or []
        total += len(items)
        cursor = data.get("cursor")
        if not cursor:
            break
        pages += 1
    return total


def _count_replies(uri: str, depth: int = 1) -> int:
    data = _http_get("app.bsky.feed.getPostThread", {"uri": uri, "depth": depth, "parentHeight": 0})
    if not data or "thread" not in data:
        return 0

    def walk(node: Dict[str, Any]) -> int:
        cnt = 0
        for r in node.get("replies", []) or []:
            if r.get("post"):
                cnt += 1
            cnt += walk(r)
        return cnt

    return walk(data["thread"])


def hydrate_engagement(posts: List[Dict[str, Any]], per_post_delay: float = 0.2) -> List[HydratedPost]:
    hydrated: List[HydratedPost] = []
    for i, p in enumerate(posts, 1):
        uri = p["uri"]
        hp = HydratedPost(
            uri=uri,
            cid=p.get("cid"),
            text=p.get("text"),
            created_at=p.get("created_at"),
        )
        # Likes
        hp.like_count = _count_paginated("app.bsky.feed.getLikes", {"uri": uri}, "likes")
        # Reposts
        hp.repost_count = _count_paginated("app.bsky.feed.getRepostedBy", {"uri": uri}, "repostedBy")
        # Quotes
        hp.quote_count = _count_paginated("app.bsky.feed.getQuotes", {"uri": uri}, "posts")
        # Replies
        hp.reply_count = _count_replies(uri, depth=1)
        hydrated.append(hp)
        # polite pacing
        time.sleep(per_post_delay)
        print(f"[{i}/{len(posts)}] {uri} -> L={hp.like_count} R={hp.repost_count} Rep={hp.reply_count} Q={hp.quote_count}")
    return hydrated


def main():
    ap = argparse.ArgumentParser(description="Hydrate the last 500 Bluesky posts with engagement")
    ap.add_argument("handle", help="Bluesky handle, e.g., user.bsky.social or @user")
    ap.add_argument("password", help="Bluesky app password")
    ap.add_argument("--limit", type=int, default=50, help="Max posts to fetch (default 50)")
    ap.add_argument("--out", default=None, help="Output JSON path (default: bluesky_posts_{handle}_{ts}.json)")
    ap.add_argument("--delay", type=float, default=0.2, help="Delay between post edge calls (seconds)")
    args = ap.parse_args()

    handle = args.handle.lstrip("@")
    if "." not in handle:
        handle = f"{handle}.bsky.social"

    client = Client()
    print(f"Logging in as {handle}...")
    client.login(handle, args.password)

    # Fetch profile for username/display name and DID
    try:
        prof = client.get_profile(handle)
        display_name = getattr(prof, "display_name", None) or getattr(prof, "displayName", None) or handle
        did = getattr(prof, "did", None) or get_profile_did(client, handle)
    except Exception:
        display_name = handle
        did = get_profile_did(client, handle)
    print(f"Resolved DID: {did}")

    print(f"Fetching last {args.limit} posts (not replies)...")
    posts = list_last_posts(client, did, limit=args.limit)
    print(f"Found {len(posts)} posts")

    print("Hydrating engagement (likes, reposts, quotes, replies)...")
    hydrated = hydrate_engagement(posts, per_post_delay=args.delay)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = args.out or f"bluesky_posts_{handle.replace('.', '_')}_{ts}.json"

    data_out = {
        "handle": handle,
        "did": did,
        "exported_at": datetime.now().isoformat(),
        "count": len(hydrated),
        "posts": [asdict(hp) for hp in hydrated],
    }

    with open(out_path, "w") as f:
        json.dump(data_out, f, indent=2)
    print(f"Saved hydrated data to {out_path}")

    # Summary display
    total_posts = len(hydrated)
    total_likes = sum(h.like_count for h in hydrated)
    total_replies = sum(h.reply_count for h in hydrated)
    total_reposts = sum(h.repost_count for h in hydrated)

    print("\nSummary")
    print(f"- Username: {display_name}")
    print(f"- Handle:   {handle}")
    print(f"- Posts:    {total_posts}")
    print(f"- Likes:    {total_likes}")
    print(f"- Comments: {total_replies}")
    print(f"- Reposts:  {total_reposts}")


if __name__ == "__main__":
    main()
