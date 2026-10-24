# Integration review: AML-Network-Graph-Engine prototype → this application

**Purpose.** An older prototype (`Tanishka405/AML-Network-Graph-Engine`, HEAD `94cfdc4`, 2026-10-01) claims SQL structuring
detection, NetworkX graph analytics, community analysis, circular-flow and multi-hop detection, 22-feature engineering, an
Isolation Forest, five AML rules, composite scoring, a FastAPI/WebSocket backend, a Streamlit dashboard, evaluation scripts and
tests. This review **verifies those claims against the source and by running the code**, compares both projects, and records
what was integrated, adapted, deferred or deliberately not reused. READMEs were treated as claims, not evidence.

A third repository (`apurva234-12/fraud-detection`, HEAD `f57b9fc`) has a byte-identical `core/` plus a PostgreSQL layer and a small
API stub, and one empty test file. It needs a live PostgreSQL that was unavailable here, so it was inspected but **not run**, and its
database layer was **not** adopted.

Base for this work: `financial-fraud-risk-engine` (upstream `main` at `5efab17`).

## Method and what was actually run

* Both repositories were cloned into separate directories; neither was modified.
* Prototype: full pinned environment installed; its own test suite run; its evaluation and SQL benchmark scripts run; suspected defects
  tested empirically with the prototype's own code (`docs/evidence/verify_prototype_claims.py`, reproduced at release time).
* This application: every comparison claim about it was checked against its source, tests or a run.

## Capability comparison

| Capability | This application | Prototype | Verified status and evidence | Decision |
|---|---|---|---|---|
| Transaction schema and validation | INR, account IDs, 6 types; row-level validator, 9 reject codes, rejects returned (`core/data/validators.py`) | USD, 7 currencies, 14 jurisdictions; `pattern_type` label stored in the transactions table; 14 post-hoc SQL checks that only *report* (`backend/data_quality.py`) | Both work. Jurisdiction/currency do not exist in this schema | **Keep ours.** Do not import jurisdiction/currency (would invent attributes) |
| Synthetic data | Deterministic; 10 scenario roles; labels in separate frames | Seeded generator. **Verified:** 45.2 % suspicious, timeline trimmed to 1 Jan–20 Jul of a configured year, HR-jurisdiction flag true on 75 % of *normal* rows | Reproduced with the prototype's own code | **Keep ours**; add one *opt-in* scenario (structuring) |
| Behavioural features | 15 per-account features, finite matrix, label-column guard | 22 per-transaction features that include rule outputs (`structuring_score`, `in_cycle`, …) which the composite then adds again | Source read (`feature_engineering.py`, `risk_engine.py`) | **Keep ours** |
| Graph construction and analytics | `MultiDiGraph`, repeats preserved; now PageRank, unweighted betweenness, seeded Louvain (descriptive) | `DiGraph`; betweenness, eigenvector, PageRank, greedy-modularity communities | Implemented and functional, but betweenness uses amount as a *distance*; window expiry uses `time.time()` so historical timestamps gave **0 edges** | **Adapt** concepts, fix both flaws |
| Circular and multi-hop | Time-ordered, amount-preserving cycle and chain search, bounded | “Circular” = membership of any SCC ≥ 2; “multi-hop” = shortest path between a transaction's own endpoints | **Verified broken:** SCC flags **100 %** of nodes (also 100 % on this app's data); multi-hop is **0 / 6,000** in pipeline order; its layering score never enters the composite | **Keep ours. Not reused** |
| AML rule coverage | 9 rules with evidence (incl. new structuring) | 5 rules | Prototype had structuring (lacking here). Its jurisdiction rule fires on 75 % of normal data | **Adapt structuring** (band-limited, INR); drop jurisdiction rule |
| Isolation Forest | Account-level, finite log features, seeded, skipped < 30 accounts | Transaction-level, RobustScaler (no effect on trees), arbitrary score mapping, retrain loop | Source read | **Keep ours** |
| Score semantics and explainability | Ordinal 0–100, rule/model/combined separate, formula and disclaimers shown | Fixed-weight 0–1 composite, text reasons | Neither is calibrated | **Keep ours** |
| Evaluation and label leakage | Injected-scenario recovery; now multi-seed, per-role, ablation, held-out protocol | 60/20/20 time split. **Look-ahead:** the graph is extended with val/test and recomputed before scoring them; train/test features computed differently | Its headline numbers reproduce only *approximately* (mine 85.04/55.16/66.91 vs README 86.39/53.82/66.33) | **Improve ours** |
| API architecture | 22 operations, pagination, error envelope, background job, size-limited upload | 6 routes, no pagination, CORS `*`, WebSocket stream | Source read | **Keep ours**; no WebSocket (no fake live monitoring) |
| Persistence and schema | In-memory dataset; SQLite append-only case events | SQLite WAL (transactions, alerts, evaluation, DQ tables); no status/notes | Neither uses PostgreSQL | **Keep SQLite**; multi-user needs listed in `docs/architecture.md` |
| Investigation workflow and audit | Status workflow, notes, history, persisted | None (`alerts` is insert-only) | Schema read | **Keep ours** |
| Frontend | React, 6 pages | Streamlit, 7 tabs | Streamlit **not run** | **Keep React** |
| Tests, performance, deployment | See *Verification status* | 163 tests pass (verified). Evaluation of 20,000 tx ≈ 51 s. **CI installs `requirements.txt` (3 packages), so it cannot run the tests** | Docker not built here | **Keep ours** |

## Findings about the prototype (all reproduced)

| Claim or design | Observation | Evidence |
|---|---|---|
| “Rolling-window graph” | Expiry uses wall-clock time; historical timestamps yield 0 edges | 0 edges after 500 inserts via `build_graph_from_transactions` |
| “Circular flow” via SCC | Giant SCC contains every account → constant feature | 200 / 200 nodes “in cycle” |
| “Multi-hop” indicator | Evaluated after the transaction's own edge is added → always 0; if evaluated before, it is nonzero for most pairs (“any reachable pair”) | 0 / 6,000 vs 5,064 / 6,000 |
| High-risk-jurisdiction rule | Normal traffic draws jurisdictions from all 14 codes (7 high-risk) | fires on 75 % of normal rows, 100 % of its pattern |
| Label rate | Patterns over-produced then the *latest* rows trimmed | 45.2 % suspicious, ends 20 Jul |
| Betweenness | Amount passed as an edge weight (a distance) | `graph_engine.py` source |
| Community tests | Assertions such as `community_id >= -1` are vacuous | `tests/` source |
| Evaluation | Look-ahead in graph features for val/test | `scripts/evaluate_detection.py` source |
| CI | Installs three packages; cannot run the test suite | `.github/workflows` + `requirements.txt` |

## Integration decisions

* **Kept:** schema/validation, synthetic generator, features, `MultiDiGraph`, rules, scoring, FastAPI service, React frontend, case workflow.
* **Adapted:** structuring concept → `STRUCTURING` rule (INR, *bounded below*, evidence, opt-in scenario); PageRank, betweenness and communities →
  `core/graph/analytics.py` with the two flaws fixed; the idea of a leakage-aware evaluation → multi-seed, held-out, paired benchmark.
* **Not reused (defective or inapplicable):** SCC circular flow, shortest-path multi-hop, jurisdiction rule, wall-clock rolling window,
  composite weights, transaction-level Isolation Forest design.
* **Deferred (no demonstrated value yet):** PostgreSQL, WebSocket streaming, BI/Power BI exports, extra data-quality report, Docker.

## What changed, by increment

| Commit | Change |
|---|---|
| `ca8f86a` | Checkpoint of the application before integration |
| `4ae11f6` | Increment 1 — multi-seed evaluation harness with designed-rule recall |
| `cd5c240` | Increment 2 — `STRUCTURING` rule, opt-in scenario (default output byte-identical), API flag, UI toggle |
| `64eba8a` | Increment 3 — graph analytics, flag-gated model features (default **off**), held-out paired ablation, API + UI, accessibility fix for segmented controls |
| `2e251bb` | Increment 4 — documentation matched to verified behaviour, docs-consistency tests, E2E scripts, model-only severity correction |
| `dd33c53` | Increment 4 — stale dependency documentation corrected (verified with an AST import scan), `pydantic`/`starlette` declared, enforcing test |
| (this commit) | Records the final verification results in this document; documentation only |

## Evidence on graph features (no improvement is claimed)

* **Exploratory (development seeds 1–12):** SCC giant component 100 %; PageRank/betweenness AUC ≈ 0.68; community-size AUC 0.42 (below chance);
  37.5 % of scenario groups share one community. Not valid evidence for a decision.
* **Held-out, pre-declared (seeds 101–150, primary metric `auc_model_score`):** ON − OFF = **+0.002**, 95 % CI **[−0.004, +0.008]**, 28 wins / 22 losses,
  Wilcoxon p = 0.40 → **no demonstrated difference**. Precision 0.909 → 0.905 and false-alert accounts 1.68 → 1.78 were nominally slightly worse
  (not significant). The model-feature flag therefore stays **off**, and graph metrics are shown as descriptive structure only.
* An earlier ad-hoc figure (+0.005 AUC) used a different feature set and is superseded by the held-out result.

## Verification status

Statuses: **PASS** = run and met its criterion; **FAIL**; **BLOCKED** = could not be run; **NOT RUN**. “Release tree” = the committed tree plus the
documentation, tests and E2E scripts of this increment.

| Check | Command | Status | Result |
|---|---|---|---|
| Backend and core tests | `pytest -q` | **PASS** | 181 passed (exit 0) |
| Docs-consistency tests (mutation-tested: 3 deliberate drifts each failed) | `pytest -q tests/unit/test_docs_consistency.py` | **PASS** | 10 passed |
| Dependency claims, AST-based incl. function-level imports (mutation-tested: 4 deliberate regressions each failed) | `pytest -q tests/unit/test_dependencies.py` | **PASS** | 4 passed |
| Frontend typecheck | `cd web && npm run typecheck` | **PASS** | exit 0 |
| Frontend tests | `cd web && npm test` | **PASS** | 45 passed, 7 files |
| Frontend production build | `cd web && npm run build` | **PASS** | built, exit 0 |
| E2E: investigation workflow (UI + API + SQLite) | `E2E_DB=… python3 web/e2e/investigation_workflow.py` | **PASS** | 16 / 16 |
| E2E: persistence across API restart | restart on same DB, reload identical dataset | **PASS** | status, 3 history events and note restored |
| E2E: CSV upload through the UI | `python3 web/e2e/upload_csv.py` | **PASS** | 21 / 21 |
| E2E: dense / truncated / empty / tiny-component graphs | `python3 web/e2e/graph_edge_cases.py` | **PASS** | 20 / 20 |
| E2E: Colour / Edges / Depth selectors (per-node vs API) | `python3 web/e2e/network_selectors.py` | **PASS** | 30 / 30 |
| Prototype claims reproduced | `docs/evidence/verify_prototype_claims.py` | **PASS** | all findings above reproduced |
| Prototype test suite (at `94cfdc4`) | `pytest tests/` in the prototype | **PASS** (earlier in this engagement) | 163 passed; not re-run for this release |
| Prototype headline metrics | `scripts/evaluate_detection.py`-equivalent in prototype | **PARTIAL** | approximate reproduction only (see table) |
| Clean-start smoke: fresh `git clone` (no venv, `node_modules` or `var/`) | `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"` | **PASS** | exit 0 (resolved newer dependency versions than development: FastAPI 0.162, pandas 3.1) |
| Clean-start smoke: frontend install | `cd web && npm install` | **PASS** | exit 0, 0 vulnerabilities |
| Clean-start smoke: servers from the README commands | `uvicorn api.main:app --port 8000`, `npm run dev` | **PASS** | both healthy; “Application startup complete”; default case DB auto-created |
| Clean-start smoke: first-run browser flow | generate dataset → overview, alerts, alert detail, network, transactions, account, data page | **PASS** | 11 / 11 (3,098 tx, 200 accounts, 16 alerts, 9 rules listed) |
| Clean-start smoke: README test commands in the clone | `pytest -q`, `python scripts/run_pipeline.py`, `npm run typecheck`, `npm test`, `npm run build` | **PASS** | 181 passed; pipeline 3,098 tx / 200 accounts; typecheck exit 0; 45 tests passed; build exit 0 |
| Prototype Streamlit frontend | — | **NOT RUN** | needs a server/session |
| Docker builds (either project) | — | **NOT RUN** | Docker unavailable |
| Prototype SQL benchmark at 500 k rows (`--full`) | — | **NOT RUN** | default mode only was run |
| This app at the 50,000-row upload limit | — | **NOT RUN** | size/row limits verified, not a full-size analysis |
| Browsers other than Chromium; screen-reader testing | — | **NOT RUN** | accessible names are asserted via role queries only |
| Phone-width layout on the current UI | — | **NOT RUN** this release | checked earlier in the project, before these changes |
| Evaluation on real labelled data | — | **BLOCKED** | no such data exists |
| PostgreSQL layer of the third repository | — | **BLOCKED** | no PostgreSQL available; not adopted |

Notes on the final pass: all E2E scripts ran on freshly started servers with a case database that did not exist beforehand. The first smoke attempt
reported one failure that was a **wrong test assertion** (the browser's `innerText` returns CSS-uppercased text, so “Weight” was not found); the
application correctly rendered all 9 rules, and the assertion was replaced by an exact rule-row check. A one-line unused `from fastapi import Query`
inside `api/routers/system.py::rejects` and the `pyproject.toml` version (`0.1.0`, versus API version `0.2.0`) were noticed and deliberately left unchanged.

## Known limitations

See `README.md` and `docs/detection.md`. In short: synthetic data only; no calibration or real-world accuracy claim; rules were written
alongside the scenarios; single user, no authentication; in-memory dataset; bounded temporal search; weak community structure in the synthetic data.

## Remaining work

1. Validate on real, labelled data before any accuracy claim; calibrate or keep scores explicitly ordinal.
2. Multi-user deployment (see `docs/architecture.md`): per-user datasets, persisted analyses, authentication, server database.
3. Re-evaluate the graph-feature flag on real data; enable only if a held-out comparison shows a benefit.
4. Optional: Dockerfile, CI that actually installs and runs the test suites, cross-browser and phone-width E2E, 50,000-row load test.
