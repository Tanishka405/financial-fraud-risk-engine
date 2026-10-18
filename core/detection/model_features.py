"""Finite, documented numeric feature matrix for the Isolation Forest.

Inputs: per-account behavioural features (`core.features`) and graph metrics
(`core.graph.metrics`). Output: one row per account, only finite floats.

Transformations (all documented, none learned):
- count / amount / degree columns: log1p (heavy-tailed, non-negative).
- inflow_outflow_ratio may be +inf (pure sink): it is NOT passed through.
  Replaced by log_inflow_outflow_ratio = clip(log10((in+1)/(out+1)), -4, 4),
  finite for every account, plus explicit indicators is_pure_sink / is_pure_source.
- active_days: used as-is (already finite, >= 0).

Scenario labels are never an input: the builder accepts only the two feature
frames, and `assert_no_label_columns` guards against accidental joins.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FORBIDDEN_FEATURE_SUBSTRINGS = ("scenario", "label", "is_fraud", "fraud")

_LOG1P_COLUMNS = (
    "txn_count_sent",
    "txn_count_received",
    "total_amount_sent",
    "total_amount_received",
    "avg_amount_sent",
    "avg_amount_received",
    "unique_counterparties_sent",
    "unique_counterparties_received",
    "max_daily_txn_count",
    "unique_counterparties_total",
)

MODEL_FEATURE_COLUMNS: tuple[str, ...] = (
    *(f"log1p_{c}" for c in _LOG1P_COLUMNS),
    "log_inflow_outflow_ratio",
    "is_pure_sink",
    "is_pure_source",
    "active_days",
    "repeat_intensity",
)


def assert_no_label_columns(columns) -> None:
    bad = [c for c in columns if any(s in str(c).lower() for s in FORBIDDEN_FEATURE_SUBSTRINGS)]
    if bad:
        raise ValueError(f"Label-like column(s) must never be model features: {bad}")


def build_model_feature_matrix(account_features: pd.DataFrame, graph_metrics: pd.DataFrame) -> pd.DataFrame:
    """Return DataFrame indexed by account_id with MODEL_FEATURE_COLUMNS, all finite."""
    assert_no_label_columns(account_features.columns)
    assert_no_label_columns(graph_metrics.columns)
    if account_features.empty:
        return pd.DataFrame(columns=list(MODEL_FEATURE_COLUMNS), index=pd.Index([], name="account_id"), dtype=float)

    df = account_features.merge(
        graph_metrics[["account_id", "unique_counterparties_total"]], on="account_id", how="left"
    ).set_index("account_id")
    df["unique_counterparties_total"] = df["unique_counterparties_total"].fillna(0)

    out = pd.DataFrame(index=df.index)
    for c in _LOG1P_COLUMNS:
        out[f"log1p_{c}"] = np.log1p(df[c].astype(float).fillna(0.0).clip(lower=0.0))

    sent = df["total_amount_sent"].astype(float).fillna(0.0)
    recv = df["total_amount_received"].astype(float).fillna(0.0)
    out["log_inflow_outflow_ratio"] = np.log10((recv + 1.0) / (sent + 1.0)).clip(-4.0, 4.0)
    out["is_pure_sink"] = ((sent == 0) & (recv > 0)).astype(float)
    out["is_pure_source"] = ((recv == 0) & (sent > 0)).astype(float)
    out["active_days"] = df["active_days"].astype(float).fillna(0.0).clip(lower=0.0)
    # repeat intensity: sent txns per unique receiver (>=1; 1 = never repeated a counterparty)
    cp = df["unique_counterparties_sent"].astype(float).replace(0, np.nan)
    out["repeat_intensity"] = (df["txn_count_sent"].astype(float) / cp).fillna(0.0)

    out = out[list(MODEL_FEATURE_COLUMNS)].astype(float)
    if not np.isfinite(out.to_numpy()).all():  # defensive: must never reach sklearn otherwise
        raise ValueError("Model feature matrix contains non-finite values")
    assert_no_label_columns(out.columns)
    return out
