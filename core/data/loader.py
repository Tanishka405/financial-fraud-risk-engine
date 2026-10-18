"""
CSV ingestion for transaction data.

Deliberately thin: this module's only job is to turn a CSV file into an
iterable of raw row dicts and hand them to `core.data.validators.validate_batch`.
All validation logic lives in one place (`validators.py`) so the synthetic
generator's output and real CSV uploads go through exactly the same checks --
there is no separate "trusted" ingestion path.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from core.config import Config
from core.data.schema import REQUIRED_COLUMNS, transactions_to_dataframe
from core.data.validators import ValidationOutcome, validate_batch


class SchemaError(ValueError):
    """Raised when a CSV is missing required columns entirely -- this is a
    structural problem with the file, not a per-row data-quality issue, so it
    is raised immediately rather than quarantining every row."""


def load_transactions_csv(path: str | Path, config: Config) -> ValidationOutcome:
    """Load a CSV file of raw transactions and validate every row.

    Returns a `ValidationOutcome` with the valid `Transaction` objects and a
    rejects DataFrame explaining every row that failed validation (including
    duplicate transaction_id detection across the whole file). Nothing is
    silently dropped.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    df = pd.read_csv(path, dtype=str, keep_default_na=True)
    return validate_raw_dataframe(df, config, source=str(path))


def validate_raw_dataframe(df: pd.DataFrame, config: Config, source: str = "<dataframe>") -> ValidationOutcome:
    """Validate an already-parsed raw (all-string) DataFrame through exactly the same
    path as `load_transactions_csv`. Lets callers (e.g. an upload endpoint) parse
    from memory without touching the filesystem. Only the canonical columns are
    passed to the validator; any extra columns are ignored by construction."""
    missing_columns = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing_columns:
        raise SchemaError(
            f"CSV {source} is missing required column(s): {sorted(missing_columns)}. "
            f"Required columns are: {REQUIRED_COLUMNS}"
        )

    rows = df[list(REQUIRED_COLUMNS)].to_dict(orient="records")
    return validate_batch(rows, config)


def valid_transactions_dataframe(outcome: ValidationOutcome) -> pd.DataFrame:
    """Convenience helper: materialise the valid transactions from a
    `ValidationOutcome` as a canonical DataFrame."""
    return transactions_to_dataframe(outcome.valid_transactions)
