import numpy as np
import pandas as pd

from core.config import Config
from core.data.synthetic import generate_synthetic_dataset
from core.data.schema import transactions_to_dataframe
from core.detection.config import DetectionConfig
from core.detection.pipeline import evaluate_on_synthetic, run_analysis
from tests.unit.detection.helpers import make_tx


def _synthetic(config):
    ds = generate_synthetic_dataset(config)
    return ds, transactions_to_dataframe(ds.transactions)


def test_empty_dataset_runs_cleanly(config):
    r = run_analysis(make_tx([]), config)
    assert r.alerts == [] and r.account_scores.empty and not r.model_ran


def test_small_dataset_skips_model_and_says_so(config):
    r = run_analysis(make_tx([("T1", "A", "B", 100, 0), ("T2", "B", "C", 90, 5)]), config)
    assert not r.model_ran and any("not run" in n for n in r.notes)
    assert r.account_scores["model_score"].isna().all()


def test_analysis_is_deterministic(config):
    _, tx = _synthetic(config)
    a, b = run_analysis(tx, config), run_analysis(tx, config)
    pd.testing.assert_frame_equal(a.account_scores, b.account_scores)
    assert [x.alert_id for x in a.alerts] == [x.alert_id for x in b.alerts]


def test_model_inputs_finite_and_scores_in_range(config):
    _, tx = _synthetic(config)
    r = run_analysis(tx, config)
    assert np.isfinite(r.model_features.to_numpy()).all() and r.model_ran
    s = r.account_scores
    for c in ("rule_score", "model_score", "risk_score"):
        assert s[c].between(0, 100).all()


def test_scores_kept_separate_and_combine_as_documented(config):
    _, tx = _synthetic(config)
    det = DetectionConfig()
    r = run_analysis(tx, config, det)
    row = r.account_scores.iloc[0]
    expected = det.rule_share * row.rule_score + (1 - det.rule_share) * row.model_score
    assert abs(row.risk_score - expected) < 0.02


def test_alert_explanations_match_triggered_signals(config):
    _, tx = _synthetic(config)
    r = run_analysis(tx, config)
    ids = set(tx["transaction_id"])
    assert r.alerts
    for a in r.alerts:
        hit_codes = sorted({h.rule_code for h in a.hits})
        assert a.reason_codes == (hit_codes or ["MODEL_ANOMALY"])
        for h in a.hits:
            assert h.account_id == a.account_id
            assert set(h.transaction_ids) <= ids  # evidence refers to real transactions
            assert h.summary
        for c in hit_codes:
            assert c.replace("_", " ").lower() in a.summary


def test_model_only_alert_flagged_as_such(config):
    _, tx = _synthetic(config)
    r = run_analysis(tx, config, DetectionConfig(model_only_alert_percentile=90.0))
    mo = [a for a in r.alerts if a.basis == "MODEL_ONLY"]
    assert mo and all(a.reason_codes == ["MODEL_ANOMALY"] and not a.hits and a.severity == "low" for a in mo)


def test_synthetic_labels_used_only_for_evaluation(config):
    ds, tx = _synthetic(config)
    r = run_analysis(tx, config)
    assert "scenario" not in tx.columns and not any("scenario" in c for c in r.model_features.columns)
    ev = evaluate_on_synthetic(r.alerts, ds.account_scenarios)
    assert ev["scope"] == "synthetic-injected-scenarios-only"
    assert ev["recall_on_injected"] >= 0.9  # sanity check on the designed scenarios, not an accuracy claim
    assert "do not estimate real-world" in ev["caveat"]


def test_repeated_transactions_preserved_in_graph_of_result(config):
    tx = make_tx([(f"T{i}", "A", "B", 100, i) for i in range(4)])
    r = run_analysis(tx, config)
    assert r.graph.number_of_edges() == 4 and len(r.graph["A"]["B"]) == 4
