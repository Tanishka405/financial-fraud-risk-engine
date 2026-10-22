import networkx as nx
import numpy as np
import pytest

from core.graph.analytics import GraphAnalyticsConfig, aggregate_digraph, compute_graph_analytics
from core.graph.builder import build_transaction_graph
from tests.unit.detection.helpers import make_tx


def G(rows):
    return build_transaction_graph(make_tx(rows))


def test_empty_graph_is_safe():
    a = compute_graph_analytics(nx.MultiDiGraph())
    assert a.nodes.empty and a.modularity is None and a.betweenness_method == "n/a" and a.notes


def test_repeated_transactions_are_aggregated_not_lost():
    g = G([(f"T{i}", "A", "B", 100, i) for i in range(4)] + [("T9", "B", "C", 50, 9)])
    d = aggregate_digraph(g)
    assert d["A"]["B"]["count"] == 4 and d["A"]["B"]["weight"] == 400
    assert g.number_of_edges() == 5  # the source MultiDiGraph is untouched


def test_betweenness_is_unweighted_amount_is_not_a_distance():
    """Path A->B->C->D carries tiny amounts, but a huge-amount shortcut must NOT make it 'longer'."""
    chain = [("T1", "A", "B", 1, 0), ("T2", "B", "C", 1, 1), ("T3", "C", "D", 1, 2)]
    a = compute_graph_analytics(G(chain)).nodes.set_index("account_id")
    b = compute_graph_analytics(G([(t, s, r, 1_000_000 * (i + 1), m) for i, (t, s, r, _, m) in enumerate(chain)])).nodes.set_index("account_id")
    assert a["betweenness"].round(9).to_dict() == b["betweenness"].round(9).to_dict()
    assert a.loc["B", "betweenness"] > a.loc["A", "betweenness"] == 0.0  # intermediaries lie on the paths


def test_pagerank_is_amount_weighted():
    """Weights decide how ONE sender splits its rank across its own receivers, so test a single source."""
    rows = [("T1", "X", "BIG", 900_000, 0), ("T2", "X", "SMALL", 10, 1)]
    n = compute_graph_analytics(G(rows)).nodes.set_index("account_id")
    assert n.loc["BIG", "pagerank"] - n.loc["SMALL", "pagerank"] > 0.1  # teleportation keeps a baseline, so compare the gap
    assert pytest.approx(n["pagerank"].sum(), rel=1e-6) == 1.0


def test_two_cliques_joined_by_one_edge_give_two_communities():
    rows, i = [], 0
    for grp in ("A", "B"):
        for x in range(4):
            for y in range(4):
                if x != y:
                    rows.append((f"T{i}", f"{grp}{x}", f"{grp}{y}", 100, i)); i += 1
    rows.append((f"T{i}", "A0", "B0", 100, i))
    a = compute_graph_analytics(G(rows))
    n = a.nodes.set_index("account_id")
    assert len(a.communities) == 2 and n.loc["A0", "community_id"] != n.loc["B0", "community_id"]
    assert len({n.loc[f"A{x}", "community_id"] for x in range(4)}) == 1
    assert (n["community_size"] == 4).all() and a.modularity > 0.3
    assert (a.communities["internal_txn_share"] > 0.9).all()


def test_community_ids_deterministic_and_ordered_largest_first():
    rows = [(f"T{i}", f"N{i % 7}", f"N{(i * 3 + 1) % 7}", 100 + i, i) for i in range(60) if i % 7 != (i * 3 + 1) % 7]
    a, b = compute_graph_analytics(G(rows)), compute_graph_analytics(G(rows))
    assert a.nodes.equals(b.nodes) and a.communities.equals(b.communities)
    sizes = a.communities["size"].tolist()
    assert sizes == sorted(sizes, reverse=True) and a.communities["community_id"].tolist() == list(range(len(sizes)))


def test_all_values_finite_and_percentiles_in_range_on_synthetic(config):
    from core.data.schema import transactions_to_dataframe
    from core.data.synthetic import generate_fixture_dataset
    tx = transactions_to_dataframe(generate_fixture_dataset(config).transactions)
    a = compute_graph_analytics(build_transaction_graph(tx))
    cols = ["pagerank", "betweenness", "pagerank_percentile", "betweenness_percentile"]
    assert np.isfinite(a.nodes[cols].to_numpy()).all()
    assert a.nodes["pagerank_percentile"].between(0, 100).all() and a.nodes["account_id"].is_unique
    assert "scenario" not in " ".join(a.nodes.columns).lower()


def test_large_graph_uses_seeded_sampling_and_says_so():
    rows = [(f"T{i}", f"N{i % 40}", f"N{(i * 7 + 3) % 40}", 100, i) for i in range(300) if i % 40 != (i * 7 + 3) % 40]
    cfg = GraphAnalyticsConfig(betweenness_exact_max_nodes=10, betweenness_sample_k=8)
    a, b = compute_graph_analytics(G(rows), cfg), compute_graph_analytics(G(rows), cfg)
    assert a.betweenness_method == "sampled(k=8)" and any("approximated" in n for n in a.notes)
    assert a.nodes.equals(b.nodes)  # seeded -> reproducible


def test_nodes_without_edges_are_handled():
    g = nx.MultiDiGraph(); g.add_nodes_from(["P", "Q"])
    a = compute_graph_analytics(g)
    assert len(a.nodes) == 2 and (a.nodes["betweenness"] == 0).all() and a.nodes["community_size"].tolist() == [1, 1]
