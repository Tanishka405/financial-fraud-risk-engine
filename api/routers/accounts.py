from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Query

from api.errors import ApiError
from api.routers.data import tx_records
from api.state import SESSION, require_data
from api.util import MAX_PAGE_SIZE, check_sort, clean, iso, paginate
from core.detection.rules import RULE_DESCRIPTIONS

router = APIRouter(prefix="/api")

ACC_SORTS = {"risk_score", "account_id", "txn_count", "total_amount_inr", "counterparties", "severity_rank"}
_SEV_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _table(s) -> pd.DataFrame:
    r = s.result
    f = r.account_features.set_index("account_id")
    g = r.graph_metrics.set_index("account_id")
    sc = r.account_scores.set_index("account_id")
    d = pd.DataFrame(index=f.index)
    d["txn_count"] = f["txn_count_sent"] + f["txn_count_received"]
    d["txn_count_sent"], d["txn_count_received"] = f["txn_count_sent"], f["txn_count_received"]
    d["total_amount_inr"] = f["total_amount_sent"] + f["total_amount_received"]
    d["counterparties"] = g["unique_counterparties_total"]
    d = d.join(sc[["rule_score", "model_score", "risk_score", "severity", "n_rules"]])
    d["severity_rank"] = d["severity"].map(_SEV_RANK)
    d["alert_id"] = [f"ALR-{a}" if f"ALR-{a}" in s.alerts_by_id else None for a in d.index]
    return d.reset_index()


GA_NOTE = ("Structural metrics computed from the whole dataset's transaction graph. They describe position in the network "
           "and are NOT risk signals: they are excluded from the risk score and, by default, from the model.")


def _ga_block(s, account_id: str):
    """Additive block; None when graph analytics were unavailable for this dataset."""
    if s.ga_nodes is None or account_id not in s.ga_nodes.index:
        return None
    r = s.ga_nodes.loc[account_id]
    ga = s.result.graph_analytics
    return clean({"pagerank": r["pagerank"], "pagerank_percentile": r["pagerank_percentile"],
                  "betweenness": r["betweenness"], "betweenness_percentile": r["betweenness_percentile"],
                  "community_id": int(r["community_id"]), "community_size": int(r["community_size"]),
                  "n_communities": int(len(ga.communities)), "modularity": ga.modularity,
                  "betweenness_method": ga.betweenness_method, "note": GA_NOTE})


@router.get("/accounts", tags=["accounts"])
def list_accounts(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=MAX_PAGE_SIZE),
                  q: str | None = Query(None, max_length=100), severity: str | None = None, has_alert: bool | None = None,
                  sort: str = "risk_score", order: str = Query("desc", pattern="^(asc|desc)$")):
    s = require_data()
    check_sort(sort, ACC_SORTS)
    if severity and severity not in _SEV_RANK:
        raise ApiError(422, "INVALID_FILTER", f"Unknown severity {severity!r}.", {"allowed": list(_SEV_RANK)})
    d = _table(s)
    if q:
        d = d[d["account_id"].str.lower().str.contains(q.strip().lower(), regex=False)]
    if severity:
        d = d[d["severity"] == severity]
    if has_alert is not None:
        d = d[d["alert_id"].notna() == has_alert]
    d = d.sort_values([sort, "account_id"], ascending=[order == "asc", True], kind="stable")
    part, meta = paginate(d, page, page_size)
    return {"items": clean(part.to_dict("records")), "meta": meta}


@router.get("/accounts/{account_id}", tags=["accounts"])
def account_detail(account_id: str):
    s = require_data()
    r, v = s.result, s.view
    f = r.account_features[r.account_features["account_id"] == account_id]
    if f.empty:
        raise ApiError(404, "ACCOUNT_NOT_FOUND", f"Account {account_id!r} does not exist in the loaded dataset.")
    f = f.iloc[0].to_dict()
    g = r.graph_metrics[r.graph_metrics["account_id"] == account_id].iloc[0].to_dict()
    sc = r.account_scores[r.account_scores["account_id"] == account_id].iloc[0].to_dict()
    mine = v[(v["sender_account_id"] == account_id) | (v["receiver_account_id"] == account_id)]
    span = v["timestamp"].max() - v["timestamp"].min()
    freq = "1h" if span < pd.Timedelta(days=3) else "1D"
    sent, recv = mine[mine["sender_account_id"] == account_id], mine[mine["receiver_account_id"] == account_id]
    idx = mine.set_index("timestamp")
    tl = pd.DataFrame({
        "sent_count": sent.set_index("timestamp")["amount_inr"].resample(freq).count(),
        "sent_amount_inr": sent.set_index("timestamp")["amount_inr"].resample(freq).sum(),
        "received_count": recv.set_index("timestamp")["amount_inr"].resample(freq).count(),
        "received_amount_inr": recv.set_index("timestamp")["amount_inr"].resample(freq).sum()}).fillna(0).reset_index()
    cp = {}
    for x in sent.itertuples():
        c = cp.setdefault(x.receiver_account_id, {"account_id": x.receiver_account_id, "sent_count": 0, "sent_amount_inr": 0.0, "received_count": 0, "received_amount_inr": 0.0})
        c["sent_count"] += 1; c["sent_amount_inr"] += x.amount_inr
    for x in recv.itertuples():
        c = cp.setdefault(x.sender_account_id, {"account_id": x.sender_account_id, "sent_count": 0, "sent_amount_inr": 0.0, "received_count": 0, "received_amount_inr": 0.0})
        c["received_count"] += 1; c["received_amount_inr"] += x.amount_inr
    cps = sorted(cp.values(), key=lambda c: -(c["sent_amount_inr"] + c["received_amount_inr"]))[:12]
    scores = r.account_scores.set_index("account_id")["severity"]
    for c in cps:
        c["severity"] = scores.get(c["account_id"])
        c["has_alert"] = f"ALR-{c['account_id']}" in s.alerts_by_id
    alert = s.alerts_by_id.get(f"ALR-{account_id}")
    hits = [{"rule_code": h.rule_code, "description": RULE_DESCRIPTIONS[h.rule_code], "role": h.role, "weight": h.weight,
             "summary": h.summary, "transaction_ids": list(h.transaction_ids), "metrics": h.metrics}
            for h in (alert.hits if alert else [])]
    return clean({
        "account_id": account_id,
        "observed": {  # facts read straight from the transactions
            "txn_count_sent": f["txn_count_sent"], "txn_count_received": f["txn_count_received"],
            "total_amount_sent_inr": f["total_amount_sent"], "total_amount_received_inr": f["total_amount_received"],
            "first_seen": iso(f["first_seen"]), "last_seen": iso(f["last_seen"])},
        "computed_features": {  # derived statistics (core.features)
            "avg_amount_sent_inr": f["avg_amount_sent"], "avg_amount_received_inr": f["avg_amount_received"],
            "unique_counterparties_sent": f["unique_counterparties_sent"],
            "unique_counterparties_received": f["unique_counterparties_received"],
            "inflow_outflow_ratio": f["inflow_outflow_ratio"],
            "inflow_outflow_ratio_note": "Pure sink (no outflow)" if f["inflow_outflow_ratio"] == float("inf") else None,
            "active_days": f["active_days"], "max_daily_txn_count": f["max_daily_txn_count"]},
        "graph_metrics": {k: g[k] for k in g if k not in ("account_id", "inflow_outflow_ratio")},
        "scores": {"rule_score": sc["rule_score"], "model_score": sc["model_score"], "risk_score": sc["risk_score"],
                   "severity": sc["severity"]},
        "graph_analytics": _ga_block(s, account_id),
        "rule_matches": hits,
        "model_signal": {"model_score": sc["model_score"], "feature_deviations": alert.feature_deviations if alert else [],
                         "note": "Isolation Forest percentile within this dataset (relative, not a probability). "
                                 "Feature deviations are descriptive robust z-scores, not model attributions."},
        "alert": {"alert_id": alert.alert_id, "severity": alert.severity,
                  "status": s.cases.state(s.meta.dataset_id, alert.alert_id)["status"]} if alert else None,
        "timeline": {"bucket": "hour" if freq == "1h" else "day",
                     "points": [{"t": iso(x["timestamp"]), **{k: x[k] for k in tl.columns if k != "timestamp"}} for _, x in tl.iterrows()]},
        "top_counterparties": cps,
        "recent_transactions": tx_records(mine.sort_values("timestamp", ascending=False).head(25)),
    })
