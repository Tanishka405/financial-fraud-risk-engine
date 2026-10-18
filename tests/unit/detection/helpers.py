from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import pytz

from core.data.schema import TRANSACTION_DF_COLUMNS

IST = pytz.timezone("Asia/Kolkata")
T0 = IST.localize(datetime(2024, 3, 1, 10, 0, 0))


def make_tx(rows) -> pd.DataFrame:
    """rows: (txn_id, sender, receiver, amount, minutes_after_T0[, type])."""
    recs = []
    for r in rows:
        tid, s, rc, amt, mins = r[:5]
        typ = r[5] if len(r) > 5 else "UPI"
        recs.append({"transaction_id": tid, "sender_account_id": s, "receiver_account_id": rc,
                     "amount_inr": float(amt), "timestamp": T0 + timedelta(minutes=mins), "transaction_type": typ})
    return pd.DataFrame.from_records(recs, columns=list(TRANSACTION_DF_COLUMNS))
