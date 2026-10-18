# Detection layer

All thresholds and weights are in `core/detection/config.py` (`DetectionConfig`). Defaults are illustrative academic values,
not regulatory thresholds, and are not tuned to any dataset.

## Model features (`model_features.py`)
Finite numeric matrix, one row per account. Counts/amounts/degrees are `log1p`-transformed. `inflow_outflow_ratio`
can be `+inf` (pure sink) and is **never** passed on: it becomes `log_inflow_outflow_ratio = clip(log10((in+1)/(out+1)), -4, 4)`
plus indicators `is_pure_sink` / `is_pure_source`. Builders reject any column whose name contains `scenario`, `label` or `fraud`;
synthetic scenario labels are used only by `evaluate_on_synthetic`.

## Rules (`rules.py`)
Each hit carries a weight, role, plain-language summary built from the actual triggering values, transaction-id evidence
(capped at 50 per hit) and metrics.

| Code | Fires when |
|---|---|
| HIGH_VELOCITY | ≥ 10 sent txns inside any 60-minute window |
| LARGE_AMOUNT | single txn ≥ min(INR 10,00,000, 5 × dataset p99); receiver gets half weight |
| REPEATED_TRANSACTIONS | same sender, receiver **and amount** ≥ 5 times |
| HIGH_FANOUT | ≥ 25 distinct receivers in the dataset window |
| PASS_THROUGH | ≥ 2 inflows forwarded within 120 min keeping 90–102 % of the amount (one-to-one matching) |
| CIRCULAR_FLOW | time-ordered loop of 3–4 accounts within 24 h, each hop keeping 80–105 % of the previous amount |
| LAYERED_MULTI_HOP | time-ordered chain of ≥ 4 hops through distinct accounts within 24 h, same retention bounds |
| BEHAVIOURAL_CHANGE | later-half sent amounts higher than earlier half: median ratio ≥ 3 **and** one-sided Mann–Whitney p ≤ 0.001 |

Cycle/chain search is bounded (`max_flow_results`, `max_flow_expansions`).

## Scores
* `rule_score = 100 × (1 − ∏(1 − w))` over distinct matched rule codes.
* `model_score` = Isolation Forest **percentile within the dataset** (relative; not comparable across datasets). Not computed when fewer than 30 accounts.
* `risk_score = 0.7 × rule_score + 0.3 × model_score` (= `rule_score` if the model did not run). Ordinal index; **not calibrated, not a probability**.
* Severity bands on `risk_score`: critical ≥ 70, high ≥ 50, medium ≥ 30, else low.
* Alert basis: any rule hit → alert; no rule hit → alert only if model percentile ≥ 99 (`MODEL_ONLY`, always low severity by construction).

## Known limitations
* Rules were designed alongside the synthetic scenarios; recovering them (see *Data & Pipeline → evaluation*) is a sanity check, not evidence of real-world accuracy.
* `BEHAVIOURAL_CHANGE` recovered the injected account on 10 of 12 tried seeds, with no false matches on ordinary accounts in those runs; it can miss when background traffic dilutes the shift.
* Ordinary random traffic can legitimately match a rule (e.g. high fan-out); such alerts are not necessarily false positives or true positives without human review.
* No labelled real data exists here, so no precision/recall claim, calibration, or threshold tuning has been done.
* Evidence lists are capped, so `flagged` transaction markers can under-report on very large rule matches.
