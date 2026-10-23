# Detection layer

Everything here is implemented in `core/detection/` and `core/graph/analytics.py`, with no web or database dependency.
**All thresholds and weights live in `core/detection/config.py` (`DetectionConfig`)** — none are hard-coded in rule logic.
Defaults are illustrative academic values, not regulatory thresholds, and are not tuned to any dataset.

> Alerts are leads for human review, not findings of fraud. `risk_score` is an uncalibrated ordinal index, not a probability.
> No result in this repository estimates real-world fraud-detection accuracy.

## Pipeline

`run_analysis(transactions, config, detection_config)` in `core/detection/pipeline.py`:

1. per-account behavioural features (`core/features`) and graph metrics on a `MultiDiGraph` (`core/graph`);
2. descriptive graph analytics (PageRank, betweenness, communities) — failure here is contained and noted, it never breaks detection;
3. the finite model-feature matrix;
4. the AML-style rules (each hit carries evidence);
5. the Isolation Forest (skipped, and said so, when there are fewer than `model_min_accounts` accounts);
6. scoring, severity and alert generation.

## Model features (`model_features.py`)

One row per account, finite floats only. Counts, amounts and degrees are `log1p`-transformed. `inflow_outflow_ratio`
can be `+inf` (a pure sink) and is **never** passed on: it becomes `log_inflow_outflow_ratio = clip(log10((in+1)/(out+1)), −4, 4)`
plus the indicators `is_pure_sink` and `is_pure_source`. The builder rejects any column whose name contains `scenario`,
`label` or `fraud`, so synthetic scenario labels cannot enter the matrix; they are used only by
`evaluate_on_synthetic` and `core/detection/benchmark.py`.

* **Base matrix: 15 columns** (always used).
* **Graph columns (3, optional):** `log_pagerank_rel`, `log1p_betweenness_rel`, `log_community_size`. Appended **only** when
  `include_graph_features_in_model` is `True`. **Default `False`.** See [Graph analytics](#graph-analytics-descriptive).

## Rules (`rules.py`)

A rule hit means “this account matches a pattern worth a human look”, **not** that fraud occurred. Each hit carries a weight,
the account's role, a plain-language summary built from the actual triggering values, transaction-id evidence (capped at 50
per hit) and metrics. Tables below are generated from the code.

| Code | Weight | What it detects |
|---|---|---|
| `HIGH_VELOCITY` | 0.45 | Many outgoing transactions inside a short sliding window. |
| `LARGE_AMOUNT` | 0.35 | A single transaction far above an absolute or dataset-relative amount threshold. |
| `REPEATED_TRANSACTIONS` | 0.40 | The same sender paid the same receiver the same amount many times. |
| `HIGH_FANOUT` | 0.40 | One account sent funds to an unusually large number of distinct receivers. |
| `PASS_THROUGH` | 0.55 | Received funds were forwarded almost in full shortly afterwards, repeatedly. |
| `CIRCULAR_FLOW` | 0.65 | Funds moved through a short, time-ordered loop and returned to the origin account. |
| `LAYERED_MULTI_HOP` | 0.55 | Funds moved along a time-ordered chain of distinct accounts with little amount lost. |
| `STRUCTURING` | 0.50 | Several transactions each just below a reporting-style threshold, sent by one account within a short window. |
| `BEHAVIOURAL_CHANGE` | 0.40 | Sent amounts shifted sharply upward between the earlier and later half of the account's activity (rank test). |

Semantics worth knowing:

* **HIGH_VELOCITY** — ≥ `velocity_min_txns` sent transactions inside any `velocity_window_minutes` sliding window.
* **LARGE_AMOUNT** — a single transaction ≥ min(`large_amount_inr`, `large_amount_p99_multiple` × dataset p99). The percentile
  branch applies only with ≥ `large_amount_min_dataset_size` transactions. The receiver gets `receiver_weight_factor` × weight.
* **REPEATED_TRANSACTIONS** — same sender, receiver **and exact amount**, ≥ `repeated_min_count` times.
* **STRUCTURING** — ≥ `structuring_min_txns` transactions **each in the band [`structuring_band_floor` × T, T)**, where
  T = `structuring_threshold_inr`, from one sender inside `structuring_window_minutes`. The band is bounded *below* on
  purpose: ordinary small payments are not “just under” a threshold. Amounts at or above T never count. T is an
  illustrative parameter (default INR 50,000), **not** a legal reporting limit; set it to the limit relevant to your data.
* **HIGH_FANOUT** — distinct receivers over the dataset window ≥ `fanout_min_receivers`.
* **PASS_THROUGH** — inflows matched one-to-one with a later outflow within `pass_through_window_minutes` retaining
  90–102 % of the amount, ≥ `pass_through_min_pairs` pairs.
* **CIRCULAR_FLOW** — a time-ordered loop of 3–4 accounts inside `cycle_window_hours`, each hop keeping 80–105 % of the previous amount.
* **LAYERED_MULTI_HOP** — a time-ordered chain of ≥ 4 hops through distinct accounts inside `layered_window_hours`, same retention bounds.
  Endpoints receive `receiver_weight_factor` × weight.
* **BEHAVIOURAL_CHANGE** — later-half sent amounts higher than the earlier half: median ratio ≥ `behaviour_median_ratio`
  **and** a one-sided Mann–Whitney p ≤ `behaviour_p_value`, with ≥ `behaviour_min_per_half` transactions in each half.

Cycle and chain search is *temporal* (edges must be time-ordered and amount-preserving) and **bounded** by
`max_flow_results` and `max_flow_expansions`. It deliberately does **not** use strongly-connected-component membership: on a
dense transaction graph a giant SCC contains essentially every account (100 % of accounts on this project's synthetic data), so
“in an SCC” carries no information.

## Configuration reference (generated from `DetectionConfig`)

| Used by | Parameter | Default |
|---|---|---|
| HIGH_VELOCITY | `velocity_window_minutes` | `60` |
| HIGH_VELOCITY | `velocity_min_txns` | `10` |
| LARGE_AMOUNT | `large_amount_inr` | `1000000.0` |
| LARGE_AMOUNT | `large_amount_p99_multiple` | `5.0` |
| LARGE_AMOUNT | `large_amount_min_dataset_size` | `50` |
| LARGE_AMOUNT | `receiver_weight_factor` | `0.5` |
| REPEATED_TRANSACTIONS | `repeated_min_count` | `5` |
| STRUCTURING | `structuring_threshold_inr` | `50000.0` |
| STRUCTURING | `structuring_band_floor` | `0.8` |
| STRUCTURING | `structuring_window_minutes` | `120` |
| STRUCTURING | `structuring_min_txns` | `4` |
| HIGH_FANOUT | `fanout_min_receivers` | `25` |
| PASS_THROUGH | `pass_through_window_minutes` | `120` |
| PASS_THROUGH | `pass_through_min_retention` | `0.9` |
| PASS_THROUGH | `pass_through_max_retention` | `1.02` |
| PASS_THROUGH | `pass_through_min_pairs` | `2` |
| CIRCULAR_FLOW / LAYERED_MULTI_HOP | `flow_min_retention` | `0.8` |
| CIRCULAR_FLOW / LAYERED_MULTI_HOP | `flow_max_retention` | `1.05` |
| CIRCULAR_FLOW / LAYERED_MULTI_HOP | `cycle_min_length` | `3` |
| CIRCULAR_FLOW / LAYERED_MULTI_HOP | `cycle_max_length` | `4` |
| CIRCULAR_FLOW / LAYERED_MULTI_HOP | `cycle_window_hours` | `24.0` |
| CIRCULAR_FLOW / LAYERED_MULTI_HOP | `layered_min_hops` | `4` |
| CIRCULAR_FLOW / LAYERED_MULTI_HOP | `layered_max_hops` | `6` |
| CIRCULAR_FLOW / LAYERED_MULTI_HOP | `layered_window_hours` | `24.0` |
| CIRCULAR_FLOW / LAYERED_MULTI_HOP | `max_flow_results` | `500` |
| CIRCULAR_FLOW / LAYERED_MULTI_HOP | `max_flow_expansions` | `1000000` |
| BEHAVIOURAL_CHANGE | `behaviour_min_txns` | `8` |
| BEHAVIOURAL_CHANGE | `behaviour_min_per_half` | `4` |
| BEHAVIOURAL_CHANGE | `behaviour_median_ratio` | `3.0` |
| BEHAVIOURAL_CHANGE | `behaviour_p_value` | `0.001` |
| Model | `model_enabled` | `True` |
| Model | `model_min_accounts` | `30` |
| Model | `model_n_estimators` | `200` |
| Model | `model_random_state` | `42` |
| Model | `include_graph_features_in_model` | `False` |
| Scoring and alerting | `rule_share` | `0.7` |
| Scoring and alerting | `alert_min_combined_if_rule_hit` | `0.0` |
| Scoring and alerting | `model_only_alert_percentile` | `99.0` |
| Scoring and alerting | `severity_critical` | `70.0` |
| Scoring and alerting | `severity_high` | `50.0` |
| Scoring and alerting | `severity_medium` | `30.0` |

## Scores

* `rule_score = 100 × (1 − ∏(1 − w))` over the *distinct* rule codes an account matched (the maximum weight per code).
* `model_score` = Isolation Forest **percentile within the dataset** (relative: “more unusual than N % of accounts here”;
  not comparable across datasets; not a probability). Not computed with fewer than `model_min_accounts` accounts.
* `risk_score = rule_share × rule_score + (1 − rule_share) × model_score` (= `rule_score` if the model did not run).
  **An ordinal index for review priority — uncalibrated.** No calibration has been performed or demonstrated.
* Severity bands apply to `risk_score`: critical ≥ `severity_critical`, high ≥ `severity_high`, medium ≥ `severity_medium`, else low.
* **Alert basis:** any rule hit raises an alert (`RULES` / `RULES+MODEL`). With no rule hit, an alert is raised only if the
  model percentile ≥ `model_only_alert_percentile` (`MODEL_ONLY`). Its `rule_score` is 0, so its `risk_score` is at most `(1 − rule_share) × 100` = 30: low severity, except that a model percentile of exactly 100 lands on the medium boundary (≥ 30) and is labelled medium.
* The three scores are always returned separately. Feature deviations shown with alerts are descriptive robust z-scores, **not**
  model attributions (Isolation Forest has none).

## Graph analytics (descriptive)

`core/graph/analytics.py`, computed from the aggregated directed graph (parallel edges summarised there; the source
`MultiDiGraph` is untouched):

| Metric | Definition | Why it is defined this way |
|---|---|---|
| PageRank | Weighted by total INR per ordered account pair | Weight = flow, where larger should mean more rank |
| Betweenness | **Unweighted**, normalised; exact up to `betweenness_exact_max_nodes`, else a seeded `betweenness_sample_k`-source sample | An amount is not a distance: weighting by amount would make larger flows look *longer* |
| Community | Seeded Louvain on the undirected projection weighted by transaction **counts**; ids relabelled largest first (ties by smallest member id) | Counts avoid one huge transfer dominating; relabelling makes ids reproducible |

| Parameter | Default |
|---|---|
| `seed` | `42` |
| `pagerank_alpha` | `0.85` |
| `betweenness_exact_max_nodes` | `500` |
| `betweenness_sample_k` | `100` |
| `louvain_resolution` | `1.0` |

Also reported: modularity and per-community size, internal-transaction share and total value. **These are structural
descriptions, not risk signals.** They are excluded from `rule_score`, `risk_score` and — by default — from the model.
Community ids are computed on the **whole dataset graph**, so an account keeps the same id in every network view.

### Why the model-feature flag is off

On 50 held-out seeds (101–150) the paired difference in model-score AUC (graph features ON − OFF) was **+0.002**,
95 % bootstrap CI **[−0.004, +0.008]**, 28 wins / 22 losses, Wilcoxon p = 0.40: **no demonstrated difference**. Precision
(0.909 → 0.905) and false-alert accounts (1.68 → 1.78) were nominally slightly worse, also not significant. Because the
primary metric and held-out seeds were declared before looking at results, this is the evidence the default rests on. It says
nothing about real data, where the answer could differ.

## Evaluation (`benchmark.py`, `scripts/evaluate_detection.py`)

Controlled, **synthetic-only**; labels are consumed in `evaluate_run` and nowhere else.

| Concept | Meaning |
|---|---|
| Development seeds | 1–12. Inspected during design; **not** valid evidence |
| Held-out seeds | 101–150. Not inspected during development |
| Primary metric | `auc_model_score` (declared in advance) |
| Verdict | “improvement demonstrated” only if the whole 95 % bootstrap CI of the paired difference is on the good side of zero |
| Designed-rule recall | Credits only the rule intended for a scenario role (`EXPECTED_RULE`) |

```bash
python scripts/evaluate_detection.py --seeds 1-12
python scripts/evaluate_detection.py --seeds 1-12 --include-structuring
python scripts/evaluate_detection.py --graph-ablation --heldout
python scripts/evaluate_detection.py --seeds 1-12 --format json --out var/benchmark.json
```

Development-seed results (default dataset): alert recall 1.000; alert precision 0.926 (min 0.842); model-only AUC 0.712
(min 0.615, max 0.783); rule-score AUC 0.998; risk-score AUC 0.987. With the opt-in STRUCTURING scenario,
`STRUCTURING_SOURCE` designed-rule recall is 1.00 on all 12 seeds and nothing else changes.
The default dataset's outputs were verified byte-identical before and after adding the structuring rule and the graph analytics.

## Known limitations

* The rules were written alongside the synthetic scenarios; recovering them is a sanity check, **not** evidence of real-world accuracy.
* `BEHAVIOURAL_CHANGE` recovered the injected account on 10 of 12 development seeds (designed-rule recall 0.83).
* Ordinary random traffic can legitimately match a rule (for example fan-out); such alerts are neither confirmed false nor
  true positives without review. On the development seeds about 1.3 non-injected accounts were alerted per run.
* No labelled real data exists here: no real-world precision/recall, no calibration, no threshold tuning.
* Evidence lists are capped (50 per hit), so rule-cited transaction markers can under-report on very large matches.
* The structuring threshold and every other default are illustrative.
* Community structure in the synthetic data is weak (modularity ≈ 0.15); communities should not be interpreted as real groups.
