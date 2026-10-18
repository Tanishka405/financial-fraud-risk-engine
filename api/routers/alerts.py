from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Query

from api.errors import ApiError
from api.routers.data import tx_records
from api.schemas import NoteCreate, StatusUpdate
from api.state import SESSION, require_data
from api.util import MAX_PAGE_SIZE, check_sort, clean, iso, paginate
from core.detection.pipeline import SCORE_DISCLAIMER
from core.detection.rules import RULE_DESCRIPTIONS
from core.detection.pipeline import Alert
from api.cases import RESOLUTIONS, STATUSES, TRANSITIONS

router = APIRouter(prefix="/api")
SORTS = {"risk_score", "severity_rank", "account_id", "rule_score", "model_score", "last_activity_at", "status"}
_SEV = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _rows(s) -> pd.DataFrame:
    st = s.cases.statuses(s.meta.dataset_id)
    feats = s.result.account_features.set_index("account_id")
    rows = []
    for a in s.result.alerts:
        c = st.get(a.alert_id, {})
        rows.append({"alert_id": a.alert_id, "account_id": a.account_id, "severity": a.severity,
                     "severity_rank": _SEV[a.severity], "risk_score": a.risk_score, "rule_score": a.rule_score,
                     "model_score": a.model_score, "reason_codes": a.reason_codes, "summary": a.summary, "basis": a.basis,
                     "status": c.get("status", "open"), "resolution": c.get("resolution"),
                     "notes_count": c.get("notes", 0), "updated_at": c.get("updated_at"),
                     "last_activity_at": iso(feats.loc[a.account_id, "last_seen"]),
                     "generated_at": s.finished_at})
    return pd.DataFrame(rows)


@router.get("/alerts", tags=["alerts"])
def list_alerts(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=MAX_PAGE_SIZE),
                q: str | None = Query(None, max_length=100), severity: str | None = None, status: str | None = None,
                reason: str | None = None, account: str | None = None,
                sort: str = "risk_score", order: str = Query("desc", pattern="^(asc|desc)$")):
    s = require_data()
    check_sort(sort, SORTS)
    if severity and severity not in _SEV:
        raise ApiError(422, "INVALID_FILTER", f"Unknown severity {severity!r}.", {"allowed": list(_SEV)})
    if status and status not in STATUSES:
        raise ApiError(422, "INVALID_FILTER", f"Unknown status {status!r}.", {"allowed": list(STATUSES)})
    all_codes = set(RULE_DESCRIPTIONS) | {"MODEL_ANOMALY"}
    if reason and reason not in all_codes:
        raise ApiError(422, "INVALID_FILTER", f"Unknown reason code {reason!r}.", {"allowed": sorted(all_codes)})
    d = _rows(s)
    counts = {"severity": {}, "status": {}, "reason": {}}
    if len(d):
        counts["severity"] = d["severity"].value_counts().to_dict()
        counts["status"] = d["status"].value_counts().to_dict()
        counts["reason"] = d["reason_codes"].explode().value_counts().to_dict()
        if q:
            ql = q.strip().lower()
            d = d[d["account_id"].str.lower().str.contains(ql, regex=False) | d["alert_id"].str.lower().str.contains(ql, regex=False)
                  | d["summary"].str.lower().str.contains(ql, regex=False)]
        if severity: d = d[d["severity"] == severity]
        if status: d = d[d["status"] == status]
        if reason: d = d[d["reason_codes"].apply(lambda xs: reason in xs)]
        if account: d = d[d["account_id"] == account]
        d = d.sort_values([sort, "alert_id"], ascending=[order == "asc", True], kind="stable")
    part, meta = paginate(d, page, page_size)
    return {"items": clean(part.to_dict("records")), "meta": meta, "facets": clean(counts)}


def _get(s, alert_id: str) -> Alert:
    a = s.alerts_by_id.get(alert_id)
    if a is None:
        raise ApiError(404, "ALERT_NOT_FOUND", f"Alert {alert_id!r} does not exist in the loaded dataset.")
    return a


@router.get("/alerts/{alert_id}", tags=["alerts"])
def alert_detail(alert_id: str):
    s = require_data()
    a = _get(s, alert_id)
    r, v, det = s.result, s.view, s.det
    codes = sorted({h.rule_code for h in a.hits})
    best = {c: max(h.weight for h in a.hits if h.rule_code == c) for c in codes}
    ev_ids = list(dict.fromkeys(i for h in a.hits for i in h.transaction_ids))
    related = v[v["transaction_id"].isin(ev_ids)].sort_values("timestamp")
    acc = a.account_id
    mine = v[(v["sender_account_id"] == acc) | (v["receiver_account_id"] == acc)]
    scores = r.account_scores.set_index("account_id")
    cp: dict[str, dict] = {}
    for x in mine.itertuples():
        o = x.receiver_account_id if x.sender_account_id == acc else x.sender_account_id
        c = cp.setdefault(o, {"account_id": o, "txn_count": 0, "total_amount_inr": 0.0})
        c["txn_count"] += 1; c["total_amount_inr"] += x.amount_inr
    nb = sorted(cp.values(), key=lambda c: -c["total_amount_inr"])[:10]
    for c in nb:
        c["severity"] = scores.severity.get(c["account_id"]); c["has_alert"] = f"ALR-{c['account_id']}" in s.alerts_by_id
    feats = r.account_features[r.account_features["account_id"] == acc].iloc[0]
    case = s.cases.state(s.meta.dataset_id, alert_id)
    return clean({
        "alert_id": a.alert_id, "account_id": acc, "severity": a.severity, "risk_score": a.risk_score,
        "rule_score": a.rule_score, "model_score": a.model_score, "basis": a.basis, "reason_codes": a.reason_codes,
        "summary": a.summary, "generated_at": s.finished_at, "last_activity_at": iso(feats["last_seen"]),
        "is_synthetic_data": s.meta.is_synthetic,
        "explanation": {
            "disclaimer": SCORE_DISCLAIMER,
            "formula": (f"risk_score = {det.rule_share:g} x rule_score + {1 - det.rule_share:g} x model_score"
                        if a.model_score is not None else "risk_score = rule_score (model did not run)"),
            "rule_score_breakdown": [{"rule_code": c, "weight": w, "description": RULE_DESCRIPTIONS[c]} for c, w in best.items()],
            "model": {"model_score": a.model_score, "meaning": "Isolation Forest percentile among accounts in this dataset (relative)."},
            "severity_bands": {"critical": det.severity_critical, "high": det.severity_high, "medium": det.severity_medium}},
        "rule_matches": [{"rule_code": h.rule_code, "description": RULE_DESCRIPTIONS[h.rule_code], "role": h.role,
                          "weight": h.weight, "summary": h.summary, "transaction_ids": list(h.transaction_ids),
                          "metrics": h.metrics} for h in a.hits],
        "feature_deviations": a.feature_deviations,
        "account_features": {"txn_count_sent": feats["txn_count_sent"], "txn_count_received": feats["txn_count_received"],
                             "total_amount_sent_inr": feats["total_amount_sent"], "total_amount_received_inr": feats["total_amount_received"],
                             "unique_counterparties_sent": feats["unique_counterparties_sent"],
                             "max_daily_txn_count": feats["max_daily_txn_count"],
                             "inflow_outflow_ratio": feats["inflow_outflow_ratio"]},
        "related_transactions": tx_records(related.head(100)), "related_transactions_total": int(len(related)),
        "network_context": {"top_counterparties": nb},
        "case": {**case, "allowed_transitions": sorted(TRANSITIONS[case["status"]]), "resolutions": list(RESOLUTIONS)}})


@router.patch("/alerts/{alert_id}/status", tags=["alerts"])
def update_status(alert_id: str, body: StatusUpdate):
    s = require_data()
    _get(s, alert_id)
    cur = s.cases.state(s.meta.dataset_id, alert_id)["status"]
    if body.status == cur:
        raise ApiError(409, "NO_CHANGE", f"Alert is already {cur}.")
    if body.status not in TRANSITIONS[cur]:
        raise ApiError(409, "INVALID_TRANSITION", f"Cannot move from {cur} to {body.status}.", {"allowed": sorted(TRANSITIONS[cur])})
    if body.status == "closed" and body.resolution is None:
        raise ApiError(422, "RESOLUTION_REQUIRED", "Closing an alert requires a resolution.", {"allowed": list(RESOLUTIONS)})
    if body.status != "closed" and body.resolution is not None:
        raise ApiError(422, "RESOLUTION_NOT_ALLOWED", "A resolution is only valid when closing an alert.")
    return clean(s.cases.set_status(s.meta.dataset_id, alert_id, body.status, body.resolution))


@router.post("/alerts/{alert_id}/notes", status_code=201, tags=["alerts"])
def add_note(alert_id: str, body: NoteCreate):
    s = require_data()
    _get(s, alert_id)
    text = body.body.strip()
    if not text:
        raise ApiError(422, "VALIDATION_ERROR", "Note cannot be blank.")
    return clean(s.cases.add_note(s.meta.dataset_id, alert_id, text))
