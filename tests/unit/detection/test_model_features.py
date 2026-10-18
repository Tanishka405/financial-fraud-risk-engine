import numpy as np
import pandas as pd
import pytest

from core.config import Config
from core.data.synthetic import generate_fixture_dataset
from core.data.schema import transactions_to_dataframe
from core.detection.model_features import (MODEL_FEATURE_COLUMNS, assert_no_label_columns,
                                           build_model_feature_matrix)
from core.features.transaction_features import compute_account_features
from core.graph.builder import build_transaction_graph
from core.graph.metrics import compute_graph_metrics
from tests.unit.detection.helpers import make_tx


def _matrix(tx, cfg=None):
    cfg = cfg or Config()
    f = compute_account_features(tx, cfg)
    g = compute_graph_metrics(build_transaction_graph(tx))
    return f, g, build_model_feature_matrix(f, g)


def test_pure_sink_inf_ratio_becomes_finite_with_indicator():
    tx = make_tx([("T1", "A", "SINK", 100, 0), ("T2", "B", "SINK", 200, 5)])
    f, _, X = _matrix(tx)
    assert np.isinf(f.set_index("account_id").loc["SINK", "inflow_outflow_ratio"])  # raw feature IS inf
    assert np.isfinite(X.to_numpy()).all()
    assert X.loc["SINK", "is_pure_sink"] == 1.0 and X.loc["SINK", "is_pure_source"] == 0.0
    assert X.loc["A", "is_pure_source"] == 1.0
    assert X.loc["SINK", "log_inflow_outflow_ratio"] > 0 > X.loc["A", "log_inflow_outflow_ratio"]


def test_feature_matrix_is_finite_on_full_fixture_and_has_documented_columns(config):
    ds = generate_fixture_dataset(config)
    _, _, X = _matrix(transactions_to_dataframe(ds.transactions), config)
    assert list(X.columns) == list(MODEL_FEATURE_COLUMNS)
    assert np.isfinite(X.to_numpy()).all()
    assert X.index.is_unique


def test_scenario_labels_never_in_feature_matrix(config):
    ds = generate_fixture_dataset(config)
    _, _, X = _matrix(transactions_to_dataframe(ds.transactions), config)
    assert not any("scenario" in c or "label" in c for c in X.columns)
    assert set(ds.account_scenarios.columns).isdisjoint(set(X.columns) - {"account_id"})


def test_label_like_columns_are_rejected():
    with pytest.raises(ValueError):
        assert_no_label_columns(["txn_count_sent", "scenario"])
    f = pd.DataFrame({"account_id": ["A"], "scenario": ["X"]})
    with pytest.raises(ValueError):
        build_model_feature_matrix(f, pd.DataFrame({"account_id": ["A"], "unique_counterparties_total": [1]}))


def test_empty_input_returns_empty_matrix():
    X = build_model_feature_matrix(pd.DataFrame(), pd.DataFrame())
    assert X.empty and list(X.columns) == list(MODEL_FEATURE_COLUMNS)
