#!/usr/bin/env python3
"""E2E: graph metrics on the account page, plus dense / truncated / empty / tiny-component network views."""
import re
from playwright.sync_api import sync_playwright
from _common import UI, Run, api, ensure_synthetic, wait_idle, wait_until

R = Run("graph_edge_cases")
PAIRS_CSV = "transaction_id,sender_account_id,receiver_account_id,amount_inr,timestamp,transaction_type\n" + "".join(
    f"T{i},P{i}a,P{i}b,100,2024-03-01 10:0{i}:00,UPI\n" for i in range(3))


def nodes(pg): return pg.locator(".react-flow__node").count()
def edges(pg): return pg.locator(".react-flow__edge").count()
def body(pg): return pg.inner_text("main")


with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1440, "height": 900}); R.watch(pg)
    try:
        ds = ensure_synthetic(); total = api("/api/dataset/summary")["kpis"]["total_accounts"]
        # ---- account page graph-structure card vs API
        g = api("/api/accounts/ACC00011")["graph_analytics"]
        pg.goto(UI + "/accounts/ACC00011"); pg.wait_for_selector("text=Graph structure"); t = body(pg)
        R.ok("account: PageRank value matches API", f"{g['pagerank']:.4f}" in t, f"{g['pagerank']:.4f}")
        R.ok("account: community '#id · size accounts' matches API", f"#{g['community_id']} · {g['community_size']} accounts" in t)
        R.ok("account: 'NOT risk signals' disclosure present", "NOT risk signals" in t)
        R.ok("account: weak-structure warning iff modularity < 0.3", ("Weak community structure" in t) == (g["modularity"] < 0.3), f"modularity={g['modularity']:.3f}")

        # ---- truncated overview (default limit 40 of 200)
        pg.goto(UI + "/network"); pg.wait_for_selector(".react-flow__node"); pg.wait_for_timeout(1200)
        m = re.search(r"Showing the (\d+) highest-risk accounts out of (\d+)", body(pg))
        R.ok("truncated overview: banner states shown/total", bool(m) and int(m.group(2)) == total, m.group(0) if m else "no banner")
        R.ok("truncated overview: rendered nodes <= limit and match the banner", bool(m) and nodes(pg) == int(m.group(1)) <= 40, f"{nodes(pg)} nodes")

        # ---- dense: all accounts (limit 300) -> no truncation, all rendered
        pg.get_by_label("Maximum nodes").select_option("300")
        ok_dense = wait_until(pg, lambda: nodes(pg) == total or None, 30)
        R.ok("dense: all accounts rendered with max-nodes=300", bool(ok_dense), f"{nodes(pg)} of {total} nodes, {edges(pg)} edges")
        R.ok("dense: no truncation banner (accounts <= limit)", "Showing a limited view" not in body(pg))
        gd = api("/api/graph?limit_nodes=300&mode=aggregated")
        R.ok("dense: DOM edge count == API", edges(pg) == len(gd["edges"]), f"{edges(pg)} vs {len(gd['edges'])}")
        # still interactive: selecting a node opens the side panel
        pg.locator(".react-flow__node").first.click(); pg.wait_for_timeout(800)
        R.ok("dense: node selection still works (side panel shows account)", "Focus neighbourhood" in body(pg))
        pg.screenshot(path="/tmp/shots/e2e_dense.png")

        # ---- centred depth 3, truncated by limit
        pg.goto(UI + "/network?account=ACC00011&depth=3"); pg.wait_for_selector(".react-flow__node"); pg.wait_for_timeout(1200)
        R.ok("depth-3 centred: truncated banner + node cap", "Showing a limited view" in body(pg) and nodes(pg) <= 40, f"{nodes(pg)} nodes")

        # ---- empty graph via filter, and recovery
        pg.goto(UI + "/network"); pg.wait_for_selector(".react-flow__node")
        pg.get_by_label("Minimum transaction amount").fill("1000000000000")
        pg.wait_for_selector("text=No transactions in this view", timeout=15000)
        R.ok("empty: friendly empty state shown, no graph canvas", nodes(pg) == 0)
        pg.get_by_role("button", name="Reset filters").click()
        R.ok("empty: 'Reset filters' recovers the graph", bool(wait_until(pg, lambda: nodes(pg) > 0 or None)), f"{nodes(pg)} nodes")

        # ---- tiny disconnected components (upload through the API, view through the UI)
        r = pg.request.post(UI + "/api/analysis/upload", multipart={"file": {"name": "pairs.csv", "mimeType": "text/csv", "buffer": PAIRS_CSV.encode()}})
        R.ok("tiny: upload accepted (202)", r.status == 202, str(r.status)); wait_idle()
        pg.goto(UI + "/network"); pg.wait_for_selector(".react-flow__node"); pg.wait_for_timeout(1200)
        R.ok("tiny: 3 disconnected pairs render 6 nodes and 3 edges", nodes(pg) == 6 and edges(pg) == 3, f"{nodes(pg)} nodes, {edges(pg)} edges")
        R.ok("tiny: no truncation banner for a small graph", "Showing a limited view" not in body(pg))
        R.ok("tiny: communities panel lists 3 two-account communities", len(re.findall(r"· 2 accounts", body(pg))) >= 3)
        pg.goto(UI + "/accounts/P0a"); pg.wait_for_selector("text=Graph structure"); t = body(pg)
        R.ok("tiny: account card explains a very small group, zero betweenness shown as a number", "Very small group" in t and "0.0000" in t)
        R.ok("tiny: no weak-structure warning (modularity of 3 disjoint pairs is high)", "Weak community structure" not in t)
        pg.screenshot(path="/tmp/shots/e2e_tiny.png")
    except Exception as ex:  # report, never hide
        R.ok("script aborted before completion", False, f"{type(ex).__name__}: {str(ex).splitlines()[0][:180]}")
        pg.screenshot(path="/tmp/shots/e2e_edge_abort.png")
    b.close()
R.finish()
