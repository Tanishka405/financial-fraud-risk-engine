"""Descriptive graph analytics: PageRank, betweenness centrality, Louvain communities.

Concept adapted from the AML-Network-Graph-Engine prototype (`backend/graph_engine.py`), with deliberate fixes:
  * betweenness is UNWEIGHTED. The prototype passed transaction amount as an edge *weight*, which networkx treats
    as a distance, so larger flows were treated as longer paths -- the opposite of intent.
  * communities use seeded Louvain on transaction COUNTS (amounts are heavy-tailed and let one transfer dominate),
    and ids are relabelled deterministically (largest first, ties by smallest member id).
  * PageRank is weighted by total amount (flow-like quantity, where a larger weight correctly means more flow).
  * All inputs are the aggregated directed graph built from the MultiDiGraph, so repeated transactions between a
    pair are summarised here, never silently dropped from the source graph.

IMPORTANT -- these are COMPUTED STRUCTURAL METRICS, not risk signals. On this project's synthetic data they were
measured (scripts/evaluate_detection.py --graph-ablation) to add no demonstrated predictive value, so they are
excluded from the model and the risk score by default (DetectionConfig.include_graph_features_in_model = False).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx
import numpy as np
import pandas as pd

ANALYTICS_COLUMNS = ("account_id", "pagerank", "pagerank_percentile", "betweenness", "betweenness_percentile",
                     "community_id", "community_size")


@dataclass(frozen=True)
class GraphAnalyticsConfig:
    seed: int = 42
    pagerank_alpha: float = 0.85
    betweenness_exact_max_nodes: int = 500  # above this, a seeded k-sample approximation is used
    betweenness_sample_k: int = 100
    louvain_resolution: float = 1.0


@dataclass
class GraphAnalytics:
    nodes: pd.DataFrame  # ANALYTICS_COLUMNS, one row per account
    communities: pd.DataFrame  # community_id, size, internal_txn_share, total_value_inr
    modularity: float | None
    betweenness_method: str  # "exact" | "sampled(k=..)" | "n/a"
    notes: list[str] = field(default_factory=list)


def aggregate_digraph(graph: nx.MultiDiGraph) -> nx.DiGraph:
    """Collapse parallel edges: weight = total INR, count = number of transactions."""
    d = nx.DiGraph()
    d.add_nodes_from(graph.nodes)
    for u, v, data in graph.edges(data=True):
        amt = float(data.get("amount_inr", 0.0))
        if d.has_edge(u, v):
            d[u][v]["weight"] += amt
            d[u][v]["count"] += 1
        else:
            d.add_edge(u, v, weight=amt, count=1)
    return d


def _percentile(s: pd.Series) -> pd.Series:
    if len(s) <= 1:
        return pd.Series(0.0, index=s.index)
    return 100.0 * (s.rank(method="average") - 1.0) / (len(s) - 1)


def _empty() -> GraphAnalytics:
    return GraphAnalytics(pd.DataFrame(columns=list(ANALYTICS_COLUMNS)),
                          pd.DataFrame(columns=["community_id", "size", "internal_txn_share", "total_value_inr"]),
                          None, "n/a", ["Graph has no accounts; no analytics computed."])


def compute_graph_analytics(graph: nx.MultiDiGraph, cfg: GraphAnalyticsConfig | None = None) -> GraphAnalytics:
    cfg = cfg or GraphAnalyticsConfig()
    if graph.number_of_nodes() == 0:
        return _empty()
    d = aggregate_digraph(graph)
    n = d.number_of_nodes()
    nodes = sorted(d.nodes)
    notes: list[str] = []

    # PageRank (amount-weighted flow). No edges -> uniform.
    if d.number_of_edges() == 0:
        pr = {a: 1.0 / n for a in nodes}
    else:
        pr = nx.pagerank(d, alpha=cfg.pagerank_alpha, weight="weight")

    # Betweenness: unweighted, exact for modest graphs, else seeded sample.
    if n < 3 or d.number_of_edges() == 0:
        bt, method = {a: 0.0 for a in nodes}, "n/a"
    elif n <= cfg.betweenness_exact_max_nodes:
        bt, method = nx.betweenness_centrality(d, normalized=True), "exact"
    else:
        k = min(cfg.betweenness_sample_k, n)
        bt, method = nx.betweenness_centrality(d, k=k, normalized=True, seed=cfg.seed), f"sampled(k={k})"
        notes.append(f"Betweenness approximated from {k} sampled sources (seed {cfg.seed}).")

    # Louvain on the undirected projection, weighted by transaction counts.
    u = nx.Graph()
    u.add_nodes_from(nodes)
    for a, b, data in d.edges(data=True):
        w = data["count"]
        if u.has_edge(a, b):
            u[a][b]["weight"] += w
        else:
            u.add_edge(a, b, weight=w)
    raw = nx.community.louvain_communities(u, weight="weight", resolution=cfg.louvain_resolution, seed=cfg.seed)
    ordered = sorted(raw, key=lambda c: (-len(c), min(c)))  # deterministic relabelling
    cid = {a: i for i, c in enumerate(ordered) for a in c}
    csize = {a: len(ordered[cid[a]]) for a in nodes}
    try:
        modularity: float | None = float(nx.community.modularity(u, ordered, weight="weight")) if u.number_of_edges() else None
    except Exception:  # noqa: BLE001 - descriptive only; never fail the analysis
        modularity = None

    df = pd.DataFrame({"account_id": nodes, "pagerank": [pr[a] for a in nodes], "betweenness": [bt[a] for a in nodes],
                       "community_id": [cid[a] for a in nodes], "community_size": [csize[a] for a in nodes]})
    df["pagerank_percentile"] = _percentile(df["pagerank"]).to_numpy()
    df["betweenness_percentile"] = _percentile(df["betweenness"]).to_numpy()
    df = df[list(ANALYTICS_COLUMNS)]

    rows = []
    for i, members in enumerate(ordered):
        ms = set(members)
        inside = outside = 0
        value = 0.0
        for a, b, data in d.edges(data=True):
            ina, inb = a in ms, b in ms
            if ina and inb:
                inside += data["count"]; value += data["weight"]
            elif ina or inb:
                outside += data["count"]
        total = inside + outside
        rows.append({"community_id": i, "size": len(ms), "internal_txn_share": inside / total if total else None,
                     "total_value_inr": round(value, 2)})
    comms = pd.DataFrame(rows, columns=["community_id", "size", "internal_txn_share", "total_value_inr"])
    if not np.isfinite(df[["pagerank", "betweenness"]].to_numpy()).all():
        raise ValueError("Graph analytics produced non-finite values")
    return GraphAnalytics(df, comms, modularity, method, notes)
