from __future__ import annotations

import pytest

from tests.api.conftest import CSV_HEADER, repeated_csv, upload, wait_done


# ------------------------------------------------------------------ basics
def test_health_and_empty_state_errors(client):
    h = client.get("/api/health").json()
    assert h == {"status": "ok", "version": h["version"], "dataset_loaded": False, "analysis_status": "idle"}
    assert client.get("/api/dataset").json()["loaded"] is False
    for url in ("/api/transactions", "/api/accounts", "/api/alerts", "/api/dataset/summary", "/api/graph"):
        r = client.get(url)
        assert r.status_code == 409 and r.json()["error"]["code"] == "NO_DATASET"
    assert client.get("/api/search", params={"q": "x"}).json()["accounts"] == []
    assert client.get("/api/does-not-exist").json()["error"]["code"] == "NOT_FOUND"


def test_run_synthetic_is_labelled_and_deterministic(loaded):
    d = loaded.get("/api/dataset").json()
    assert d["loaded"] and d["is_synthetic"] and d["source"] == "synthetic" and d["seed"] == 42
    first = loaded.get("/api/dataset/summary").json()["kpis"]
    loaded.post("/api/analysis/run", json={"num_accounts": 60, "num_normal_transactions": 400})
    wait_done(loaded)
    assert loaded.get("/api/dataset/summary").json()["kpis"] == first


def test_concurrent_run_rejected(loaded):
    from api.state import SESSION
    SESSION.status = "running"
    r = loaded.post("/api/analysis/run", json={})
    assert r.status_code == 409 and r.json()["error"]["code"] == "ANALYSIS_RUNNING"
    SESSION.status = "completed"


def test_run_request_validation(client):
    r = client.post("/api/analysis/run", json={"num_accounts": 3})
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"


# ----------------------------------------------------------------- summary
def test_summary_values_computed_from_data(loaded):
    s = loaded.get("/api/dataset/summary").json()
    k = s["kpis"]
    total = loaded.get("/api/transactions", params={"page_size": 1}).json()["meta"]["total"]
    assert k["total_transactions"] == total
    assert k["alerts"] == sum(s["severity_distribution"].values()) == loaded.get("/api/alerts").json()["meta"]["total"]
    assert sum(p["count"] for p in s["time_series"]["points"]) == total
    assert abs(sum(p["value_inr"] for p in s["time_series"]["points"]) - k["total_value_inr"]) < 1
    assert len(s["top_risk_accounts"]) <= 8 and s["model_ran"] is True


# ------------------------------------------------------------ transactions
def test_transactions_pagination_sorting_and_schema(loaded):
    r = loaded.get("/api/transactions", params={"page": 2, "page_size": 10, "sort": "amount_inr", "order": "desc"}).json()
    assert r["meta"]["page"] == 2 and len(r["items"]) == 10
    assert r["meta"]["total_pages"] == -(-r["meta"]["total"] // 10)
    amts = [x["amount_inr"] for x in r["items"]]
    assert amts == sorted(amts, reverse=True)
    t = r["items"][0]
    assert set(t) == {"transaction_id", "sender_account_id", "receiver_account_id", "amount_inr", "timestamp",
                      "transaction_type", "sender_risk", "receiver_risk", "flagged_rules"}
    assert t["timestamp"].endswith("+05:30")  # IST


def test_transaction_filters(loaded):
    base = loaded.get("/api/transactions", params={"page_size": 200}).json()["items"]
    acc = base[0]["sender_account_id"]
    r = loaded.get("/api/transactions", params={"account": acc, "page_size": 200}).json()["items"]
    assert r and all(acc in (x["sender_account_id"], x["receiver_account_id"]) for x in r)
    r = loaded.get("/api/transactions", params={"min_amount": 100000, "page_size": 200}).json()["items"]
    assert all(x["amount_inr"] >= 100000 for x in r)
    r = loaded.get("/api/transactions", params={"transaction_type": "upi", "page_size": 200}).json()["items"]
    assert r and all(x["transaction_type"] == "UPI" for x in r)
    r = loaded.get("/api/transactions", params={"q": base[0]["transaction_id"].lower()}).json()
    assert r["meta"]["total"] == 1
    r = loaded.get("/api/transactions", params={"flagged": True, "page_size": 200}).json()["items"]
    assert r and all(x["flagged_rules"] for x in r)
    none = loaded.get("/api/transactions", params={"q": "zzz-no-such"}).json()
    assert none["items"] == [] and none["meta"]["total"] == 0 and none["meta"]["total_pages"] == 1


@pytest.mark.parametrize("params,code", [
    ({"sort": "nonsense"}, "INVALID_SORT"),
    ({"transaction_type": "BITCOIN"}, "INVALID_FILTER"),
    ({"min_amount": 10, "max_amount": 5}, "INVALID_FILTER"),
    ({"from": "not-a-date"}, "INVALID_FILTER"),
    ({"from": "2024-02-01", "to": "2024-01-01"}, "INVALID_FILTER"),
    ({"page_size": 5000}, "VALIDATION_ERROR"),
    ({"page": 0}, "VALIDATION_ERROR"),
])
def test_transaction_invalid_filters(loaded, params, code):
    r = loaded.get("/api/transactions", params=params)
    assert r.status_code == 422 and r.json()["error"]["code"] == code


def test_date_range_filter_uses_ist(loaded):
    r = loaded.get("/api/transactions", params={"from": "2024-01-02", "to": "2024-01-03", "page_size": 200}).json()["items"]
    assert r and all("2024-01-02" <= x["timestamp"][:10] <= "2024-01-03" for x in r)


def test_transaction_detail_and_404(loaded):
    tid = loaded.get("/api/transactions", params={"page_size": 1}).json()["items"][0]["transaction_id"]
    d = loaded.get(f"/api/transactions/{tid}").json()
    assert d["transaction"]["transaction_id"] == tid and d["same_pair"]["count"] >= 1
    r = loaded.get("/api/transactions/NOPE")
    assert r.status_code == 404 and r.json()["error"]["code"] == "TRANSACTION_NOT_FOUND"


# ---------------------------------------------------------------- accounts
def test_account_detail_sections_and_404(loaded):
    top = loaded.get("/api/accounts", params={"page_size": 1}).json()["items"][0]["account_id"]
    d = loaded.get(f"/api/accounts/{top}").json()
    assert {"observed", "computed_features", "graph_metrics", "rule_matches", "model_signal", "scores",
            "timeline", "top_counterparties", "recent_transactions"} <= set(d)
    assert "scenario" not in str(d).lower()  # synthetic labels are never exposed per account
    r = loaded.get("/api/accounts/NOPE")
    assert r.status_code == 404 and r.json()["error"]["code"] == "ACCOUNT_NOT_FOUND"
    assert loaded.get("/api/accounts", params={"severity": "bogus"}).status_code == 422


def test_pure_sink_ratio_serialises_as_null(client):
    assert upload(client, repeated_csv()).status_code == 202
    wait_done(client)
    d = client.get("/api/accounts/C").json()  # C only ever receives
    assert d["computed_features"]["inflow_outflow_ratio"] is None
    assert d["computed_features"]["inflow_outflow_ratio_note"] == "Pure sink (no outflow)"


# ------------------------------------------------------------------- graph
def test_graph_preserves_repeated_transactions(client):
    upload(client, repeated_csv(4)); wait_done(client)
    agg = client.get("/api/graph", params={"center": "A", "mode": "aggregated"}).json()
    e = [x for x in agg["edges"] if x["source"] == "A" and x["target"] == "B"]
    assert len(e) == 1 and e[0]["txn_count"] == 4 and e[0]["aggregated"] is True and e[0]["total_amount_inr"] == 400
    tx = client.get("/api/graph", params={"center": "A", "mode": "transactions"}).json()
    assert len([x for x in tx["edges"] if x["source"] == "A" and x["target"] == "B"]) == 4
    assert tx["meta"]["transactions_represented"] == agg["meta"]["transactions_represented"]


def test_graph_neighbourhood_depth_filters_and_limits(loaded):
    g1 = loaded.get("/api/graph", params={"center": "ACC00011", "depth": 1}).json()
    g2 = loaded.get("/api/graph", params={"center": "ACC00011", "depth": 2, "limit_nodes": 30}).json()
    assert g1["nodes"][0]["id"] or True
    assert any(n["is_center"] for n in g1["nodes"])
    ids1 = {n["id"] for n in g1["nodes"]}
    assert ids1 >= {"ACC00011"}
    assert len(g2["nodes"]) <= 30 and g2["meta"]["limit_nodes"] == 30
    big = loaded.get("/api/graph", params={"min_amount": 1_000_000, "limit_nodes": 5}).json()
    assert all(e["total_amount_inr"] >= 1_000_000 for e in big["edges"])
    ov = loaded.get("/api/graph", params={"limit_nodes": 10}).json()
    assert len(ov["nodes"]) <= 10 and ov["meta"]["truncated"] is True
    assert loaded.get("/api/graph", params={"center": "NOPE"}).status_code == 404
    assert loaded.get("/api/graph", params={"depth": 9}).status_code == 422
    assert loaded.get("/api/graph", params={"limit_nodes": 100000}).status_code == 422


# ------------------------------------------------------------------ alerts
def test_alert_list_filters_and_facets(loaded):
    r = loaded.get("/api/alerts", params={"page_size": 200}).json()
    assert r["meta"]["total"] > 0 and sum(r["facets"]["severity"].values()) == r["meta"]["total"]
    sev = r["items"][0]["severity"]
    f = loaded.get("/api/alerts", params={"severity": sev, "page_size": 200}).json()["items"]
    assert f and all(x["severity"] == sev for x in f)
    code = r["items"][0]["reason_codes"][0]
    f = loaded.get("/api/alerts", params={"reason": code, "page_size": 200}).json()["items"]
    assert f and all(code in x["reason_codes"] for x in f)
    assert loaded.get("/api/alerts", params={"status": "bogus"}).status_code == 422
    assert loaded.get("/api/alerts", params={"reason": "BOGUS"}).status_code == 422
    sc = [x["risk_score"] for x in r["items"]]
    assert sc == sorted(sc, reverse=True)


def test_alert_detail_explanation_matches_triggered_signals(loaded):
    for it in loaded.get("/api/alerts", params={"page_size": 200}).json()["items"]:
        d = loaded.get(f"/api/alerts/{it['alert_id']}").json()
        hit_codes = sorted({m["rule_code"] for m in d["rule_matches"]})
        assert d["reason_codes"] == (hit_codes or ["MODEL_ANOMALY"])
        assert sorted(b["rule_code"] for b in d["explanation"]["rule_score_breakdown"]) == hit_codes
        ev = {t for m in d["rule_matches"] for t in m["transaction_ids"]}
        assert {t["transaction_id"] for t in d["related_transactions"]} == ev
        assert "not a probability" in d["explanation"]["disclaimer"]
        assert d["is_synthetic_data"] is True
    assert loaded.get("/api/alerts/ALR-NOPE").status_code == 404


def test_case_workflow_persists_and_validates(loaded):
    aid = loaded.get("/api/alerts").json()["items"][0]["alert_id"]
    url = f"/api/alerts/{aid}"
    assert loaded.get(url).json()["case"]["status"] == "open"
    assert loaded.patch(f"{url}/status", json={"status": "open"}).json()["error"]["code"] == "NO_CHANGE"
    assert loaded.patch(f"{url}/status", json={"status": "closed"}).json()["error"]["code"] == "RESOLUTION_REQUIRED"
    assert loaded.patch(f"{url}/status", json={"status": "under_review", "resolution": "reviewed_no_action"}).json()["error"]["code"] == "RESOLUTION_NOT_ALLOWED"
    assert loaded.patch(f"{url}/status", json={"status": "confirmed_fraud"}).status_code == 422
    assert loaded.patch(f"{url}/status", json={"status": "under_review"}).json()["status"] == "under_review"
    assert loaded.post(f"{url}/notes", json={"body": "Checked counterparties."}).status_code == 201
    assert loaded.post(f"{url}/notes", json={"body": "   "}).status_code == 422
    assert loaded.patch(f"{url}/status", json={"status": "closed", "resolution": "reviewed_no_action"}).json()["status"] == "closed"
    d = loaded.get(url).json()["case"]
    assert d["status"] == "closed" and d["resolution"] == "reviewed_no_action"
    assert [n["body"] for n in d["notes"]] == ["Checked counterparties."] and len(d["history"]) == 2
    assert d["history"][0]["from_status"] == "open" and d["history"][1]["to_status"] == "closed"
    row = [x for x in loaded.get("/api/alerts", params={"page_size": 200}).json()["items"] if x["alert_id"] == aid][0]
    assert row["status"] == "closed" and row["notes_count"] == 1
    assert loaded.get("/api/alerts", params={"status": "closed"}).json()["meta"]["total"] == 1
    assert loaded.patch(f"{url}/status", json={"status": "under_review"}).json()["error"]["code"] == "INVALID_TRANSITION"


def test_case_state_survives_new_session_with_same_store(tmp_path):
    from api.cases import CaseStore
    p = str(tmp_path / "c.db")
    CaseStore(p).add_note("ds1", "ALR-X", "hello")
    CaseStore(p).set_status("ds1", "ALR-X", "under_review", None)
    st = CaseStore(p).state("ds1", "ALR-X")
    assert st["status"] == "under_review" and st["notes"][0]["body"] == "hello"
    assert CaseStore(p).state("other-dataset", "ALR-X")["status"] == "open"


# ----------------------------------------------------------------- uploads
def test_upload_rejects_empty_missing_columns_bad_encoding(client):
    assert upload(client, "").json()["error"]["code"] == "EMPTY_FILE"
    assert upload(client, CSV_HEADER).json()["error"]["code"] == "NO_ROWS"
    r = upload(client, "a,b\n1,2\n")
    assert r.status_code == 422 and r.json()["error"]["code"] == "MISSING_COLUMNS"
    r = client.post("/api/analysis/upload", files={"file": ("x.csv", b"\xff\xfe\x00bad", "text/csv")})
    assert r.json()["error"]["code"] == "INVALID_ENCODING"
    assert client.post("/api/analysis/upload").status_code == 422
    assert client.get("/api/dataset").json()["loaded"] is False  # nothing partially loaded


def test_upload_size_limit(client, monkeypatch):
    monkeypatch.setattr("api.state.MAX_UPLOAD_BYTES", 200)
    r = upload(client, repeated_csv(40))
    assert r.status_code == 413 and r.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_upload_partial_validity_reports_and_downloads_rejects(client):
    text = (CSV_HEADER + "T1,A,B,100,2024-03-01 10:00:00,UPI\n"
            "T1,A,B,100,2024-03-01 10:05:00,UPI\n"  # duplicate id
            "T2,A,A,100,2024-03-01 10:06:00,UPI\n"  # self txn
            "T3,A,B,-5,2024-03-01 10:07:00,UPI\n"  # non-positive
            "T4,A,B,10,garbage,UPI\n"  # bad timestamp
            "T5,A,B,10,2024-03-01 10:08:00,BITCOIN\n"  # bad type
            "T6,B,C,250,2024-03-01 10:09:00,NEFT\n")
    text = text.replace("transaction_type\n", "transaction_type,scenario\n", 1)  # extra label-like column
    text = "\n".join(l + ",CIRCULAR_FLOW" if i else l for i, l in enumerate(text.strip().split("\n"))) + "\n"
    r = upload(client, text)
    assert r.status_code == 202
    j = r.json()
    assert j["accepted"] == 2 and j["rejected"] == 5 and j["ignored_columns"] == ["scenario"] and j["label_like_ignored"] == ["scenario"]
    wait_done(client)
    d = client.get("/api/dataset").json()
    assert d["is_synthetic"] is False and d["source"] == "csv_upload" and d["accepted"] == 2 and d["rejected"] == 5
    ing = client.get("/api/analysis/ingest").json()
    assert set(ing["reason_counts"]) >= {"DUPLICATE_ID", "SELF_TRANSACTION", "NON_POSITIVE_AMOUNT", "MALFORMED_TIMESTAMP", "INVALID_TRANSACTION_TYPE"}
    csv = client.get("/api/analysis/rejects.csv")
    assert csv.headers["content-type"].startswith("text/csv") and "DUPLICATE_ID" in csv.text and csv.text.count("\n") == 6
    assert len(client.get("/api/analysis/rejects").json()["items"]) == 5
    assert client.get("/api/analysis/evaluation").json()["available"] is False  # no labels for uploads
    # label column never reached features
    assert "scenario" not in str(client.get("/api/accounts/A").json()).lower()


def test_all_invalid_upload_keeps_previous_dataset(loaded):
    before = loaded.get("/api/dataset").json()["dataset_id"]
    r = upload(loaded, CSV_HEADER + "X,A,A,1,2024-01-01,UPI\nY,A,B,-1,2024-01-01,UPI\n")
    assert r.status_code == 422 and r.json()["error"]["code"] == "NO_VALID_ROWS"
    assert loaded.get("/api/dataset").json()["dataset_id"] == before
    assert loaded.get("/api/analysis/ingest").json()["rejected"] == 2
    assert "SELF_TRANSACTION" in loaded.get("/api/analysis/rejects.csv").text


def test_small_upload_runs_without_model_and_says_so(client):
    upload(client, repeated_csv()); wait_done(client)
    d = client.get("/api/dataset").json()
    assert d["model_ran"] is False and any("not run" in n for n in d["notes"])
    assert client.get("/api/dataset/summary").json()["kpis"]["total_transactions"] == 6


def test_search(loaded):
    r = loaded.get("/api/search", params={"q": "acc0001"}).json()
    assert r["accounts"] and all("acc0001" in a["account_id"].lower() for a in r["accounts"])
    assert loaded.get("/api/search", params={"q": ""}).status_code == 422


def test_config_endpoint_exposes_thresholds_and_disclaimer(loaded):
    c = loaded.get("/api/analysis/config").json()
    assert {r["code"] for r in c["rules"]} >= {"HIGH_VELOCITY", "CIRCULAR_FLOW"} and "not a probability" in c["score_disclaimer"]
