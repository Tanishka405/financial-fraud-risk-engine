"""Transparent, configurable AML-style rules.

Every rule returns `RuleHit`s carrying evidence (transaction ids + metrics +
a plain-language summary built from the *actual* triggering values). A rule
hit means "this account matches a pattern worth a human look" -- it is NOT
a finding of fraud. Rules never read synthetic scenario labels.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu

from core.detection.config import DetectionConfig

EVIDENCE_TXN_CAP = 50

RULE_DESCRIPTIONS: dict[str, str] = {
    "HIGH_VELOCITY": "Many outgoing transactions inside a short sliding window.",
    "LARGE_AMOUNT": "A single transaction far above an absolute or dataset-relative amount threshold.",
    "REPEATED_TRANSACTIONS": "The same sender paid the same receiver the same amount many times.",
    "HIGH_FANOUT": "One account sent funds to an unusually large number of distinct receivers.",
    "PASS_THROUGH": "Received funds were forwarded almost in full shortly afterwards, repeatedly.",
    "CIRCULAR_FLOW": "Funds moved through a short, time-ordered loop and returned to the origin account.",
    "LAYERED_MULTI_HOP": "Funds moved along a time-ordered chain of distinct accounts with little amount lost.",
    "STRUCTURING": "Several transactions each just below a reporting-style threshold, sent by one account within a short window.",
    "BEHAVIOURAL_CHANGE": "Sent amounts shifted sharply upward between the earlier and later half of the account's activity (rank test).",
}


@dataclass(frozen=True)
class RuleHit:
    rule_code: str
    account_id: str
    weight: float
    role: str
    summary: str
    transaction_ids: tuple[str, ...] = ()
    metrics: dict[str, Any] = field(default_factory=dict)


def _inr(x: float) -> str:
    return f"INR {x:,.2f}"


def _prep(tx: pd.DataFrame) -> pd.DataFrame:
    df = tx.sort_values("timestamp", kind="stable").reset_index(drop=True).copy()
    df["t_epoch"] = (df["timestamp"] - pd.Timestamp("1970-01-01", tz="UTC")).dt.total_seconds()
    return df


def _cap(ids) -> tuple[tuple[str, ...], bool]:
    ids = list(ids)
    return tuple(ids[:EVIDENCE_TXN_CAP]), len(ids) > EVIDENCE_TXN_CAP


# ---------------------------------------------------------------- simple rules
def rule_high_velocity(df: pd.DataFrame, cfg: DetectionConfig) -> list[RuleHit]:
    hits: list[RuleHit] = []
    w = cfg.rule_weights["HIGH_VELOCITY"]
    win = cfg.velocity_window_minutes * 60.0
    for sender, g in df.groupby("sender_account_id", sort=True):
        if len(g) < cfg.velocity_min_txns:
            continue
        t = g["t_epoch"].to_numpy()
        j = np.searchsorted(t, t + win, side="right")
        counts = j - np.arange(len(t))
        i = int(np.argmax(counts))
        if counts[i] >= cfg.velocity_min_txns:
            ids, trunc = _cap(g["transaction_id"].iloc[i:j[i]])
            amt = float(g["amount_inr"].iloc[i:j[i]].sum())
            hits.append(RuleHit(
                "HIGH_VELOCITY", sender, w, "sender",
                f"{int(counts[i])} outgoing transactions within {cfg.velocity_window_minutes} minutes "
                f"(threshold {cfg.velocity_min_txns}), totalling {_inr(amt)}.",
                ids, {"txns_in_window": int(counts[i]), "window_minutes": cfg.velocity_window_minutes,
                      "total_amount_inr": round(amt, 2), "evidence_truncated": trunc,
                      "threshold": cfg.velocity_min_txns}))
    return hits


def rule_large_amount(df: pd.DataFrame, cfg: DetectionConfig) -> list[RuleHit]:
    if df.empty:
        return []
    thr = cfg.large_amount_inr
    basis = f"absolute threshold {_inr(cfg.large_amount_inr)}"
    p99 = None
    if len(df) >= cfg.large_amount_min_dataset_size:
        p99 = float(np.percentile(df["amount_inr"], 99))
        rel = p99 * cfg.large_amount_p99_multiple
        if rel < thr:
            thr, basis = rel, f"{cfg.large_amount_p99_multiple:g} x dataset 99th percentile ({_inr(p99)})"
    w = cfg.rule_weights["LARGE_AMOUNT"]
    hits = []
    for r in df[df["amount_inr"] >= thr].itertuples(index=False):
        m = {"amount_inr": float(r.amount_inr), "threshold_inr": round(float(thr), 2), "basis": basis,
             "dataset_p99_inr": None if p99 is None else round(p99, 2)}
        s = f"Transaction {r.transaction_id} of {_inr(r.amount_inr)} meets the {basis} ({_inr(thr)})."
        hits.append(RuleHit("LARGE_AMOUNT", r.sender_account_id, w, "sender", s, (r.transaction_id,), m))
        hits.append(RuleHit("LARGE_AMOUNT", r.receiver_account_id, w * cfg.receiver_weight_factor, "receiver", s,
                            (r.transaction_id,), m))
    return hits


def rule_repeated(df: pd.DataFrame, cfg: DetectionConfig) -> list[RuleHit]:
    hits = []
    w = cfg.rule_weights["REPEATED_TRANSACTIONS"]
    grp = df.groupby(["sender_account_id", "receiver_account_id", "amount_inr"], sort=True)
    for (s, r, a), g in grp:
        if len(g) >= cfg.repeated_min_count:
            ids, trunc = _cap(g["transaction_id"])
            span_h = (g["t_epoch"].max() - g["t_epoch"].min()) / 3600.0
            m = {"count": int(len(g)), "amount_inr": float(a), "span_hours": round(float(span_h), 2),
                 "threshold": cfg.repeated_min_count, "evidence_truncated": trunc}
            txt = (f"{len(g)} transactions of {_inr(a)} from {s} to {r} over {span_h:.1f} hours "
                   f"(threshold {cfg.repeated_min_count}).")
            hits.append(RuleHit("REPEATED_TRANSACTIONS", s, w, "sender", txt, ids, m))
            hits.append(RuleHit("REPEATED_TRANSACTIONS", r, w * cfg.receiver_weight_factor, "receiver", txt, ids, m))
    return hits


def rule_structuring(df: pd.DataFrame, cfg: DetectionConfig) -> list[RuleHit]:
    """Adapted from the AML-Network-Graph-Engine prototype's structuring concept, with two fixes: the band is
    bounded BELOW (an ordinary small payment is not 'just under' a threshold) and evidence is returned.
    Amounts at or above the threshold are never counted."""
    hits: list[RuleHit] = []
    w = cfg.rule_weights["STRUCTURING"]
    thr = cfg.structuring_threshold_inr
    lo = thr * cfg.structuring_band_floor
    band = df[(df["amount_inr"] >= lo) & (df["amount_inr"] < thr)]
    win = cfg.structuring_window_minutes * 60.0
    for sender, g in band.groupby("sender_account_id", sort=True):
        if len(g) < cfg.structuring_min_txns:
            continue
        t = g["t_epoch"].to_numpy()
        j = np.searchsorted(t, t + win, side="right")
        counts = j - np.arange(len(t))
        i = int(np.argmax(counts))
        if counts[i] >= cfg.structuring_min_txns:
            sub = g.iloc[i:j[i]]
            ids, trunc = _cap(sub["transaction_id"])
            agg = float(sub["amount_inr"].sum())
            m = {"txns_in_window": int(counts[i]), "aggregate_inr": round(agg, 2), "threshold_inr": thr,
                 "band_floor_inr": round(lo, 2), "window_minutes": cfg.structuring_window_minutes,
                 "distinct_receivers": int(sub["receiver_account_id"].nunique()),
                 "min_txns_threshold": cfg.structuring_min_txns, "evidence_truncated": trunc}
            hits.append(RuleHit(
                "STRUCTURING", sender, w, "sender",
                f"{int(counts[i])} transactions each between {_inr(lo)} and {_inr(thr)} (just below the {_inr(thr)} threshold) "
                f"within {cfg.structuring_window_minutes} minutes, totalling {_inr(agg)} (threshold {cfg.structuring_min_txns}).",
                ids, m))
    return hits


def rule_high_fanout(df: pd.DataFrame, cfg: DetectionConfig) -> list[RuleHit]:
    hits = []
    w = cfg.rule_weights["HIGH_FANOUT"]
    for sender, g in df.groupby("sender_account_id", sort=True):
        n = g["receiver_account_id"].nunique()
        if n >= cfg.fanout_min_receivers:
            ids, trunc = _cap(g["transaction_id"])
            m = {"unique_receivers": int(n), "txn_count": int(len(g)), "threshold": cfg.fanout_min_receivers,
                 "total_amount_inr": round(float(g["amount_inr"].sum()), 2), "evidence_truncated": trunc}
            hits.append(RuleHit("HIGH_FANOUT", sender, w, "sender",
                                f"Sent to {n} distinct receivers across {len(g)} transactions "
                                f"(threshold {cfg.fanout_min_receivers}).", ids, m))
    return hits


def rule_pass_through(df: pd.DataFrame, cfg: DetectionConfig) -> list[RuleHit]:
    hits = []
    w = cfg.rule_weights["PASS_THROUGH"]
    win = cfg.pass_through_window_minutes * 60.0
    ins = {k: g for k, g in df.groupby("receiver_account_id", sort=True)}
    outs = {k: g for k, g in df.groupby("sender_account_id", sort=True)}
    for acc in sorted(set(ins) & set(outs)):
        gi, go = ins[acc], outs[acc]
        if len(gi) > 5000 or len(go) > 5000:
            continue  # performance safeguard
        out_t = go["t_epoch"].to_numpy(); out_a = go["amount_inr"].to_numpy(); out_id = go["transaction_id"].to_numpy()
        used = np.zeros(len(go), dtype=bool)
        pairs = []
        for r in gi.itertuples(index=False):
            lo = np.searchsorted(out_t, r.t_epoch, side="right")  # strictly after the inflow
            hi = np.searchsorted(out_t, r.t_epoch + win, side="right")
            for k in range(lo, hi):
                if used[k]:
                    continue
                ratio = out_a[k] / r.amount_inr
                if cfg.pass_through_min_retention <= ratio <= cfg.pass_through_max_retention:
                    used[k] = True
                    pairs.append((r.transaction_id, str(out_id[k]), float(r.amount_inr), float(out_a[k]),
                                  float((out_t[k] - r.t_epoch) / 60.0)))
                    break
        if len(pairs) >= cfg.pass_through_min_pairs:
            ids, trunc = _cap([x for p in pairs for x in p[:2]])
            avg_ret = float(np.mean([p[3] / p[2] for p in pairs]))
            m = {"matched_pairs": len(pairs), "avg_retention": round(avg_ret, 4),
                 "max_delay_minutes": round(max(p[4] for p in pairs), 1),
                 "window_minutes": cfg.pass_through_window_minutes,
                 "threshold_pairs": cfg.pass_through_min_pairs, "evidence_truncated": trunc}
            hits.append(RuleHit("PASS_THROUGH", acc, w, "intermediary",
                                f"{len(pairs)} inflows were forwarded onward within "
                                f"{cfg.pass_through_window_minutes} minutes keeping on average "
                                f"{avg_ret*100:.1f}% of the amount (threshold {cfg.pass_through_min_pairs} pairs).",
                                ids, m))
    return hits


# ------------------------------------------------------------ temporal flows
class _FlowSearch:
    """Time-ordered, amount-preserving path search over transactions."""

    def __init__(self, df: pd.DataFrame, cfg: DetectionConfig):
        self.cfg = cfg
        self.t = df["t_epoch"].to_numpy()
        self.a = df["amount_inr"].to_numpy()
        self.s = df["sender_account_id"].to_numpy()
        self.r = df["receiver_account_id"].to_numpy()
        self.id = df["transaction_id"].to_numpy()
        by: dict[str, list[int]] = defaultdict(list)
        for i, snd in enumerate(self.s):
            by[snd].append(i)  # df is time-sorted, so each list is time-sorted
        self.by_sender = {k: np.array(v) for k, v in by.items()}
        self.by_sender_t = {k: self.t[v] for k, v in self.by_sender.items()}
        self.expansions = 0

    def _next(self, node: str, after_t: float, until_t: float, prev_amt: float):
        idx = self.by_sender.get(node)
        if idx is None:
            return []
        ts = self.by_sender_t[node]
        lo = np.searchsorted(ts, after_t, side="right")
        hi = np.searchsorted(ts, until_t, side="right")
        out = []
        for i in idx[lo:hi]:
            ratio = self.a[i] / prev_amt
            if self.cfg.flow_min_retention <= ratio <= self.cfg.flow_max_retention:
                out.append(int(i))
        return out

    def cycles(self) -> list[list[int]]:
        cfg, found, seen = self.cfg, [], set()
        win = cfg.cycle_window_hours * 3600.0

        def dfs(path: list[int], t0: float):
            if len(found) >= cfg.max_flow_results or self.expansions > cfg.max_flow_expansions:
                return
            last = path[-1]
            origin = self.s[path[0]]
            for i in self._next(self.r[last], self.t[last], t0 + win, self.a[last]):
                self.expansions += 1
                n_edges = len(path) + 1
                if self.r[i] == origin:
                    if n_edges >= cfg.cycle_min_length:
                        key = frozenset(self.id[j] for j in path + [i])
                        if key not in seen:
                            seen.add(key); found.append(path + [i])
                elif n_edges < cfg.cycle_max_length and self.r[i] not in {self.s[j] for j in path}:
                    dfs(path + [i], t0)

        for i0 in range(len(self.t)):
            dfs([i0], self.t[i0])
            if len(found) >= cfg.max_flow_results or self.expansions > cfg.max_flow_expansions:
                break
        return found

    def chains(self) -> list[list[int]]:
        cfg, found = self.cfg, []
        win = cfg.layered_window_hours * 3600.0

        def dfs(path: list[int], t0: float, visited: set):
            if len(found) >= cfg.max_flow_results * 4 or self.expansions > cfg.max_flow_expansions:
                return
            if len(path) >= cfg.layered_min_hops:
                found.append(path)
            if len(path) >= cfg.layered_max_hops:
                return
            last = path[-1]
            for i in self._next(self.r[last], self.t[last], t0 + win, self.a[last]):
                self.expansions += 1
                if self.r[i] not in visited:
                    dfs(path + [i], t0, visited | {self.r[i]})

        for i0 in range(len(self.t)):
            dfs([i0], self.t[i0], {self.s[i0], self.r[i0]})
            if self.expansions > cfg.max_flow_expansions:
                break
        sets = [frozenset(self.id[j] for j in p) for p in found]
        keep = [p for p, s in zip(found, sets) if not any(s < o for o in sets)]
        uniq, seen = [], set()
        for p in keep:
            k = frozenset(self.id[j] for j in p)
            if k not in seen:
                seen.add(k); uniq.append(p)
        return uniq[: cfg.max_flow_results]


def rule_flows(df: pd.DataFrame, cfg: DetectionConfig) -> list[RuleHit]:
    if df.empty:
        return []
    fs = _FlowSearch(df, cfg)
    hits: list[RuleHit] = []
    wc, wl = cfg.rule_weights["CIRCULAR_FLOW"], cfg.rule_weights["LAYERED_MULTI_HOP"]
    for path in fs.cycles():
        accts = [fs.s[j] for j in path]
        ids = tuple(str(fs.id[j]) for j in path)
        span_h = (fs.t[path[-1]] - fs.t[path[0]]) / 3600.0
        loop = " -> ".join(accts + [accts[0]])
        m = {"length": len(path), "span_hours": round(float(span_h), 2), "loop": loop,
             "amounts_inr": [round(float(fs.a[j]), 2) for j in path], "window_hours": cfg.cycle_window_hours}
        txt = (f"Time-ordered loop {loop} over {span_h:.1f} hours; each hop kept "
               f"{cfg.flow_min_retention*100:.0f}-{cfg.flow_max_retention*100:.0f}% of the previous amount.")
        for acc in accts:
            hits.append(RuleHit("CIRCULAR_FLOW", acc, wc, "participant", txt, ids, m))
    for path in fs.chains():
        accts = [fs.s[j] for j in path] + [fs.r[path[-1]]]
        ids = tuple(str(fs.id[j]) for j in path)
        span_h = (fs.t[path[-1]] - fs.t[path[0]]) / 3600.0
        chain = " -> ".join(accts)
        m = {"hops": len(path), "span_hours": round(float(span_h), 2), "chain": chain,
             "amounts_inr": [round(float(fs.a[j]), 2) for j in path], "window_hours": cfg.layered_window_hours}
        txt = (f"{len(path)}-hop time-ordered chain {chain} over {span_h:.1f} hours "
               f"with amounts {_inr(fs.a[path[0]])} -> {_inr(fs.a[path[-1]])}.")
        for pos, acc in enumerate(accts):
            end = pos in (0, len(accts) - 1)
            hits.append(RuleHit("LAYERED_MULTI_HOP", acc, wl * (cfg.receiver_weight_factor if end else 1.0),
                                "endpoint" if end else "intermediary", txt, ids, m))
    return hits


def rule_behaviour_change(df: pd.DataFrame, cfg: DetectionConfig) -> list[RuleHit]:
    hits = []
    w = cfg.rule_weights["BEHAVIOURAL_CHANGE"]
    for sender, g in df.groupby("sender_account_id", sort=True):
        if len(g) < cfg.behaviour_min_txns:
            continue
        mid = (g["t_epoch"].min() + g["t_epoch"].max()) / 2.0
        a, b = g[g["t_epoch"] <= mid], g[g["t_epoch"] > mid]
        if len(a) < cfg.behaviour_min_per_half or len(b) < cfg.behaviour_min_per_half:
            continue
        ma, mb = float(a["amount_inr"].median()), float(b["amount_inr"].median())
        if ma <= 0 or mb / ma < cfg.behaviour_median_ratio:
            continue
        # One-sided rank test: are later amounts stochastically larger? (distribution-free)
        p_val = float(mannwhitneyu(b["amount_inr"], a["amount_inr"], alternative="greater").pvalue)
        if p_val <= cfg.behaviour_p_value:
            ids, trunc = _cap(b["transaction_id"])
            m = {"median_first_half_inr": round(ma, 2), "median_second_half_inr": round(mb, 2),
                 "median_ratio": round(mb / ma, 2), "p_value": p_val, "txns_first_half": int(len(a)),
                 "txns_second_half": int(len(b)), "threshold_median_ratio": cfg.behaviour_median_ratio,
                 "threshold_p_value": cfg.behaviour_p_value, "evidence_truncated": trunc}
            hits.append(RuleHit("BEHAVIOURAL_CHANGE", sender, w, "sender",
                                f"Median sent amount rose from {_inr(ma)} ({len(a)} txns) to {_inr(mb)} ({len(b)} txns), "
                                f"x{mb/ma:.1f}; one-sided Mann-Whitney p={p_val:.2g} (thresholds x{cfg.behaviour_median_ratio:g}, "
                                f"p<={cfg.behaviour_p_value:g}).", ids, m))
    return hits


def run_rules(transactions: pd.DataFrame, cfg: DetectionConfig) -> list[RuleHit]:
    """Run every rule on a canonical transaction DataFrame. Deterministic."""
    if transactions.empty:
        return []
    df = _prep(transactions)
    hits: list[RuleHit] = []
    for fn in (rule_high_velocity, rule_large_amount, rule_repeated, rule_structuring, rule_high_fanout,
               rule_pass_through, rule_flows, rule_behaviour_change):
        hits.extend(fn(df, cfg))
    return hits
