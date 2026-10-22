#!/usr/bin/env python3
"""Browser E2E for the Network page selectors (Colour by / Edges / Depth).

Optional dev check (Playwright is NOT a declared project dependency): pip install playwright && playwright install chromium.
Requires: API on :8000 with a dataset loaded, and the Vite dev server on :5173.
Verifies against the API, per node, that selecting an option actually changes the DISPLAYED data.
"""
import json, sys, time, urllib.request
from playwright.sync_api import sync_playwright

UI, API = "http://127.0.0.1:5173", "http://127.0.0.1:8000"
SEV = {"critical": "#ef4444", "high": "#f87171", "medium": "#fbbf24", "low": "#22d3ee"}
NEUTRAL = "#4a5a78"
PALETTE = ["#38bdf8", "#a78bfa", "#34d399", "#f59e0b", "#f472b6", "#2dd4bf", "#fb923c", "#94a3b8"]
results, errs = [], []


def ok(name, cond, extra=""):
    results.append(("PASS" if cond else "FAIL", name, extra))


def api(path):
    return json.load(urllib.request.urlopen(API + path))


def rgb(h):
    h = h.lstrip("#"); return f"rgb({int(h[0:2],16)}, {int(h[2:4],16)}, {int(h[4:6],16)})"


def rendered(pg):
    """id -> {fill, ring} read from the real DOM (computed styles of each node's circle)."""
    return pg.evaluate("""() => Object.fromEntries([...document.querySelectorAll('.react-flow__node')].map(n => {
        const c = n.querySelector('.rounded-full'); const cs = getComputedStyle(c);
        return [n.getAttribute('data-id'), {fill: cs.backgroundColor, ring: cs.boxShadow}]; }))""")


def wait_until(pg, fn, secs=10):
    t = time.time()
    while time.time() - t < secs:
        v = fn()
        if v: return v
        pg.wait_for_timeout(250)
    return fn()


def expect_risk(g):  # what Risk mode must show per node, derived from API data
    return {n["id"]: rgb(SEV[n["severity"]] if n["has_alert"] and n["severity"] else NEUTRAL) for n in g["nodes"]}


def expect_comm(g):
    return {n["id"]: rgb(PALETTE[n["community_id"] % 8]) for n in g["nodes"]}


def run():
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1440, "height": 900})
        pg.on("console", lambda m: errs.append((m.type, m.text[:200])) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errs.append(("pageerror", str(e)[:300])))
        try:
            g = api("/api/graph?limit_nodes=40&mode=aggregated")
            pg.goto(UI + "/network"); pg.wait_for_selector(".react-flow__node"); pg.wait_for_timeout(1500)

            # ---- accessible names, via role queries in a real browser
            names = {"Depth": ["1 hop", "2", "3"], "Colour by": ["Risk", "Community"], "Edges": ["Aggregated", "Individual"]}
            for grp, opts in names.items():
                ok(f"a11y: group '{grp}' exists once", pg.get_by_role("group", name=grp, exact=True).count() == 1)
                for o in opts:
                    ok(f"a11y: radio named exactly '{o}' exists once", pg.get_by_role("radio", name=o, exact=True).count() == 1)
            ok("a11y: total radios = 7 and none named after a wrapping label",
               pg.get_by_role("radio").count() == 7 and pg.get_by_role("radio", name="Colour by").count() == 0)

            # ---- Colour by: Risk (default) -> per-node fills equal API-derived expectation
            ok("colour: Risk checked by default", pg.get_by_role("radio", name="Risk", exact=True).get_attribute("aria-checked") == "true")
            r0 = {k: v["fill"] for k, v in rendered(pg).items()}
            ok("colour[risk]: every node's rendered fill matches API (severity/neutral)", r0 == expect_risk(g),
               f"{len(r0)} nodes; mismatches={[k for k in r0 if r0[k] != expect_risk(g).get(k)][:3]}")
            ok("colour[risk]: contains both alerted and neutral fills", len(set(r0.values())) >= 2, str(sorted(set(r0.values()))))

            # ---- switch to Community (mouse)
            pg.get_by_role("radio", name="Community", exact=True).click()
            want_c = expect_comm(g)
            c1 = wait_until(pg, lambda: (lambda d: d if d == want_c else None)({k: v["fill"] for k, v in rendered(pg).items()}))
            ok("colour[community]: every node's fill equals palette[community_id % 8] from API", bool(c1), f"{len(want_c)} nodes")
            ok("colour[community]: URL has color=community and radio state flipped",
               "color=community" in pg.url and pg.get_by_role("radio", name="Community", exact=True).get_attribute("aria-checked") == "true"
               and pg.get_by_role("radio", name="Risk", exact=True).get_attribute("aria-checked") == "false")
            changed = sum(1 for k in r0 if r0[k] != want_c.get(k))
            ok("colour: switching modes changed the displayed fill on most nodes", changed >= len(r0) * 0.6, f"{changed}/{len(r0)} nodes changed")
            ring = {k: v["ring"] for k, v in rendered(pg).items()}
            alerted = [n for n in g["nodes"] if n["has_alert"]]
            ok("colour[community]: each alerted node has a ring in its severity colour",
               all(rgb(SEV[n["severity"]]) in ring[n["id"]] for n in alerted), f"{len(alerted)} alerted")
            ok("colour[community]: non-alerted nodes have no ring", all(ring[n["id"]] in ("none", "") for n in g["nodes"] if not n["has_alert"]))
            ok("colour[community]: counts line shows communities + weak-structure note", "communities in dataset" in pg.inner_text("main"))

            # ---- back to Risk (keyboard: focus + Space)
            pg.get_by_role("radio", name="Risk", exact=True).focus(); pg.keyboard.press("Space")
            r2 = wait_until(pg, lambda: (lambda d: d if d == expect_risk(g) else None)({k: v["fill"] for k, v in rendered(pg).items()}))
            ok("colour: keyboard (Space) on 'Risk' restores the exact risk fills", bool(r2))
            ok("colour: URL param cleared and community summary gone", "color=" not in pg.url and "communities in dataset" not in pg.inner_text("main"))

            # ---- Edges: Aggregated <-> Individual changes the number of rendered edges to match the API
            ga, gt = api("/api/graph?limit_nodes=40&mode=aggregated"), api("/api/graph?limit_nodes=40&mode=transactions")
            ok("edges[aggregated]: DOM edge count == API", pg.locator(".react-flow__edge").count() == len(ga["edges"]), f"{pg.locator('.react-flow__edge').count()} vs {len(ga['edges'])}")
            pg.get_by_role("radio", name="Individual", exact=True).click()
            n_t = wait_until(pg, lambda: pg.locator(".react-flow__edge").count() == len(gt["edges"]) or None)
            ok("edges[individual]: DOM edge count == API and differs from aggregated", bool(n_t) and len(gt["edges"]) > len(ga["edges"]), f"{len(gt['edges'])} vs {len(ga['edges'])}")
            ok("edges[individual]: URL has mode=transactions", "mode=transactions" in pg.url)
            pg.get_by_role("radio", name="Aggregated", exact=True).click()
            n_a = wait_until(pg, lambda: pg.locator(".react-flow__edge").count() == len(ga["edges"]) or None)
            ok("edges[aggregated]: back to the aggregated edge count", bool(n_a))

            # ---- Depth: 1 hop vs 2 for a focused account changes the displayed node set
            d1, d2 = api("/api/graph?center=ACC00011&depth=1&limit_nodes=40"), api("/api/graph?center=ACC00011&depth=2&limit_nodes=40")
            pg.goto(UI + "/network?account=ACC00011"); pg.wait_for_selector(".react-flow__node")
            n1 = wait_until(pg, lambda: pg.locator(".react-flow__node").count() == len(d1["nodes"]) or None)
            ok("depth[1 hop]: DOM node count == API", bool(n1), f"{len(d1['nodes'])}")
            pg.get_by_role("radio", name="2", exact=True).click()
            n2 = wait_until(pg, lambda: pg.locator(".react-flow__node").count() == len(d2["nodes"]) or None)
            ok("depth[2]: DOM node count == API and larger than 1 hop", bool(n2) and len(d2["nodes"]) > len(d1["nodes"]), f"{len(d2['nodes'])} vs {len(d1['nodes'])}")
            ok("depth[2]: radio state + URL", pg.get_by_role("radio", name="2", exact=True).get_attribute("aria-checked") == "true" and "depth=2" in pg.url)
        except Exception as ex:  # report rather than hide
            ok("E2E aborted before completion", False, f"{type(ex).__name__}: {str(ex).splitlines()[0][:160]}")
            pg.screenshot(path="/tmp/shots/e2e_abort.png")
        b.close()


run()
for r in results:
    print(*r)
ok("no console/page errors", not errs, str(errs[:3]))
print(*results[-1])
fails = [r for r in results if r[0] == "FAIL"]
print(f"SUMMARY: {len(results)-len(fails)} passed, {len(fails)} failed")
sys.exit(1 if fails else 0)
