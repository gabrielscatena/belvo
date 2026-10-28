"""Economic and data-integrity regression tests, independent of private CSVs."""

import contextlib
import csv
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from belvo.data.eda import Settings, allocate_cents, money_to_cents, run_analysis


class BelvoEDATests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(
            prefix=".eda_test_",
            dir=Path(__file__).resolve().parent,
        )
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raw = self.root / "raw"
        self.raw.mkdir()
        self.output = self.root / "output"
        self.clients = pd.DataFrame(
            [
                ["C1", "60.00"],
                ["C2", "50.00"],
            ],
            columns=["client_id", "max_installment_amount"],
        )
        self.snapshots = pd.DataFrame(
            [
                ["2026-01-01", "L1", "C1", "100.00", 5, "100.00", "monthly", "bank_1", 12],
                ["2026-01-02", "L1", "C1", "40.00", 6, "100.00", "monthly", "bank_1", 12],
                ["2026-01-01", "L2", "C2", "50.00", 16, "50.00", "weekly", "bank_2", 3],
                ["2026-01-03", "L2", "C2", "50.00", 18, "50.00", "weekly", "bank_2", 3],
            ],
            columns=[
                "snapshot_date",
                "loan_id",
                "client_id",
                "outstanding_balance",
                "days_past_due",
                "original_amount",
                "payroll_cycle",
                "debtor_bank",
                "customer_tenure_months",
            ],
        )
        self.attempts = pd.DataFrame(
            [
                ["A1", "L1", "2026-01-01", 1, 2, "60.00", "A", "success", "1.00"],
                ["A2", "L1", "2026-01-01", 2, 2, "40.00", "B", "failed", "2.00"],
            ],
            columns=[
                "attempt_id",
                "loan_id",
                "attempt_date",
                "installment_index",
                "installment_count",
                "amount",
                "provider",
                "status",
                "fee",
            ],
        )

    def run_fixture(self):
        for name, frame in [
            ("clients", self.clients),
            ("loan_snapshots", self.snapshots),
            ("payment_attempts", self.attempts),
        ]:
            frame.to_csv(self.raw / f"{name}.csv", index=False)
        before = {p.name: p.read_bytes() for p in self.raw.glob("*.csv")}
        with contextlib.redirect_stdout(io.StringIO()):
            status = run_analysis(Settings(self.raw, self.output))
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.raw.glob("*.csv")})
        return status

    def checks(self):
        return pd.read_csv(self.output / "validation_checks.csv").set_index("check")

    def test_revenue_fees_lender_reconciliation_and_gap_semantics(self):
        self.assertEqual(self.run_fixture(), 0)
        metrics = json.loads((self.output / "metrics.json").read_text())
        self.assertEqual(metrics["sample_commission_revenue"], "9.0000")
        self.assertEqual(metrics["sample_usage_margin"], "6.0000")
        self.assertEqual(metrics["sample_observed_contribution"], "7.0000")
        self.assertEqual(metrics["sample_a_attempts"], 1)  # failed B also costs 2
        self.assertEqual(metrics["sample_b_attempts"], 1)
        self.assertEqual(metrics["snapshot_gaps"], 1)
        self.assertEqual(metrics["nonzero_adjacent_residuals"], 0)
        self.assertIsNone(metrics["realized_full_window_margin"])
        lenders = pd.read_csv(self.output / "economics_by_lender.csv")
        self.assertEqual(len(lenders), 2)  # lender with no attempts is retained
        self.assertEqual(lenders.commission_revenue.sum(), 9)
        coverage = pd.read_csv(self.output / "commitment_coverage_by_lender.csv")
        for _, group in coverage.groupby("allocation_scenario"):
            self.assertAlmostEqual(group.allocated_full_a_commitment.sum(), 10_000_000, places=2)
            self.assertAlmostEqual(
                group.commitment_coverage_at_observed_cutoff.sum(), 7 * 15 - 10_000_000, places=2
            )

    def test_duplicate_attempt_identity_stops_before_economics(self):
        self.attempts.loc[1, "attempt_id"] = "A1"
        self.assertEqual(self.run_fixture(), 2)
        self.assertEqual(self.checks().loc["payment_attempts_key", "affected_count"], 2)
        self.assertFalse((self.output / "economics_by_lender.csv").exists())
        with (self.output / "examples/payment_attempts_key.csv").open(
            encoding="utf-8-sig"
        ) as stream:
            headers = next(csv.reader(stream))
        self.assertEqual(len(headers), len(set(headers)))

    def test_duplicate_snapshot_does_not_multiply_attempt_revenue(self):
        self.snapshots = pd.concat([self.snapshots, self.snapshots.iloc[[0]]], ignore_index=True)
        self.assertEqual(self.run_fixture(), 2)
        self.assertFalse((self.output / "economics_by_lender.csv").exists())

    def test_missing_same_day_snapshot_is_not_forward_filled(self):
        self.attempts.loc[:, "attempt_date"] = "2026-01-03"
        self.assertEqual(self.run_fixture(), 2)
        self.assertEqual(self.checks().loc["attempt_same_day_snapshot", "affected_count"], 2)
        self.assertFalse((self.output / "economic_totals.csv").exists())

    def test_historical_cap_violation_is_reported_without_clipping(self):
        self.clients.loc[0, "max_installment_amount"] = "50.00"
        self.assertEqual(self.run_fixture(), 2)
        self.assertEqual(self.checks().loc["installment_cap", "affected_count"], 1)
        metrics = json.loads((self.output / "metrics.json").read_text())
        self.assertEqual(metrics["sample_commission_revenue"], "9.0000")

    def test_fractional_cents_rejected(self):
        self.attempts.loc[0, "amount"] = "60.001"
        self.assertEqual(self.run_fixture(), 2)
        self.assertEqual(
            self.checks().loc["payment_attempts_amount_precision", "affected_count"], 1
        )

    def test_incomplete_installment_group_detected(self):
        self.attempts.loc[1, "installment_index"] = 1
        self.assertEqual(self.run_fixture(), 2)
        self.assertEqual(self.checks().loc["installment_group_coherence", "affected_count"], 1)

    def test_ownership_ambiguity_not_assigned_arbitrarily(self):
        self.snapshots.loc[1, "client_id"] = "C2"
        self.assertEqual(self.run_fixture(), 2)
        self.assertEqual(self.checks().loc["loan_owner_ambiguity", "affected_count"], 2)
        self.assertFalse((self.output / "economic_totals.csv").exists())

    def test_total_plan_exceeds_balance_even_when_installments_fit_cap(self):
        self.clients.loc[0, "max_installment_amount"] = "100.00"
        self.attempts.loc[1, "amount"] = "50.00"
        self.assertEqual(self.run_fixture(), 2)
        self.assertEqual(self.checks().loc["loan_day_balance_limit", "affected_count"], 1)
        self.assertEqual(self.checks().loc["installment_cap", "affected_count"], 0)

    def test_unexpected_fee_is_counted_and_flagged(self):
        self.attempts.loc[1, "fee"] = "3.00"
        self.assertEqual(self.run_fixture(), 2)
        self.assertEqual(self.checks().loc["provider_fee_mapping", "affected_count"], 1)
        metrics = json.loads((self.output / "metrics.json").read_text())
        self.assertEqual(metrics["sample_usage_margin"], "5.0000")
        self.assertEqual(metrics["sample_observed_contribution"], "6.0000")

    def test_exact_money_and_allocation(self):
        self.assertEqual(money_to_cents("0.29"), 29)
        self.assertEqual(money_to_cents("-0.01"), -1)
        for invalid in ["nan", "inf", "", "1.001", "1e2", " 1.00"]:
            self.assertIsNone(money_to_cents(invalid))
        self.assertEqual(allocate_cents(100, [1, 1, 1]), [34, 33, 33])
        self.assertEqual(allocate_cents(100, [0, 0]), [50, 50])


if __name__ == "__main__":
    unittest.main()
