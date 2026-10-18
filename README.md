# Fraudulent Transaction Detection — Graph-Based Anomaly Detection & AML Risk Scoring

B.Tech CS minor project. INR-denominated digital transaction data is modelled as a graph
of accounts and transaction flows, then analysed for **anomalous / suspicious / high-risk**
activity for human investigation. The system never claims to conclusively prove fraud.

## Status: Phase 0/1 complete

This phase establishes the foundation only:

- Canonical transaction schema + strict validation (`core/data`)
- Deterministic, scenario-labelled synthetic transaction generator (`core/data/synthetic.py`)
- CSV loader built on the same validation path (`core/data/loader.py`)
- Baseline per-account behavioural features (`core/features`)
- Transaction graph construction on `networkx.MultiDiGraph` (`core/graph/builder.py`)
- Initial graph metrics: degree, weighted degree, unique counterparties, inflow/outflow ratio
  (`core/graph/metrics.py`)
- Unit tests for every module above, including edge cases
- An end-to-end demonstration script (`scripts/run_pipeline.py`)

**Not implemented yet** (by design — later phases): FastAPI, PostgreSQL, React,
authentication, anomaly detection, AML rules, risk scoring. See `docs/design_decisions.md`
for the full architecture and phase plan.

## Project layout

```
core/
  data/       canonical schema, validation, synthetic generator, CSV loader
  features/   per-account behavioural feature engineering
  graph/      MultiDiGraph construction + graph metrics
config/       central, non-hardcoded configuration (timezone, thresholds, allowed types)
tests/unit/   pytest suite, mirrors core/ structure
scripts/      run_pipeline.py — synthetic data -> validation -> features -> graph -> metrics
docs/         design decisions and rationale
```

The `core` package has **no dependency on any web framework or database** — it is a plain
Python library, importable and testable on its own. This is intentional: FastAPI/PostgreSQL
(later phases) will be thin adapters around it, not the other way round.

## Setup

```bash
cd fraud-detection
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running the demonstration pipeline

```bash
python scripts/run_pipeline.py
```

This generates a reproducible synthetic dataset, validates it, computes account features,
builds the transaction graph, computes graph metrics, and prints a summary report.

## Running tests

```bash
pytest -v
```

## Design conventions (see `docs/design_decisions.md` for full rationale)

- All timestamps are interpreted and stored in **IST (Asia/Kolkata)**.
- Currency is **INR only**; no multi-currency/crypto/card-instrument handling in this phase.
- Invalid records are never silently dropped — they are collected into a **rejects report**
  with a machine-readable reason code, so nothing disappears unexplained.
- Synthetic scenario labels (e.g. `HIGH_FANOUT`, `CIRCULAR_FLOW`) are **not** part of the
  transaction schema and are **not** fraud labels — they are kept in a separate table for
  later evaluation of the detection pipeline, so they can never leak into features or models.

---

## Web application (Graph Risk Intelligence)

A FastAPI adapter (`api/`) and a React + TypeScript frontend (`web/`) on top of the unchanged `core/` library, plus a new
`core/detection/` layer (feature matrix, AML-style rules, Isolation Forest, scoring).

> **Read this first.** Alerts are *leads for human review*, not findings of fraud. `risk_score` is an **uncalibrated ordinal
> index (0–100)**, not a probability. The built-in dataset is **synthetic**: detection results on it describe recovery of
> *injected test scenarios*, not real-world fraud-detection accuracy.

### Quick start

Requirements: Python 3.10+ and Node.js 20+ (developed on Python 3.12 / Node 22).

```bash
# 1. Backend (terminal A)
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
uvicorn api.main:app --port 8000                          # API docs: http://127.0.0.1:8000/docs

# 2. Frontend (terminal B)
cd web
npm install
npm run dev                                               # http://localhost:5173  (proxies /api -> :8000)
```

Open http://localhost:5173 and click **Generate synthetic dataset** (or go to *Data & Pipeline* to upload a CSV).

Production-style build: `cd web && npm run build` (output in `web/dist`). Point `VITE_API_BASE` at the API origin if it is not
served from the same host; set `FRAUD_CORS_ORIGINS` (comma-separated) on the backend accordingly.

### Tests and checks

```bash
pytest -q                          # backend + core (existing 59 + detection + API tests)
python scripts/run_pipeline.py     # original demonstration pipeline (unchanged)
cd web && npm run typecheck && npm test && npm run build
```

### Pages

| Page | What it does |
|---|---|
| Overview | KPIs, activity trend, severity distribution, top accounts, recent alerts, network preview, dataset info — all computed from the loaded data |
| Transactions | Search, filters (type, amount, IST date range, flagged), sorting, pagination, detail drawer |
| Network | Directed account graph (React Flow); focus/depth/min-amount/date filters; aggregated or per-transaction edges; side panel with metrics and connections |
| Alerts | Filterable queue and investigation view: score breakdown, rule evidence, model signal, related transactions, case workflow + notes (persisted in SQLite) |
| Accounts | Account list and detail, separating *observed facts*, *computed metrics*, *rule matches* and *model signal* |
| Data & Pipeline | Run the deterministic synthetic dataset, upload CSV (5 MB / 50 000 rows), accepted/rejected counts, rejects report download, detection config |

### API routes (all under `/api`; interactive docs at `/docs`)

| Method | Route | Purpose |
|---|---|---|
| GET | `/health` | Liveness, dataset-loaded flag, analysis status |
| GET | `/dataset`, `/dataset/summary` | Dataset metadata; KPIs, series, distributions |
| GET | `/transactions`, `/transactions/{id}` | Paginated/filtered listing; detail with context |
| GET | `/accounts`, `/accounts/{id}` | Account table; features, graph metrics, rule matches, timeline |
| GET | `/graph` | Bounded neighbourhood or overview (`center, depth, min_amount, from, to, mode, limit_nodes`) |
| GET | `/alerts`, `/alerts/{id}` | Queue with facets; full explanation |
| PATCH | `/alerts/{id}/status` | `open → under_review → closed` (closing needs a resolution) |
| POST | `/alerts/{id}/notes` | Investigator note |
| POST | `/analysis/run` | Start deterministic synthetic analysis (202) |
| POST | `/analysis/upload` | Validate + analyse a CSV (multipart; never written to disk) |
| GET | `/analysis/status`, `/ingest`, `/rejects`, `/rejects.csv`, `/evaluation`, `/config` | Pipeline state and reports |
| GET | `/search?q=` | Global search across accounts, alerts, transactions |

Errors use one envelope: `{"error": {"code", "message", "details"}}` (e.g. `NO_DATASET` 409, `INVALID_FILTER` 422, `FILE_TOO_LARGE` 413).

### Architecture

```
core/                      unchanged analytical library (schema, validation, features, graph)
core/detection/            NEW  model_features · rules · model (IsolationForest) · pipeline (scoring, alerts, evaluation) · config
api/                       FastAPI adapter: routers, schemas, state (in-memory session), cases (SQLite), errors
web/                       React + TS + Vite + Tailwind v4 + Recharts + React Flow (+ d3-force layout)
```

The dataset and analysis live in memory for the running process (single-user local tool). Only investigator workflow
(status changes, notes) is persisted — to SQLite at `var/cases.sqlite3` (override with `FRAUD_DB_PATH`), keyed by a content
fingerprint of the dataset so state never bleeds between datasets. There is **no authentication**; notes carry no identity.

See `docs/detection.md` for rule definitions, score semantics and known limitations.
