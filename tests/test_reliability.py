import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from belvo.config import Protocol
from belvo.domain import Loan
from belvo.state import SimulatedProvider, Store, execute, reconcile


@pytest.fixture
def root():
    with tempfile.TemporaryDirectory(dir=Path(__file__).parent, prefix=".state_test_") as folder:
        yield Path(folder)


def loan(index=1, day="2026-04-01", version="v1"):
    return Loan(f"L{index}", "C1", day, 1000, 500, 0, version)


def test_independent_processes_share_atomic_quota_and_duplicate_keys(root):
    target = root / "engine.db"
    Store(target, Protocol.load(), capacity=3)
    worker = """
import sys
from pathlib import Path
from belvo.config import Protocol
from belvo.domain import Loan
from belvo.state import Store
s=Store(Path(sys.argv[1]), Protocol.load(), capacity=3)
i=sys.argv[2]
l=Loan('L'+i,'C1','2026-04-01',1000,500,0,'v1')
s.commit_day([l],[],[],'2026-04-01')
"""

    def run(index):
        return subprocess.run(
            [sys.executable, "-c", worker, str(target), str(index)],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(run, [1, 1, 2, 3, 4, 5, 6, 6]))
    assert all(r.returncode == 0 for r in results)
    store = Store(target, Protocol.load(), capacity=3)
    assert store.quota()["reserved"] == 3 and store.quota()["free"] == 0
    assert len(store.attempts()) == 6
    provider = SimulatedProvider(root / "provider.db")
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda _: execute(store, provider, "2026-04-01"), range(3)))
    assert store.quota()["consumed"] == 3 and store.quota()["reserved"] == 0
    assert all(r["state"] == "submitted" for r in store.attempts())


def test_full_portfolio_withdrawal_and_reappearance_before_submission(root):
    store = Store(root / "state.db", Protocol.load(), capacity=2)
    store.commit_day([loan()], [], [], "2026-04-01", portfolio_clients={"C1"})
    withdrawn = store.commit_day(
        [], [], [], "2026-04-01", portfolio_clients={"C1"}, source_revision=2
    )
    assert withdrawn[0]["status"] == "withdrawn" and store.quota()["reserved"] == 0
    store.commit_day([loan()], [], [], "2026-04-01", portfolio_clients={"C1"}, source_revision=3)
    assert store.quota()["reserved"] == 1
    # Identical data can reappear: reactivate only proven unsent intents.
    store.commit_day(
        [loan(version="v2")], [], [], "2026-04-01", portfolio_clients={"C1"}, source_revision=4
    )
    store.commit_day([loan()], [], [], "2026-04-01", portfolio_clients={"C1"}, source_revision=5)
    assert store.quota()["reserved"] == 1
    provider = SimulatedProvider(root / "provider.db")
    execute(store, provider, "2026-04-01")
    assert sum(r["state"] == "submitted" for r in store.attempts()) == 1


def test_withdrawal_does_not_release_unknown_and_scope_is_lender_specific(root):
    store = Store(root / "state.db", Protocol.load(), capacity=2)
    store.commit_day([loan()], [], [], "2026-04-01")
    provider = SimulatedProvider(root / "provider.db")
    execute(store, provider, "2026-04-01", "timeout_after")
    store.commit_day([], [], [], "2026-04-01", portfolio_clients={"C2"})
    assert store.quota()["reserved"] == 1
    store.commit_day([], [], [], "2026-04-01", portfolio_clients={"C1"}, source_revision=2)
    assert store.quota()["reserved"] == 1
    reconcile(store, provider)
    assert store.quota()["consumed"] == 1


def test_expiration_cancels_unsent_without_erasing_consumed(root):
    store = Store(root / "state.db", Protocol.load(), capacity=2)
    store.commit_day([loan(day="2026-06-30")], [], [], "2026-06-30")
    result = store.commit_day([loan(2, "2026-07-01")], [], [], "2026-07-01")
    assert store.quota()["reserved"] == 0
    assert result[0]["plan"]["providers"] == ("B",)
    assert store.claim("2026-06-30") is None
    with pytest.raises(ValueError, match="rewind"):
        store.commit_day([loan()], [], [], "2026-04-01")


def test_state_unavailability_fails_before_submission(root):
    blocker = root / "not_a_directory"
    blocker.write_text("blocked")
    with pytest.raises(OSError):
        Store(blocker / "state.db", Protocol.load())
    store = Store(root / "state.db", Protocol.load(), capacity=1)
    store.bind_policy("baseline-v1")
    with pytest.raises(ValueError, match="different policy"):
        store.bind_policy("economic-v1")
    assert not store.attempts()


def test_store_rejects_valid_identity_plan_that_overbooks_capacity(root):
    store = Store(root / "state.db", Protocol.load(), capacity=1)

    def overbook(loans, quota, protocol):
        return [
            {
                "loan_id": "L1",
                "client_id": "C1",
                "day": "2026-04-01",
                "version": "v1",
                "status": "attempt",
                "reason": "test",
                "plan": {"amounts": [100, 100], "providers": ["A", "A"]},
            }
        ], -1

    with pytest.raises(ValueError, match="overbooking"):
        store.commit_day([loan()], [], [], "2026-04-01", overbook)
    assert store.quota()["free"] == 1 and not store.attempts()


def test_decision_versions_and_receipts_are_auditable(root):
    store = Store(root / "state.db", Protocol.load(), capacity=2)
    store.commit_day([loan()], [], [], "2026-04-01")
    store.commit_day([loan(version="v2")], [], [], "2026-04-01", source_revision=2)
    with store.connect() as db:
        assert db.execute("SELECT count(*) FROM decision_events").fetchone()[0] == 2
        assert db.execute("SELECT received_at FROM batches").fetchone()[0]


def test_proven_non_submission_retries_with_a_new_generation(root):
    store = Store(root / "state.db", Protocol.load(), capacity=1)
    provider = SimulatedProvider(root / "provider.db")
    store.commit_day([loan()], [], [], "2026-04-01")
    identity = store.attempts()[0]["id"]
    execute(store, provider, "2026-04-01", "timeout_before")
    reconcile(store, provider)
    assert store.quota()["free"] == 1
    store.commit_day([loan()], [], [], "2026-04-01")
    execute(store, provider, "2026-04-01")
    assert len(store.attempts()) == 2
    submitted = [a for a in store.attempts() if a["state"] == "submitted"]
    assert len(submitted) == 1 and submitted[0]["id"] != identity
    assert store.quota()["consumed"] == 1


def test_reconciliation_fences_a_sender_that_has_not_reached_provider(root):
    store = Store(root / "state.db", Protocol.load(), capacity=1)
    provider = SimulatedProvider(root / "provider.db")
    store.commit_day([loan()], [], [], "2026-04-01")
    delayed = store.claim("2026-04-01")
    reconcile(store, provider)
    assert store.quota()["free"] == 1
    store.commit_day([loan(2)], [], [], "2026-04-01")
    execute(store, provider, "2026-04-01")
    assert provider.submit(delayed) is False
    assert not provider.exists(delayed["id"])
    assert store.quota()["consumed"] == 1 and store.quota()["free"] == 0


def test_cap_correction_automatically_revalidates_same_snapshot(root):
    from belvo.pipelines.daily import validate

    snapshot = {
        "loan_id": "L1",
        "client_id": "C1",
        "snapshot_date": "2026-04-01",
        "outstanding_balance": "10.00",
        "days_past_due": "0",
    }
    store = Store(root / "state.db", Protocol.load(), capacity=1)
    valid, rejected, raw = validate([snapshot], {}, "2026-04-01")
    store.commit_day(valid, rejected, raw, "2026-04-01")
    valid, rejected, raw = validate([snapshot], {"C1": 200}, "2026-04-01")
    decisions = store.commit_day(valid, rejected, raw, "2026-04-01", source_revision=2)
    assert decisions[0]["status"] == "attempt"
    assert max(decisions[0]["plan"]["amounts"]) <= 200


def test_replaced_provider_registry_cannot_release_unknown_capacity(root):
    store = Store(root / "state.db", Protocol.load(), capacity=1)
    original = SimulatedProvider(root / "original.db")
    store.commit_day([loan()], [], [], "2026-04-01")
    execute(store, original, "2026-04-01", "timeout_after")
    replacement = SimulatedProvider(root / "empty_replacement.db")
    with pytest.raises(ValueError, match="registry was replaced"):
        reconcile(store, replacement)
    assert store.quota()["reserved"] == 1
