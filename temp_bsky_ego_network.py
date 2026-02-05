#!/usr/bin/env python3
"""
Build an ego network for a single Bluesky account using the public AppView API.

- Resolve your handle -> DID
- Fetch all your followers
- Optionally fetch all accounts you follow
- For each ego node, fetch who they follow and keep edges inside ego set
- Export nodes and edges as CSV for use in Gephi / NetworkX / etc.

Requires: pip install requests
"""

import csv
import sys
import time
from typing import Dict, List, Set, Optional

import requests

APPVIEW_BASE = "https://public.api.bsky.app/xrpc"

# ------------- CONFIG -------------
YOUR_HANDLE = "lukesteuber.com"  # <-- set this
INCLUDE_YOUR_FOLLOWS = True             # also include accounts you follow
REQUEST_DELAY = 0.2                     # seconds between requests, be polite
MAX_PER_PAGE = 100                      # API max is typically 100
# ----------------------------------


def api_get(endpoint: str, params: Dict) -> dict:
    """Simple wrapper for GET requests to the AppView XRPC API."""
    url = f"{APPVIEW_BASE}/{endpoint}"
    while True:
        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except requests.HTTPError as e:
            print(f"[HTTP error] {e} on {endpoint} {params}", file=sys.stderr)
            # crude backoff
            time.sleep(2)
        except requests.RequestException as e:
            print(f"[Network error] {e} on {endpoint} {params}", file=sys.stderr)
            time.sleep(2)


def get_profile(handle_or_did: str) -> Optional[dict]:
    """Resolve a handle to a profile (or fetch by DID)."""
    data = api_get("app.bsky.actor.getProfile", {"actor": handle_or_did})
    # If we get here, we probably have a valid profile
    if "did" not in data:
        print(f"[WARN] No DID in profile for {handle_or_did}: {data}", file=sys.stderr)
        return None
    return data


def paginate_graph(endpoint: str, actor_did: str) -> List[dict]:
    """
    Generic paginator for graph endpoints:
    - app.bsky.graph.getFollowers
    - app.bsky.graph.getFollows

    Returns a flat list of 'followers' or 'follows' entries.
    """
    results: List[dict] = []
    cursor = None
    while True:
        params = {
            "actor": actor_did,
            "limit": MAX_PER_PAGE,
        }
        if cursor:
            params["cursor"] = cursor

        data = api_get(endpoint, params)

        # endpoint returns "followers" or "follows"
        key = "followers" if "followers" in data else "follows"
        page_items = data.get(key, [])
        results.extend(page_items)

        cursor = data.get("cursor")
        if not cursor:
            break

        time.sleep(REQUEST_DELAY)

    return results


def fetch_followers(did: str) -> List[dict]:
    """Fetch all followers of a DID."""
    print(f"Fetching followers for {did} ...")
    return paginate_graph("app.bsky.graph.getFollowers", did)


def fetch_follows(did: str) -> List[dict]:
    """Fetch all accounts that DID follows."""
    print(f"Fetching follows for {did} ...")
    return paginate_graph("app.bsky.graph.getFollows", did)


def build_ego_network(your_handle: str,
                      include_your_follows: bool = True) -> None:
    # 1) Resolve your handle -> DID
    print(f"Resolving handle {your_handle} ...")
    me_profile = get_profile(your_handle)
    if not me_profile:
        print(f"Could not resolve profile for {your_handle}", file=sys.stderr)
        return

    me_did = me_profile["did"]
    print(f"Your DID: {me_did}")
    print(f"Followers: {me_profile.get('followersCount')}, "
          f"Follows: {me_profile.get('followsCount')}")

    # 2) Fetch your followers
    followers = fetch_followers(me_did)
    print(f"Fetched {len(followers)} followers.")

    # 3) Optionally fetch your follows (people you follow)
    my_follows: List[dict] = []
    if include_your_follows:
        my_follows = fetch_follows(me_did)
        print(f"Fetched {len(my_follows)} accounts you follow.")

    # 4) Build ego DID set and basic node info
    ego_dids: Set[str] = {me_did}
    node_info: Dict[str, dict] = {}

    # Add "me"
    node_info[me_did] = {
        "did": me_did,
        "handle": me_profile.get("handle"),
        "displayName": me_profile.get("displayName"),
        "is_you": True,
        "is_follower": False,
        "is_following": False,
    }

    # Followers
    for f in followers:
        did = f.get("did")
        if not did:
            continue
        ego_dids.add(did)
        if did not in node_info:
            node_info[did] = {
                "did": did,
                "handle": f.get("handle"),
                "displayName": f.get("displayName"),
                "is_you": False,
                "is_follower": True,
                "is_following": False,
            }
        else:
            node_info[did]["is_follower"] = True

    # Accounts you follow
    for f in my_follows:
        did = f.get("did")
        if not did:
            continue
        ego_dids.add(did)
        if did not in node_info:
            node_info[did] = {
                "did": did,
                "handle": f.get("handle"),
                "displayName": f.get("displayName"),
                "is_you": False,
                "is_follower": False,
                "is_following": True,
            }
        else:
            node_info[did]["is_following"] = True

    print(f"Total ego nodes (you + followers + follows): {len(ego_dids)}")

    # 5) For each ego DID, fetch who they follow, keep edges inside ego set
    edges = []
    processed = 0
    total = len(ego_dids)

    for did in ego_dids:
        processed += 1
        print(f"[{processed}/{total}] Fetching follows for ego node {did} ...")
        follows = fetch_follows(did)
        for f in follows:
            target_did = f.get("did")
            if not target_did:
                continue
            if target_did in ego_dids:
                edges.append((did, target_did))

        time.sleep(REQUEST_DELAY)

    print(f"Collected {len(edges)} edges inside ego network.")

    # 6) Export to CSV
    export_nodes_csv("bsky_ego_nodes.csv", node_info)
    export_edges_csv("bsky_ego_edges.csv", edges)

    print("\nDone.")
    print("Nodes written to bsky_ego_nodes.csv")
    print("Edges written to bsky_ego_edges.csv")
    print("You can now open these in Gephi, NetworkX, or convert to JSON for D3.")


def export_nodes_csv(path: str, node_info: Dict[str, dict]) -> None:
    fieldnames = [
        "id",
        "did",
        "handle",
        "displayName",
        "is_you",
        "is_follower",
        "is_following",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for idx, (did, info) in enumerate(node_info.items()):
            row = {
                "id": idx,
                "did": did,
                "handle": info.get("handle"),
                "displayName": info.get("displayName"),
                "is_you": info.get("is_you", False),
                "is_follower": info.get("is_follower", False),
                "is_following": info.get("is_following", False),
            }
            writer.writerow(row)


def export_edges_csv(path: str, edges: List[tuple]) -> None:
    fieldnames = ["source", "target"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for src, tgt in edges:
            writer.writerow({"source": src, "target": tgt})


if __name__ == "__main__":
    if YOUR_HANDLE == "your-handle.bsky.social":
        print("Edit YOUR_HANDLE at the top of this script before running.", file=sys.stderr)
        sys.exit(1)

    build_ego_network(YOUR_HANDLE, INCLUDE_YOUR_FOLLOWS)

