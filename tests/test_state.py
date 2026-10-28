import tempfile
from pathlib import Path

import pytest

from belvo.config import Protocol
from belvo.domain import Loan
from belvo.state import SimulatedProvider, Store, execute, reconcile


@pytest.fixture
def setup():
    with tempfile.TemporaryDirectory(dir=Path(__file__).parent, prefix=".state_test_") as folder:
        root = Path(folder)
        store = Store(root / "engine.db", Protocol.load(), capacity=2)
        yield store, SimulatedProvider(root / "provider.db")


def loan(version="v1", balance=1000):
    return Loan("L1", "C1", "2026-04-01", balance, 500, 5, version)


def test_atomic_replay_and_failure_consumption(setup):
    store, provider = setup
    store.commit_day([loan()], [], [], "2026-04-01")
    store.commit_day([loan()], [], [], "2026-04-01")
    assert store.quota()["reserved"] == 1
    execute(store, provider, "2026-04-01")
    execute(store, provider, "2026-04-01")
    aid = store.attempts()[0]["id"]
    store.outcome(aid, "failed", "2026-04-02")
    store.outcome(aid, "failed", "2026-04-02")
    assert store.quota()["consumed"] == 1
    assert store.quota()["reserved"] == 0
    assert len(store.attempts()) == 1


@pytest.mark.parametrize("fault", ["timeout_before", "timeout_after", "crash_after"])
def test_unknown_reserves_until_authoritative_reconciliation(setup, fault):
    store, provider = setup
    store.commit_day([loan()], [], [], "2026-04-01")
    if fault == "crash_after":
        with pytest.raises(RuntimeError):
            execute(store, provider, "2026-04-01", fault)
    else:
        execute(store, provider, "2026-04-01", fault)
    assert store.quota()["reserved"] == 1 and store.quota()["free"] == 1
    corrected = store.commit_day([loan("v2")], [], [], "2026-04-01")
    assert corrected[0]["status"] == "protected"
    restarted = Store(store.path, store.protocol, capacity=2)
    reconcile(restarted, provider)
    reconcile(restarted, provider)
    assert restarted.quota()["reserved"] == 0
    assert restarted.quota()["consumed"] == (fault != "timeout_before")


def test_correction_replaces_only_unsent_and_invalid_cancels(setup):
    store, _ = setup
    store.commit_day([loan()], [], [], "2026-04-01")
    store.commit_day([loan("v2", 200)], [], [], "2026-04-01")
    assert store.quota()["reserved"] == 1
    assert [a["state"] for a in store.attempts()].count("cancelled") == 1
    rejected = {
        "loan_id": "L1",
        "client_id": "C1",
        "day": "2026-04-01",
        "version": "bad",
        "status": "quarantined",
        "reason": "invalid",
        "plan": {"amounts": [], "providers": []},
    }
    store.commit_day([], [rejected], [], "2026-04-01")
    assert store.quota()["reserved"] == 0


def test_transaction_rolls_back_on_selector_overbooking(setup):
    store, _ = setup

    def unsafe(loans, quota, protocol):
        return [{"plan": {"providers": ["A"] * 3}}], -1

    with pytest.raises(ValueError):
        store.commit_day([loan()], [], [], "2026-04-01", unsafe)
    assert store.quota()["free"] == 2 and not store.attempts()


def test_invalid_correction_cannot_erase_accepted_submission(setup):
    store, provider = setup
    store.commit_day([loan()], [], [], "2026-04-01")
    execute(store, provider, "2026-04-01")
    rejected = {
        "loan_id": "L1",
        "client_id": "C1",
        "day": "2026-04-01",
        "version": "bad",
        "status": "quarantined",
        "reason": "invalid",
        "plan": {"amounts": [], "providers": []},
    }
    result = store.commit_day([], [rejected], [], "2026-04-01")
    assert result[0]["status"] == "protected_invalid_correction"
    assert store.quota()["consumed"] == 1


def test_outcome_requires_next_day_and_preserves_first_result(setup):
    store, provider = setup
    store.commit_day([loan()], [], [], "2026-04-01")
    execute(store, provider, "2026-04-01")
    aid = store.attempts()[0]["id"]
    with pytest.raises(ValueError):
        store.outcome(aid, "success", "2026-04-01")
    store.outcome(aid, "success", "2026-04-02")
    with pytest.raises(ValueError):
        store.outcome(aid, "failed", "2026-04-02")
