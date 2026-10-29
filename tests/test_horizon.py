from decimal import Decimal

import pandas as pd
import pytest

from belvo.config import Protocol
from belvo.domain import Plan
from belvo.evaluation.horizon import ReleaseSchedule, admit_logged_plans, evaluate_horizon


def test_cumulative_integer_release_carries_unspent_units_and_expires():
    schedule = ReleaseSchedule(7, "2026-04-01", "2026-04-03")
    assert [schedule.released(day) for day in ("2026-04-01", "2026-04-02", "2026-04-03")] == [
        2,
        4,
        7,
    ]
    assert schedule.available("2026-04-02", 1) == 3
    assert schedule.available("2026-03-31", 0) == 0
    assert schedule.available("2026-04-04", 0) == 0
    assert schedule.released("2026-04-04") == 7


def test_release_sensitivity_is_fixed_at_opening_and_never_exceeds_total():
    slower = ReleaseSchedule(7, "2026-04-01", "2026-04-03", Decimal("0.75"))
    faster = ReleaseSchedule(7, "2026-04-01", "2026-04-03", Decimal("1.25"))
    unpaced = ReleaseSchedule(7, "2026-04-01", "2026-04-03", None)
    assert slower.released("2026-04-03") == 5
    assert faster.released("2026-04-03") == 7
    assert unpaced.available("2026-04-01", 0) == 7
    assert faster.available("2026-04-02", 2) == faster.released("2026-04-02") - 2
    with pytest.raises(ValueError):
        ReleaseSchedule(-1, "2026-04-01", "2026-04-03")
    with pytest.raises(ValueError):
        ReleaseSchedule(7, "2026-04-01", "2026-04-03", Decimal("NaN"))
    with pytest.raises(ValueError):
        faster.available("2026-04-01", 8)


def test_logged_admission_keeps_complete_plans_with_outcome_independent_rank():
    plans = {key: Plan((100, 100), ("A", "A")) for key in ("L1", "L2", "L3")}
    admitted, remaining, report = admit_logged_plans(plans, 3, day="2026-04-01")
    chosen = [key for key, plan in admitted.items() if plan.amounts]
    assert len(chosen) == 1 and remaining == 1
    assert report["quota_rejected_plans"] == 2
    # Amount/revenue and insertion order do not affect the ID-only rank.
    changed = {key: Plan((9900, 9900), ("A", "A")) for key in reversed(plans)}
    repeated, _, _ = admit_logged_plans(changed, 3, day="2026-04-01")
    assert [key for key, plan in repeated.items() if plan.amounts] == chosen
    assert all(plan in (Plan(), plans[key]) for key, plan in admitted.items())


def test_calendar_rejection_drops_whole_logged_plan_including_its_b_installment():
    class Support:
        def check(self, provider, day):
            return {"admitted": provider != "B"}

    mixed = Plan((100, 100), ("A", "B"))
    admitted, remaining, report = admit_logged_plans(
        {"L1": mixed, "L2": Plan((100,), ("A",))},
        2,
        day="2026-04-01",
        support=Support(),
    )
    assert admitted["L1"] == Plan() and admitted["L2"].a_units == 1
    assert remaining == 1 and report["calendar_rejected_plans"] == 1


def horizon_fixture(data, failed_b=False):
    data.mkdir()
    pd.DataFrame([("C1", "100.00")], columns=["client_id", "max_installment_amount"]).to_csv(
        data / "clients.csv",
        index=False,
    )
    snapshots = [("2026-01-01", f"H{i}", "C1", "100.00", 0) for i in range(91)]
    attempts = [(f"A{i}", f"H{i}", "2026-01-01", 1, 1, "100.00", "A", "success") for i in range(91)]
    for day in ("2026-04-01", "2026-04-02", "2026-04-03"):
        for loan in ("L1", "L2"):
            snapshots.append((day, loan, "C1", "100.00", 0))
    attempts += [
        ("X1", "L1", "2026-04-01", 1, 1, "100.00", "A", "success"),
        ("X2", "L2", "2026-04-01", 1, 1, "100.00", "B" if failed_b else "A", "failed"),
    ]
    pd.DataFrame(
        snapshots,
        columns=["snapshot_date", "loan_id", "client_id", "outstanding_balance", "days_past_due"],
    ).to_csv(
        data / "loan_snapshots.csv",
        index=False,
    )
    pd.DataFrame(
        attempts,
        columns=[
            "attempt_id",
            "loan_id",
            "attempt_date",
            "installment_index",
            "installment_count",
            "amount",
            "provider",
            "status",
        ],
    ).to_csv(
        data / "payment_attempts.csv",
        index=False,
    )
    return Protocol(
        Protocol.load().values
        | {
            "test_end": "2026-04-03",
            "sample_weight": 1,
            "full_a_capacity": 182,
            "full_a_upfront": "181",
            "min_cell_attempts": 1,
            "prior_strength": 1,
            "conservative_z": 0,
            "max_installments": 1,
            "amount_fractions": ["1.00"],
        }
    )


def test_horizon_sensitivity_matches_independent_money_and_capacity_oracle(tmp_path):
    data = tmp_path / "data"
    protocol = horizon_fixture(data)
    output = tmp_path / "output"
    summary = evaluate_horizon(data, output, protocol)
    rows = {row["variant"]: row for row in summary["scenarios"]}
    # Six candidate A debits at 100 * 15%, and 181 * 3/181 fixed expense.
    assert rows["unpaced__calendar_off"]["candidate_margin"] == pytest.approx(87)
    # R=91, horizon=91days, one new A unit per day => three debits, 45-3.
    assert rows["paced_1.00__calendar_off"]["candidate_margin"] == pytest.approx(42)
    assert rows["paced_0.75__calendar_off"]["candidate_margin"] == pytest.approx(27)
    # Original logged benchmark remains success 15 + failure 0 - fixed3 =12.
    assert summary["original_observed_legacy_margin"] == pytest.approx(12)
    for row in rows.values():
        assert row["original_observed_legacy_margin"] == pytest.approx(12)
        assert row["candidate_a_units"] <= row["released_a_at_test_end"]
    # No Feb-Mar exposure: calendar gate rejects A for BOTH compared policies.
    gated = rows["unpaced__calendar_on"]
    assert gated["candidate_margin"] == pytest.approx(-3)
    assert gated["retained_logged_observed_margin"] == pytest.approx(-3)
    per_client = pd.read_csv(output / "per_client.csv")
    for name, row in rows.items():
        assert per_client.loc[per_client.variant.eq(name)].candidate_margin.sum() == pytest.approx(
            row["candidate_margin"]
        )
    daily = pd.read_csv(output / "daily.csv")
    assert (daily.candidate_cumulative_a <= daily.released_a).all()
    assert (daily.retained_logged_cumulative_a <= daily.released_a).all()
    assert daily.candidate_physical_remaining_a.ge(0).all()


def test_failed_logged_b_cost_and_prior_overage_are_explicit(tmp_path):
    data = tmp_path / "data"
    protocol = horizon_fixture(data, failed_b=True)
    protocol = Protocol(protocol.values | {"full_a_capacity": 90})
    summary = evaluate_horizon(data, tmp_path / "output", protocol)
    rows = {row["variant"]: row for row in summary["scenarios"]}
    assert summary["prior_capacity_overage"] is True
    assert summary["opening_a_remaining"] == 0
    # Original benchmark: successful A15, failed B costs2, fixedexpense3 =>10.
    assert summary["original_observed_legacy_margin"] == pytest.approx(10)
    # No A allowance; retained failed B still costs2, plus fixedexpense3 =>-5.
    ungated = rows["unpaced__calendar_off"]
    assert ungated["retained_logged_observed_margin"] == pytest.approx(-5)
    assert ungated["retained_logged_b_units"] == 1
    # Rejecting B before dispatch avoids its new fee; prepaidfixedexpense remains.
    gated = rows["unpaced__calendar_on"]
    assert gated["retained_logged_observed_margin"] == pytest.approx(-3)
    assert gated["retained_logged_b_units"] == 0
    assert all(row["candidate_a_units"] == 0 for row in rows.values())
