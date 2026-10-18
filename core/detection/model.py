"""Isolation Forest baseline. Unsupervised: it never sees labels of any kind.

`model_percentile` is the account's anomaly *rank* within THIS dataset in
[0,100] (100 = most isolated). It is a relative ordering, not a probability and
not comparable across datasets. Isolation Forest scores say "unusual versus the
other accounts here", which on its own is not evidence of wrongdoing.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import rankdata
from sklearn.ensemble import IsolationForest

from core.detection.config import DetectionConfig


def fit_score_isolation_forest(X: pd.DataFrame, cfg: DetectionConfig) -> pd.DataFrame | None:
    """Return DataFrame[account_id index; model_raw, model_percentile] or None if the
    model is disabled / dataset too small. Raises if X is not finite."""
    if not cfg.model_enabled or len(X) < cfg.model_min_accounts:
        return None
    arr = X.to_numpy(dtype=float)
    if not np.isfinite(arr).all():
        raise ValueError("Isolation Forest input contains non-finite values")
    clf = IsolationForest(n_estimators=cfg.model_n_estimators, random_state=cfg.model_random_state,
                          contamination="auto", n_jobs=1)
    clf.fit(arr)
    raw = -clf.score_samples(arr)  # higher = more anomalous
    pct = 100.0 * (rankdata(raw, method="average") - 1.0) / max(len(raw) - 1, 1)
    return pd.DataFrame({"model_raw": raw, "model_percentile": pct}, index=X.index)


def feature_deviations(X: pd.DataFrame, account_id: str, top_k: int = 3) -> list[dict]:
    """Descriptive robust z-scores of an account's features versus the population.
    This is NOT a model attribution (Isolation Forest has none); it simply shows
    which features are furthest from typical, to help a reviewer."""
    if account_id not in X.index:
        return []
    out = []
    row = X.loc[account_id]
    for col in X.columns:
        if col.startswith("is_pure"):
            continue
        med = float(X[col].median())
        mad = float((X[col] - med).abs().median()) * 1.4826
        scale = mad if mad > 1e-9 else float(X[col].std(ddof=0))
        if scale <= 1e-9:
            continue
        z = (float(row[col]) - med) / scale
        out.append({"feature": col, "value": round(float(row[col]), 4), "population_median": round(med, 4),
                    "robust_z": round(float(z), 2)})
    out.sort(key=lambda d: abs(d["robust_z"]), reverse=True)
    return out[:top_k]
