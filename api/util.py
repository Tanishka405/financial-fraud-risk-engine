from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from api.errors import ApiError

MAX_PAGE_SIZE = 200


def clean(v: Any) -> Any:
    """Recursively convert numpy/pandas scalars to JSON-safe Python; NaN/inf -> None."""
    if isinstance(v, dict):
        return {str(k): clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, set)):
        return [clean(x) for x in v]
    if isinstance(v, (np.floating, float)):
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else f
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.bool_):
        return bool(v)
    if isinstance(v, np.str_):
        return str(v)
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    if v is pd.NaT:
        return None
    return v


def iso(ts) -> str | None:
    if ts is None or ts is pd.NaT:
        return None
    return pd.Timestamp(ts).isoformat()


def parse_ts(value: str | None, field: str):
    """Parse an ISO date/time filter. Naive values are interpreted as IST."""
    if value is None or value == "":
        return None
    try:
        t = pd.Timestamp(value)
    except Exception:
        raise ApiError(422, "INVALID_FILTER", f"'{field}' is not a valid ISO date/time: {value!r}", {"field": field})
    return t.tz_localize("Asia/Kolkata") if t.tzinfo is None else t.tz_convert("Asia/Kolkata")


def paginate(df: pd.DataFrame, page: int, page_size: int):
    total = len(df)
    pages = max(1, math.ceil(total / page_size))
    start = (page - 1) * page_size
    return df.iloc[start:start + page_size], {"page": page, "page_size": page_size, "total": total, "total_pages": pages}


def check_sort(sort: str, allowed: set[str]) -> None:
    if sort not in allowed:
        raise ApiError(422, "INVALID_SORT", f"Cannot sort by {sort!r}.", {"allowed": sorted(allowed)})
