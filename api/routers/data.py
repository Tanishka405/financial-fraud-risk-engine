from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Query

from api.errors import ApiError
from api.schemas import TransactionPage
from api.state import SESSION, require_data
from api.util import MAX_PAGE_SIZE, check_sort, clean, iso, paginate, parse_ts

router = APIRouter(prefix="/api")

TX_SORTS = {"timestamp", "amount_inr", "transaction_id", "sender_account_id", "receiver_account_id", "transaction_type",
            "sender_risk", "receiver_risk"}


def tx_records(df: pd.DataFrame) -> list[dict]:
    out = []
    for r in df.to_dict("records"):
        out.append(clean({
            "transaction_id": r["transaction_id"], "sender_account_id": r["sender_account_id"],
            "receiver_account_id": r["receiver_account_id"], "amount_inr": r["amount_inr"],
            "timestamp": iso(r["timestamp"]), "transaction_type": r["transaction_type"],
            "sender_risk": r.get("sender_risk"), "receiver_risk": r.get("receiver_risk"),
            "flagged_rules": SESSION.flagged.get(r["transaction_id"], [])}))
    return out


def _time_series(view: pd.DataFrame) -> dict:
    if view.empty:
        return {"bucket": "day", "points": []}
    span = view["timestamp"].max() - view["timestamp"].min()
    bucket = "hour" if span < pd.Timedelta(days=3) else "day"
    g = view.set_index("timestamp").resample("1h" if bucket == "hour" else "1D")["amount_inr"].agg(["count", "sum"])
    return {"bucket": bucket, "points": [{"t": iso(t), "count": int(r["count"]), "value_inr": round(float(r["sum"]), 2)}
                                          for t, r in g.iterrows()]}


@router.get("/dataset/summary", tags=["dataset"])
def summary():
    s = require_data()
    r, v = s.result, s.view
    sc = r.account_scores
    feats = r.account_features.set_index("account_id")
    alert_by = {a.account_id: a for a in r.alerts}
    sev = {k: 0 for k in ("critical", "high", "medium", "low")}
    for a in r.alerts:
        sev[a.severity] += 1

    def acc_row(aid):
        f, a = feats.loc[aid], alert_by.get(aid)
        srow = sc.set_index("account_id").loc[aid]
        return {"account_id": aid, "risk_score": clean(srow["risk_score"]), "severity": srow["severity"],
                "txn_count": int(f["txn_count_sent"] + f["txn_count_received"]),
                "total_amount_inr": clean(f["total_amount_sent"] + f["total_amount_received"]),
                "alert_id": a.alert_id if a else None}

    top_risk = sc.sort_values(["risk_score", "account_id"], ascending=[False, True]).head(8)["account_id"].tolist()
    active = (feats["txn_count_sent"] + feats["txn_count_received"]).sort_values(ascending=False).head(8).index.tolist()
    last_act = {aid: iso(feats.loc[aid, "last_seen"]) for aid in feats.index}
    recent = sorted(r.alerts, key=lambda a: last_act.get(a.account_id) or "", reverse=True)[:6]
    by_type = v.groupby("transaction_type")["amount_inr"].agg(["count", "sum"]).reset_index()
    return clean({
        "kpis": {"total_transactions": len(v), "total_accounts": len(feats),
                 "total_value_inr": round(float(v["amount_inr"].sum()), 2),
                 "suspicious_accounts": len(alert_by), "alerts": len(r.alerts),
                 "rejected_records": s.meta.rejected},
        "severity_distribution": sev,
        "account_severity_distribution": sc["severity"].value_counts().to_dict(),
        "time_series": _time_series(v),
        "by_type": [{"transaction_type": x.transaction_type, "count": x["count"], "value_inr": round(float(x["sum"]), 2)}
                    for _, x in by_type.iterrows()],
        "top_risk_accounts": [acc_row(a) for a in top_risk],
        "most_active_accounts": [acc_row(a) for a in active],
        "recent_alerts": [{"alert_id": a.alert_id, "account_id": a.account_id, "severity": a.severity,
                           "risk_score": a.risk_score, "reason_codes": a.reason_codes, "summary": a.summary,
                           "last_activity_at": last_act.get(a.account_id),
                           "max_evidence_amount_inr": max([h.metrics.get("amount_inr", 0) or 0 for h in a.hits] + [0]) or None}
                          for a in recent],
        "model_ran": r.model_ran, "notes": r.notes})


@router.get("/transactions", response_model=TransactionPage, tags=["transactions"])
def list_transactions(
    page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=MAX_PAGE_SIZE),
    q: str | None = Query(None, max_length=100), account: str | None = None, sender: str | None = None,
    receiver: str | None = None, transaction_type: str | None = None,
    min_amount: float | None = Query(None, ge=0), max_amount: float | None = Query(None, ge=0),
    date_from: str | None = Query(None, alias="from"), date_to: str | None = Query(None, alias="to"),
    flagged: bool | None = None, sort: str = "timestamp", order: str = Query("desc", pattern="^(asc|desc)$"),
):
    v = require_data().view
    check_sort(sort, TX_SORTS)
    if min_amount is not None and max_amount is not None and min_amount > max_amount:
        raise ApiError(422, "INVALID_FILTER", "min_amount cannot exceed max_amount.", {"field": "min_amount"})
    t0, t1 = parse_ts(date_from, "from"), parse_ts(date_to, "to")
    if t0 is not None and t1 is not None and t0 > t1:
        raise ApiError(422, "INVALID_FILTER", "'from' must not be after 'to'.", {"field": "from"})
    m = pd.Series(True, index=v.index)
    if q:
        ql = q.strip().lower()
        m &= (v["transaction_id"].str.lower().str.contains(ql, regex=False) |
              v["sender_account_id"].str.lower().str.contains(ql, regex=False) |
              v["receiver_account_id"].str.lower().str.contains(ql, regex=False))
    if account:
        m &= (v["sender_account_id"] == account) | (v["receiver_account_id"] == account)
    if sender:
        m &= v["sender_account_id"] == sender
    if receiver:
        m &= v["receiver_account_id"] == receiver
    if transaction_type:
        allowed = set(SESSION.config.allowed_transaction_types)
        if transaction_type.upper() not in allowed:
            raise ApiError(422, "INVALID_FILTER", f"Unknown transaction_type {transaction_type!r}.", {"allowed": sorted(allowed)})
        m &= v["transaction_type"] == transaction_type.upper()
    if min_amount is not None:
        m &= v["amount_inr"] >= min_amount
    if max_amount is not None:
        m &= v["amount_inr"] <= max_amount
    if t0 is not None:
        m &= v["timestamp"] >= t0
    if t1 is not None:
        m &= v["timestamp"] <= t1
    if flagged is not None:
        isf = v["transaction_id"].isin(SESSION.flagged.keys())
        m &= isf if flagged else ~isf
    f = v[m].sort_values([sort, "transaction_id"], ascending=[order == "asc", True], kind="stable")
    part, meta = paginate(f, page, page_size)
    return {"items": tx_records(part), "meta": meta}


@router.get("/transactions/{transaction_id}", tags=["transactions"])
def transaction_detail(transaction_id: str):
    s = require_data()
    v = s.view
    row = v[v["transaction_id"] == transaction_id]
    if row.empty:
        raise ApiError(404, "TRANSACTION_NOT_FOUND", f"Transaction {transaction_id!r} does not exist.")
    t = row.iloc[0]
    pair = v[(v["sender_account_id"] == t.sender_account_id) & (v["receiver_account_id"] == t.receiver_account_id)]
    rules = s.flagged.get(transaction_id, [])
    alerts = [a.alert_id for a in s.result.alerts if transaction_id in {i for h in a.hits for i in h.transaction_ids}]
    sender_recent = v[(v["sender_account_id"] == t.sender_account_id) & (v["transaction_id"] != transaction_id)]
    return clean({
        "transaction": tx_records(row)[0],
        "same_pair": {"count": len(pair), "total_amount_inr": round(float(pair["amount_inr"].sum()), 2),
                      "others": tx_records(pair[pair["transaction_id"] != transaction_id].tail(10))},
        "flagged_rules": rules, "related_alert_ids": alerts,
        "sender_nearby": tx_records(sender_recent.iloc[(sender_recent["timestamp"] - t.timestamp).abs().argsort()[:5]]),
        "note": "Risk values are those of the sender/receiver accounts, not of this transaction alone."})
