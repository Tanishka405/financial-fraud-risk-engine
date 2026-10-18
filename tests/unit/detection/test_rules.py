from core.detection.config import DetectionConfig
from core.detection.rules import run_rules
from tests.unit.detection.helpers import make_tx

CFG = DetectionConfig()


def codes(hits, acc=None):
    return {h.rule_code for h in hits if acc is None or h.account_id == acc}


def test_empty_dataset_no_hits():
    assert run_rules(make_tx([]), CFG) == []


def test_high_velocity_fires_and_has_evidence():
    rows = [(f"T{i}", "A", f"R{i}", 500, i * 3) for i in range(12)]  # 12 txns in 33 minutes
    hits = [h for h in run_rules(make_tx(rows), CFG) if h.rule_code == "HIGH_VELOCITY"]
    assert len(hits) == 1 and hits[0].account_id == "A"
    assert hits[0].metrics["txns_in_window"] == 12 and len(hits[0].transaction_ids) == 12
    assert "12 outgoing" in hits[0].summary


def test_high_velocity_not_triggered_when_spread_out():
    rows = [(f"T{i}", "A", f"R{i}", 500, i * 30) for i in range(12)]  # one every 30 min
    assert "HIGH_VELOCITY" not in codes(run_rules(make_tx(rows), CFG))


def test_large_amount_absolute_threshold_sender_full_receiver_reduced():
    hits = [h for h in run_rules(make_tx([("T1", "A", "B", 2_000_000, 0)]), CFG) if h.rule_code == "LARGE_AMOUNT"]
    by = {h.account_id: h for h in hits}
    assert by["B"].weight == by["A"].weight * CFG.receiver_weight_factor
    assert by["A"].role == "sender" and by["B"].role == "receiver"


def test_large_amount_not_triggered_below_threshold():
    assert "LARGE_AMOUNT" not in codes(run_rules(make_tx([("T1", "A", "B", 999_999, 0)]), CFG))


def test_repeated_same_amount_pair():
    rows = [(f"T{i}", "A", "B", 9500, i * 360) for i in range(6)]
    hits = [h for h in run_rules(make_tx(rows), CFG) if h.rule_code == "REPEATED_TRANSACTIONS"]
    assert {h.account_id for h in hits} == {"A", "B"} and hits[0].metrics["count"] == 6
    rows2 = [(f"T{i}", "A", "B", 9500 + i, i * 360) for i in range(6)]  # amounts differ -> no hit
    assert "REPEATED_TRANSACTIONS" not in codes(run_rules(make_tx(rows2), CFG))


def test_high_fanout_counts_unique_receivers_not_transactions():
    many_to_few = [(f"T{i}", "A", f"R{i % 3}", 100 + i, i * 600) for i in range(60)]
    assert "HIGH_FANOUT" not in codes(run_rules(make_tx(many_to_few), CFG))
    fan = [(f"T{i}", "A", f"R{i}", 100 + i, i * 600) for i in range(26)]
    h = [x for x in run_rules(make_tx(fan), CFG) if x.rule_code == "HIGH_FANOUT"]
    assert h and h[0].metrics["unique_receivers"] == 26


def test_pass_through_needs_min_pairs_and_retention():
    rows = [("I1", "X", "M", 10000, 0), ("O1", "M", "Y", 9800, 20),
            ("I2", "Z", "M", 20000, 500), ("O2", "M", "W", 19600, 530)]
    hits = [h for h in run_rules(make_tx(rows), CFG) if h.rule_code == "PASS_THROUGH"]
    assert [h.account_id for h in hits] == ["M"] and hits[0].metrics["matched_pairs"] == 2
    low = [("I1", "X", "M", 10000, 0), ("O1", "M", "Y", 5000, 20),
           ("I2", "Z", "M", 20000, 500), ("O2", "M", "W", 10000, 530)]
    assert "PASS_THROUGH" not in codes(run_rules(make_tx(low), CFG))


def test_circular_flow_requires_time_order_and_amount_retention():
    ok = make_tx([("T1", "A", "B", 50000, 0), ("T2", "B", "C", 48500, 120), ("T3", "C", "A", 47000, 240)])
    h = [x for x in run_rules(ok, CFG) if x.rule_code == "CIRCULAR_FLOW"]
    assert {x.account_id for x in h} == {"A", "B", "C"}
    wrong_order = make_tx([("T1", "A", "B", 50000, 240), ("T2", "B", "C", 48500, 120), ("T3", "C", "A", 47000, 0)])
    assert "CIRCULAR_FLOW" not in codes(run_rules(wrong_order, CFG))
    big_drop = make_tx([("T1", "A", "B", 50000, 0), ("T2", "B", "C", 10000, 120), ("T3", "C", "A", 9000, 240)])
    assert "CIRCULAR_FLOW" not in codes(run_rules(big_drop, CFG))


def test_layered_chain_detected_and_not_closed_loop():
    rows = [(f"T{i}", f"N{i}", f"N{i+1}", 100000 * (0.95 ** i), i * 180) for i in range(4)]
    h = [x for x in run_rules(make_tx(rows), CFG) if x.rule_code == "LAYERED_MULTI_HOP"]
    assert {x.account_id for x in h} == {f"N{i}" for i in range(5)}
    assert all(x.metrics["hops"] == 4 for x in h)
    ends = {x.account_id: x.role for x in h}
    assert ends["N0"] == "endpoint" and ends["N2"] == "intermediary"
    three = rows[:3]
    assert "LAYERED_MULTI_HOP" not in codes(run_rules(make_tx(three), CFG))


def test_behavioural_change_fires_on_regime_shift_not_on_stable_account():
    quiet = [(f"Q{i}", "A", f"R{i}", 300 + i, i * 1000) for i in range(5)]
    loud = [(f"L{i}", "A", f"S{i}", 50000 + i * 100, 40000 + i * 1000) for i in range(12)]
    assert "BEHAVIOURAL_CHANGE" in codes(run_rules(make_tx(quiet + loud), CFG), "A")
    stable = [(f"S{i}", "A", f"R{i}", 5000 + (i % 3) * 50, i * 1000) for i in range(16)]
    assert "BEHAVIOURAL_CHANGE" not in codes(run_rules(make_tx(stable), CFG))


def test_thresholds_are_configurable():
    rows = [(f"T{i}", "A", f"R{i}", 500, i * 3) for i in range(5)]
    assert "HIGH_VELOCITY" not in codes(run_rules(make_tx(rows), CFG))
    assert "HIGH_VELOCITY" in codes(run_rules(make_tx(rows), DetectionConfig(velocity_min_txns=5)))


def test_flow_search_respects_expansion_cap():
    rows = [(f"T{i}", f"N{i%6}", f"N{(i+1)%6}", 1000, i) for i in range(60)]
    run_rules(make_tx(rows), DetectionConfig(max_flow_expansions=50, max_flow_results=5))  # must terminate


# ------------------------------------------------------------------ STRUCTURING
def _struct(n=4, amount=45_000, gap=10, sender="S", start=0):
    return [(f"X{start}_{i}", sender, f"R{i}", amount, start + i * gap) for i in range(n)]


def test_structuring_fires_with_evidence_and_metrics():
    h = [x for x in run_rules(make_tx(_struct(5)), CFG) if x.rule_code == "STRUCTURING"]
    assert len(h) == 1 and h[0].account_id == "S" and h[0].role == "sender"
    assert h[0].metrics["txns_in_window"] == 5 and h[0].metrics["aggregate_inr"] == 225_000
    assert h[0].metrics["threshold_inr"] == 50_000 and h[0].metrics["band_floor_inr"] == 40_000
    assert len(h[0].transaction_ids) == 5 and "just below" in h[0].summary


def test_structuring_not_triggered_by_ordinary_small_payments():
    """The prototype's rule (count of any sub-threshold txns) would fire here; a band-limited rule must not."""
    small = [(f"S{i}", "A", f"R{i}", 300, i * 5) for i in range(8)]
    assert "STRUCTURING" not in codes(run_rules(make_tx(small), CFG))


def test_structuring_band_boundaries_floor_included_threshold_excluded():
    at_floor = [(f"F{i}", "A", f"R{i}", 40_000, i) for i in range(4)]
    assert "STRUCTURING" in codes(run_rules(make_tx(at_floor), CFG))
    just_under_floor = [(f"G{i}", "A", f"R{i}", 39_999.99, i) for i in range(4)]
    assert "STRUCTURING" not in codes(run_rules(make_tx(just_under_floor), CFG))
    at_threshold = [(f"T{i}", "A", f"R{i}", 50_000, i) for i in range(4)]
    assert "STRUCTURING" not in codes(run_rules(make_tx(at_threshold), CFG))  # at/above threshold is not 'below'
    above = [(f"U{i}", "A", f"R{i}", 60_000, i) for i in range(4)]
    assert "STRUCTURING" not in codes(run_rules(make_tx(above), CFG))


def test_structuring_requires_min_count_and_window():
    assert "STRUCTURING" not in codes(run_rules(make_tx(_struct(3)), CFG))  # below min txns
    assert "STRUCTURING" not in codes(run_rules(make_tx(_struct(4, gap=60)), CFG))  # 4 txns over 180 min > 120 min window
    assert "STRUCTURING" in codes(run_rules(make_tx(_struct(4, gap=40)), CFG))  # 120 min span fits the window


def test_structuring_is_per_sender_not_pooled_across_accounts():
    rows = _struct(2, sender="A") + _struct(2, sender="B", start=1)
    assert "STRUCTURING" not in codes(run_rules(make_tx(rows), CFG))


def test_structuring_threshold_is_configurable():
    rows = [(f"C{i}", "A", f"R{i}", 9_000, i) for i in range(4)]
    assert "STRUCTURING" not in codes(run_rules(make_tx(rows), CFG))
    cfg = DetectionConfig(structuring_threshold_inr=10_000.0)
    assert "STRUCTURING" in codes(run_rules(make_tx(rows), cfg))
