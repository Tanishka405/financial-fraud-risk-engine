"""Shared helpers for the optional Playwright E2E scripts. (Playwright is NOT a declared project dependency.)"""
import json, sys, time, urllib.request, urllib.error

UI = "http://127.0.0.1:5173"
API = "http://127.0.0.1:8000"


class Run:
    def __init__(self, name):
        self.name, self.results, self.errs = name, [], []

    def ok(self, label, cond, extra=""):
        self.results.append(("PASS" if cond else "FAIL", label, extra))

    def watch(self, pg, allow_4xx=False):
        def on_console(m):
            if m.type != "error":
                return
            if allow_4xx and "status of 4" in m.text:  # deliberate invalid requests produce a browser-logged 4xx
                return
            self.errs.append(("console", m.text[:200]))
        pg.on("console", on_console)
        pg.on("pageerror", lambda e: self.errs.append(("pageerror", str(e)[:300])))

    def finish(self):
        self.ok("no unexpected console/page errors", not self.errs, str(self.errs[:3]))
        for r in self.results:
            print(*r)
        fails = [r for r in self.results if r[0] == "FAIL"]
        print(f"SUMMARY[{self.name}]: {len(self.results) - len(fails)} passed, {len(fails)} failed")
        sys.exit(1 if fails else 0)


def api(path, method="GET", body=None):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"} if body is not None else {})
    try:
        return json.load(urllib.request.urlopen(req))
    except urllib.error.HTTPError as e:
        return {"_http_status": e.code, **json.loads(e.read() or b"{}")}


def wait_idle(timeout=60):
    t = time.time()
    while time.time() - t < timeout:
        s = api("/api/analysis/status")
        if s["status"] != "running":
            return s
        time.sleep(0.4)
    raise TimeoutError("analysis still running")


def ensure_synthetic(**kw):
    api("/api/analysis/run", "POST", {"source": "synthetic", **kw})
    s = wait_idle()
    assert s["status"] == "completed", s
    return api("/api/dataset")


def wait_until(pg, fn, secs=12):
    t = time.time()
    while time.time() - t < secs:
        v = fn()
        if v:
            return v
        pg.wait_for_timeout(250)
    return fn()
