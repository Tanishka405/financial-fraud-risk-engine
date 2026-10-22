"""The graph-analytics model features are OFF by default and must not leak into default behaviour."""
import numpy as np
import pandas as pd
import pytest

from core.config import Config
from core.data.schema import transactions_to_dataframe
from core.data.synthetic import generate_synthetic_dataset
from core.detection.config import DetectionConfig
from core.detection.model_features import GRAPH_FEATURE_COLUMNS, MODEL_FEATURE_COLUMNS, assert_no_label_columns
from core.detection.pipeline import run_analysis

GRAPH_WORDS = ("pagerank", "betweenness", "community")


@pytest.fixture(scope="module")
def tx():
    cfg = Config()
    return transactions_to_dataframe(generate_synthetic_dataset(cfg, num_accounts=80, num_normal_transactions=600).transactions)


def test_flag_is_off_by_default():
    assert DetectionConfig().include_graph_features_in_model is False


def test_default_matrix_has_exactly_the_base_columns_and_analytics_stay_descriptive(tx):
    r = run_analysis(tx, Config())
    assert list(r.model_features.columns) == list(MODEL_FEATURE_COLUMNS)
    assert not any(w in c for c in r.model_features.columns for w in GRAPH_WORDS)
    assert r.graph_analytics is not None and len(r.graph_analytics.nodes) == len(r.model_features)  # computed, just not used


def test_enabled_matrix_appends_graph_columns_finite_and_label_free(tx):
    r = run_analysis(tx, Config(), DetectionConfig(include_graph_features_in_model=True))
    assert list(r.model_features.columns) == list(MODEL_FEATURE_COLUMNS) + list(GRAPH_FEATURE_COLUMNS)
    assert np.isfinite(r.model_features.to_numpy()).all()
    assert_no_label_columns(r.model_features.columns)
    ga = r.graph_analytics.nodes
    assert ga["pagerank"].between(0, 1).all() and ga["community_size"].ge(1).all()


def test_enabling_flag_changes_only_model_dependent_outputs(tx):
    off = run_analysis(tx, Config())
    on = run_analysis(tx, Config(), DetectionConfig(include_graph_features_in_model=True))
    assert [(h.rule_code, h.account_id, h.summary) for h in off.rule_hits] == [(h.rule_code, h.account_id, h.summary) for h in on.rule_hits]
    pd.testing.assert_series_equal(off.account_scores.set_index("account_id")["rule_score"], on.account_scores.set_index("account_id")["rule_score"])
    assert not off.account_scores["model_score"].equals(on.account_scores["model_score"])  # the model input really changed


def test_default_outputs_do_not_depend_on_analytics_and_failure_is_contained(tx, monkeypatch):
    ref = run_analysis(tx, Config())
    monkeypatch.setattr("core.detection.pipeline.compute_graph_analytics", lambda g: (_ for _ in ()).throw(RuntimeError("boom")))
    broken = run_analysis(tx, Config())
    pd.testing.assert_frame_equal(ref.account_scores, broken.account_scores)  # default scores independent of analytics
    assert [a.alert_id for a in ref.alerts] == [a.alert_id for a in broken.alerts]
    assert broken.graph_analytics is None and any("Graph analytics unavailable" in n for n in broken.notes)


def test_flag_on_with_failed_analytics_falls_back_to_base_matrix(tx, monkeypatch):
    monkeypatch.setattr("core.detection.pipeline.compute_graph_analytics", lambda g: (_ for _ in ()).throw(RuntimeError("boom")))
    r = run_analysis(tx, Config(), DetectionConfig(include_graph_features_in_model=True))
    assert list(r.model_features.columns) == list(MODEL_FEATURE_COLUMNS) and r.model_ran


def test_empty_and_tiny_datasets_with_flag_on(config):
    from tests.unit.detection.helpers import make_tx
    det = DetectionConfig(include_graph_features_in_model=True)
    e = run_analysis(make_tx([]), config, det)
    assert e.alerts == [] and e.graph_analytics is not None and e.graph_analytics.nodes.empty
    t = run_analysis(make_tx([("T1", "A", "B", 10, 0)]), config, det)  # <30 accounts: model skipped, analytics still valid
    assert not t.model_ran and len(t.graph_analytics.nodes) == 2
