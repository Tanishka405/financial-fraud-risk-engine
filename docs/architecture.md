# Architecture

A modular Python analytical core, a single FastAPI service that adapts it to HTTP, and a React frontend. The core has **no web
framework or database dependency**; the API and UI are thin adapters around it.

```
                       ┌──────────────────────────── core/ (pure Python) ────────────────────────────┐
 CSV upload ──┐        │ data/validators ─► data/schema ─► features ─► graph (MultiDiGraph) ─► metrics │
 Synthetic ───┴─►      │                                      │                       │               │
 generator (seeded)    │                              detection/model_features   graph/analytics      │
                       │                                      │                  (descriptive only)   │
                       │                  detection/rules ──► detection/pipeline ◄─ detection/model    │
                       │                       (evidence)        (scores, alerts)    (Isolation Forest)│
                       └───────────────────────────────────┬─────────────────────────────────────────┘
                                                           │ AnalysisResult (in memory)
   api/state.Session (process-wide, in memory) ◄───────────┘
        │   background thread: validate → analyse → build view
        ├── api/routers/*   22 operations, pagination, filters, bounded graph queries
        └── api/cases.CaseStore ──► SQLite (investigation events only)
                                       ▲
   web/ (React + TS)  ──HTTP /api──────┘      Vite dev proxy → :8000
```

## Modules

| Path | Responsibility |
|---|---|
| `core/data/` | Canonical schema; row-level validation with machine-readable reject reasons; deterministic synthetic generator (labels in separate frames); CSV loader and `validate_raw_dataframe` (the in-memory path used by uploads) |
| `core/features/` | Per-account behavioural features |
| `core/graph/` | `MultiDiGraph` builder (repeated transactions preserved), degree/counterparty metrics, descriptive analytics |
| `core/detection/` | Model-feature matrix, rules, Isolation Forest, scoring and alerting, synthetic-only benchmark |
| `api/` | FastAPI application, routers, response schemas, error envelope, in-memory `Session`, SQLite `CaseStore` |
| `web/src/` | `api/` (typed client, hooks), `components/` (ui, layout, charts, domain), `features/network/` (layout, nodes, edges, palette, legend), `pages/`, `test/` |
| `web/e2e/` | Optional Playwright scripts (not a project dependency) |

## Data flow

1. **Ingest.** Either `generate_synthetic_dataset(...)` (seeded; optional opt-in STRUCTURING scenario) or a CSV upload parsed
   from memory (UTF-8, ≤ 5 MB, ≤ 50,000 rows). Both go through the same `validate_batch` path; invalid rows go to a rejects
   report with reason codes. Extra CSV columns are ignored and disclosed, and never reach features.
2. **Analyse.** `run_analysis` builds features, the graph, graph analytics, the model matrix, rule hits, the Isolation Forest
   and scores/alerts. It runs in a background thread so the UI can show *running / completed / failed*. A failed upload does not
   replace the previously loaded dataset.
3. **Serve.** Routers read the in-memory result. A content fingerprint (`dataset_id`) identifies the dataset.
4. **Investigate.** Status changes and notes are appended to SQLite, keyed by `(dataset_id, alert_id)`.

## Persistence

* **In memory (per process):** the dataset, analysis result, graph analytics, rejects report. Lost on restart; regenerate with the
  same seed (or re-upload the same file) to get the identical `dataset_id`.
* **SQLite (`var/cases.sqlite3`, override with `FRAUD_DB_PATH`):** one append-only table.

  | Column | Meaning |
  |---|---|
  | `id` | autoincrement |
  | `dataset_id`, `alert_id` | the case key |
  | `kind` | `status` or `note` (CHECK-constrained) |
  | `from_status`, `to_status`, `resolution`, `body` | event payload |
  | `created_at` | IST ISO timestamp |

  Current state is derived from the latest `status` event, so history is never rewritten. Workflow: `open → under_review → closed`,
  `closed → open` (reopen); closing requires a resolution (`reviewed_no_action`, `reviewed_escalate`, `data_quality_issue`).
  There is deliberately **no “confirmed fraud” outcome**. Events carry **no user identity** because there is no authentication.
* Verified: case state survives an API restart against the same database file when the same dataset is reloaded.

### Is SQLite adequate? A single-user answer, and what multi-user would need

For the intended **single-user, local** deployment, yes: investigation state is tiny and append-only, and nothing else needs a
database. PostgreSQL was therefore **not** added. The real blocker for multi-user use is not SQLite but the **process-wide
in-memory session**, so a multi-user deployment would need, at minimum:

1. per-user or per-workspace dataset isolation (the global `Session` singleton cannot serve two users with different data);
2. persisted datasets and analyses (or a reproducible job store) so restarts and multiple workers do not lose them;
3. authentication and authorisation, with a user identity on every case event (currently none);
4. a server database for case events with concurrent-writer semantics (PostgreSQL, or SQLite in WAL mode for a very small team);
5. a shared analysis cache/queue instead of an in-process thread, for more than one worker process.

None of this is implemented.

## API behaviour

* One error envelope for every failure; no stack traces or filesystem paths are returned.
* Pagination (`page_size` ≤ 200), whitelisted sort fields, validated filters; invalid input is a 422 with a machine-readable code.
* **Bounded graph queries:** at most 300 nodes; individual-transaction mode is capped at 1,500 edges (largest by amount) and says
  when it truncated. Neighbourhood expansion keeps the highest-risk, best-connected accounts first.
* Uploads are size- and row-limited and never written to disk. CORS defaults to the local dev origins only.
* No secrets are used or stored.

## Frontend

React 19 + TypeScript + Vite + Tailwind v4; Recharts for charts; React Flow with a deterministic d3-force layout for the network;
TanStack Query for data fetching. Pages are code-split. API types mirror the backend contracts in `web/src/api/types.ts`.
Accessibility notes: a composite control (for example a segmented radio group) must use `<Field group>` and not a wrapping
`<label>`, which would otherwise rename its first option.

## Performance (measured on the development machine)

* Default synthetic dataset (3,098 transactions, 200 accounts): full analysis ≈ 1 s.
* Network view with all 200 accounts and 2,975 aggregated edges renders and stays interactive (verified in a browser).
* Cycle/chain search is bounded; betweenness switches to a seeded sample above 500 accounts. Larger datasets have **not** been
  benchmarked.

## Key decisions

* **Account-level scoring**, not per-transaction: a transaction's risk is described through the accounts involved.
* **Rules and the model are kept separate** and the combination is an explicit, documented formula — not a hidden composite.
* **Temporal flow search instead of SCC membership** for circular flow (see `docs/detection.md`).
* **Descriptive graph analytics, not model inputs by default**, because held-out evaluation showed no demonstrated gain.
* **Labels isolated by construction**: separate frames, a column-name guard, and evaluation-only consumption.
