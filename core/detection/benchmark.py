"""Controlled multi-seed evaluation on SYNTHETIC injected scenarios.

Purpose: make every detection change *measurable* (per scenario role, per
signal, across seeds) instead of anecdotal. Scenario labels are consumed here
and nowhere else; the detector never sees them.

What this does NOT do: estimate real-world detection performance. The scenarios
are hand-designed and the rules were written alongside them, so recovery rates
are a regression/sanity measure, not an accuracy claim.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Iterable

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from core.config import Config
from core.data.schema import transactions_to_dataframe
from core.data.synthetic import generate_synthetic_dataset
from core.detection.config import DetectionConfig
from core.detection.pipeline import AnalysisResult, run_analysis

CAVEAT = (
    "Synthetic, injected, hand-designed scenarios; rules were written alongside them. "
    "These figures are a regression and sanity measure and do NOT estimate real-world fraud-detection accuracy. "
    "Scores are uncalibrated ordinal indices."
)
SIGNALS = ("rule_score", "model_score", "risk_score")

# Scenario role -> the rule designed to catch it. Used to credit ONLY the intended rule, because an
# account can also be alerted by an unrelated rule (e.g. a behavioural-change account that also fans out).
EXPECTED_RULE: dict[str, str] = {
    "HIGH_VELOCITY_SOURCE": "HIGH_VELOCITY", "HIGH_FANOUT_SOURCE": "HIGH_FANOUT",
    "LARGE_TRANSFER_SENDER": "LARGE_AMOUNT", "LARGE_TRANSFER_RECEIVER": "LARGE_AMOUNT",
    "REPEATED_TRANSACTIONS_SENDER": "REPEATED_TRANSACTIONS", "REPEATED_TRANSACTIONS_RECEIVER": "REPEATED_TRANSACTIONS",
    "PASS_THROUGH_INTERMEDIARY": "PASS_THROUGH", "CIRCULAR_FLOW_PARTICIPANT": "CIRCULAR_FLOW",
    "LAYERED_MULTI_HOP_PARTICIPANT": "LAYERED_MULTI_HOP", "BEHAVIOURAL_CHANGE": "BEHAVIOURAL_CHANGE",
}


def parse_seeds(spec: str) -> list[int]:
    """'1-3,7,10-11' -> [1,2,3,7,10,11]."""
    out: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            lo, hi = int(a), int(b)
            if hi < lo:
                raise ValueError(f"Invalid seed range {part!r}")
            out.extend(range(lo, hi + 1))
        else:
            out.append(int(part))
    if not out:
        raise ValueError("No seeds given")
    return sorted(set(out))


def _auc(y: np.ndarray, s: np.ndarray) -> float | None:
    if y.all() or not y.any() or np.isnan(s).all():
        return None
    return float(roc_auc_score(y, np.nan_to_num(s, nan=0.0)))


def evaluate_run(result: AnalysisResult, account_scenarios: pd.DataFrame) -> dict[str, Any]:
    """Score one analysed synthetic dataset against its injected-scenario labels."""
    scores = result.account_scores.set_index("account_id")
    injected = set(account_scenarios["account_id"])
    y = np.array([a in injected for a in scores.index])
    alerted = {a.account_id for a in result.alerts}
    tp = injected & alerted
    by_rule: dict[str, set[str]] = {}
    for h in result.rule_hits:
        by_rule.setdefault(h.rule_code, set()).add(h.account_id)
    roles = []
    for role, g in account_scenarios.groupby("scenario"):
        ids = set(g["account_id"])
        exp = EXPECTED_RULE.get(role)
        roles.append({"role": role, "accounts": len(ids), "alerted": len(ids & alerted), "expected_rule": exp,
                      "designed_rule_hit": len(ids & by_rule.get(exp, set())) if exp else None})
    return {
        "injected_accounts": len(injected), "alerted_accounts": len(alerted),
        "alert_recall": len(tp) / len(injected) if injected else None,
        "alert_precision": len(tp) / len(alerted) if alerted else None,
        "false_alert_accounts": len(alerted - injected),
        **{f"auc_{k}": _auc(y, scores[k].to_numpy(dtype=float)) for k in SIGNALS},
        "roles": roles,
    }


def run_seed(seed: int, *, num_accounts: int | None = None, num_normal: int | None = None,
             det: DetectionConfig | None = None, include_structuring: bool = False,
             base_config: Config | None = None) -> dict[str, Any]:
    cfg = replace(base_config or Config(), random_seed=seed)
    kw: dict[str, Any] = {}
    if include_structuring:
        kw["include_structuring"] = True
    ds = generate_synthetic_dataset(cfg, num_accounts=num_accounts, num_normal_transactions=num_normal, **kw)
    result = run_analysis(transactions_to_dataframe(ds.transactions), cfg, det)
    return {"seed": seed, **evaluate_run(result, ds.account_scenarios)}


def _agg(values: Iterable[float | None]) -> dict[str, float | None]:
    v = np.array([x for x in values if x is not None], dtype=float)
    if v.size == 0:
        return {"mean": None, "std": None, "min": None, "max": None, "n": 0}
    return {"mean": float(v.mean()), "std": float(v.std(ddof=0)), "min": float(v.min()), "max": float(v.max()), "n": int(v.size)}


def summarize(runs: list[dict[str, Any]]) -> dict[str, Any]:
    keys = ["alert_recall", "alert_precision", "false_alert_accounts", *(f"auc_{k}" for k in SIGNALS)]
    out: dict[str, Any] = {"seeds": [r["seed"] for r in runs], "n_runs": len(runs), "caveat": CAVEAT,
                           "metrics": {k: _agg(r.get(k) for r in runs) for k in keys}}
    roles: dict[str, list[float]] = {}
    designed: dict[str, list[float]] = {}
    exp: dict[str, str | None] = {}
    for r in runs:
        for x in r["roles"]:
            roles.setdefault(x["role"], []).append(x["alerted"] / x["accounts"] if x["accounts"] else np.nan)
            exp[x["role"]] = x["expected_rule"]
            if x["designed_rule_hit"] is not None and x["accounts"]:
                designed.setdefault(x["role"], []).append(x["designed_rule_hit"] / x["accounts"])
    out["roles"] = [{"role": k, "mean_recall": float(np.nanmean(v)), "min_recall": float(np.nanmin(v)),
                     "seeds_fully_missed": int(sum(1 for x in v if x == 0.0)), "n": len(v), "expected_rule": exp.get(k),
                     "designed_rule_recall": float(np.mean(designed[k])) if k in designed else None,
                     "designed_rule_min": float(np.min(designed[k])) if k in designed else None} for k, v in sorted(roles.items())]
    return out


def evaluate_seeds(seeds: Iterable[int], **kw: Any) -> dict[str, Any]:
    runs = [run_seed(s, **kw) for s in seeds]
    summary = summarize(runs)
    summary["runs"] = runs
    return summary


def to_markdown(summary: dict[str, Any], title: str = "Detection benchmark (synthetic)") -> str:
    f = lambda x: "n/a" if x is None else f"{x:.3f}"  # noqa: E731
    lines = [f"### {title}", "", f"Seeds: {summary['seeds']}  ·  runs: {summary['n_runs']}", "",
             "| Metric | mean | std | min | max |", "|---|---|---|---|---|"]
    for k, v in summary["metrics"].items():
        lines.append(f"| {k} | {f(v['mean'])} | {f(v['std'])} | {f(v['min'])} | {f(v['max'])} |")
    lines += ["", "| Scenario role | alert recall (any signal) | designed rule | designed-rule recall (mean / min) |", "|---|---|---|---|"]
    for r in summary["roles"]:
        d = "n/a" if r["designed_rule_recall"] is None else f"{r['designed_rule_recall']:.2f} / {r['designed_rule_min']:.2f}"
        lines.append(f"| {r['role']} | {r['mean_recall']:.2f} (min {r['min_recall']:.2f}) | {r['expected_rule'] or 'n/a'} | {d} |")
    lines += ["", f"> {summary['caveat']}"]
    return "\n".join(lines)
