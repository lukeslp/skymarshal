"""Graph analytics pipeline built on NetworkX.

Ported from blueballs/backend/app/analytics/graph_analysis.py.
Provides Louvain community detection, PageRank, centrality metrics,
spiral positioning, and Swiss grid layout.
"""

from __future__ import annotations

import importlib.metadata as importlib_metadata
import logging
import math
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

# Harden entry point handling for environments with malformed metadata
try:
    _original_normalize = importlib_metadata.Prepared.normalize  # type: ignore[attr-defined]
except AttributeError:
    _original_normalize = None
else:

    def _safe_normalize(name: object) -> str:
        if not isinstance(name, str):
            name = str(name)
        return _original_normalize(name)  # type: ignore[misc]

    importlib_metadata.Prepared.normalize = staticmethod(_safe_normalize)  # type: ignore[attr-defined]

os.environ.setdefault("NETWORKX_DISABLE_BACKENDS_DISCOVERY", "1")

import networkx as nx
from networkx.algorithms import community
from networkx.algorithms.link_analysis import pagerank_alg

logger = logging.getLogger(__name__)


def _to_python_native(value: Any) -> Any:
    """Convert numpy types to Python native types for JSON serialization."""
    if hasattr(value, "item"):
        return value.item()
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, dict):
        return {k: _to_python_native(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(_to_python_native(item) for item in value)
    return value


DEFAULT_CLUSTER_PALETTE = [
    "#00A8E8",
    "#10B981",
    "#F59E0B",
    "#EC4899",
    "#6366F1",
    "#F97316",
    "#14B8A6",
    "#8B5CF6",
    "#F43F5E",
    "#22D3EE",
]


@dataclass
class GraphAnalyticsResult:
    node_metrics: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    edge_weights: Dict[Tuple[str, str], float] = field(default_factory=dict)
    clusters: List[Dict[str, Any]] = field(default_factory=list)
    graph_metrics: Dict[str, Any] = field(default_factory=dict)


class GraphAnalytics:
    """Compute analytics for a social network graph."""

    def __init__(self, *, cluster_palette: Sequence[str] | None = None) -> None:
        self._palette = list(cluster_palette or DEFAULT_CLUSTER_PALETTE)

    def analyse(
        self,
        nodes: Iterable[Mapping[str, Any]],
        edges: Iterable[Mapping[str, Any]],
    ) -> GraphAnalyticsResult:
        graph = self._build_graph(nodes, edges)
        if graph.number_of_nodes() == 0:
            return GraphAnalyticsResult()

        degree_centrality = nx.degree_centrality(graph)
        betweenness = nx.betweenness_centrality(graph, weight="weight")
        try:
            pagerank = nx.pagerank(graph, weight="weight")
        except ModuleNotFoundError:
            pagerank = pagerank_alg._pagerank_numpy(graph, weight="weight")

        clusters = self._detect_clusters(graph)
        cluster_assignments = self._map_clusters(clusters)

        edge_weights = self._weight_edges(graph)
        spiral_positions = self._compute_spiral_positions(clusters, pagerank)

        node_metrics: Dict[str, Dict[str, Any]] = {}
        for node_id in graph.nodes:
            node_metrics[node_id] = {
                "cluster_id": cluster_assignments.get(node_id),
                "degree_centrality": _to_python_native(
                    degree_centrality.get(node_id, 0.0)
                ),
                "betweenness_centrality": _to_python_native(
                    betweenness.get(node_id, 0.0)
                ),
                "pagerank": _to_python_native(pagerank.get(node_id, 0.0)),
                **{
                    k: _to_python_native(v)
                    for k, v in spiral_positions.get(node_id, {}).items()
                },
            }

        graph_metrics = self._summarise_graph(
            graph, clusters, degree_centrality, pagerank
        )
        cluster_summaries = self._summarise_clusters(clusters, node_metrics)

        return GraphAnalyticsResult(
            node_metrics=node_metrics,
            edge_weights=edge_weights,
            clusters=cluster_summaries,
            graph_metrics=graph_metrics,
        )

    @staticmethod
    def _build_graph(
        nodes: Iterable[Mapping[str, Any]],
        edges: Iterable[Mapping[str, Any]],
    ) -> nx.Graph:
        graph = nx.Graph()
        for node in nodes:
            node_id = str(node.get("id", node.get("handle", "")))
            graph.add_node(node_id, **dict(node))

        for edge in edges:
            source = str(edge["source"])
            target = str(edge["target"])
            if source == target:
                continue
            weight = float(edge.get("weight", 1.0))
            graph.add_edge(source, target, weight=weight)

        return graph

    def _detect_clusters(self, graph: nx.Graph) -> List[List[str]]:
        if graph.number_of_nodes() < 3:
            return [[node] for node in graph.nodes]
        try:
            communities_result = community.louvain_communities(
                graph, weight="weight", seed=42
            )
        except AttributeError:
            communities_result = community.greedy_modularity_communities(
                graph, weight="weight"
            )
        return [sorted(map(str, comm)) for comm in communities_result]

    @staticmethod
    def _map_clusters(clusters: Sequence[Sequence[str]]) -> Dict[str, str]:
        assignments: Dict[str, str] = {}
        for index, cluster in enumerate(clusters):
            cluster_id = f"cluster-{index}"
            for node_id in cluster:
                assignments[node_id] = cluster_id
        return assignments

    def _weight_edges(self, graph: nx.Graph) -> Dict[Tuple[str, str], float]:
        edge_weights: Dict[Tuple[str, str], float] = {}
        for u, v in graph.edges():
            shared_neighbors = len(list(nx.common_neighbors(graph, u, v)))
            degree_u = graph.degree(u)
            degree_v = graph.degree(v)
            weight = 1.0 + shared_neighbors
            if max(degree_u, degree_v):
                weight += min(degree_u, degree_v) / max(degree_u, degree_v)
            graph.edges[u, v]["weight"] = weight
            edge_weights[(u, v)] = weight
        return edge_weights

    def _compute_spiral_positions(
        self,
        clusters: Sequence[Sequence[str]],
        pagerank: Mapping[str, float],
    ) -> Dict[str, Dict[str, float]]:
        positions: Dict[str, Dict[str, float]] = {}
        if not clusters:
            return positions

        total_clusters = len(clusters)
        base_radius = 120.0
        radial_increment = 14.0
        angular_step = 0.45

        for idx, cluster in enumerate(clusters):
            cluster_angle_offset = (2 * math.pi * idx) / max(total_clusters, 1)
            sorted_nodes = sorted(
                cluster,
                key=lambda nid: pagerank.get(nid, 0.0),
                reverse=True,
            )
            for rank, node_id in enumerate(sorted_nodes):
                radius = base_radius + (idx * 40) + (rank * radial_increment)
                theta = cluster_angle_offset + (rank * angular_step)
                positions[node_id] = {
                    "spiral_radius": radius,
                    "spiral_theta": theta,
                    "spiral_x": radius * math.cos(theta),
                    "spiral_y": radius * math.sin(theta),
                }

        return positions

    def _summarise_graph(
        self,
        graph: nx.Graph,
        clusters: Sequence[Sequence[str]],
        degree_centrality: Mapping[str, float],
        pagerank: Mapping[str, float],
    ) -> Dict[str, Any]:
        density = nx.density(graph)
        clustering_coeff = nx.average_clustering(graph, weight="weight")
        modularity_val = None
        if clusters:
            try:
                modularity_val = community.modularity(graph, clusters, weight="weight")
            except Exception:
                pass

        top_degree = sorted(
            degree_centrality.items(), key=lambda item: item[1], reverse=True
        )[:5]
        top_pagerank = sorted(
            pagerank.items(), key=lambda item: item[1], reverse=True
        )[:5]

        return {
            "density": _to_python_native(density),
            "average_clustering": _to_python_native(clustering_coeff),
            "modularity": (
                _to_python_native(modularity_val) if modularity_val is not None else None
            ),
            "top_degree": [
                (node, _to_python_native(val)) for node, val in top_degree
            ],
            "top_pagerank": [
                (node, _to_python_native(val)) for node, val in top_pagerank
            ],
            "cluster_count": len(clusters),
        }

    def _summarise_clusters(
        self,
        clusters: Sequence[Sequence[str]],
        node_metrics: Mapping[str, Mapping[str, Any]],
    ) -> List[Dict[str, Any]]:
        summaries: List[Dict[str, Any]] = []
        palette_size = len(self._palette)

        for idx, cluster in enumerate(clusters):
            if not cluster:
                continue
            color = (
                self._palette[idx % palette_size] if palette_size else "#94a3b8"
            )
            centrality_values = [
                node_metrics[nid]["degree_centrality"]
                for nid in cluster
                if nid in node_metrics
            ]
            summaries.append(
                {
                    "id": f"cluster-{idx}",
                    "size": len(cluster),
                    "color": color,
                    "approximate_radius": _to_python_native(
                        max(
                            (
                                node_metrics[nid].get("spiral_radius", 0.0)
                                for nid in cluster
                                if nid in node_metrics
                            ),
                            default=0.0,
                        )
                    ),
                    "average_degree_centrality": _to_python_native(
                        (
                            sum(centrality_values) / len(centrality_values)
                            if centrality_values
                            else 0.0
                        )
                    ),
                }
            )

        return summaries


# ---------------------------------------------------------------------------
# Swiss Grid Layout (ported from blueballs swiss_analytics.py)
# ---------------------------------------------------------------------------

RING_RADII = {0: 200, 1: 400, 2: 600}


def compute_grid_positions(nodes: List[Dict[str, Any]]) -> None:
    """Compute (x, y) polar grid positions in-place.

    - Target node at center (0, 0)
    - Tier 0 (strong >20 orbit connections): radius 200
    - Tier 1 (medium 5-20): radius 400
    - Tier 2 (weak <5): radius 600
    """
    tier_0 = [n for n in nodes if n.get("tier") == 0 and not n.get("is_target")]
    tier_1 = [n for n in nodes if n.get("tier") == 1]
    tier_2 = [n for n in nodes if n.get("tier") == 2]
    target = next((n for n in nodes if n.get("is_target")), None)

    if target:
        target["x"] = 0.0
        target["y"] = 0.0

    _place_ring(tier_0, RING_RADII[0])
    _place_ring(tier_1, RING_RADII[1])
    _place_ring(tier_2, RING_RADII[2])

    logger.info(
        "Grid positions: %d tier-0, %d tier-1, %d tier-2",
        len(tier_0),
        len(tier_1),
        len(tier_2),
    )


def _place_ring(nodes: List[Dict[str, Any]], radius: float) -> None:
    if not nodes:
        return
    count = len(nodes)
    angle_step = (2 * math.pi) / count
    for i, node in enumerate(nodes):
        angle = i * angle_step
        node["x"] = radius * math.cos(angle)
        node["y"] = radius * math.sin(angle)


def compute_orbit_strength_ratio(nodes: List[Dict[str, Any]]) -> Dict[str, float]:
    """Compute distribution of orbit strengths for metadata."""
    total = len(nodes)
    if total == 0:
        return {"strong": 0.0, "medium": 0.0, "weak": 0.0}

    tier_counts = {0: 0, 1: 0, 2: 0}
    for node in nodes:
        tier = node.get("tier", 2)
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

    return {
        "strong": tier_counts[0] / total,
        "medium": tier_counts[1] / total,
        "weak": tier_counts[2] / total,
    }
