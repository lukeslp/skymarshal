"""Network fetcher service — orchestrates data collection for a handle.

Ported from blueballs/backend/app/services/network_fetcher.py.
Sync implementation using threading for concurrent fetches (eventlet-compatible).
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from skymarshal.network.analysis import (
    GraphAnalytics,
    compute_grid_positions,
    compute_orbit_strength_ratio,
)
from skymarshal.network.client import BlueskyClient

logger = logging.getLogger(__name__)


class NetworkFetcher:
    """Fetch and assemble network data for a Bluesky handle.

    All operations are synchronous (eventlet-compatible).
    Progress is reported via a callback: (operation, current, total) -> None.
    """

    def __init__(
        self,
        client: BlueskyClient,
        *,
        analytics: GraphAnalytics | None = None,
        max_workers: int = 8,
    ) -> None:
        self._client = client
        self._analytics = analytics
        self._max_workers = max_workers

    def fetch_network(
        self,
        *,
        handle: str,
        include_followers: bool = True,
        include_following: bool = True,
        max_followers: Optional[int] = 500,
        max_following: Optional[int] = 500,
        mode: str = "balanced",
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> Dict[str, Any]:
        """Return network data for the specified handle.

        Args:
            handle: Bluesky handle (e.g. user.bsky.social)
            include_followers: Fetch followers
            include_following: Fetch following
            max_followers: Maximum followers to fetch
            max_following: Maximum following to fetch
            mode: "fast" (no interconnections), "balanced" (top 150), "detailed" (all)
            progress_callback: (operation, current, total) -> None

        Returns:
            Dict with "nodes", "edges", "metadata" keys.
        """
        if not include_followers and not include_following:
            raise ValueError("At least one of include_followers or include_following must be True")

        def report(operation: str, current: int, total: int) -> None:
            if progress_callback:
                progress_callback(operation, current, total)

        # Stage 1: Fetch target profile
        report("Fetching target profile", 0, 1)
        target_profile = self._client.get_profile(handle)
        if target_profile is None:
            raise ValueError(f"Handle '{handle}' not found on Bluesky")
        report("Fetching target profile", 1, 1)

        nodes: Dict[str, Dict[str, Any]] = {
            handle: _create_node(target_profile, is_target=True)
        }
        edges: List[Dict[str, Any]] = []

        # Stage 2: Fetch followers/following (parallel)
        report("Fetching followers and following", 0, 1)
        follows_data, followers_data = self._gather_primary_relations(
            handle=handle,
            include_followers=include_followers,
            include_following=include_following,
            max_followers=max_followers,
            max_following=max_following,
        )
        total_primary = len(follows_data) + len(followers_data)
        report("Fetching followers and following", total_primary, total_primary)

        network_handles: Set[str] = set()

        if include_following:
            for entry in follows_data:
                follow_handle = entry.get("handle")
                if follow_handle:
                    network_handles.add(follow_handle)
                    edges.append({"source": handle, "target": follow_handle, "type": "follows"})

        if include_followers:
            for entry in followers_data:
                follower_handle = entry.get("handle")
                if follower_handle:
                    network_handles.add(follower_handle)
                    edges.append({"source": follower_handle, "target": handle, "type": "follows"})

        # Stage 3: Hydrate profiles (batch)
        report("Hydrating profiles", 0, len(network_handles))
        self._hydrate_profiles(nodes, network_handles)
        report("Hydrating profiles", len(network_handles), len(network_handles))

        # Stage 4: Detect mutuals
        report("Analyzing mutual connections", 0, 1)
        _detect_mutuals(nodes, edges, target_handle=handle)
        report("Analyzing mutual connections", 1, 1)

        # Stage 5: Orbit interconnections (the slow part)
        if mode != "fast":
            self._augment_interconnections(
                nodes, network_handles, edges, mode=mode, progress_callback=report
            )

        # Classify orbit tiers
        _classify_orbit_tiers(nodes)

        # Compute grid positions
        result_nodes = list(nodes.values())
        compute_grid_positions(result_nodes)

        # Build metadata
        orbit_edges = [e for e in edges if e.get("type") == "orbit_connection"]
        follow_edges = [e for e in edges if e.get("type") == "follows"]

        metadata: Dict[str, Any] = {
            "target_handle": handle,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "orbit_edge_count": len(orbit_edges),
            "follow_edge_count": len(follow_edges),
            "orbit_strength_distribution": compute_orbit_strength_ratio(result_nodes),
        }

        # Top interconnected
        top_interconnected = sorted(
            (node for node in nodes.values() if not node.get("is_target")),
            key=lambda item: (
                item.get("orbit_connections", 0),
                item.get("mutual_connections", 0),
            ),
            reverse=True,
        )[:20]
        metadata["top_interconnected"] = [
            {
                "handle": entry.get("handle"),
                "name": entry.get("name"),
                "mutual_connections": entry.get("mutual_connections", 0),
                "orbit_connections": entry.get("orbit_connections", 0),
            }
            for entry in top_interconnected
        ]

        # Graph analytics (optional, expensive)
        if self._analytics is not None:
            analytics_result = self._analytics.analyse(result_nodes, edges)
            for node in result_nodes:
                node_id = node.get("id")
                if node_id and node_id in analytics_result.node_metrics:
                    node.update(analytics_result.node_metrics[node_id])

            for edge in edges:
                source = str(edge.get("source"))
                target = str(edge.get("target"))
                weight = analytics_result.edge_weights.get(
                    (source, target)
                ) or analytics_result.edge_weights.get((target, source))
                if weight is not None:
                    edge["weight"] = weight

            metadata["clusters"] = analytics_result.clusters
            metadata["graph_metrics"] = analytics_result.graph_metrics

        return {"nodes": result_nodes, "edges": edges, "metadata": metadata}

    def _gather_primary_relations(
        self,
        *,
        handle: str,
        include_followers: bool,
        include_following: bool,
        max_followers: Optional[int],
        max_following: Optional[int],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Fetch followers and following in parallel."""
        follows_data: List[Dict[str, Any]] = []
        followers_data: List[Dict[str, Any]] = []

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = {}
            if include_following:
                futures["following"] = pool.submit(
                    self._client.get_follows, handle, max_following
                )
            if include_followers:
                futures["followers"] = pool.submit(
                    self._client.get_followers, handle, max_followers
                )

            for key, future in futures.items():
                try:
                    result = future.result(timeout=120)
                    if key == "following":
                        follows_data = result
                        logger.info("Fetched %d following for %s", len(result), handle)
                    else:
                        followers_data = result
                        logger.info("Fetched %d followers for %s", len(result), handle)
                except Exception as exc:
                    logger.error("Error fetching %s for %s: %s", key, handle, exc)

        return follows_data, followers_data

    def _hydrate_profiles(
        self,
        nodes: Dict[str, Dict[str, Any]],
        network_handles: Set[str],
    ) -> None:
        """Batch-fetch profiles for all handles in the network."""
        handles = list(network_handles)
        if not handles:
            return

        batch_size = 25
        batches = [handles[i: i + batch_size] for i in range(0, len(handles), batch_size)]

        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            futures = [
                pool.submit(self._client.get_profiles_batch, batch)
                for batch in batches
            ]
            completed = 0
            for future in as_completed(futures):
                try:
                    profiles = future.result(timeout=60)
                    for profile in profiles:
                        h = profile.get("handle")
                        if h:
                            nodes[h] = _create_node(profile)
                            completed += 1
                except Exception as exc:
                    logger.warning("Profile hydration batch failed: %s", exc)

        logger.info("Hydrated %d profiles", completed)

    def _augment_interconnections(
        self,
        nodes: Dict[str, Dict[str, Any]],
        network_handles: Set[str],
        edges: List[Dict[str, Any]],
        *,
        mode: str,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> None:
        """Fetch orbit interconnections — how people in the network connect to each other."""
        handle_list = sorted(
            network_handles,
            key=lambda h: (
                nodes.get(h, {}).get("mutual_connections", 0),
                nodes.get(h, {}).get("followers_count", 0),
            ),
            reverse=True,
        )

        if mode == "balanced":
            handle_list = handle_list[:150]

        total = len(handle_list)
        if progress_callback:
            progress_callback("Computing orbit interconnections", 0, total)

        lock = threading.Lock()
        progress_counter = [0]

        def fetch_orbit(source_handle: str) -> None:
            try:
                follows = self._client.get_follows(source_handle, limit=200)
                batch_edges = []
                orbit_connections = 0

                for follow in follows:
                    target_handle = follow.get("handle")
                    if target_handle and target_handle in nodes and target_handle != source_handle:
                        batch_edges.append({
                            "source": source_handle,
                            "target": target_handle,
                            "type": "orbit_connection",
                        })
                        orbit_connections += 1

                with lock:
                    if batch_edges:
                        edges.extend(batch_edges)
                    if source_handle in nodes:
                        nodes[source_handle]["orbit_connections"] = orbit_connections
                    progress_counter[0] += 1

                    if progress_counter[0] % 10 == 0 and progress_callback:
                        progress_callback(
                            "Computing orbit interconnections",
                            progress_counter[0],
                            total,
                        )

            except Exception as exc:
                logger.warning("Orbit fetch failed for %s: %s", source_handle, exc)
                with lock:
                    progress_counter[0] += 1

        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            futures = [pool.submit(fetch_orbit, h) for h in handle_list]
            for future in as_completed(futures):
                future.result()  # Propagate exceptions for logging

        orbit_count = sum(1 for e in edges if e.get("type") == "orbit_connection")
        logger.info(
            "Computed orbit connections for %d/%d handles (%d orbit edges)",
            progress_counter[0],
            total,
            orbit_count,
        )

        if progress_callback:
            progress_callback("Computing orbit interconnections", total, total)


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def _create_node(profile: Dict[str, Any], is_target: bool = False) -> Dict[str, Any]:
    """Create a simplified node from a profile."""
    return {
        "id": profile.get("handle"),
        "handle": profile.get("handle"),
        "name": profile.get("displayName") or profile.get("handle") or "Unknown",
        "avatar": profile.get("avatar"),
        "followers_count": int(profile.get("followersCount", 0)),
        "follows_count": int(profile.get("followsCount", 0)),
        "is_target": is_target,
        "relationship": "target" if is_target else "indirect",
        "orbit_connections": 0,
        "mutual_connections": 0,
        "x": 0.0,
        "y": 0.0,
        "tier": 2,
    }


def _detect_mutuals(
    nodes: Dict[str, Dict[str, Any]],
    edges: List[Dict[str, Any]],
    *,
    target_handle: str,
) -> None:
    """Mark mutual follows and relationship types."""
    following: Dict[str, Set[str]] = defaultdict(set)
    for edge in edges:
        following[edge["source"]].add(edge["target"])

    mutual_count: Dict[str, int] = defaultdict(int)
    following_target = {
        src for src, targets in following.items() if target_handle in targets
    }

    for source, targets in following.items():
        for target in targets:
            if source in following.get(target, set()):
                mutual_count[source] += 1
                mutual_count[target] += 1

    followers_of_target = following.get(target_handle, set())

    for handle, node in nodes.items():
        node["mutual_connections"] = mutual_count.get(handle, 0) // 2
        node["you_follow"] = handle in followers_of_target
        node["follows_you"] = handle in following_target

        if node.get("is_target"):
            node["relationship"] = "target"
        elif node["you_follow"] and node["follows_you"]:
            node["relationship"] = "mutual"
        elif node["you_follow"]:
            node["relationship"] = "following"
        elif node["follows_you"]:
            node["relationship"] = "follower"
        else:
            node["relationship"] = "indirect"


def _classify_orbit_tiers(nodes: Dict[str, Dict[str, Any]]) -> None:
    """Classify nodes into orbit strength tiers.

    Tier 0 (strong): >20 connections within orbit
    Tier 1 (medium): 5-20 connections
    Tier 2 (weak): <5 connections
    """
    for node in nodes.values():
        if node.get("is_target"):
            node["tier"] = 0
            continue
        orbit = node.get("orbit_connections", 0)
        if orbit > 20:
            node["tier"] = 0
        elif orbit >= 5:
            node["tier"] = 1
        else:
            node["tier"] = 2
