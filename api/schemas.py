"""Response contracts (also drive the OpenAPI docs at /docs)."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

Severity = Literal["low", "medium", "high", "critical"]
CaseStatus = Literal["open", "under_review", "closed"]
Resolution = Literal["reviewed_no_action", "reviewed_escalate", "data_quality_issue"]


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any = None


class ErrorEnvelope(BaseModel):
    error: ErrorBody


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class Health(BaseModel):
    status: Literal["ok"]
    version: str
    dataset_loaded: bool
    analysis_status: str


class DatasetInfo(BaseModel):
    loaded: bool
    dataset_id: Optional[str] = None
    name: Optional[str] = None
    source: Optional[str] = None
    is_synthetic: Optional[bool] = None
    loaded_at: Optional[str] = None
    accepted: Optional[int] = None
    rejected: Optional[int] = None
    window_start: Optional[str] = None
    window_end: Optional[str] = None
    seed: Optional[int] = None
    ignored_columns: list[str] = []
    analysis_completed_at: Optional[str] = None
    model_ran: Optional[bool] = None
    notes: list[str] = []


class AnalysisStatus(BaseModel):
    status: Literal["idle", "running", "completed", "failed"]
    stage: str
    error: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    dataset_loaded: bool


class RunRequest(BaseModel):
    source: Literal["synthetic"] = "synthetic"
    seed: Optional[int] = Field(None, ge=0, le=2**31 - 1)
    num_accounts: Optional[int] = Field(None, ge=20, le=2000)
    num_normal_transactions: Optional[int] = Field(None, ge=0, le=50_000)
    include_structuring: bool = Field(False, description="Append the opt-in STRUCTURING test scenario (needs >= 30 accounts).")


class TransactionOut(BaseModel):
    transaction_id: str
    sender_account_id: str
    receiver_account_id: str
    amount_inr: float
    timestamp: str
    transaction_type: str
    sender_risk: Optional[float] = None
    receiver_risk: Optional[float] = None
    flagged_rules: list[str] = []


class TransactionPage(BaseModel):
    items: list[TransactionOut]
    meta: PageMeta


class StatusUpdate(BaseModel):
    status: CaseStatus
    resolution: Optional[Resolution] = None


class NoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
