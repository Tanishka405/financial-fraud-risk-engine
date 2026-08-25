from __future__ import annotations

from core.config import Config
from core.data.synthetic import generate_fixture_dataset, generate_synthetic_dataset
from core.data.validators import validate_batch
from core.data.schema import transactions_to_dataframe


EXPECTED_SCENARIOS = {
    "NORMAL",
    "HIGH_VELOCITY",
    "LARGE_TRANSFER",
    "REPEATED_TRANSACTIONS",
    "HIGH_FANOUT",
    "PASS_THROUGH",
    "CIRCULAR_FLOW",
    "LAYERED_MULTI_HOP",
    "BEHAVIOURAL_CHANGE_BEFORE",
    "BEHAVIOURAL_CHANGE_AFTER",
}


def test_fixture_dataset_reproducible(config: Config):
    ds1 = generate_fixture_dataset(config)
    ds2 = generate_fixture_dataset(config)

    ids1 = [t.transaction_id for t in ds1.transactions]
    ids2 = [t.transaction_id for t in ds2.transactions]
    amounts1 = [t.amount_inr for t in ds1.transactions]
    amounts2 = [t.amount_inr for t in ds2.transactions]

    assert ids1 == ids2
    assert amounts1 == amounts2


def test_different_seed_gives_different_data():
    ds1 = generate_fixture_dataset(Config(random_seed=1))
    ds2 = generate_fixture_dataset(Config(random_seed=2))
    amounts1 = [t.amount_inr for t in ds1.transactions]
    amounts2 = [t.amount_inr for t in ds2.transactions]
    assert amounts1 != amounts2


def test_fixture_dataset_contains_all_expected_scenarios(config: Config):
    ds = generate_fixture_dataset(config)
    present = set(ds.transaction_scenarios["scenario"].unique())
    assert EXPECTED_SCENARIOS.issubset(present)


def test_generator_requires_minimum_accounts(config: Config):
    import pytest

    with pytest.raises(ValueError):
        generate_synthetic_dataset(config, num_accounts=5, num_normal_transactions=10)


def test_all_generated_transactions_pass_validation(config: Config):
    """The generator must only produce schema-valid transactions -- scenario
    injection is about behavioural patterns, not malformed data."""
    ds = generate_fixture_dataset(config)
    rows = [
        {
            "transaction_id": t.transaction_id,
            "sender_account_id": t.sender_account_id,
            "receiver_account_id": t.receiver_account_id,
            "amount_inr": t.amount_inr,
            "timestamp": t.timestamp,
            "transaction_type": t.transaction_type.value,
        }
        for t in ds.transactions
    ]
    outcome = validate_batch(rows, config)
    assert outcome.rejects.empty
    assert len(outcome.valid_transactions) == len(ds.transactions)


def test_transaction_ids_globally_unique(config: Config):
    ds = generate_fixture_dataset(config)
    ids = [t.transaction_id for t in ds.transactions]
    assert len(ids) == len(set(ids))


def test_scenario_labels_not_a_transaction_field(config: Config):
    """Scenario labels must live outside the canonical schema entirely."""
    ds = generate_fixture_dataset(config)
    df = transactions_to_dataframe(ds.transactions)
    assert "scenario" not in df.columns


def test_high_fanout_account_has_many_unique_receivers(config: Config):
    ds = generate_fixture_dataset(config)
    fanout_accounts = ds.account_scenarios[ds.account_scenarios["scenario"] == "HIGH_FANOUT_SOURCE"]["account_id"]
    assert len(fanout_accounts) == 1
    account = fanout_accounts.iloc[0]
    receivers = {
        t.receiver_account_id for t in ds.transactions if t.sender_account_id == account
    }
    assert len(receivers) >= 25  # scenario injects 30 unique fanout receivers


def test_circular_flow_returns_to_origin(config: Config):
    ds = generate_fixture_dataset(config)
    circular_txns = [
        t for t in ds.transactions
        if t.transaction_id in set(
            ds.transaction_scenarios[ds.transaction_scenarios["scenario"] == "CIRCULAR_FLOW"]["transaction_id"]
        )
    ]
    circular_txns.sort(key=lambda t: t.timestamp)
    assert len(circular_txns) == 3
    # last hop's receiver must equal first hop's sender (closed loop)
    assert circular_txns[-1].receiver_account_id == circular_txns[0].sender_account_id


def test_full_generator_size_uses_config_defaults(config: Config):
    ds = generate_synthetic_dataset(config)
    assert len(ds.transactions) > config.synthetic_num_normal_transactions
