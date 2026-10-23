#!/usr/bin/env python3
"""E2E: alert investigation workflow through the UI, with persistence checks against the API and the SQLite file.
Env: E2E_DB = path of the SQLite case DB the API was started with (default /tmp/e2e_cases.sqlite3)."""
import os, re, sqlite3
from playwright.sync_api import sync_playwright
from _common import UI, Run, api, ensure_synthetic

R = Run("investigation_workflow")
DB = os.environ.get("E2E_DB", "/tmp/e2e_cases.sqlite3")
body = lambda pg: pg.inner_text("main")
NOTE = "Counterparties look like a payroll run."

with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1440, "height": 900}); R.watch(pg)
    try:
        ds = ensure_synthetic(); did = ds["dataset_id"]
        alert = next(a for a in api("/api/alerts?page_size=50&sort=risk_score&order=desc")["items"] if a["status"] == "open")
        aid = alert["alert_id"]; print(f"WORKFLOW_ALERT={aid} DATASET_ID={did}")
        # ---- open from the queue
        pg.goto(UI + "/alerts"); pg.wait_for_selector("tbody tr")
        pg.locator("tbody tr", has_text=aid).first.click(); pg.wait_for_selector("text=Case status")
        R.ok("queue row opens the investigation view", pg.url.endswith(f"/alerts/{aid}"))
        t = body(pg)
        R.ok("view: explanation, rule evidence, disclaimer and no-auth notice present",
             all(x in t for x in ["Why this alert was generated", "Rule matches", "This is a lead, not a finding", "No authentication"]))
        R.ok("view: starts as Open with 'Start review' and 'Close alert' offered", "Open" in t and pg.get_by_role("button", name="Start review").count() == 1 and pg.get_by_role("button", name="Close alert").count() == 1)
        # ---- open -> under review (with confirmation)
        pg.get_by_role("button", name="Start review").click(); pg.wait_for_selector("[role=alertdialog]")
        R.ok("confirm dialog shown before a state change", "Change status" in pg.inner_text("[role=alertdialog]"))
        pg.get_by_role("alertdialog").get_by_role("button", name="Cancel").click(); pg.wait_for_timeout(300)
        R.ok("cancelling leaves the status unchanged (API)", api(f"/api/alerts/{aid}")["case"]["status"] == "open")
        pg.get_by_role("button", name="Start review").click(); pg.get_by_role("alertdialog").get_by_role("button", name="Confirm").click()
        pg.wait_for_selector("text=Status changed to Under review"); pg.wait_for_timeout(600)
        R.ok("status becomes Under review in UI and API", "Under review" in body(pg) and api(f"/api/alerts/{aid}")["case"]["status"] == "under_review")
        # ---- note
        pg.get_by_label("Add a note").fill(NOTE); pg.get_by_role("button", name="Add note").click(); pg.wait_for_selector("text=Note saved"); pg.wait_for_timeout(500)
        R.ok("note appears with an IST timestamp and is stored", NOTE in body(pg) and "IST" in body(pg) and len(api(f"/api/alerts/{aid}")["case"]["notes"]) == 1)
        # ---- close requires a resolution; no 'confirmed fraud' outcome exists
        pg.get_by_role("button", name="Close alert").click(); pg.wait_for_selector("[role=alertdialog]")
        dlg = pg.get_by_role("alertdialog")
        R.ok("closing: Confirm disabled until a resolution is chosen", dlg.get_by_role("button", name="Confirm").is_disabled())
        opts = dlg.locator("select option").all_inner_texts()
        R.ok("closing: resolutions offered never include a 'confirmed fraud' outcome", len(opts) == 4 and not any("confirm" in o.lower() and "fraud" in o.lower() for o in opts), str(opts))
        dlg.locator("select").select_option("reviewed_no_action"); dlg.get_by_role("button", name="Confirm").click()
        pg.wait_for_selector("text=Status changed to Closed"); pg.wait_for_timeout(600)
        c = api(f"/api/alerts/{aid}")["case"]
        R.ok("closed with resolution; only 'Reopen' is offered", c["status"] == "closed" and c["resolution"] == "reviewed_no_action" and pg.get_by_role("button", name="Reopen").count() == 1 and pg.get_by_role("button", name="Close alert").count() == 0)
        # ---- persistence across reload
        pg.reload(); pg.wait_for_selector("text=Case status"); t = body(pg)
        R.ok("after reload: Closed, resolution, note and 2 history rows persist", "Closed" in t and "Reviewed — no action" in t and NOTE in t and len(re.findall(r"(open|under_review) → (under_review|closed)", t)) == 2)
        # ---- queue reflects it
        pg.goto(UI + "/alerts"); pg.wait_for_selector("tbody tr"); pg.get_by_label("Status", exact=True).select_option("closed"); pg.wait_for_timeout(800)
        rows = pg.locator("tbody tr")
        R.ok("queue: Closed filter shows exactly this alert with its note count", rows.count() == 1 and aid in rows.first.inner_text() and "1 note" in rows.first.inner_text(), rows.first.inner_text().replace("\n", " ")[:80])
        # ---- server-side workflow guard + SQLite audit trail
        bad = api(f"/api/alerts/{aid}/status", "PATCH", {"status": "under_review"})
        R.ok("API guard: closed -> under_review rejected with 409 INVALID_TRANSITION", bad.get("_http_status") == 409 and bad["error"]["code"] == "INVALID_TRANSITION")
        con = sqlite3.connect(DB); ev = con.execute("SELECT kind, from_status, to_status, resolution FROM case_events WHERE dataset_id=? AND alert_id=? ORDER BY id", (did, aid)).fetchall(); con.close()
        R.ok("SQLite: append-only event log has 2 status events + 1 note, in order", [e[0] for e in ev] == ["status", "note", "status"] and ev[0][1:3] == ("open", "under_review") and ev[2][2:4] == ("closed", "reviewed_no_action"), str(ev))
        # ---- reopen through the UI
        pg.goto(UI + f"/alerts/{aid}"); pg.wait_for_selector("text=Case status"); pg.get_by_role("button", name="Reopen").click(); pg.get_by_role("alertdialog").get_by_role("button", name="Confirm").click()
        pg.wait_for_selector("text=Status changed to Open"); pg.wait_for_timeout(600)
        c = api(f"/api/alerts/{aid}")["case"]
        R.ok("reopen: status Open, history keeps all 3 changes, note retained", c["status"] == "open" and len(c["history"]) == 3 and len(c["notes"]) == 1)
        pg.screenshot(path="/tmp/shots/e2e_workflow.png", full_page=True)
    except Exception as ex:
        R.ok("script aborted before completion", False, f"{type(ex).__name__}: {str(ex).splitlines()[0][:180]}")
        pg.screenshot(path="/tmp/shots/e2e_workflow_abort.png")
    b.close()
R.finish()
