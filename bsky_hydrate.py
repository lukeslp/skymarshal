#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bluesky: fetch last 500 posts and hydrate with likes, reposts, quotes, and replies.

Outputs:
  - posts_500.jsonl           # one JSON per line with your last 500 posts (or fewer)
  - post_engagements.jsonl    # one JSON per line with engagement details per post
  - post_summary.csv          # quick summary table with counts per post

Requirements:
  pip install atproto pandas

Usage:
  python bsky_hydrate.py

Environment variables (optional):
  export BSKY_HANDLE="your-handle.bsky.social"   # or you@yourdomain.tld
  export BSKY_APP_PASSWORD="xxxx-xxxx-xxxx-xxxx" # Settings → App passwords
"""

import os
import sys
import time
import json
import math
from typing import Dict, List, Any, Optional, Tuple
from getpass import getpass

import pandas as pd
from atproto import Client, models

# ---------------------------
# Config
# ---------------------------
MAX_POSTS = 500
PAGE_LIMIT = 100  # max allowed by API for feed/likes/reposts/quotes
SLEEP_BETWEEN_REQUESTS = 0.2  # be polite; adjust if you hit rate limits

OUT_POSTS = "posts_500.jsonl"
OUT_ENG = "post_engagements.jsonl"
OUT_SUMMARY = "post_summary.csv"


def getenv_or_prompt(key: str, prompt_text: str, secret: bool = False) -> str:
    """Get value from environment variable or prompt user."""
    val = os.getenv(key)
    if val:
        return val
    return getpass(prompt_text) if secret else input(prompt_text)


def login_client() -> Tuple[Client, str]:
    """Authenticate with Bluesky and return client and actor DID."""
    handle = getenv_or_prompt("BSKY_HANDLE", "Bluesky handle (e.g., you.bsky.social): ")
    app_pw = getenv_or_prompt("BSKY_APP_PASSWORD", "App password (xxxx-xxxx-xxxx-xxxx): ", secret=True)
    client = Client()
    client.login(handle, app_pw)
    me = client.me
    actor_did = me.did if hasattr(me, "did") else me["did"]  # defensive
    return client, actor_did


def paginate(call_fn, base_params, *, limit=PAGE_LIMIT):
    """
    Generic paginator. Yields each page's JSON-like response.
    Handles both old and new SDK parameter formats.
    """
    cursor = None
    while True:
        time.sleep(SLEEP_BETWEEN_REQUESTS)
        
        # Create a copy of base params for this iteration
        params = base_params.copy()
        params['limit'] = limit
        if cursor:
            params['cursor'] = cursor
        
        # Try different parameter passing methods for SDK compatibility
        try:
            # Method 1: params object (newer SDK)
            resp = call_fn(params)
        except TypeError:
            try:
                # Method 2: keyword arguments (older SDK)
                resp = call_fn(**params)
            except TypeError:
                # Method 3: positional arguments for some methods
                if 'actor' in params:
                    resp = call_fn(params['actor'], limit=params.get('limit'), cursor=params.get('cursor'))
                elif 'uri' in params:
                    resp = call_fn(params['uri'], limit=params.get('limit'), cursor=params.get('cursor'))
                else:
                    raise
        
        yield resp
        cursor = getattr(resp, "cursor", None) or (resp.get("cursor") if isinstance(resp, dict) else None)
        if not cursor:
            break


def fetch_last_n_posts(client: Client, actor: str, n: int = MAX_POSTS) -> List[Dict[str, Any]]:
    """Get up to n most recent posts by actor using app.bsky.feed.getAuthorFeed."""
    posts = []
    params = {'actor': actor}
    
    for page in paginate(client.app.bsky.feed.get_author_feed, params, limit=PAGE_LIMIT):
        feed_items = getattr(page, "feed", None) or []
        for item in feed_items:
            post = getattr(item, "post", None)
            if not post:
                continue
            posts.append(_post_to_dict(post))
            if len(posts) >= n:
                return posts
    return posts


def _post_to_dict(post_obj) -> Dict[str, Any]:
    """Convert atproto post response to a plain dict with useful fields."""
    # post_obj has fields: uri, cid, author, record, indexedAt, likeCount, repostCount, replyCount, quoteCount, etc.
    d = {
        "uri": getattr(post_obj, "uri", None),
        "cid": getattr(post_obj, "cid", None),
        "indexedAt": getattr(post_obj, "indexed_at", None) or getattr(post_obj, "indexedAt", None),
        "author_did": getattr(getattr(post_obj, "author", None), "did", None),
        "author_handle": getattr(getattr(post_obj, "author", None), "handle", None),
        "likeCount": getattr(post_obj, "like_count", None) or getattr(post_obj, "likeCount", None),
        "repostCount": getattr(post_obj, "repost_count", None) or getattr(post_obj, "repostCount", None),
        "replyCount": getattr(post_obj, "reply_count", None) or getattr(post_obj, "replyCount", None),
        "quoteCount": getattr(post_obj, "quote_count", None) or getattr(post_obj, "quoteCount", None),
        "record": None,
        "text": None,
        "langs": None,
        "tags": None,
    }
    record = getattr(post_obj, "record", None)
    if isinstance(record, dict):
        d["record"] = record
        d["text"] = record.get("text")
        d["langs"] = record.get("langs")
        d["tags"] = record.get("tags")
    else:
        d["record"] = getattr(record, "__dict__", None)
        d["text"] = getattr(record, "text", None)
        d["langs"] = getattr(record, "langs", None)
        d["tags"] = getattr(record, "tags", None)
    return d


def save_jsonl(path: str, rows: List[Dict[str, Any]]):
    """Save list of dictionaries as JSONL file."""
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def fetch_likes(client: Client, uri: str, max_pages: Optional[int] = None) -> List[Dict[str, Any]]:
    """Fetch likes for a post using app.bsky.feed.getLikes"""
    likes = []
    pages = 0
    params = {'uri': uri}
    
    for page in paginate(client.app.bsky.feed.get_likes, params, limit=PAGE_LIMIT):
        pages += 1
        for it in getattr(page, "likes", []) or []:
            likes.append({
                "uri": uri,
                "actor_did": getattr(getattr(it, "actor", None), "did", None),
                "actor_handle": getattr(getattr(it, "actor", None), "handle", None),
                "createdAt": getattr(it, "created_at", None) or getattr(it, "createdAt", None),
            })
        if max_pages and pages >= max_pages:
            break
    return likes


def fetch_reposts(client: Client, uri: str, max_pages: Optional[int] = None) -> List[Dict[str, Any]]:
    """Fetch reposts for a post using app.bsky.feed.getRepostedBy"""
    users = []
    pages = 0
    params = {'uri': uri}
    
    for page in paginate(client.app.bsky.feed.get_reposted_by, params, limit=PAGE_LIMIT):
        pages += 1
        for it in getattr(page, "reposted_by", []) or []:
            users.append({
                "uri": uri,
                "actor_did": getattr(it, "did", None),
                "actor_handle": getattr(it, "handle", None),
            })
        if max_pages and pages >= max_pages:
            break
    return users


def fetch_quotes(client: Client, uri: str, max_pages: Optional[int] = None) -> List[Dict[str, Any]]:
    """Fetch quote posts using app.bsky.feed.getQuotes"""
    quotes = []
    pages = 0
    params = {'uri': uri}
    
    for page in paginate(client.app.bsky.feed.get_quotes, params, limit=PAGE_LIMIT):
        pages += 1
        for it in getattr(page, "quotes", []) or []:
            post = getattr(it, "post", None)
            if not post:
                continue
            quotes.append({
                "target_uri": uri,
                "quote_uri": getattr(post, "uri", None),
                "quote_cid": getattr(post, "cid", None),
                "author_did": getattr(getattr(post, "author", None), "did", None),
                "author_handle": getattr(getattr(post, "author", None), "handle", None),
                "indexedAt": getattr(post, "indexed_at", None) or getattr(post, "indexedAt", None),
                "text": getattr(getattr(post, "record", None), "text", None)
            })
        if max_pages and pages >= max_pages:
            break
    return quotes


def fetch_replies(client: Client, uri: str, depth: int = 6) -> List[Dict[str, Any]]:
    """
    Fetch replies using app.bsky.feed.getPostThread, then walk descendants to collect replies.
    Depth 6 is the API default max commonly supported.
    """
    replies = []
    time.sleep(SLEEP_BETWEEN_REQUESTS)
    
    # Try different parameter passing methods for SDK compatibility
    try:
        # Method 1: params object
        params = {'uri': uri, 'depth': depth}
        thread_resp = client.app.bsky.feed.get_post_thread(params)
    except TypeError:
        try:
            # Method 2: keyword arguments
            thread_resp = client.app.bsky.feed.get_post_thread(uri=uri, depth=depth)
        except TypeError:
            # Method 3: positional arguments
            thread_resp = client.app.bsky.feed.get_post_thread(uri, depth=depth)
    
    node = getattr(thread_resp, "thread", None)
    if not node:
        return replies

    def walk(n):
        # n can be a PostView or ThreadViewPost wrapper, depending on SDK
        post = getattr(n, "post", None) or n
        post_uri = getattr(post, "uri", None)
        if post_uri and post_uri != uri:
            replies.append({
                "parent_uri": uri,
                "reply_uri": post_uri,
                "reply_cid": getattr(post, "cid", None),
                "author_did": getattr(getattr(post, "author", None), "did", None),
                "author_handle": getattr(getattr(post, "author", None), "handle", None),
                "indexedAt": getattr(post, "indexed_at", None) or getattr(post, "indexedAt", None),
                "text": getattr(getattr(post, "record", None), "text", None),
            })
        # descend into children
        children = getattr(n, "replies", None)
        if isinstance(children, list):
            for c in children:
                walk(c)

    walk(node)
    return replies


def main():
    """Main execution function."""
    client, my_did = login_client()

    # Resolve the actor you want to fetch. For your own feed, use your own DID/handle.
    # We'll fetch by handle to be friendly with federation.
    my_profile = client.get_profile(my_did)
    actor_identifier = getattr(my_profile, "handle", None) or my_did

    print(f"Fetching up to {MAX_POSTS} posts for {actor_identifier}...")
    posts = fetch_last_n_posts(client, actor_identifier, MAX_POSTS)
    if not posts:
        print("No posts found, exiting.")
        sys.exit(0)

    save_jsonl(OUT_POSTS, posts)
    print(f"Wrote {len(posts)} posts to {OUT_POSTS}")

    # Engagement hydration
    eng_rows = []
    for i, p in enumerate(posts, 1):
        uri = p["uri"]
        if not uri:
            continue
        print(f"[{i}/{len(posts)}] Hydrating {uri}")

        likes = fetch_likes(client, uri)
        reposts = fetch_reposts(client, uri)
        quotes = fetch_quotes(client, uri)
        replies = fetch_replies(client, uri)

        eng_rows.append({
            "uri": uri,
            "cid": p["cid"],
            "indexedAt": p["indexedAt"],
            "likeCount": len(likes),
            "repostCount": len(reposts),
            "quoteCount": len(quotes),
            "replyCount": len(replies),
            "likes": likes,
            "reposts": reposts,
            "quotes": quotes,
            "replies": replies,
        })

    save_jsonl(OUT_ENG, eng_rows)
    print(f"Wrote engagement details for {len(eng_rows)} posts to {OUT_ENG}")

    # Quick summary CSV
    df = pd.DataFrame([{
        "uri": r["uri"],
        "cid": r["cid"],
        "indexedAt": r["indexedAt"],
        "likes": r["likeCount"],
        "reposts": r["repostCount"],
        "quotes": r["quoteCount"],
        "replies": r["replyCount"],
        "total_engagements": (r["likeCount"] + r["repostCount"] + r["quoteCount"] + r["replyCount"]),
    } for r in eng_rows])
    df.sort_values(["total_engagements", "likes"], ascending=[False, False], inplace=True)
    df.to_csv(OUT_SUMMARY, index=False)
    print(f"Wrote summary to {OUT_SUMMARY}")

    print("Done.")


if __name__ == "__main__":
    main()
