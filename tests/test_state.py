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
    corrected = store.commit_day([loan("v2")], [], [], "2026-04-01", source_revision=2)
    assert corrected[0]["status"] == "protected"
    restarted = Store(store.path, store.protocol, capacity=2)
    reconcile(restarted, provider)
    reconcile(restarted, provider)
    assert restarted.quota()["reserved"] == 0
    assert restarted.quota()["consumed"] == (fault != "timeout_before")


def test_correction_replaces_only_unsent_and_invalid_cancels(setup):
    store, _ = setup
    store.commit_day([loan()], [], [], "2026-04-01")
    store.commit_day([loan("v2", 200)], [], [], "2026-04-01", source_revision=2)
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
    store.commit_day([], [rejected], [], "2026-04-01", source_revision=3)
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
    result = store.commit_day([], [rejected], [], "2026-04-01", source_revision=3)
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


def test_stale_retry_cannot_reopen_a_zero_balance_correction(setup):
    store, provider = setup
    scope = {"C1"}
    store.commit_day([loan()], [], [], "2026-04-01", portfolio_clients=scope, source_revision=1)
    store.commit_day(
        [loan("paid", 0)], [], [], "2026-04-01", portfolio_clients=scope, source_revision=2
    )
    for revision in (None, 1, 2):
        with pytest.raises(ValueError, match="source revision"):
            store.commit_day(
                [loan()], [], [], "2026-04-01", portfolio_clients=scope, source_revision=revision
            )
    execute(store, provider, "2026-04-01")
    assert store.quota()["consumed"] == store.quota()["reserved"] == 0
    assert all(a["state"] == "cancelled" for a in store.attempts())
    with store.connect() as db:
        assert db.execute("SELECT version FROM decisions").fetchone()[0] == "paid"


def test_withdrawal_requires_new_source_revision_to_reappear(setup):
    store, _ = setup
    scope = {"C1"}
    store.commit_day([loan()], [], [], "2026-04-01", portfolio_clients=scope)
    store.commit_day([], [], [], "2026-04-01", portfolio_clients=scope, source_revision=2)
    with pytest.raises(ValueError, match="source revision"):
        store.commit_day([loan()], [], [], "2026-04-01")
    store.commit_day([loan()], [], [], "2026-04-01", portfolio_clients=scope, source_revision=3)
    assert store.quota()["reserved"] == 1


def test_source_ordering_is_lender_scoped_and_survives_restart(setup):
    store, _ = setup
    store.commit_day([loan()], [], [], "2026-04-01", portfolio_clients={"C1"}, source_revision=5)
    other = Loan("L2", "C2", "2026-04-01", 1000, 500, 5, "v1")
    store.commit_day([other], [], [], "2026-04-01", portfolio_clients={"C2"}, source_revision=1)
    restarted = Store(store.path, store.protocol, capacity=2)
    with pytest.raises(ValueError, match="Stale source revision"):
        restarted.commit_day(
            [loan("paid", 0)], [], [], "2026-04-01", portfolio_clients={"C1"}, source_revision=4
        )
    assert restarted.quota()["reserved"] == 2


def test_source_revision_updates_roll_back_with_invalid_selection(setup):
    store, _ = setup
    store.commit_day([loan()], [], [], "2026-04-01", source_revision=1)

    def broken(*args):
        raise RuntimeError("planner interrupted")

    with pytest.raises(RuntimeError):
        store.commit_day([loan("v2")], [], [], "2026-04-01", broken, source_revision=2)
    with store.connect() as db:
        assert db.execute("SELECT revision FROM source_heads").fetchone()[0] == 1
    assert store.quota()["reserved"] == 1


def test_concurrent_revisions_cannot_restore_a_stale_positive_balance(setup):
    from concurrent.futures import ThreadPoolExecutor

    store, provider = setup
    store.commit_day([loan()], [], [], "2026-04-01", source_revision=1)

    def submit(revision):
        try:
            store.commit_day(
                [loan(str(revision), 0 if revision == 3 else 200)],
                [],
                [],
                "2026-04-01",
                source_revision=revision,
            )
            return "accepted"
        except ValueError as error:
            assert "Stale source revision" in str(error)
            return "stale"

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(submit, [2, 3]))
    execute(store, provider, "2026-04-01")
    assert store.quota()["consumed"] == store.quota()["reserved"] == 0
    with store.connect() as db:
        assert db.execute("SELECT version FROM decisions").fetchone()[0] == "3"


def test_legacy_state_without_source_order_cannot_guess_a_revision(setup):
    store, _ = setup
    store.commit_day([loan()], [], [], "2026-04-01")
    with store.connect() as db:
        db.execute("DELETE FROM source_heads")  # Simulate the pre-ordering schema contents.
    with pytest.raises(ValueError, match="Legacy state has no source ordering"):
        store.commit_day([loan("paid", 0)], [], [], "2026-04-01", source_revision=2)
    assert store.quota()["reserved"] == 1
