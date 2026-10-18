import numpy as np
import pandas as pd
import pytest

from core.detection.benchmark import (CAVEAT, EXPECTED_RULE, _auc, evaluate_run, evaluate_seeds, parse_seeds, run_seed,
                                      summarize, to_markdown)
from core.detection.config import DetectionConfig
from core.detection.rules import RULE_DESCRIPTIONS

SMALL = dict(num_accounts=60, num_normal=300)


def test_parse_seeds_ranges_lists_and_errors():
    assert parse_seeds("1-3,7,10-11") == [1, 2, 3, 7, 10, 11]
    assert parse_seeds("5,5,4") == [4, 5]
    for bad in ("", "3-1", "a"):
        with pytest.raises(ValueError):
            parse_seeds(bad)


def test_auc_handles_degenerate_inputs():
    assert _auc(np.array([True, False, True, False]), np.array([0.9, 0.1, 0.8, 0.2])) == 1.0
    assert _auc(np.array([True, True]), np.array([1.0, 2.0])) is None  # one class only
    assert _auc(np.array([True, False]), np.array([np.nan, np.nan])) is None


def test_run_seed_is_deterministic_and_has_expected_shape():
    a, b = run_seed(3, **SMALL), run_seed(3, **SMALL)
    assert a == b
    assert a["injected_accounts"] > 0 and 0 <= a["alert_recall"] <= 1
    assert {"auc_rule_score", "auc_model_score", "auc_risk_score", "roles"} <= set(a)
    assert all(0.0 <= a[k] <= 1.0 for k in ("auc_rule_score", "auc_risk_score"))


def test_every_scenario_role_has_a_known_designed_rule_that_exists():
    r = run_seed(1, **SMALL)
    for x in r["roles"]:
        assert x["expected_rule"] in RULE_DESCRIPTIONS, x
        assert 0 <= x["designed_rule_hit"] <= x["accounts"]
    assert set(EXPECTED_RULE.values()) <= set(RULE_DESCRIPTIONS)


def test_summary_aggregates_across_seeds_and_includes_caveat():
    s = evaluate_seeds([1, 2], **SMALL)
    assert s["n_runs"] == 2 and s["seeds"] == [1, 2] and len(s["runs"]) == 2
    m = s["metrics"]["alert_recall"]
    assert m["min"] <= m["mean"] <= m["max"] and m["n"] == 2
    assert s["caveat"] == CAVEAT and "do NOT estimate real-world" in s["caveat"]
    md = to_markdown(s)
    assert "designed-rule recall" in md and "uncalibrated" in md.lower()


def test_summarize_math_on_handmade_runs():
    role = lambda alerted, hit: [{"role": "R", "accounts": 2, "alerted": alerted, "expected_rule": "HIGH_FANOUT", "designed_rule_hit": hit}]  # noqa: E731
    runs = [{"seed": 1, "alert_recall": 1.0, "alert_precision": 0.5, "false_alert_accounts": 1, "auc_rule_score": 1.0,
             "auc_model_score": None, "auc_risk_score": 0.9, "roles": role(2, 2)},
            {"seed": 2, "alert_recall": 0.5, "alert_precision": None, "false_alert_accounts": 3, "auc_rule_score": 0.8,
             "auc_model_score": None, "auc_risk_score": 0.7, "roles": role(0, 0)}]
    s = summarize(runs)
    assert s["metrics"]["alert_recall"]["mean"] == 0.75
    assert s["metrics"]["alert_precision"]["n"] == 1  # None excluded, not counted as 0
    assert s["metrics"]["auc_model_score"]["mean"] is None
    r = s["roles"][0]
    assert r["seeds_fully_missed"] == 1 and r["designed_rule_recall"] == 0.5 and r["designed_rule_min"] == 0.0


def test_evaluation_uses_labels_only_after_detection(config):
    """Detector output must be identical whether or not labels exist: labels are consumed only in evaluate_run."""
    from core.data.schema import transactions_to_dataframe
    from core.data.synthetic import generate_synthetic_dataset
    from core.detection.pipeline import run_analysis
    ds = generate_synthetic_dataset(config, num_accounts=60, num_normal_transactions=300)
    tx = transactions_to_dataframe(ds.transactions)
    r1 = run_analysis(tx, config)
    shuffled = ds.account_scenarios.sample(frac=1.0, random_state=0).reset_index(drop=True)
    r2 = run_analysis(tx, config)
    pd.testing.assert_frame_equal(r1.account_scores, r2.account_scores)
    assert evaluate_run(r1, ds.account_scenarios)["alert_recall"] == evaluate_run(r1, shuffled)["alert_recall"]


def test_rules_only_ablation_has_no_model_signal():
    r = run_seed(2, det=DetectionConfig(model_enabled=False), **SMALL)
    assert r["auc_model_score"] is None
    assert r["alert_recall"] is not None
