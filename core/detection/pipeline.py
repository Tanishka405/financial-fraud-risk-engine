"""End-to-end analysis: features -> graph -> rules -> model -> scores -> alerts.

Score semantics (documented, uncalibrated):
- rule_score  [0,100]: 100*(1-prod(1-w)) over distinct rule codes hit by the account.
- model_percentile [0,100]: Isolation Forest rank within this dataset (relative).
- risk_score  [0,100]: ordinal *risk index* = rule_share*rule_score + (1-rule_share)*model_percentile
              (= rule_score if the model did not run). NOT a fraud probability.
The three are always returned separately.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

import networkx as nx
import numpy as np
import pandas as pd

from core.config import Config
from core.detection.config import DetectionConfig
from core.detection.model import feature_deviations, fit_score_isolation_forest
from core.detection.model_features import build_model_feature_matrix
from core.detection.rules import RULE_DESCRIPTIONS, RuleHit, run_rules
from core.features.transaction_features import compute_account_features
from core.graph.builder import build_transaction_graph
from core.graph.metrics import compute_graph_metrics

SCORE_DISCLAIMER = (
    "risk_score is an uncalibrated, ordinal risk index (0-100) for prioritising human review. "
    "It is not a probability of fraud, and an alert is not a finding of fraud."
)


@dataclass
class Alert:
    alert_id: str
    account_id: str
    severity: str
    risk_score: float
    rule_score: float
    model_score: float | None
    reason_codes: list[str]
    hits: list[RuleHit]
    feature_deviations: list[dict]
    summary: str
    basis: str  # "RULES", "RULES+MODEL", "MODEL_ONLY"


@dataclass
class AnalysisResult:
    dataset_id: str
    transactions: pd.DataFrame
    account_features: pd.DataFrame
    graph_metrics: pd.DataFrame
    graph: nx.MultiDiGraph
    model_features: pd.DataFrame
    rule_hits: list[RuleHit]
    account_scores: pd.DataFrame  # account_id, rule_score, model_score, risk_score, severity, n_rules
    alerts: list[Alert]
    detection_config: DetectionConfig
    model_ran: bool
    notes: list[str] = field(default_factory=list)


def dataset_fingerprint(tx: pd.DataFrame) -> str:
    h = hashlib.sha1()
    if not tx.empty:
        for r in tx[["transaction_id", "sender_account_id", "receiver_account_id", "amount_inr"]].itertuples(index=False):
            h.update(f"{r[0]}|{r[1]}|{r[2]}|{r[3]:.2f};".encode())
    return h.hexdigest()[:12]


def severity_for(score: float, cfg: DetectionConfig) -> str:
    if score >= cfg.severity_critical:
        return "critical"
    if score >= cfg.severity_high:
        return "high"
    if score >= cfg.severity_medium:
        return "medium"
    return "low"


def _rule_score(hits: list[RuleHit]) -> float:
    best: dict[str, float] = {}
    for h in hits:
        best[h.rule_code] = max(best.get(h.rule_code, 0.0), h.weight)
    prod = 1.0
    for w in best.values():
        prod *= 1.0 - min(max(w, 0.0), 1.0)
    return 100.0 * (1.0 - prod)


def _alert_summary(account_id: str, codes: list[str], model_pct: float | None, basis: str) -> str:
    if basis == "MODEL_ONLY":
        return (f"{account_id} matched no AML rule but ranks in the top of the Isolation Forest anomaly ordering "
                f"(percentile {model_pct:.1f}); a statistical outlier versus other accounts in this dataset.")
    names = ", ".join(c.replace("_", " ").lower() for c in codes)
    return f"{account_id} matched {len(codes)} rule(s): {names}."


def run_analysis(transactions: pd.DataFrame, config: Config, det: DetectionConfig | None = None) -> AnalysisResult:
    det = det or DetectionConfig()
    tx = transactions.reset_index(drop=True)
    feats = compute_account_features(tx, config)
    graph = build_transaction_graph(tx)
    gm = compute_graph_metrics(graph)
    X = build_model_feature_matrix(feats, gm)
    hits = run_rules(tx, det)
    model = fit_score_isolation_forest(X, det) if len(X) else None
    notes: list[str] = []
    if model is None:
        notes.append(f"Isolation Forest not run (disabled or fewer than {det.model_min_accounts} accounts); "
                     "risk_score equals rule_score.")

    by_acc: dict[str, list[RuleHit]] = {}
    for h in hits:
        by_acc.setdefault(h.account_id, []).append(h)

    rows, alerts = [], []
    for acc in X.index:
        ah = by_acc.get(acc, [])
        rs = _rule_score(ah)
        mp = float(model.loc[acc, "model_percentile"]) if model is not None else None
        risk = rs if mp is None else det.rule_share * rs + (1.0 - det.rule_share) * mp
        sev = severity_for(risk, det)
        codes = sorted({h.rule_code for h in ah})
        rows.append({"account_id": acc, "rule_score": round(rs, 2), "model_score": None if mp is None else round(mp, 2),
                     "risk_score": round(risk, 2), "severity": sev, "n_rules": len(codes)})
        basis = None
        if codes and rs >= det.alert_min_combined_if_rule_hit:
            basis = "RULES+MODEL" if mp is not None else "RULES"
        elif not codes and mp is not None and mp >= det.model_only_alert_percentile:
            basis = "MODEL_ONLY"
        if basis:
            alerts.append(Alert(
                alert_id=f"ALR-{acc}", account_id=acc, severity=sev, risk_score=round(risk, 2),
                rule_score=round(rs, 2), model_score=None if mp is None else round(mp, 2),
                reason_codes=codes if codes else ["MODEL_ANOMALY"], hits=ah,
                feature_deviations=feature_deviations(X, acc), summary=_alert_summary(acc, codes, mp, basis),
                basis=basis))
    alerts.sort(key=lambda a: (-a.risk_score, a.account_id))
    scores = pd.DataFrame(rows, columns=["account_id", "rule_score", "model_score", "risk_score", "severity", "n_rules"])
    return AnalysisResult(dataset_fingerprint(tx), tx, feats, gm, graph, X, hits, scores, alerts, det,
                          model is not None, notes)


def evaluate_on_synthetic(alerts: list[Alert], account_scenarios: pd.DataFrame) -> dict[str, Any]:
    """CONTROLLED evaluation only: compares alerted accounts to the synthetic generator's injected
    scenario participants. Labels are consumed here and nowhere else. Says nothing about real-world
    detection accuracy."""
    injected = set(account_scenarios["account_id"]) if not account_scenarios.empty else set()
    alerted = {a.account_id for a in alerts}
    tp = injected & alerted
    per_role = []
    if not account_scenarios.empty:
        for role, g in account_scenarios.groupby("scenario"):
            ids = set(g["account_id"])
            per_role.append({"scenario_role": role, "accounts": len(ids), "alerted": len(ids & alerted)})
    return {
        "scope": "synthetic-injected-scenarios-only",
        "injected_accounts": len(injected), "alerted_accounts": len(alerted),
        "injected_and_alerted": len(tp),
        "recall_on_injected": round(len(tp) / len(injected), 4) if injected else None,
        "alert_precision_vs_injected": round(len(tp) / len(alerted), 4) if alerted else None,
        "per_scenario_role": per_role,
        "caveat": ("Injected scenarios are hand-designed academic patterns. Alerts on non-injected accounts "
                   "are not necessarily false positives (ordinary random traffic can match a rule), and "
                   "these figures do not estimate real-world fraud detection performance."),
    }
