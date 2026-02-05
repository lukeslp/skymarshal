#!/usr/bin/env python3
"""
bluesky_post_import_cli.py
------------------------------------------------------------
Interactive CLI for BlueSky authentication, post fetching, and database import.

Features:
- Prompts for BlueSky username and password (password masked)
- Authenticates with BlueSky API
- Fetches the last 50 posts for the authenticated user
- Stores posts in the database with deduplication (using URI)
- Displays each post with confirmation if it was newly saved or already present
- Efficient: minimizes API and DB calls, uses upsert logic

Usage:
    python bluesky_post_import_cli.py

Accessibility:
- Clear prompts and output
- Keyboard-only operation
- Error messages are explicit

------------------------------------------------------------
"""
import sys
import getpass
import textwrap
from datetime import datetime

from bluevibes.db import init_db, get_session, Post, User
from bluevibes.api.bsky_api import BlueSkyAPI
from bluevibes.storage import storage_manager

# Initialize the database
init_db()

def prompt_credentials():
    print("\n=== BlueSky Authentication ===")
    username = input("BlueSky username (handle or email): ").strip()
    password = getpass.getpass("BlueSky password: ")
    return username, password

def print_post_summary(posts, status_map):
    print("\n=== Post Import Results ===\n")
    for post in posts:
        created_at = post.get("created_at") or "?"
        text = post.get("text", "").replace("\n", " ").strip()
        snippet = textwrap.shorten(text, width=60, placeholder="...")
        uri = post.get("uri", "")
        status = status_map.get(uri, "?")
        print(f"[{created_at}] {snippet}\n    Status: {status}\n")

def main():
    print("\nBlueSky Post Import CLI\n------------------------")
    try:
        username, password = prompt_credentials()
        api = BlueSkyAPI()
        auth_result = api.authenticate_bsky(username, password)
        if not auth_result.get("success"):
            print(f"ERROR: Authentication failed: {auth_result.get('error')}")
            sys.exit(1)
        handle = auth_result.get("handle")
        print(f"\nAuthenticated as: @{handle}")
        # Fetch last 50 posts
        print("Fetching last 50 posts from BlueSky...")
        posts_data = api.get_bsky_posts(handle, limit=50)
        posts = api.process_posts_for_display(posts_data)
        if not posts:
            print("No posts found for this user.")
            sys.exit(0)
        # Get existing post URIs from DB for this user
        session = get_session()
        user = session.query(User).filter(User.handle == handle).first()
        existing_uris = set()
        if user:
            db_posts = session.query(Post).filter(Post.user_id == user.id).all()
            existing_uris = {p.uri for p in db_posts}
        session.close()
        # Store posts (deduplication handled by storage_manager)
        num_stored = storage_manager.store_posts(handle, posts)
        # After storing, get all post URIs again
        session = get_session()
        user = session.query(User).filter(User.handle == handle).first()
        db_posts = session.query(Post).filter(Post.user_id == user.id).all() if user else []
        db_uris = {p.uri for p in db_posts}
        session.close()
        # Build status map for display
        status_map = {}
        for post in posts:
            uri = post.get("uri", "")
            if not uri:
                status_map[uri] = "Invalid URI"
            elif uri in existing_uris:
                status_map[uri] = "Already in DB"
            elif uri in db_uris:
                status_map[uri] = "Saved"
            else:
                status_map[uri] = "Unknown (not saved)"
        print_post_summary(posts, status_map)
        print(f"\nSummary: {len(posts)} posts processed. {num_stored} posts saved or updated in the database.")
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 