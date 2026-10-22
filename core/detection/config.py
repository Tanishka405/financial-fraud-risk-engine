"""All detection thresholds and weights live here -- none are scattered through
rule code. Defaults are *illustrative academic values*, not regulatory
thresholds, and are tuned to nothing. Override by constructing DetectionConfig.
"""
from __future__ import annotations

from dataclasses import dataclass, field


def _default_rule_weights() -> dict[str, float]:
    # Each weight w in [0,1] is the rule's standalone contribution to the rule
    # score. Account rule score = 100 * (1 - prod(1 - w_i)) over distinct
    # rule codes hit (saturating combination; never exceeds 100).
    return {
        "HIGH_VELOCITY": 0.45,
        "LARGE_AMOUNT": 0.35,
        "REPEATED_TRANSACTIONS": 0.40,
        "HIGH_FANOUT": 0.40,
        "PASS_THROUGH": 0.55,
        "CIRCULAR_FLOW": 0.65,
        "LAYERED_MULTI_HOP": 0.55,
        "BEHAVIOURAL_CHANGE": 0.40,
        "STRUCTURING": 0.50,
    }


@dataclass(frozen=True)
class DetectionConfig:
    # --- HIGH_VELOCITY: >= N sent txns inside one sliding window ----------
    velocity_window_minutes: int = 60
    velocity_min_txns: int = 10
    # --- LARGE_AMOUNT: single txn >= absolute INR OR >= k x dataset p99 ----
    large_amount_inr: float = 1_000_000.0
    large_amount_p99_multiple: float = 5.0
    large_amount_min_dataset_size: int = 50  # percentile branch needs enough data
    receiver_weight_factor: float = 0.5  # receiver of a flagged txn gets reduced weight
    # --- REPEATED_TRANSACTIONS: same sender, receiver and amount N+ times --
    repeated_min_count: int = 5
    # --- STRUCTURING: >= N sent txns, each just BELOW a threshold, in one window.
    # Threshold is illustrative (NOT a legal reporting limit); set it to the limit relevant to your data.
    structuring_threshold_inr: float = 50_000.0
    structuring_band_floor: float = 0.80  # a txn counts only if amount in [floor*T, T)
    structuring_window_minutes: int = 120
    structuring_min_txns: int = 4
    # --- HIGH_FANOUT: unique receivers over the dataset window -------------
    fanout_min_receivers: int = 25
    # --- PASS_THROUGH: inflow forwarded almost whole, soon after -----------
    pass_through_window_minutes: int = 120
    pass_through_min_retention: float = 0.90
    pass_through_max_retention: float = 1.02
    pass_through_min_pairs: int = 2
    # --- Temporal flow search (CIRCULAR_FLOW / LAYERED_MULTI_HOP) ----------
    flow_min_retention: float = 0.80  # next hop amount / previous hop amount (lower bound)
    flow_max_retention: float = 1.05  # ... (upper bound)
    cycle_min_length: int = 3
    cycle_max_length: int = 4
    cycle_window_hours: float = 24.0
    layered_min_hops: int = 4
    layered_max_hops: int = 6
    layered_window_hours: float = 24.0
    max_flow_results: int = 500  # performance safeguard for DFS output
    max_flow_expansions: int = 1_000_000  # hard cap on DFS steps (performance safeguard)
    # --- BEHAVIOURAL_CHANGE: upward sent-amount shift between halves of own span --
    behaviour_min_txns: int = 8
    behaviour_min_per_half: int = 4
    behaviour_median_ratio: float = 3.0  # median(second half) / median(first half)
    behaviour_p_value: float = 0.001  # one-sided Mann-Whitney U, later > earlier
    # --- Rule weights ------------------------------------------------------
    rule_weights: dict[str, float] = field(default_factory=_default_rule_weights)
    # --- Isolation Forest baseline ----------------------------------------
    model_enabled: bool = True
    model_min_accounts: int = 30
    model_n_estimators: int = 200
    model_random_state: int = 42
    # OFF by default: PageRank/betweenness/community features showed no demonstrated gain on synthetic data
    # (see scripts/evaluate_detection.py --graph-ablation). Flip only after evaluating on your own data.
    include_graph_features_in_model: bool = False
    # --- Combined risk index ----------------------------------------------
    rule_share: float = 0.7  # combined = rule_share*rule + (1-rule_share)*model
    # --- Alerting ----------------------------------------------------------
    alert_min_combined_if_rule_hit: float = 0.0  # any rule hit raises an alert
    model_only_alert_percentile: float = 99.0  # no rule hit: alert only if model pct >= this
    # severity bands on the combined index (lower bounds)
    severity_critical: float = 70.0
    severity_high: float = 50.0
    severity_medium: float = 30.0
