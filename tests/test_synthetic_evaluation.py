import json
from decimal import Decimal

import pandas as pd
import pytest

from belvo.config import Protocol
from belvo.domain import Loan, Plan
from belvo.evaluation.offline import evaluate
from belvo.evaluation.synthetic import generate, is_payday, score, true_commission, true_probability


def test_known_response_is_amount_sensitive_and_provider_neutral():
    truth = {"base": {"C1": 0.02}}
    assert true_probability(truth, "C1", 0, "2026-04-02") == 0.02
    assert true_probability(truth, "C1", 0, "2026-04-01") == 0.04
    assert true_probability(truth, "C1", 200000, "2026-04-02") < true_probability(
        truth, "C1", 100000, "2026-04-02"
    )
    assert is_payday("2026-02-28") and not is_payday("2026-02-27")
    loan = Loan("L1", "C1", "2026-04-02", 100000, 100000, 30, "synthetic")
    assert true_commission(truth, loan, Plan((100000,), ("A",))) == true_commission(
        truth, loan, Plan((100000,), ("B",))
    )


def test_generator_is_repeatable_and_keeps_truth_outside_model_inputs(tmp_path):
    first, truth = generate(tmp_path / "first", n_loans=8, n_clients=2, end="2026-01-05")
    second, repeated = generate(tmp_path / "second", n_loans=8, n_clients=2, end="2026-01-05")
    assert truth == repeated
    assert {p.name for p in first.iterdir()} == {
        "clients.csv",
        "loan_snapshots.csv",
        "payment_attempts.csv",
    }
    for path in first.iterdir():
        assert path.read_bytes() == (second / path.name).read_bytes()
    snapshots = pd.read_csv(first / "loan_snapshots.csv")
    assert snapshots.outstanding_balance.le(snapshots.original_amount).all()
    attempts = pd.read_csv(first / "payment_attempts.csv")
    assert all(is_payday(d) for d in attempts.loc[attempts.provider.eq("B"), "attempt_date"])
    with pytest.raises(FileExistsError):
        generate(tmp_path / "first", n_loans=8)


def accounting_fixture(data):
    """One attempt per plan; all training labels succeed, then one test debit fails.

    A's 181 prepaid units are already consumed. Thus the only positive candidate
    plans are two B debits of 100, at independently specified 15% and 50% shares.
    """
    data.mkdir()
    pd.DataFrame(
        [("C1", "100.00"), ("C2", "100.00")], columns=["client_id", "max_installment_amount"]
    ).to_csv(data / "clients.csv", index=False)
    snapshots, attempts = [], []
    historical = [(f"A{i}", "C1", "A", 0) for i in range(181)] + [
        ("B1", "C1", "B", 0),
        ("B2", "C2", "B", 91),
    ]
    for loan, client, provider, dpd in historical:
        snapshots.append(("2026-01-01", loan, client, "100.00", dpd))
        attempts.append((loan, loan, "2026-01-01", 1, 1, "100.00", provider, "success"))
    for loan, client, dpd, outcome in (("X1", "C1", 0, "success"), ("X2", "C2", 91, "failed")):
        snapshots.append(("2026-04-02", loan, client, "100.00", dpd))
        attempts.append((loan, loan, "2026-04-02", 1, 1, "100.00", "B", outcome))
    pd.DataFrame(
        snapshots,
        columns=["snapshot_date", "loan_id", "client_id", "outstanding_balance", "days_past_due"],
    ).to_csv(data / "loan_snapshots.csv", index=False)
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
    ).to_csv(data / "payment_attempts.csv", index=False)
    return Protocol(
        Protocol.load().values
        | {
            "test_start": "2026-04-02",
            "test_end": "2026-04-02",
            "sample_weight": 1,
            "full_a_capacity": 181,
            "full_a_upfront": "181",
            "min_cell_attempts": 1,
            "prior_strength": 1,
            "conservative_z": 0,
            "max_installments": 1,
            "amount_fractions": ["1.00"],
        }
    )


def test_offline_evaluation_matches_independent_money_oracle(tmp_path):
    data = tmp_path / "data"
    protocol = accounting_fixture(data)
    result = evaluate(data, tmp_path / "evaluation", protocol)
    # These constants come from the fixture, not the model/accounting functions:
    # candidate commission=100*15%+100*50%=65; B fees=2*2; fixed=181/181=1.
    assert result["candidate_estimated_april_margin"] == pytest.approx(60)
    # The failed B attempt still costs 2: observed=15-2-2-1=10.
    assert result["legacy_observed_april_margin"] == pytest.approx(10)
    assert result["legacy_estimated_april_margin"] == pytest.approx(60)
    assert result["april_fixed_cost"] == pytest.approx(1)
    assert result["candidate_b_units"] == 2 and result["remaining_a"] == 0
    lenders = pd.read_csv(tmp_path / "evaluation/per_client.csv", index_col="client_id")
    assert lenders.loc["C1", "candidate_april_margin"] == pytest.approx(12.5)
    assert lenders.loc["C2", "candidate_april_margin"] == pytest.approx(47.5)
    assert lenders.loc["C2", "legacy_observed_april_margin"] == pytest.approx(-2.5)
    assert sum(Decimal(str(v)) for v in lenders.candidate_april_margin) == Decimal("60.0")
    # Jan history contributes 181*15 + (15-2) + (50-2)=2776, then charge upfront once.
    assert result["candidate_jan_apr_coverage"] == pytest.approx(2776 + 61 - 181)


def test_truth_stress_checks_money_support_and_oracle_scope(tmp_path):
    data = tmp_path / "data"
    protocol = accounting_fixture(data)
    result = score(data, {"base": {"C1": 0.02, "C2": 0.03}}, protocol)
    totals = result["totals"]
    assert totals["candidate_estimated_margin"] == pytest.approx(60)
    assert totals["candidate_true_expected_commission"] < 65
    assert totals["candidate_true_expected_margin"] == pytest.approx(
        totals["candidate_true_expected_commission"] - 4 - 1
    )
    assert totals["candidate_b_without_calendar_support"] == 2
    assert totals["candidate_nonpayday_b"] == 2
    assert sum(v["candidate_true_expected_margin"] for v in result["per_client"].values()) == (
        pytest.approx(totals["candidate_true_expected_margin"])
    )
    assert result["remaining_a"] == 0
    assert result["oracle"]["capacity_feasible"] is False
    assert result["oracle"]["sequential"] is False
    assert result["oracle"]["historical_support_enforced"] is False
    assert result["oracle"]["lender_budgets_enforced"] is False
    alternate = score(data, {"base": {"C1": 0.04, "C2": 0.06}}, protocol)
    assert alternate["model_hash"] == result["model_hash"]
    assert alternate["totals"]["candidate_estimated_margin"] == totals["candidate_estimated_margin"]
    assert alternate["totals"]["candidate_true_expected_commission"] == pytest.approx(
        2 * totals["candidate_true_expected_commission"]
    )
    json.dumps(result)  # Report remains portable without numpy scalar serialization failures.
