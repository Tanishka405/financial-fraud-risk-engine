"""Case-management persistence (SQLite, stdlib only).

Only investigator workflow state is stored here: status changes and notes,
as an append-only event log keyed by (dataset_id, alert_id). Analytics are
never persisted; they are recomputed from `core`. dataset_id is a content
fingerprint, so state never bleeds between different datasets.
There is no authentication in this app, so events carry no user identity.
"""
from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

import pytz

STATUSES = ("open", "under_review", "closed")
RESOLUTIONS = ("reviewed_no_action", "reviewed_escalate", "data_quality_issue")
TRANSITIONS = {"open": {"under_review", "closed"}, "under_review": {"open", "closed"}, "closed": {"open"}}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS case_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  dataset_id TEXT NOT NULL, alert_id TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('status','note')),
  from_status TEXT, to_status TEXT, resolution TEXT, body TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_case_alert ON case_events (dataset_id, alert_id, id);
"""


def default_db_path() -> str:
    return os.environ.get("FRAUD_DB_PATH", str(Path(__file__).resolve().parent.parent / "var" / "cases.sqlite3"))


class CaseStore:
    def __init__(self, path: str | None = None):
        self.path = path or default_db_path()
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)

    @staticmethod
    def _now() -> str:
        return datetime.now(pytz.timezone("Asia/Kolkata")).isoformat(timespec="seconds")

    def state(self, dataset_id: str, alert_id: str) -> dict:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM case_events WHERE dataset_id=? AND alert_id=? ORDER BY id", (dataset_id, alert_id)
            ).fetchall()
        status, resolution, updated = "open", None, None
        events = []
        for r in rows:
            events.append({k: r[k] for k in r.keys() if k not in ("dataset_id", "alert_id")})
            if r["kind"] == "status":
                status, resolution, updated = r["to_status"], r["resolution"], r["created_at"]
        return {"status": status, "resolution": resolution, "updated_at": updated,
                "notes": [e for e in events if e["kind"] == "note"],
                "history": [e for e in events if e["kind"] == "status"]}

    def statuses(self, dataset_id: str) -> dict[str, dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT alert_id, to_status, resolution, created_at FROM case_events "
                "WHERE dataset_id=? AND kind='status' ORDER BY id", (dataset_id,)).fetchall()
            n = self._conn.execute(
                "SELECT alert_id, COUNT(*) c FROM case_events WHERE dataset_id=? AND kind='note' GROUP BY alert_id",
                (dataset_id,)).fetchall()
        out: dict[str, dict] = {}
        for r in rows:
            out[r["alert_id"]] = {"status": r["to_status"], "resolution": r["resolution"], "updated_at": r["created_at"]}
        for r in n:
            out.setdefault(r["alert_id"], {"status": "open", "resolution": None, "updated_at": None})["notes"] = r["c"]
        return out

    def set_status(self, dataset_id: str, alert_id: str, to: str, resolution: str | None) -> dict:
        cur = self.state(dataset_id, alert_id)["status"]
        with self._lock:
            self._conn.execute(
                "INSERT INTO case_events (dataset_id, alert_id, kind, from_status, to_status, resolution, created_at) "
                "VALUES (?,?,?,?,?,?,?)", (dataset_id, alert_id, "status", cur, to, resolution, self._now()))
            self._conn.commit()
        return self.state(dataset_id, alert_id)

    def add_note(self, dataset_id: str, alert_id: str, body: str) -> dict:
        with self._lock:
            self._conn.execute(
                "INSERT INTO case_events (dataset_id, alert_id, kind, body, created_at) VALUES (?,?,?,?,?)",
                (dataset_id, alert_id, "note", body, self._now()))
            self._conn.commit()
        return self.state(dataset_id, alert_id)
