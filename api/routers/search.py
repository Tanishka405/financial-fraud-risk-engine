from __future__ import annotations

from fastapi import APIRouter, Query

from api.state import SESSION
from api.util import clean, iso

router = APIRouter(prefix="/api")


@router.get("/search", tags=["search"])
def search(q: str = Query(..., min_length=1, max_length=100), limit: int = Query(5, ge=1, le=20)):
    s = SESSION
    if s.result is None:
        return {"q": q, "accounts": [], "transactions": [], "alerts": []}
    ql, r, v = q.strip().lower(), s.result, s.view
    sc = r.account_scores.set_index("account_id")
    accts = [a for a in sc.index if ql in a.lower()]
    accts.sort(key=lambda a: (not a.lower().startswith(ql), -sc.risk_score[a], a))
    tx = v[v["transaction_id"].str.lower().str.contains(ql, regex=False)].head(limit)
    al = [a for a in r.alerts if ql in a.alert_id.lower() or ql in a.account_id.lower()][:limit]
    return clean({"q": q,
                  "accounts": [{"account_id": a, "risk_score": sc.risk_score[a], "severity": sc.severity[a]} for a in accts[:limit]],
                  "transactions": [{"transaction_id": t.transaction_id, "sender_account_id": t.sender_account_id,
                                    "receiver_account_id": t.receiver_account_id, "amount_inr": t.amount_inr} for t in tx.itertuples()],
                  "alerts": [{"alert_id": a.alert_id, "account_id": a.account_id, "severity": a.severity, "risk_score": a.risk_score} for a in al]})
