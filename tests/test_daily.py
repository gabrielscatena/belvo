from decimal import Decimal

from belvo.config import Protocol
from belvo.domain import Loan, cents, plans
from belvo.pipelines.daily import baseline, read_csv, validate


def row(**changes):
    return {
        "loan_id": "L1",
        "client_id": "C1",
        "snapshot_date": "2026-04-01",
        "outstanding_balance": "10.01",
        "days_past_due": "5",
    } | changes


def test_exact_plans_respect_joint_limits():
    loan = Loan("L1", "C1", "2026-04-01", 1001, 400, 5, "v1")
    assert cents("10.01") == 1001
    for p in plans(loan):
        assert sum(p.amounts) <= loan.balance
        assert all(0 < m <= loan.cap for m in p.amounts)
        assert all(isinstance(m, int) for m in p.amounts)
    assert any(p.amounts == (334, 334, 333) for p in plans(loan))
    assert Decimal("10.01") == Decimal(cents("10.01")) / 100


def test_quarantine_and_automatic_revalidation():
    valid, rejected, raw = validate(
        [row(outstanding_balance="oops"), row(loan_id="L2")], {"C1": 500}, "2026-04-01"
    )
    assert len(valid) == len(rejected) == 1
    assert len(raw) == 2
    assert not rejected[0]["plan"]["amounts"]
    corrected, bad, _ = validate([row()], {"C1": 500}, "2026-04-01")
    assert len(corrected) == 1 and not bad
    assert corrected[0].version != rejected[0]["version"]


def test_duplicate_keys_are_not_silently_deduplicated():
    valid, rejected, raw = validate([row(), row()], {"C1": 500}, "2026-04-01")
    assert not valid and len(rejected) == 1 and len(raw) == 2
    assert "duplicate_loan_day" in rejected[0]["reason"]


def test_cap_changes_are_part_of_the_decision_version():
    first, _, _ = validate([row()], {"C1": 500}, "2026-04-01")
    corrected, _, raw = validate([row()], {"C1": 200}, "2026-04-01")
    assert first[0].version != corrected[0].version
    assert raw[0]["context"]["cap_cents"] == 200


def test_missing_identity_does_not_collide_with_real_identifier():
    valid, rejected, _ = validate(
        [row(loan_id=""), row(loan_id="__missing_identity_0")], {"C1": 500}, "2026-04-01"
    )
    assert len(valid) == len(rejected) == 1
    assert valid[0].loan_id == "__missing_identity_0"


def test_extra_csv_fields_quarantine_only_the_bad_record(tmp_path):
    target = tmp_path / "bad.csv"
    target.write_text(
        "loan_id,client_id,snapshot_date,outstanding_balance,days_past_due\n"
        "L1,C1,2026-04-01,10.00,0,extra\nL2,C1,2026-04-01,10.00,0\n"
    )
    rows = read_csv(target, {"loan_id"})
    valid, rejected, _ = validate(rows, {"C1": 500}, "2026-04-01")
    assert len(valid) == len(rejected) == 1
    assert rejected[0]["reason"] == "extra_csv_fields"


def test_zero_balance_and_exhausted_capacity():
    p = Protocol.load()
    loans = [
        Loan("L1", "C1", "2026-04-01", 1000, 500, 5, "v1"),
        Loan("L2", "C1", "2026-04-01", 0, 500, 5, "v1"),
    ]
    result, quota = baseline(loans, 0, p)
    assert quota == 0 and result[0]["plan"]["providers"] == ("B",)
    assert result[1]["status"] == "no_attempt"
    expired, _ = baseline(loans, 1, p.__class__(p.values | {"contract_end": "2026-03-31"}))
    assert expired[0]["plan"]["providers"] == ("B",)
