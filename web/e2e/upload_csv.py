#!/usr/bin/env python3
"""E2E: CSV upload through the Data & Pipeline page - client-side checks, server errors, partial validity, rejects report."""
import re
from playwright.sync_api import sync_playwright
from _common import UI, Run, api, ensure_synthetic, wait_idle, wait_until

R = Run("upload_csv")
H = "transaction_id,sender_account_id,receiver_account_id,amount_inr,timestamp,transaction_type\n"
MIXED = (H + "T1,A,B,100,2024-03-01 10:00:00,UPI,CIRCULAR_FLOW\nT1,A,B,100,2024-03-01 10:05:00,UPI,CIRCULAR_FLOW\n"
         "T2,A,A,100,2024-03-01 10:06:00,UPI,NORMAL\nT3,A,B,-5,2024-03-01 10:07:00,UPI,NORMAL\n"
         "T4,A,B,10,garbage,UPI,NORMAL\nT5,A,B,10,2024-03-01 10:08:00,BITCOIN,NORMAL\nT6,B,C,250,2024-03-01 10:09:00,NEFT,NORMAL\n"
         ).replace("transaction_type\n", "transaction_type,scenario\n", 1)
body = lambda pg: pg.inner_text("main")


def upload(pg, name, data, mime="text/csv"):
    pg.set_input_files("input[type=file]", {"name": name, "mimeType": mime, "buffer": data})


with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1440, "height": 900}); R.watch(pg, allow_4xx=True)
    validate = lambda: pg.get_by_role("button", name=re.compile("Validate"))
    try:
        base = ensure_synthetic(num_accounts=60, num_normal_transactions=300)
        pg.goto(UI + "/data"); pg.wait_for_selector("text=Upload transaction CSV")
        R.ok("start: validate button disabled before a file is chosen", validate().is_disabled())

        # ---- client-side rejections (nothing is sent to the server)
        upload(pg, "notes.txt", b"hello", "text/plain"); pg.wait_for_timeout(300)
        R.ok("client: non-.csv rejected with message, button stays disabled", "Please choose a .csv file." in body(pg) and validate().is_disabled())
        upload(pg, "empty.csv", b""); pg.wait_for_timeout(300)
        R.ok("client: empty file rejected", "The file is empty." in body(pg) and validate().is_disabled())
        upload(pg, "big.csv", b"x" * (5 * 1024 * 1024 + 10)); pg.wait_for_timeout(500)
        R.ok("client: file over 5 MB rejected with size in message", bool(re.search(r"File is 5\.\d MB; the limit is 5 MB", body(pg))) and validate().is_disabled())

        # ---- server-side errors leave the loaded dataset untouched
        upload(pg, "bad_header.csv", b"a,b\n1,2\n"); validate().click(); pg.wait_for_selector("text=MISSING_COLUMNS", timeout=10000)
        R.ok("server: missing columns -> MISSING_COLUMNS callout", True)
        R.ok("server: previous dataset preserved after missing-columns error", api("/api/dataset")["dataset_id"] == base["dataset_id"])
        upload(pg, "all_bad.csv", (H + "X,A,A,1,2024-01-01,UPI\nY,A,B,-1,2024-01-01,UPI\n").encode()); validate().click()
        pg.wait_for_selector("text=NO_VALID_ROWS", timeout=10000)
        R.ok("server: all-invalid file -> NO_VALID_ROWS callout", True)
        R.ok("server: previous dataset still preserved", api("/api/dataset")["dataset_id"] == base["dataset_id"])
        ing = api("/api/analysis/ingest")
        R.ok("server: rejects of the failed upload are still reportable (2 rejected, 0 accepted)", ing["rejected"] == 2 and ing["accepted"] == 0, str((ing["accepted"], ing["rejected"])))

        # ---- partially valid file with a label-like extra column
        upload(pg, "mixed.csv", MIXED.encode()); validate().click()
        pg.wait_for_selector("text=Accepted 2 rows, rejected 5", timeout=10000); wait_idle()
        pg.wait_for_selector("text=Last ingestion"); pg.wait_for_timeout(1500)
        d = api("/api/dataset")
        R.ok("mixed: dataset replaced, labelled as uploaded (not synthetic), 2 accepted / 5 rejected",
             d["source"] == "csv_upload" and d["is_synthetic"] is False and (d["accepted"], d["rejected"]) == (2, 5), str((d["source"], d["accepted"], d["rejected"])))
        t = body(pg)
        R.ok("mixed: UI shows Uploaded CSV badge", "Uploaded CSV" in t)
        R.ok("mixed: all five reason codes listed", all(c in t for c in ["DUPLICATE_ID", "SELF_TRANSACTION", "NON_POSITIVE_AMOUNT", "MALFORMED_TIMESTAMP", "INVALID_TRANSACTION_TYPE"]))
        R.ok("mixed: rejects table has 5 rows", pg.locator("table:has-text('Reason codes') tbody tr").count() == 5, str(pg.locator("table:has-text('Reason codes') tbody tr").count()))
        R.ok("mixed: ignored label-like column disclosed and never used", "Ignored columns" in t and "scenario" in t and "never passed to features" in t)
        R.ok("mixed: 'Download rejects report' control present", pg.get_by_role("button", name="Download rejects report").count() == 1)
        rep = pg.request.get(UI + "/api/analysis/rejects.csv")
        lines = rep.text().strip().split("\n")
        R.ok("mixed: rejects.csv downloads as text/csv with header + 5 rows and reasons", rep.status == 200 and "text/csv" in rep.headers.get("content-type", "") and len(lines) == 6 and "DUPLICATE_ID" in rep.text(), f"{len(lines)} lines")
        acc = api("/api/accounts/A")
        R.ok("mixed: label column absent from analysis outputs", "scenario" not in str(acc).lower() and "circular" not in str(acc.get("rule_matches")).lower())
        pg.goto(UI + "/"); pg.wait_for_selector("text=Risk Intelligence"); pg.wait_for_timeout(1200)
        R.ok("mixed: overview KPIs computed from the uploaded data (2 transactions, 3 accounts, no synthetic banner)",
             "Synthetic, deterministic demo data" not in body(pg) and api("/api/dataset/summary")["kpis"]["total_transactions"] == 2 and api("/api/dataset/summary")["kpis"]["total_accounts"] == 3)
        pg.goto(UI + "/alerts"); pg.wait_for_selector("text=Alerts & Investigations"); pg.wait_for_timeout(800)
        R.ok("mixed: tiny dataset shows the valid empty-alerts state (not an error)", "No alerts in this dataset" in body(pg))
        pg.goto(UI + "/data"); pg.wait_for_selector("text=Last ingestion")
        R.ok("mixed: after reload the ingestion report persists in the UI", "Accepted" in body(pg) and "DUPLICATE_ID" in body(pg))
        pg.screenshot(path="/tmp/shots/e2e_upload.png", full_page=True)
    except Exception as ex:
        R.ok("script aborted before completion", False, f"{type(ex).__name__}: {str(ex).splitlines()[0][:180]}")
        pg.screenshot(path="/tmp/shots/e2e_upload_abort.png")
    b.close()
R.finish()
