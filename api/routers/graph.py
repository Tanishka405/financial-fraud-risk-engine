"""Bounded graph neighbourhoods. The core MultiDiGraph is the source of truth; edges are returned either
aggregated per ordered pair (count + total, flagged `aggregated`) or as individual transactions."""
from __future__ import annotations

from collections import defaultdict

import pandas as pd
from fastapi import APIRouter, Query

from api.errors import ApiError
from api.state import SESSION, require_data
from api.util import clean, iso, parse_ts

router = APIRouter(prefix="/api")
HARD_MAX_NODES, HARD_MAX_TXN_EDGES = 300, 1500


@router.get("/graph", tags=["graph"])
def graph(center: str | None = Query(None, max_length=64), depth: int = Query(1, ge=1, le=3),
          min_amount: float | None = Query(None, ge=0), date_from: str | None = Query(None, alias="from"),
          date_to: str | None = Query(None, alias="to"), mode: str = Query("aggregated", pattern="^(aggregated|transactions)$"),
          limit_nodes: int = Query(80, ge=5, le=HARD_MAX_NODES), only_flagged: bool = False):
    s = require_data()
    r, v = s.result, s.view
    scores = r.account_scores.set_index("account_id")
    gm = r.graph_metrics.set_index("account_id")
    t0, t1 = parse_ts(date_from, "from"), parse_ts(date_to, "to")
    m = pd.Series(True, index=v.index)
    if min_amount is not None:
        m &= v["amount_inr"] >= min_amount
    if t0 is not None:
        m &= v["timestamp"] >= t0
    if t1 is not None:
        m &= v["timestamp"] <= t1
    f = v[m]
    if center is not None and center not in set(r.account_features["account_id"]):
        raise ApiError(404, "ACCOUNT_NOT_FOUND", f"Account {center!r} does not exist in the loaded dataset.")

    nbr: dict[str, set] = defaultdict(set)
    for a, b in zip(f["sender_account_id"], f["receiver_account_id"]):
        nbr[a].add(b); nbr[b].add(a)
    deg = {k: len(x) for k, x in nbr.items()}
    truncated, scope_total = False, 0
    if center:
        chosen, frontier = [center], {center}
        seen = {center}
        for _ in range(depth):
            nxt = {n for a in frontier for n in nbr.get(a, ())} - seen
            room = limit_nodes - len(chosen)
            if len(nxt) > room:
                truncated = True
                nxt = set(sorted(nxt, key=lambda n: (-(scores.risk_score.get(n, 0) or 0), -deg.get(n, 0), n))[:max(room, 0)])
            chosen += sorted(nxt); seen |= nxt; frontier = nxt
            if not nxt:
                break
        scope_total = len(seen) if not truncated else len(seen) + 1  # lower bound when truncated
        node_ids = set(chosen)
    else:
        pool = list(nbr.keys())
        if only_flagged:
            pool = [a for a in pool if f"ALR-{a}" in s.alerts_by_id]
        scope_total = len(pool)
        ranked = sorted(pool, key=lambda a: (-(scores.risk_score.get(a, 0) or 0), -deg.get(a, 0), a))
        truncated = len(ranked) > limit_nodes
        node_ids = set(ranked[:limit_nodes])

    sub = f[f["sender_account_id"].isin(node_ids) & f["receiver_account_id"].isin(node_ids)]
    edges: list[dict] = []
    if mode == "aggregated":
        for (a, b), g in sub.groupby(["sender_account_id", "receiver_account_id"], sort=True):
            edges.append({"id": f"{a}>{b}", "source": a, "target": b, "aggregated": True, "txn_count": int(len(g)),
                          "total_amount_inr": round(float(g["amount_inr"].sum()), 2),
                          "min_amount_inr": float(g["amount_inr"].min()), "max_amount_inr": float(g["amount_inr"].max()),
                          "first_at": iso(g["timestamp"].min()), "last_at": iso(g["timestamp"].max()),
                          "transaction_ids": g["transaction_id"].tolist()[:20],
                          "flagged": bool(g["transaction_id"].isin(s.flagged.keys()).any())})
    else:
        if len(sub) > HARD_MAX_TXN_EDGES:
            sub = sub.sort_values("amount_inr", ascending=False).head(HARD_MAX_TXN_EDGES)
            truncated = True
        for x in sub.itertuples():
            edges.append({"id": x.transaction_id, "source": x.sender_account_id, "target": x.receiver_account_id,
                          "aggregated": False, "txn_count": 1, "total_amount_inr": x.amount_inr,
                          "transaction_ids": [x.transaction_id], "timestamp": iso(x.timestamp),
                          "transaction_type": x.transaction_type, "flagged": x.transaction_id in s.flagged})
    ids_in_edges = {e["source"] for e in edges} | {e["target"] for e in edges}
    nodes = []
    for a in sorted(node_ids):
        if not center and a not in ids_in_edges:
            continue
        al = s.alerts_by_id.get(f"ALR-{a}")
        sub_in, sub_out = sub[sub["receiver_account_id"] == a], sub[sub["sender_account_id"] == a]
        nodes.append({"id": a, "is_center": a == center, "risk_score": scores.risk_score.get(a), "severity": scores.severity.get(a),
                      "has_alert": al is not None, "reason_codes": al.reason_codes if al else [],
                      "degree_total": int(gm.in_degree.get(a, 0) + gm.out_degree.get(a, 0)),
                      "counterparties": int(gm.unique_counterparties_total.get(a, 0)),
                      "visible_in": int(len(sub_in)), "visible_out": int(len(sub_out)),
                      "visible_in_inr": round(float(sub_in["amount_inr"].sum()), 2),
                      "visible_out_inr": round(float(sub_out["amount_inr"].sum()), 2)})
    return clean({"mode": mode, "center": center, "depth": depth if center else None,
                  "nodes": nodes, "edges": edges,
                  "meta": {"node_count": len(nodes), "edge_count": len(edges),
                           "transactions_represented": int(len(sub)), "truncated": truncated,
                           "scope_nodes": scope_total, "limit_nodes": limit_nodes,
                           "max_transaction_edges": HARD_MAX_TXN_EDGES,
                           "note": ("Each edge is one ordered account pair summarising all its transactions."
                                    if mode == "aggregated" else "Each edge is one individual transaction (parallel edges preserved).")}})
