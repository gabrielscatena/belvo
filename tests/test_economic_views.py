"""Accounting identities must hold independently of response-model optimism."""

import csv
import hashlib
import json
from decimal import Decimal

import pytest

from belvo.config import Protocol
from belvo.evaluation.economic_views import (
    allocated_charges,
    allocation_views,
    lambda_views,
    run,
    tariff_views,
)


def example_rows():
    return [
        {
            "client_id": "C1",
            "legacy_observed": "25",
            "legacy_estimated": "30",
            "legacy_a": "2",
            "legacy_b": "1",
            "candidate": "60",
            "candidate_conservative": "40",
            "candidate_a": "7",
            "candidate_b": "0",
        },
        {
            "client_id": "C2",
            "legacy_observed": "75",
            "legacy_estimated": "80",
            "legacy_a": "8",
            "legacy_b": "0",
            "candidate": "140",
            "candidate_conservative": "100",
            "candidate_a": "3",
            "candidate_b": "2",
        },
    ]


def test_all_cash_allocations_charge_fixed_commitment_once_and_reconcile():
    views = allocation_views(example_rows(), Decimal(30), {"C1": 1, "C2": 3})
    for policy in {row["policy"] for row in views}:
        for method in {row["allocation"] for row in views}:
            group = [r for r in views if r["policy"] == policy and r["allocation"] == method]
            total = next(row for row in group if row["client_id"] == "TOTAL")
            lenders = [row for row in group if row["client_id"] != "TOTAL"]
            assert sum(row["allocated_fixed_A_cost"] for row in lenders) == 30
            assert sum(row["accounting_margin"] for row in lenders) == total["accounting_margin"]
            assert total["accounting_margin"] == total["contribution_net_B_fees"] - 30
            assert total["accounting_margin"] == {
                "legacy_observed": 70,
                "legacy_estimated": 80,
                "candidate_estimated": 170,
            }[policy]


def test_fixed_weights_stay_identical_and_own_policy_weights_are_separate():
    views = allocation_views(example_rows(), Decimal(30), {"C1": 1, "C2": 3})
    pretest = [
        row
        for row in views
        if row["allocation"] == "pretest_A_use_fixed_weights" and row["client_id"] == "C1"
    ]
    assert {row["allocation_weight"] for row in pretest} == {Decimal("0.25")}
    assert {row["allocated_fixed_A_cost"] for row in pretest} == {Decimal("7.5")}
    own = {
        row["policy"]: row["allocated_fixed_A_cost"]
        for row in views
        if row["allocation"] == "own_policy_A_use_diagnostic" and row["client_id"] == "C1"
    }
    assert own == {"legacy_observed": 6, "legacy_estimated": 6, "candidate_estimated": 21}


def test_zero_usage_allocation_retains_cost_and_decimal_residual():
    rows = example_rows()
    for row in rows:
        row["candidate_a"] = 0
    views = allocation_views(rows, Decimal(30), {})
    candidate = [
        row
        for row in views
        if row["policy"] == "candidate_estimated"
        and row["allocation"] == "own_policy_A_use_diagnostic"
        and row["client_id"] != "TOTAL"
    ]
    assert [row["allocated_fixed_A_cost"] for row in candidate] == [15, 15]
    weights = {f"C{i}": Decimal(1) / 3 for i in range(3)}
    assert sum(allocated_charges(Decimal("100.01"), weights).values()) == Decimal("100.01")


def test_tariff_diagnostic_is_not_allocation_and_bridges_without_double_B_cost():
    rows = example_rows()
    result = tariff_views(rows, Decimal(30))
    for total in [row for row in result if row["client_id"] == "TOTAL"]:
        assert (
            total["usage_priced_margin_diagnostic"] - total["fixed_cost_minus_tariff_charges"]
            == total["reconciled_cash_margin"]
        )
    legacy = next(
        row for row in result if row["policy"] == "legacy_observed" and row["client_id"] == "C1"
    )
    assert legacy["usage_priced_margin_diagnostic"] == 23  # Input already excludes B fees.
    heavy_use = tariff_views(rows, Decimal(5))
    total = next(
        row
        for row in heavy_use
        if row["policy"] == "candidate_estimated" and row["client_id"] == "TOTAL"
    )
    assert total["fixed_cost_minus_tariff_charges"] == -5  # Not physical unused allowance.
    assert total["reconciled_cash_margin"] == 195


def test_lambda_changes_decision_scores_but_never_cash_margin():
    views = [
        row for row in lambda_views(example_rows(), 30) if row["policy"] == "candidate_estimated"
    ]
    assert [row["lambda_per_A_unit"] for row in views] == [
        Decimal(x) for x in ("0", "0.25", "0.5", "1", "2")
    ]
    assert {row["unchanged_accounting_margin"] for row in views} == {170}
    assert views[3]["mean_contribution_score"] == 190
    assert views[3]["conservative_contribution_score"] == 130
    assert views[3]["shadow_adjusted_score_after_fixed_cost_not_cash"] == 160
    with pytest.raises(ValueError, match="nonnegative"):
        lambda_views(example_rows(), 30, prices=[-1])


def fixture_evaluation(tmp_path):
    evaluation, data = tmp_path / "evaluation", tmp_path / "data"
    evaluation.mkdir()
    data.mkdir()
    protocol = Protocol.load()
    (data / "clients.csv").write_text("client_id\nC1\nC2\n")
    (data / "loan_snapshots.csv").write_text(
        "loan_id,client_id,snapshot_date\n"
        "L1,C1,2026-01-01\nL2,C2,2026-03-31\n"
    )
    attempts = data / "payment_attempts.csv"
    attempts.write_text(
        "attempt_date,provider,loan_id,status\n"
        "2026-01-01,A,L1,failed\n"
        "2026-03-31,A,L2,failed\n"
        "2026-03-31,B,L1,success\n"
        "2026-04-01,A,L1,success\n"
    )
    with (evaluation / "per_client.csv").open("w", newline="") as stream:
        rows = example_rows()
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "protocol": protocol.values,
        "scope": "Test April conditional replay",
        "initial_a_consumed": 2,
        "april_fixed_cost": 30,
        "source_sha256": {"payment_attempts.csv": hashlib.sha256(attempts.read_bytes()).hexdigest()},
    }
    (evaluation / "summary.json").write_text(json.dumps(summary))
    return evaluation, data, protocol


def test_diagnostic_run_preserves_frozen_sources_and_never_overwrites(tmp_path):
    evaluation, data, protocol = fixture_evaluation(tmp_path)
    before = {p.name: p.read_bytes() for p in evaluation.iterdir()}
    output = tmp_path / "views"
    meta = run(evaluation, data, output, protocol)
    assert meta["pretest_A_units_by_lender"] == {"C1": 1, "C2": 1}
    assert {p.name: p.read_bytes() for p in evaluation.iterdir()} == before
    assert {p.name for p in output.iterdir()} == {
        "allocation_views.csv",
        "tariff_diagnostic.csv",
        "fixed_action_lambda.csv",
        "metadata.json",
        "README.md",
    }
    assert any("no six-month" in warning for warning in meta["warnings"])
    with pytest.raises(FileExistsError):
        run(evaluation, data, output, protocol)


def test_changed_source_or_economic_protocol_is_rejected_before_output(tmp_path):
    evaluation, data, protocol = fixture_evaluation(tmp_path)
    output = tmp_path / "views"
    changed = Protocol(protocol.values | {"a_opportunity_cost": "1"})
    with pytest.raises(ValueError, match="Configuration"):
        run(evaluation, data, output, changed)
    assert not output.exists()
    attempts = data / "payment_attempts.csv"
    attempts.write_text(attempts.read_text().replace("failed", "success"))
    with pytest.raises(ValueError, match="source differs"):
        run(evaluation, data, output, protocol)
    assert not output.exists()
