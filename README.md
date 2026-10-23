# Fraudulent Transaction Detection — Graph-Based Anomaly Detection & AML Risk Scoring

B.Tech CS minor project. INR-denominated digital transaction data is modelled as a graph of accounts and
transaction flows, then analysed for **anomalous / suspicious / high-risk** activity for human investigation.

> **Read this first.**
> * Alerts are **leads for human review, not findings of fraud**. The system never claims to prove fraud.
> * `risk_score` is an **uncalibrated ordinal index (0–100)** used to prioritise review. It is **not a probability**.
> * The bundled dataset is **synthetic**. Results on it describe recovery of *injected, hand-designed test scenarios*;
>   they are **not** evidence of real-world fraud-detection accuracy. No labelled real data was used.
> * Graph-analytics model features exist behind a flag that is **off by default**, because a pre-declared 50-seed held-out
>   evaluation found **no demonstrated improvement** (see [Evaluation](#evaluation-protocol-and-results)).

## Status

A working local application, built around an unchanged Python analytical core:

| Layer | What exists |
|---|---|
| `core/data`, `core/features`, `core/graph` | Canonical schema + strict validation with a rejects report, deterministic synthetic generator, CSV loader, per-account features, `MultiDiGraph` builder and metrics, **descriptive graph analytics** (PageRank, betweenness, Louvain communities) |
| `core/detection` | Finite model-feature matrix, **9 configurable AML-style rules** with evidence, Isolation Forest baseline, scoring and alerting, synthetic-only multi-seed benchmark |
| `api/` | FastAPI adapter (22 operations), in-memory analysis session, SQLite case store |
| `web/` | React + TypeScript + Vite + Tailwind v4 frontend (Recharts, React Flow) |

Not present, by design: authentication, multi-user support, a server database, real-time streaming, model calibration.
See [`docs/architecture.md`](docs/architecture.md), [`docs/detection.md`](docs/detection.md) and
[`docs/integration_review.md`](docs/integration_review.md).

## Quick start

Requirements: **Python ≥ 3.10** and **Node.js ≥ 22.12** (the dev server and build need ≥ 20.19, but the Vitest 5 test runner needs ≥ 22.12; developed on Python 3.12 and Node 22.22). Run all commands from the repository root.

**Terminal A — backend**

```bash
python3 -m venv .venv
source .venv/bin/activate                 # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
uvicorn api.main:app --port 8000          # API docs at http://127.0.0.1:8000/docs
```

The first start takes ~15–25 s (scikit-learn/scipy import); wait for `Application startup complete`.

**Terminal B — frontend**

```bash
cd web
npm install
npm run dev                               # http://localhost:5173 (proxies /api to :8000)
```

Open <http://localhost:5173>. On first run no dataset is loaded: click **Generate synthetic dataset** (or open
*Data & Pipeline* to upload a CSV). Analysis of the default 3,098-transaction dataset takes about a second.

Optional environment variables:

| Variable | Where | Meaning | Default |
|---|---|---|---|
| `FRAUD_DB_PATH` | backend | SQLite file for investigation state | `var/cases.sqlite3` |
| `FRAUD_CORS_ORIGINS` | backend | Comma-separated allowed origins | `http://localhost:5173,http://127.0.0.1:5173` |
| `VITE_API_BASE` | frontend build | API origin if not served same-origin | empty (same origin / dev proxy) |
| `VITE_API_PROXY` | frontend dev | Vite dev-proxy target | `http://127.0.0.1:8000` |

Production-style frontend build: `cd web && npm run build` (output in `web/dist`).

## Tests and checks

```bash
# Backend + core (from the repository root, venv active)
pytest -q

# Original demonstration pipeline (unchanged from Phase 0/1)
python scripts/run_pipeline.py

# Frontend
cd web && npm run typecheck && npm test && npm run build
```

**Optional browser E2E** (Playwright is *not* a project dependency; it needs Chromium):

```bash
pip install playwright && playwright install chromium      # one-off, in any Python environment
# with the backend on :8000 and `npm run dev` on :5173, ideally with a throwaway case DB:
#   FRAUD_DB_PATH=/tmp/e2e_cases.sqlite3 uvicorn api.main:app --port 8000
cd web/e2e
python3 network_selectors.py        # colour / edges / depth selectors, per-node checks against the API
python3 graph_edge_cases.py         # account metrics; dense, truncated, empty and tiny-component graphs
python3 upload_csv.py               # CSV upload: client + server errors, partial validity, rejects report
E2E_DB=/tmp/e2e_cases.sqlite3 python3 investigation_workflow.py   # alert workflow + SQLite audit trail
```

Each script loads the data it needs through the API and exits non-zero on any failed check.
They replace the loaded dataset, so do not run them against data you want to keep.

## What the application does

| Page | Purpose |
|---|---|
| **Overview** | KPIs, activity trend, severity distribution, highest-risk accounts, recent alerts, network preview, dataset info — all computed from the loaded data |
| **Transactions** | Search, filters (type, amount, IST date range, rule-cited), sorting, pagination, detail drawer |
| **Network** | Directed account graph: focus/depth/min-amount/date filters, aggregated or per-transaction edges, colour by **Risk** or **Community**, side panel with metrics and connections |
| **Alerts** | Filterable queue and investigation view: score breakdown, rule evidence, model signal, related transactions, status workflow and notes |
| **Accounts** | List and detail, separating *observed facts*, *computed metrics*, *graph structure*, *rule matches* and the *model signal* |
| **Data & Pipeline** | Run the deterministic synthetic dataset (optionally with the STRUCTURING scenario), upload CSV, accepted/rejected counts, rejects report, detection configuration, synthetic-only evaluation |

## API

All routes are under `/api`; interactive documentation is served at `/docs`. Errors share one envelope:
`{"error": {"code", "message", "details"}}` (for example `NO_DATASET` 409, `INVALID_FILTER` 422, `FILE_TOO_LARGE` 413,
`INVALID_TRANSITION` 409).

<!-- routes:start -->
| Method | Route | Purpose |
|---|---|---|
| GET | `/api/accounts` | Account table (search, severity, has-alert, sort) |
| GET | `/api/accounts/{account_id}` | Observed facts, computed features, graph metrics, graph analytics, rule matches, model signal, timeline |
| GET | `/api/alerts` | Alert queue with filters, sorting and facets |
| GET | `/api/alerts/{alert_id}` | Full explanation, rule evidence, related transactions, case state |
| POST | `/api/alerts/{alert_id}/notes` | Add an investigator note |
| PATCH | `/api/alerts/{alert_id}/status` | `open → under_review → closed` (closing needs a resolution; `closed → open` reopens) |
| GET | `/api/analysis/config` | Rules, weights, thresholds and the score formula |
| GET | `/api/analysis/evaluation` | Synthetic-only evaluation against injected scenarios |
| GET | `/api/analysis/ingest` | Last ingestion: accepted/rejected, reason counts, ignored columns |
| GET | `/api/analysis/rejects` | Paginated rejected records with reason codes |
| GET | `/api/analysis/rejects.csv` | Rejects report download |
| POST | `/api/analysis/run` | Start the deterministic synthetic analysis (202); optional `include_structuring` |
| GET | `/api/analysis/status` | `idle` / `running` / `completed` / `failed` and the current stage |
| POST | `/api/analysis/upload` | Validate and analyse a CSV (multipart; 5 MB / 50,000 rows; never written to disk) |
| GET | `/api/dataset` | Loaded-dataset metadata (source, window, counts, notes) |
| GET | `/api/dataset/summary` | KPIs, activity series, severity distribution, top accounts, recent alerts |
| GET | `/api/graph` | Bounded overview or neighbourhood (`center, depth, min_amount, from, to, mode, limit_nodes, only_flagged`); nodes carry `community_id` |
| GET | `/api/graph/communities` | Largest dataset-wide communities (descriptive only) |
| GET | `/api/health` | Liveness, dataset-loaded flag, analysis status |
| GET | `/api/search` | Global search across accounts, alerts and transactions |
| GET | `/api/transactions` | Paginated, filterable, sortable transaction listing |
| GET | `/api/transactions/{transaction_id}` | Detail with same-pair history and the rules/alerts citing it |

22 operations.
<!-- routes:end -->

## Architecture

```
core/                  analytical library — no web framework, no database
  data/                canonical schema, validation, synthetic generator, CSV loader
  features/            per-account behavioural features
  graph/               MultiDiGraph builder, metrics, descriptive analytics
  detection/           model features, rules, Isolation Forest, scoring/alerts, benchmark
api/                   FastAPI adapter: routers, schemas, in-memory session, SQLite case store
web/                   React frontend (+ optional Playwright E2E scripts in web/e2e)
scripts/               run_pipeline.py (Phase 0/1 demo) · evaluate_detection.py (multi-seed benchmark)
docs/                  architecture, detection semantics, integration review, original design decisions
```

The dataset and its analysis live **in memory** in the running process. Only investigation state (status changes and
notes) is persisted, in SQLite, as an append-only event log keyed by a content fingerprint of the dataset. See
[`docs/architecture.md`](docs/architecture.md) for data flow, persistence and the requirements for multi-user use.

## Detection and scoring

Nine transparent, configurable rules (high velocity, large amount, repeated transactions, **structuring**, high fan-out,
pass-through, circular flow, layered multi-hop, behavioural change) produce evidence-backed **rule matches**. An
Isolation Forest provides a separate **model percentile**. They are kept distinct and combined as

```
rule_score  = 100 × (1 − ∏(1 − w))                 over distinct matched rule codes
model_score = Isolation Forest percentile within THIS dataset (relative)
risk_score  = 0.7 × rule_score + 0.3 × model_score  (= rule_score if the model did not run)
```

`risk_score` is an **ordinal index, not a calibrated probability**. Severity bands (critical ≥ 70, high ≥ 50, medium ≥ 30)
are on that index. Every rule, threshold and weight is in `core/detection/config.py` — full definitions in
[`docs/detection.md`](docs/detection.md). Synthetic scenario labels are never model features and are consumed only by the
evaluation code.

## Graph analytics and the model-feature flag

`core/graph/analytics.py` computes, for every dataset, three **descriptive structural metrics** per account:

* **PageRank** — weighted by total INR flow.
* **Betweenness centrality** — *unweighted* (the amount is not a distance), exact up to 500 accounts, otherwise a seeded
  100-source sample (disclosed in the UI and in the dataset notes).
* **Community** — seeded Louvain on transaction counts, ids relabelled deterministically (largest first).

They appear on the Account page, in the Network side panel and as an optional **Colour by: Community** mode.
They are **not risk signals** and are **excluded from the risk score**. Community structure in the bundled synthetic data
is weak (modularity ≈ 0.15) and the UI says so.

They can also be fed to the Isolation Forest as three extra model features, controlled by
`DetectionConfig.include_graph_features_in_model`:

* **Default: `False` (off).** With the flag off, scores, alerts, rule hits and the 15-column model matrix are
  byte-identical to a build without graph analytics (checked over 24 synthetic scenarios).
* **Not exposed** through the API or UI. To enable it, use the library:

  ```python
  from core.detection.config import DetectionConfig
  from core.detection.pipeline import run_analysis
  result = run_analysis(transactions_df, config, DetectionConfig(include_graph_features_in_model=True))
  ```

* **Why it is off:** on 50 held-out seeds the paired change in model-score AUC was +0.002 (95 % CI −0.004 to +0.008),
  i.e. **no demonstrated difference**; nominal changes in precision and false alerts were slightly *worse*, also not
  significant. Enable it only after evaluating on your own data.

## Evaluation protocol and results

`scripts/evaluate_detection.py` runs **controlled** evaluation on the synthetic data: it compares alerted accounts with
the generator's injected scenario participants. Labels are used only there.

```bash
python scripts/evaluate_detection.py --seeds 1-12                        # development seeds: per-signal AUC, per-role recall
python scripts/evaluate_detection.py --seeds 1-12 --include-structuring  # with the opt-in STRUCTURING scenario
python scripts/evaluate_detection.py --graph-ablation --heldout          # paired OFF/ON ablation on held-out seeds 101-150
```

* **Seeds 1–12 are development seeds** (inspected while designing); only seeds **101–150** count as held-out evidence.
* The primary metric (`auc_model_score`) and the verdict rule (“improvement” only if the 95 % bootstrap CI of the paired
  difference excludes zero) are declared in code before any result is viewed.
* *Designed-rule recall* credits only the rule intended for each scenario, because an account can also be alerted by an
  unrelated rule.

Measured on development seeds 1–12 (default dataset): alert recall 1.000, alert precision 0.926 (≈1.3 non-injected accounts
alerted per run), model-only AUC 0.712 ± 0.054, rule-score AUC 0.998. Designed-rule recall is 1.00 for every role except
`BEHAVIOURAL_CHANGE` (0.83: missed on 2 of 12 seeds). **These figures are a regression and sanity check, not an accuracy
estimate** — the rules were written alongside the scenarios.

## Known limitations

* Synthetic data only; no real labelled data, hence no precision/recall claim for real-world use, no calibration and no
  threshold tuning. Default thresholds are illustrative, not regulatory limits (the structuring threshold of INR 50,000
  is an example, not a legal reporting limit).
* Ordinary random traffic can legitimately match a rule (for example high fan-out); such alerts need human review.
* `BEHAVIOURAL_CHANGE` can miss when background traffic dilutes the shift (2 of 12 development seeds).
* Evidence lists are capped at 50 transactions per rule hit, so rule-cited transaction markers can under-report on very
  large matches. Cycle/chain search is bounded (`max_flow_results`, `max_flow_expansions`).
* Single user, no authentication: notes and status changes carry no user identity. The dataset is held in memory per
  process. Uploads are limited to 5 MB / 50,000 rows and are never written to disk.
* Graph analytics describe structure only; communities in the synthetic data are weak (modularity ≈ 0.15).
* There is no real-time ingestion: analysis is a batch process.

## Design conventions (see `docs/design_decisions.md` for full rationale)

* All timestamps are interpreted and stored in **IST (Asia/Kolkata)**; the UI displays IST.
* Currency is **INR only**; no multi-currency, crypto or card-instrument handling.
* Invalid records are never silently dropped — they are collected into a **rejects report** with machine-readable reason
  codes, and can be downloaded.
* Synthetic scenario labels (e.g. `HIGH_FANOUT`, `CIRCULAR_FLOW`) are **not** part of the transaction schema and are **not**
  fraud labels. They are kept in separate tables for evaluation only and can never reach features or models.
* `MultiDiGraph` semantics are respected: repeated transactions between the same accounts are never silently lost;
  edges are aggregated only where the UI says so.
