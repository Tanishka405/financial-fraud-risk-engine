from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from api.cases import CaseStore
from api.main import create_app
from api.state import SESSION


def wait_done(client: TestClient, timeout: float = 30.0) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = client.get("/api/analysis/status").json()
        if st["status"] != "running":
            return st
        time.sleep(0.05)
    raise TimeoutError("analysis did not finish")


@pytest.fixture
def client() -> TestClient:
    SESSION.reset(CaseStore(":memory:"))
    return TestClient(create_app())


@pytest.fixture
def loaded(client) -> TestClient:
    r = client.post("/api/analysis/run", json={"num_accounts": 60, "num_normal_transactions": 400})
    assert r.status_code == 202
    assert wait_done(client)["status"] == "completed"
    return client


CSV_HEADER = "transaction_id,sender_account_id,receiver_account_id,amount_inr,timestamp,transaction_type\n"


def upload(client, text: str, name: str = "t.csv"):
    return client.post("/api/analysis/upload", files={"file": (name, text.encode(), "text/csv")})


def repeated_csv(n: int = 4) -> str:
    rows = [f"T{i},A,B,100.0,2024-03-01 10:{i:02d}:00,UPI" for i in range(n)]
    rows += ["T90,B,C,50,2024-03-01 11:00:00,NEFT", "T91,D,B,70,2024-03-01 12:00:00,IMPS"]
    return CSV_HEADER + "\n".join(rows) + "\n"
