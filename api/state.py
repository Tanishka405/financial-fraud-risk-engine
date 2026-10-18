"""Process-wide analysis session: loaded dataset, analysis result, job status.

The dataset lives in memory (single-user local tool). Heavy work runs in a
background thread so the UI can show real running / completed / failed states.
"""
from __future__ import annotations

import io
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd
import pytz

from core.config import Config
from core.data.loader import SchemaError, validate_raw_dataframe
from core.data.schema import REQUIRED_COLUMNS, transactions_to_dataframe
from core.data.synthetic import generate_synthetic_dataset
from core.data.validators import ValidationOutcome, validate_batch
from core.detection.config import DetectionConfig
from core.detection.pipeline import AnalysisResult, evaluate_on_synthetic, run_analysis
from api.cases import CaseStore
from api.errors import ApiError

IST = pytz.timezone("Asia/Kolkata")
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_UPLOAD_ROWS = 50_000
LABEL_LIKE = ("scenario", "label", "fraud")


def now_ist() -> str:
    return datetime.now(IST).isoformat(timespec="seconds")


@dataclass
class DatasetMeta:
    dataset_id: str
    name: str
    source: str  # "synthetic" | "csv_upload"
    is_synthetic: bool
    loaded_at: str
    accepted: int
    rejected: int
    window_start: str | None
    window_end: str | None
    seed: int | None = None
    ignored_columns: list[str] = field(default_factory=list)


@dataclass
class IngestInfo:
    name: str
    source: str
    accepted: int
    rejected: int
    rejects: pd.DataFrame
    ignored_columns: list[str]
    at: str


class Session:
    def __init__(self, config: Config | None = None, det: DetectionConfig | None = None, cases: CaseStore | None = None):
        self.cases = cases or CaseStore()
        self.config = config or Config()
        self.det = det or DetectionConfig()
        self.lock = threading.RLock()
        self.status = "idle"  # idle | running | completed | failed
        self.stage = ""
        self.error: str | None = None
        self.started_at: str | None = None
        self.finished_at: str | None = None
        self.meta: DatasetMeta | None = None
        self.result: AnalysisResult | None = None
        self.view: pd.DataFrame | None = None
        self.evaluation: dict | None = None
        self.last_ingest: IngestInfo | None = None
        self.alerts_by_id: dict[str, Any] = {}
        self.flagged: dict[str, list[str]] = {}

    def reset(self, cases: CaseStore | None = None) -> None:
        """Drop all loaded state (used by tests)."""
        self.__init__(self.config, self.det, cases or self.cases)  # type: ignore[misc]

    # ------------------------------------------------------------ job control
    def _begin(self) -> None:
        with self.lock:
            if self.status == "running":
                raise ApiError(409, "ANALYSIS_RUNNING", "An analysis is already running.")
            self.status, self.stage, self.error = "running", "Starting", None
            self.started_at, self.finished_at = now_ist(), None

    def _fail(self, msg: str) -> None:
        with self.lock:
            self.status, self.error, self.finished_at = "failed", msg, now_ist()

    def start_synthetic(self, seed: int | None, num_accounts: int | None, num_normal: int | None, background: bool = True) -> None:
        self._begin()
        job = lambda: self._run_synthetic(seed, num_accounts, num_normal)
        if background:
            threading.Thread(target=job, daemon=True).start()
        else:
            job()

    def _run_synthetic(self, seed, num_accounts, num_normal) -> None:
        try:
            cfg = self.config if seed is None else Config(**{**self.config.__dict__, "random_seed": seed})
            with self.lock:
                self.stage = "Generating deterministic synthetic transactions"
            ds = generate_synthetic_dataset(cfg, num_accounts=num_accounts, num_normal_transactions=num_normal)
            raw = [{"transaction_id": t.transaction_id, "sender_account_id": t.sender_account_id,
                    "receiver_account_id": t.receiver_account_id, "amount_inr": t.amount_inr,
                    "timestamp": t.timestamp, "transaction_type": t.transaction_type.value} for t in ds.transactions]
            with self.lock:
                self.stage = "Validating records"
            outcome = validate_batch(raw, cfg)
            name = f"Synthetic (seed {cfg.random_seed})"
            self._finish(outcome, cfg, name, "synthetic", True, seed=cfg.random_seed, scenarios=ds.account_scenarios)
        except Exception as e:  # noqa: BLE001 - surfaced to UI as failed state
            self._fail(f"{type(e).__name__}: {e}")

    def ingest_csv(self, filename: str, data: bytes) -> dict:
        """Synchronous parse+validate (bounded); analysis then runs in the background."""
        if len(data) == 0:
            raise ApiError(422, "EMPTY_FILE", "The uploaded file is empty.")
        if len(data) > MAX_UPLOAD_BYTES:
            raise ApiError(413, "FILE_TOO_LARGE", f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.")
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise ApiError(422, "INVALID_ENCODING", "File must be UTF-8 encoded CSV.")
        try:
            df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=True)
        except Exception:
            raise ApiError(422, "INVALID_CSV", "The file could not be parsed as CSV.")
        if len(df) == 0:
            raise ApiError(422, "NO_ROWS", "The CSV has a header but no data rows.")
        if len(df) > MAX_UPLOAD_ROWS:
            raise ApiError(413, "TOO_MANY_ROWS", f"CSV exceeds the {MAX_UPLOAD_ROWS:,} row limit.")
        df.columns = [str(c).strip() for c in df.columns]
        ignored = [c for c in df.columns if c not in REQUIRED_COLUMNS]
        try:
            outcome = validate_raw_dataframe(df, self.config, source="upload")
        except SchemaError as e:
            raise ApiError(422, "MISSING_COLUMNS", str(e), {"required": list(REQUIRED_COLUMNS), "found": list(df.columns)})
        safe_name = (filename or "upload.csv").replace("\\", "/").split("/")[-1][:120]
        info = IngestInfo(safe_name, "csv_upload", len(outcome.valid_transactions), len(outcome.rejects),
                          outcome.rejects, ignored, now_ist())
        with self.lock:
            self.last_ingest = info
        if not outcome.valid_transactions:
            raise ApiError(422, "NO_VALID_ROWS", "Every row failed validation; nothing to analyse. Download the rejects report.",
                           {"accepted": 0, "rejected": info.rejected})
        self._begin()
        threading.Thread(target=lambda: self._finish_safe(outcome, safe_name, ignored), daemon=True).start()
        return {"accepted": info.accepted, "rejected": info.rejected, "ignored_columns": ignored,
                "label_like_ignored": [c for c in ignored if any(s in c.lower() for s in LABEL_LIKE)]}

    def _finish_safe(self, outcome, name, ignored) -> None:
        try:
            self._finish(outcome, self.config, name, "csv_upload", False, ignored=ignored)
        except Exception as e:  # noqa: BLE001
            self._fail(f"{type(e).__name__}: {e}")

    def _finish(self, outcome: ValidationOutcome, cfg: Config, name: str, source: str, synthetic: bool,
                seed: int | None = None, scenarios: pd.DataFrame | None = None, ignored: list[str] | None = None) -> None:
        with self.lock:
            self.stage = "Running features, graph, rules and anomaly model"
        tx = transactions_to_dataframe(outcome.valid_transactions)
        result = run_analysis(tx, cfg, self.det)
        view = build_view(result)
        flagged: dict[str, list[str]] = {}
        for h in result.rule_hits:
            for t in h.transaction_ids:
                flagged.setdefault(t, [])
                if h.rule_code not in flagged[t]:
                    flagged[t].append(h.rule_code)
        meta = DatasetMeta(result.dataset_id, name, source, synthetic, now_ist(), len(tx), len(outcome.rejects),
                           pd.Timestamp(tx["timestamp"].min()).isoformat() if len(tx) else None,
                           pd.Timestamp(tx["timestamp"].max()).isoformat() if len(tx) else None, seed, ignored or [])
        evaluation = evaluate_on_synthetic(result.alerts, scenarios) if (synthetic and scenarios is not None) else None
        with self.lock:
            self.result, self.view, self.meta, self.evaluation = result, view, meta, evaluation
            self.alerts_by_id = {a.alert_id: a for a in result.alerts}
            self.flagged = flagged
            if synthetic:
                self.last_ingest = IngestInfo(name, source, len(tx), len(outcome.rejects), outcome.rejects, [], now_ist())
            self.status, self.stage, self.finished_at = "completed", "Done", now_ist()


def build_view(result: AnalysisResult) -> pd.DataFrame:
    tx = result.transactions.copy()
    sc = result.account_scores.set_index("account_id")["risk_score"] if len(result.account_scores) else pd.Series(dtype=float)
    tx["sender_risk"] = tx["sender_account_id"].map(sc)
    tx["receiver_risk"] = tx["receiver_account_id"].map(sc)
    return tx.sort_values("timestamp", kind="stable").reset_index(drop=True)


SESSION = Session()


def require_data() -> Session:
    if SESSION.result is None:
        raise ApiError(409, "NO_DATASET", "No dataset is loaded. Generate the synthetic dataset or upload a CSV first.")
    return SESSION
