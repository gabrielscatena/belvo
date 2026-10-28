"""Auditable, descriptive EDA for the supplied collections challenge.

Inputs are never edited or deduplicated. Money is checked and calculated in
integer minor units; commissions retain four decimal places (no per-attempt
rounding). Invalid keys/types stop dependent analysis instead of changing its
population silently. No model fitting or counterfactual simulation is performed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DPD_LABELS = ["0-5", "6-15", "16-30", "31-60", "61-90", "91+"]
SCHEMAS = {
    "clients": ["client_id", "max_installment_amount"],
    "loan_snapshots": [
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
    "payment_attempts": [
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
}
MONEY_FIELDS = {
    "clients": ["max_installment_amount"],
    "loan_snapshots": ["outstanding_balance", "original_amount"],
    "payment_attempts": ["amount", "fee"],
}
INTEGER_FIELDS = {
    "clients": [],
    "loan_snapshots": ["days_past_due", "customer_tenure_months"],
    "payment_attempts": ["installment_index", "installment_count"],
}


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    output_dir: Path
    sample_weight: int = 15
    contract_start: str = "2026-01-01"
    contract_end: str = "2026-06-30"
    a_allowance: int = 10_000_000
    a_upfront_cents: int = 1_000_000_000
    example_limit: int = 25


def money_to_cents(value: str) -> int | None:
    """Reject precision loss, nonfinite values, scientific notation and blanks."""
    if not re.fullmatch(r"[+-]?\d+(?:\.\d{1,2})?", str(value)):
        return None
    try:
        return int(Decimal(str(value)) * 100)
    except (InvalidOperation, ValueError, OverflowError):
        return None


def format_fixed(value: int, places: int) -> str:
    number = int(value)
    sign = "-" if number < 0 else ""
    number = abs(number)
    scale = 10**places
    return f"{sign}{number // scale}.{number % scale:0{places}d}"


def allocate_cents(total: int, numerators: list[int]) -> list[int]:
    """Proportional allocation with deterministic largest-remainder rounding."""
    denominator = sum(numerators)
    if denominator <= 0:
        numerators = [1] * len(numerators)
        denominator = len(numerators)
    allocations = [total * n // denominator for n in numerators]
    order = sorted(
        range(len(numerators)),
        key=lambda i: (-(total * numerators[i] % denominator), i),
    )
    for i in order[: total - sum(allocations)]:
        allocations[i] += 1
    assert sum(allocations) == total
    return allocations


class Audit:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.checks: list[dict] = []
        self.metadata: dict = {}
        self.metrics: dict = {}
        self.table_names: list[str] = []
        settings.output_dir.mkdir(parents=True, exist_ok=False)

    @property
    def errors(self) -> int:
        return sum(c["severity"] == "error" and c["affected_count"] > 0 for c in self.checks)

    def check(
        self,
        name: str,
        severity: str,
        count: int,
        detail: str,
        examples: pd.DataFrame | None = None,
    ) -> None:
        example_file = ""
        if count and examples is not None and not examples.empty:
            folder = self.settings.output_dir / "examples"
            folder.mkdir(exist_ok=True)
            example_file = f"examples/{name}.csv"
            self.export_frame(examples.head(self.settings.example_limit)).to_csv(
                self.settings.output_dir / example_file,
                index=False,
                encoding="utf-8-sig",
            )
        self.checks.append(
            {
                "check": name,
                "severity": severity,
                "status": "pass" if count == 0 else ("fail" if severity == "error" else "review"),
                "affected_count": int(count),
                "detail": detail,
                "examples": example_file,
            }
        )

    @staticmethod
    def export_frame(frame: pd.DataFrame) -> pd.DataFrame:
        result = frame.copy()
        for col in frame.columns:
            places = 2 if col.endswith("_cents") else 4 if col.endswith("_units") else None
            if places is not None:
                result[col] = frame[col].map(
                    lambda v, places=places: "" if pd.isna(v) else format_fixed(int(v), places)
                )
                target = col.rsplit("_", 1)[0]
                # Evidence frames may contain both the raw token and parsed money.
                if target in result.columns:
                    target += "_validated"
                result.rename(columns={col: target}, inplace=True)
        return result

    def table(self, name: str, frame: pd.DataFrame) -> None:
        self.export_frame(frame).to_csv(
            self.settings.output_dir / f"{name}.csv",
            index=False,
            encoding="utf-8-sig",
        )
        self.table_names.append(f"{name}.csv")

    def finish(self, complete: bool) -> int:
        self.table("validation_checks", pd.DataFrame(self.checks))
        self.metadata["analysis_completed"] = complete
        self.metadata["validation_error_checks"] = self.errors
        self.metadata["review_checks"] = sum(
            c["severity"] == "warning" and c["affected_count"] > 0 for c in self.checks
        )
        self.metadata["tables"] = self.table_names
        (self.settings.output_dir / "run_metadata.json").write_text(
            json.dumps(self.metadata, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (self.settings.output_dir / "metrics.json").write_text(
            json.dumps(self.metrics, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (self.settings.output_dir / "report.md").write_text(self.report(complete), encoding="utf-8")
        print(f"Report: {self.settings.output_dir / 'report.md'}")
        print(f"Failed validation checks: {self.errors}")
        return 2 if self.errors else 0

    def report(self, complete: bool) -> str:
        lines = [
            "# Belvo challenge-specific EDA",
            "",
            f"Analysis completed: **{complete}**. Failed validation checks: **{self.errors}**.",
            "",
            "## Scope and reproducibility",
            "",
            "- Inputs were read without modification, deduplication, clipping or imputation.",
            "- File SHA-256 hashes, versions and settings are in `run_metadata.json`.",
            "- Monetary input checks use exact cents. Commission and margin use integer units",
            "  of 0.0001 currency units; commission is not rounded per attempt.",
            "- Rates are descriptive fractions; provider differences are not causal effects.",
            "- Counts in validation_checks.csv refer to the entity described by each check.",
            "- Examples are bounded; affected counts refer to all detected cases.",
            "",
            "## Validation findings",
            "",
            "| Check | Severity | Status | Affected |",
            "|---|---|---|---:|",
        ]
        lines.extend(
            f"| {c['check']} | {c['severity']} | {c['status']} | {c['affected_count']:,} |"
            for c in self.checks
            if c["affected_count"]
        )
        if not any(c["affected_count"] for c in self.checks):
            lines.append("| All implemented checks | - | pass | 0 |")
        if not complete:
            lines += [
                "",
                "Dependent analysis was stopped because structural or attribution",
                "checks failed. No partially attributed economics are presented.",
            ]
        else:
            m = self.metrics
            lines += [
                "",
                "## Observed legacy economics",
                "",
                f"- Observed attempt dates: {m['attempt_start']} through {m['attempt_end']}.",
                f"- Sample commission revenue: **{m['sample_commission_revenue']}**.",
                f"- Sample recorded attempt fees: **{m['sample_recorded_fees']}**.",
                f"- Sample usage-priced margin diagnostic: **{m['sample_usage_margin']}**.",
                f"- Sample A / B attempts: **{m['sample_a_attempts']:,} / {m['sample_b_attempts']:,}**.",
                (
                    f"- Lenders with non-positive sample usage-priced diagnostic: "
                    f"**{m['nonpositive_usage_margin_lenders']}**. This is not contract profitability."
                ),
                "",
                "The usage-priced diagnostic is commission minus recorded fees. It is not",
                "the prepaid-contract margin: unused A capacity is not costed by usage fees.",
                "Observed-period contribution excludes the already committed A payment and",
                "subtracts recorded B charges; no A fee is subtracted a second time.",
                "",
                "## Sample and contract boundary",
                "",
                f"- Loan inclusion weight: **{self.settings.sample_weight}** (default from package README).",
                f"- A contract: **{self.settings.contract_start} to {self.settings.contract_end}**.",
                f"- Full-book A allowance: **{self.settings.a_allowance:,}**.",
                f"- Full-book A upfront cost: **{format_fixed(self.settings.a_upfront_cents, 2)}**.",
                (
                    f"- Weighted observed-period A utilization estimate: "
                    f"**{m['weighted_a_utilization_fraction']:.2%}**."
                ),
                "- Weighted tables estimate additive full-book observed-period totals, not exact",
                "  full-book realized values. Sampling uncertainty is not quantified here.",
                "- Rates and individual payment amounts are not multiplied by the sample weight.",
                "- Missing May-June activity is not forecast or fabricated by this script.",
                "- `commitment_coverage_by_lender.csv` subtracts the entire committed A cost",
                "  from weighted observed-period contribution under explicit allocation scenarios.",
                "  It measures commitment coverage at the observed cutoff, not final six-month margin.",
                "- Allocation scenarios use equal weights, opening observed portfolio balance",
                "  shares, and ex-post A usage shares. Ex-post usage is descriptive only; it must",
                "  not silently determine a prospective profitability constraint.",
                "- Zero-denominator allocation scenarios fall back to equal weights.",
                "",
                "## Balance and legacy-policy interpretation",
                "",
                (
                    f"- Adjacent-calendar-day balance residuals different from zero: "
                    f"**{m['nonzero_adjacent_residuals']:,}**."
                ),
                f"- Gaps between observed snapshots of the same loan: **{m['snapshot_gaps']:,}**.",
                "- For adjacent days, residual = next balance - current balance + current-day",
                "  successful collections. A nonzero residual is unexplained by these observed",
                "  collections; it is not proof of an external payment, error, or adjustment.",
                "- Gap transitions are separate: intervening activity is not observed for that loan.",
                "- Loan exits at the last observed date are right-censored, not confirmed closures.",
                "- A snapshot without an attempt means no observed attempt, not a known rejection reason.",
                "- All-zero/all-success installment-plan frequencies are descriptive; no independence",
                "  of installments is assumed, and provider success differences are not causal.",
                "- History before the extract is left-truncated. The inferred next-day outcome",
                "  availability date is not a provider arrival timestamp or a decision-cutoff guarantee.",
                "- Legacy future snapshots already incorporate legacy collections. They are not a",
                "  validated trajectory for an alternative multi-day policy.",
                "",
                "## Evidence to refine docs 01-04",
                "",
                "| Document | Evidence | Still unresolved |",
                "|---|---|---|",
                (
                    "| 01 Business process | daily_portfolio, loan_observability, validation_checks | "
                    "Within-day cutoff, provider acceptance/idempotency guarantees |"
                ),
                (
                    "| 02 Domain model | dataset_overview, validation_checks, balance_transition_summary | "
                    "Unobserved history, external adjustments and account-level identity |"
                ),
                (
                    "| 03 Economic model | economics_by_lender, economics_weighted_full_book, "
                    "commitment_coverage_by_lender | Final contract profit, May-June, approved cost allocation |"
                ),
                (
                    "| 04 Problem framing | legacy_segments, plan_patterns, loan_day_activity_summary | "
                    "Counterfactual support, calibrated success models, dynamic transitions and optimum |"
                ),
            ]
        lines += ["", "## Outputs", ""]
        lines.extend(f"- [{name}]({name})" for name in self.table_names)
        lines += [
            "",
            "Detailed check explanations and example paths are in `validation_checks.csv`.",
            "",
        ]
        return "\n".join(lines)


def failure_rows(
    audit: Audit,
    name: str,
    frame: pd.DataFrame,
    mask: pd.Series,
    detail: str,
    severity: str = "error",
) -> None:
    mask = mask.fillna(True)
    audit.check(name, severity, int(mask.sum()), detail, frame.loc[mask])


def parse_inputs(audit: Audit) -> dict[str, pd.DataFrame] | None:
    frames = {}
    overview = []
    for name, required in SCHEMAS.items():
        path = audit.settings.data_dir / f"{name}.csv"
        print(f"Reading and validating {path.name}...", flush=True)
        if not path.is_file():
            audit.check(f"{name}_file", "error", 1, f"Missing input: {path}")
            continue
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        audit.metadata["inputs"][name] = {
            "path": str(path.resolve()),
            "bytes": path.stat().st_size,
            "sha256": digest.hexdigest(),
        }
        with path.open(encoding="utf-8-sig", newline="") as stream:
            header = next(csv.reader(stream), [])
        repeated_headers = sorted({h for h in header if header.count(h) > 1})
        audit.check(
            f"{name}_duplicate_headers",
            "error",
            len(repeated_headers),
            f"Duplicate CSV headers would be renamed by pandas: {repeated_headers}",
        )
        # Explicit strings preserve invalid numeric tokens, blanks and ID formatting.
        frame = pd.read_csv(path, dtype="string", keep_default_na=False, encoding="utf-8-sig")
        frames[name] = frame
        missing = sorted(set(required) - set(frame.columns))
        audit.check(f"{name}_required_columns", "error", len(missing), f"Missing: {missing}")
        audit.check(f"{name}_nonempty", "error", int(frame.empty), "Dataset must contain rows.")
        duplicates = frame.duplicated(keep=False)
        failure_rows(
            audit,
            f"{name}_duplicate_rows",
            frame,
            duplicates,
            "Rows belonging to exact duplicate groups; no rows are silently dropped.",
        )
        overview.append(
            {
                "dataset": name,
                "rows": len(frame),
                "columns": len(frame.columns),
                "duplicate_group_rows": int(duplicates.sum()),
                "blank_cells": int(frame.eq("").sum().sum()),
            }
        )
        if missing or frame.empty:
            continue
        for col in required:
            failure_rows(
                audit,
                f"{name}_{col}_blank",
                frame,
                frame[col].str.strip().eq(""),
                f"Blank required {col}; row count.",
            )
        for col in MONEY_FIELDS[name]:
            parsed = pd.Series(
                [money_to_cents(v) for v in frame[col]], index=frame.index, dtype=object
            )
            # Bound guarantees aggregate cents and commission units cannot overflow int64.
            limit = np.iinfo(np.int64).max // (
                100 * audit.settings.sample_weight * max(len(frame), 1)
            )
            invalid = parsed.map(lambda v, limit=limit: pd.isna(v) or abs(int(v)) > limit)
            failure_rows(
                audit,
                f"{name}_{col}_precision",
                frame,
                invalid,
                "Requires finite decimal money with <=2 decimal places and safe integer range.",
            )
            frame[f"{col}_cents"] = pd.array(parsed.where(~invalid), dtype="Int64")
        for col in INTEGER_FIELDS[name]:
            parsed = pd.Series(
                [int(v) if re.fullmatch(r"[+-]?\d+", str(v)) else None for v in frame[col]],
                index=frame.index,
                dtype=object,
            )
            invalid = parsed.map(lambda v: pd.isna(v) or abs(int(v)) > np.iinfo(np.int64).max // 4)
            failure_rows(
                audit,
                f"{name}_{col}_integer",
                frame,
                invalid,
                "Requires an integer in the supported range; no fractional truncation.",
            )
            frame[col] = pd.array(parsed.where(~invalid), dtype="Int64")
        date_col = (
            "snapshot_date"
            if name == "loan_snapshots"
            else ("attempt_date" if name == "payment_attempts" else None)
        )
        if date_col:
            parsed = pd.to_datetime(frame[date_col], format="%Y-%m-%d", errors="coerce")
            invalid = parsed.isna() | ~frame[date_col].str.fullmatch(r"\d{4}-\d{2}-\d{2}")
            failure_rows(audit, f"{name}_date_format", frame, invalid, "Requires valid YYYY-MM-DD.")
            frame[date_col] = parsed
    audit.table("dataset_overview", pd.DataFrame(overview))
    if audit.errors:
        return None
    return frames


def structural_checks(frames: dict[str, pd.DataFrame], audit: Audit) -> bool:
    clients, snapshots, attempts = (frames[n] for n in SCHEMAS)
    for name, keys in [
        ("clients", ["client_id"]),
        ("loan_snapshots", ["loan_id", "snapshot_date"]),
        ("payment_attempts", ["attempt_id"]),
    ]:
        f = frames[name]
        failure_rows(
            audit,
            f"{name}_key",
            f,
            f.duplicated(keys, keep=False),
            f"Rows in non-unique key groups: {keys}.",
        )
    owners = snapshots.groupby("loan_id")["client_id"].nunique()
    bad_loans = owners[owners != 1].index
    failure_rows(
        audit,
        "loan_owner_ambiguity",
        snapshots,
        snapshots.loan_id.isin(bad_loans),
        "Snapshot rows for loans with multiple clients; attempts have no client_id.",
    )
    failure_rows(
        audit,
        "snapshot_client_fk",
        snapshots,
        ~snapshots.client_id.isin(clients.client_id),
        "Snapshot rows with unknown clients.",
    )
    failure_rows(
        audit,
        "attempt_loan_fk",
        attempts,
        ~attempts.loan_id.isin(snapshots.loan_id),
        "Attempt rows with no observed loan.",
    )
    domains = [
        ("client_cap_positive", clients, clients.max_installment_amount_cents.le(0)),
        ("balance_nonnegative", snapshots, snapshots.outstanding_balance_cents.lt(0)),
        ("original_amount_positive", snapshots, snapshots.original_amount_cents.le(0)),
        ("dpd_nonnegative", snapshots, snapshots.days_past_due.lt(0)),
        ("tenure_nonnegative", snapshots, snapshots.customer_tenure_months.lt(0)),
        ("attempt_amount_positive", attempts, attempts.amount_cents.le(0)),
        ("fee_nonnegative", attempts, attempts.fee_cents.lt(0)),
        ("installment_count_positive", attempts, attempts.installment_count.le(0)),
        (
            "installment_index_range",
            attempts,
            attempts.installment_index.lt(1)
            | attempts.installment_index.gt(attempts.installment_count),
        ),
        ("provider_domain", attempts, ~attempts.provider.isin(["A", "B"])),
        ("status_domain", attempts, ~attempts.status.isin(["success", "failed"])),
        (
            "payroll_domain",
            snapshots,
            ~snapshots.payroll_cycle.isin(["weekly", "biweekly", "monthly"]),
        ),
        (
            "bank_domain",
            snapshots,
            ~snapshots.debtor_bank.isin(["bank_1", "bank_2", "bank_3", "bank_4"]),
        ),
    ]
    for name, f, mask in domains:
        failure_rows(audit, name, f, mask, "Rows violating the documented domain.")
    for name, col in [("loan_snapshots", "snapshot_date"), ("payment_attempts", "attempt_date")]:
        f = frames[name]
        mask = ~f[col].between(
            pd.Timestamp(audit.settings.contract_start), pd.Timestamp(audit.settings.contract_end)
        )
        failure_rows(
            audit,
            f"{name}_contract_dates",
            f,
            mask,
            "Rows outside the configured contract; one-window accounting is not applicable.",
        )
    return audit.errors == 0


def join_attempts(frames: dict[str, pd.DataFrame], audit: Audit) -> pd.DataFrame | None:
    clients, snapshots, attempts = (frames[n] for n in SCHEMAS)
    snapshot_cols = [
        "loan_id",
        "snapshot_date",
        "client_id",
        "days_past_due",
        "outstanding_balance_cents",
    ]
    joined = attempts.merge(
        snapshots[snapshot_cols],
        left_on=["loan_id", "attempt_date"],
        right_on=["loan_id", "snapshot_date"],
        how="left",
        validate="many_to_one",
        indicator=True,
    )
    assert len(joined) == len(attempts), "Dated join changed attempt row count."
    failure_rows(
        audit,
        "attempt_same_day_snapshot",
        joined,
        joined["_merge"].ne("both"),
        "Attempts without an exact same-day snapshot; no forward/back-fill is applied.",
    )
    if audit.errors:
        return None
    joined = joined.drop(columns="_merge").merge(
        clients[["client_id", "max_installment_amount_cents"]],
        on="client_id",
        how="left",
        validate="many_to_one",
    )
    failure_rows(
        audit,
        "installment_cap",
        joined,
        joined.amount_cents.gt(joined.max_installment_amount_cents),
        "Attempts exceeding the lender cap; historical violations are not clipped.",
    )
    expected_fee = joined.provider.map({"A": 100, "B": 200}).astype("Int64")
    failure_rows(
        audit,
        "provider_fee_mapping",
        joined,
        joined.fee_cents.ne(expected_fee),
        "Attempts with a recorded fee different from A=1.0 or B=2.0.",
    )
    joined["dpd_band"] = pd.cut(
        joined.days_past_due.astype("int64"),
        [-1, 5, 15, 30, 60, 90, np.inf],
        labels=DPD_LABELS,
    )
    joined["commission_percent"] = (
        joined.dpd_band.astype("string")
        .map(dict(zip(DPD_LABELS, [15, 20, 25, 30, 40, 50])))
        .astype("int64")
    )
    joined["success"] = joined.status.eq("success").astype("int64")
    joined["recovered_amount_cents"] = joined.amount_cents * joined.success
    joined["commission_revenue_units"] = joined.recovered_amount_cents * joined.commission_percent
    joined["recorded_fees_units"] = joined.fee_cents * 100
    joined["a_attempts"] = joined.provider.eq("A").astype("int64")
    joined["b_attempts"] = joined.provider.eq("B").astype("int64")
    joined["b_fees_units"] = joined.recorded_fees_units * joined.b_attempts
    joined["usage_margin_units"] = joined.commission_revenue_units - joined.recorded_fees_units
    joined["observed_contribution_units"] = joined.commission_revenue_units - joined.b_fees_units
    # Derived availability only, not a claim about within-day arrival ordering.
    joined["outcome_available_date_assumed"] = joined.attempt_date + pd.Timedelta(days=1)
    joined["amount_to_balance_ratio"] = (
        joined.amount_cents / joined.outstanding_balance_cents.replace(0, pd.NA)
    )
    joined["amount_to_cap_ratio"] = joined.amount_cents / joined.max_installment_amount_cents
    joined["amount_band"] = (
        pd.cut(
            joined.amount_to_balance_ratio.astype("float64"),
            [0, 0.1, 0.25, 0.5, 0.75, 1, np.inf],
            labels=["0-10%", "10-25%", "25-50%", "50-75%", "75-100%", ">100%"],
            include_lowest=True,
        )
        .astype("string")
        .fillna("undefined_zero_balance")
    )
    return joined


def summarize_attempts(attempts: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    result = (
        attempts.groupby(keys, observed=True, dropna=False)
        .agg(
            attempts=("attempt_id", "size"),
            loans=("loan_id", "nunique"),
            successes=("success", "sum"),
            a_attempts=("a_attempts", "sum"),
            b_attempts=("b_attempts", "sum"),
            attempted_amount_cents=("amount_cents", "sum"),
            recovered_amount_cents=("recovered_amount_cents", "sum"),
            commission_revenue_units=("commission_revenue_units", "sum"),
            recorded_fees_units=("recorded_fees_units", "sum"),
            b_fees_units=("b_fees_units", "sum"),
            usage_margin_units=("usage_margin_units", "sum"),
            observed_contribution_units=("observed_contribution_units", "sum"),
        )
        .reset_index()
    )
    result["success_rate"] = result.successes / result.attempts
    result["amount_recovery_rate"] = result.recovered_amount_cents / result.attempted_amount_cents
    return result


def build_plans(attempts: pd.DataFrame, audit: Audit) -> pd.DataFrame:
    ordered = attempts.sort_values(["loan_id", "attempt_date", "installment_index", "attempt_id"])
    plans = (
        ordered.groupby(["loan_id", "attempt_date"], observed=True)
        .agg(
            client_id=("client_id", "first"),
            attempts=("attempt_id", "size"),
            declared_count=("installment_count", "first"),
            count_variants=("installment_count", "nunique"),
            unique_indices=("installment_index", "nunique"),
            first_index=("installment_index", "min"),
            last_index=("installment_index", "max"),
            provider_pattern=("provider", "".join),
            min_amount_cents=("amount_cents", "min"),
            max_amount_cents=("amount_cents", "max"),
            attempted_amount_cents=("amount_cents", "sum"),
            recovered_amount_cents=("recovered_amount_cents", "sum"),
            outstanding_balance_cents=("outstanding_balance_cents", "first"),
            successes=("success", "sum"),
        )
        .reset_index()
    )
    invalid = (
        plans.count_variants.ne(1)
        | plans.attempts.ne(plans.declared_count)
        | plans.unique_indices.ne(plans.attempts)
        | plans.first_index.ne(1)
        | plans.last_index.ne(plans.declared_count)
    )
    failure_rows(
        audit,
        "installment_group_coherence",
        plans,
        invalid,
        "Loan-days with inconsistent count, repeated/missing indices or incomplete groups.",
    )
    failure_rows(
        audit,
        "loan_day_balance_limit",
        plans,
        plans.attempted_amount_cents.gt(plans.outstanding_balance_cents),
        "Loan-day total attempted amount exceeds the dated balance.",
    )
    plans["equal_amounts"] = plans.min_amount_cents.eq(plans.max_amount_cents)
    plans["all_success"] = plans.successes.eq(plans.attempts)
    plans["all_failed"] = plans.successes.eq(0)
    patterns = (
        plans.groupby(["declared_count", "provider_pattern"], observed=True)
        .agg(
            loan_days=("loan_id", "size"),
            loans=("loan_id", "nunique"),
            all_success_plans=("all_success", "sum"),
            all_failed_plans=("all_failed", "sum"),
            equal_amount_plans=("equal_amounts", "sum"),
        )
        .reset_index()
    )
    patterns["all_success_fraction"] = patterns.all_success_plans / patterns.loan_days
    patterns["all_failed_fraction"] = patterns.all_failed_plans / patterns.loan_days
    audit.table("plan_patterns", patterns)
    return plans


def portfolio_and_balances(
    frames: dict[str, pd.DataFrame], plans: pd.DataFrame, attempts: pd.DataFrame, audit: Audit
) -> None:
    snapshots = frames["loan_snapshots"].sort_values(["loan_id", "snapshot_date"]).copy()
    observed = snapshots.merge(
        plans[
            [
                "loan_id",
                "attempt_date",
                "attempts",
                "recovered_amount_cents",
                "attempted_amount_cents",
            ]
        ],
        left_on=["loan_id", "snapshot_date"],
        right_on=["loan_id", "attempt_date"],
        how="left",
        validate="one_to_one",
    )
    for col in ["attempts", "recovered_amount_cents", "attempted_amount_cents"]:
        observed[col] = observed[col].fillna(0).astype("int64")
    observed["observed_attempt"] = observed.attempts.gt(0)
    observed["dpd_band"] = pd.cut(
        observed.days_past_due.astype("int64"),
        [-1, 5, 15, 30, 60, 90, np.inf],
        labels=DPD_LABELS,
    )
    activity = (
        observed.groupby(["client_id", "dpd_band"], observed=True)
        .agg(
            observed_loan_days=("loan_id", "size"),
            distinct_loans=("loan_id", "nunique"),
            attempted_loan_days=("observed_attempt", "sum"),
        )
        .reset_index()
    )
    activity["no_observed_attempt_days"] = (
        activity.observed_loan_days - activity.attempted_loan_days
    )
    activity["attempted_day_fraction"] = activity.attempted_loan_days / activity.observed_loan_days
    audit.table("loan_day_activity_summary", activity)
    grouped = observed.groupby("loan_id", sort=False)
    observed["next_snapshot_date"] = grouped.snapshot_date.shift(-1)
    observed["next_balance_cents"] = grouped.outstanding_balance_cents.shift(-1)
    observed["next_dpd"] = grouped.days_past_due.shift(-1)
    observed["gap_days"] = (observed.next_snapshot_date - observed.snapshot_date).dt.days.astype(
        "Int64"
    )
    transitions = observed.loc[observed.next_snapshot_date.notna()].copy()
    transitions["balance_change_cents"] = (
        transitions.next_balance_cents - transitions.outstanding_balance_cents
    )
    transitions["collection_residual_cents"] = (
        transitions.balance_change_cents + transitions.recovered_amount_cents
    ).where(transitions.gap_days.eq(1))
    transitions["dpd_change_minus_elapsed_days"] = (
        transitions.next_dpd - transitions.days_past_due - transitions.gap_days
    )
    transitions["transition_type"] = np.select(
        [
            transitions.gap_days.gt(1).to_numpy(dtype=bool),
            transitions.collection_residual_cents.eq(0).fillna(False).to_numpy(dtype=bool),
            transitions.collection_residual_cents.lt(0).fillna(False).to_numpy(dtype=bool),
        ],
        [
            "gap_between_observations",
            "adjacent_matches_observed_collections",
            "adjacent_unexplained_decrease",
        ],
        default="adjacent_unexplained_increase",
    )
    balance_summary = (
        transitions.groupby(["client_id", "transition_type"], observed=True)
        .agg(
            transitions=("loan_id", "size"),
            loans=("loan_id", "nunique"),
            balance_change_cents=("balance_change_cents", "sum"),
            collection_residual_cents=("collection_residual_cents", lambda s: s.sum(min_count=1)),
        )
        .reset_index()
    )
    audit.table("balance_transition_summary", balance_summary)
    example_cols = [
        "loan_id",
        "client_id",
        "snapshot_date",
        "next_snapshot_date",
        "gap_days",
        "outstanding_balance_cents",
        "next_balance_cents",
        "recovered_amount_cents",
        "collection_residual_cents",
        "transition_type",
        "dpd_change_minus_elapsed_days",
    ]
    audit.table(
        "balance_transition_examples",
        transitions.groupby(
            "transition_type",
            observed=True,
            group_keys=False,
        ).head(audit.settings.example_limit)[example_cols],
    )
    gaps = transitions.loc[transitions.gap_days.gt(1), example_cols]
    audit.table("snapshot_gap_events", gaps)
    residual_mask = transitions.gap_days.eq(1) & transitions.collection_residual_cents.ne(0)
    audit.check(
        "adjacent_balance_residual",
        "warning",
        int(residual_mask.sum()),
        "Adjacent loan-day transitions not explained by the observed current-day collections.",
        transitions.loc[residual_mask, example_cols],
    )
    unusual_dpd = transitions.dpd_change_minus_elapsed_days.ne(0)
    audit.check(
        "dpd_progression_review",
        "warning",
        int(unusual_dpd.sum()),
        "Transitions where DPD change differs from elapsed days; review, do not auto-correct.",
        transitions.loc[unusual_dpd, example_cols],
    )
    audit.metrics["nonzero_adjacent_residuals"] = int(residual_mask.sum())
    audit.metrics["snapshot_gaps"] = len(gaps)
    loans = (
        observed.groupby("loan_id", observed=True)
        .agg(
            client_id=("client_id", "first"),
            first_observed=("snapshot_date", "min"),
            last_observed=("snapshot_date", "max"),
            observed_days=("snapshot_date", "size"),
            attempted_days=("observed_attempt", "sum"),
        )
        .reset_index()
    )
    gap_counts = gaps.groupby("loan_id").size()
    loans["gaps_between_observations"] = loans.loan_id.map(gap_counts).fillna(0).astype("int64")
    loans["observed_at_extract_end"] = loans.last_observed.eq(snapshots.snapshot_date.max())
    audit.table("loan_observability", loans)
    prior_date = grouped.snapshot_date.shift(1)
    observed["first_observation"] = prior_date.isna()
    observed["return_after_gap"] = (observed.snapshot_date - prior_date).dt.days.gt(1)
    daily = (
        observed.groupby("snapshot_date", observed=True)
        .agg(
            observed_loans=("loan_id", "size"),
            attempted_loan_days=("observed_attempt", "sum"),
            outstanding_balance_cents=("outstanding_balance_cents", "sum"),
            first_observations=("first_observation", "sum"),
            returns_after_gap=("return_after_gap", "sum"),
        )
        .reset_index()
    )
    # Retain a full calendar; absent portfolio days are not silently imputed as zero loans.
    calendar = pd.DataFrame(
        {
            "snapshot_date": pd.date_range(
                min(snapshots.snapshot_date.min(), attempts.attempt_date.min()),
                max(snapshots.snapshot_date.max(), attempts.attempt_date.max()),
                freq="D",
            )
        }
    )
    daily = calendar.merge(daily, on="snapshot_date", how="left", validate="one_to_one")
    daily["portfolio_day_observed"] = daily.observed_loans.notna()
    daily["no_observed_attempt_days"] = daily.observed_loans - daily.attempted_loan_days
    daily["attempted_day_fraction"] = daily.attempted_loan_days / daily.observed_loans
    by_date = summarize_attempts(attempts, ["attempt_date"]).rename(
        columns={"attempt_date": "snapshot_date"}
    )
    daily = daily.merge(by_date, on="snapshot_date", how="left", validate="one_to_one")
    audit.table("daily_portfolio", daily)
    audit.check(
        "missing_calendar_portfolio_days",
        "warning",
        int((~daily.portfolio_day_observed).sum()),
        "Calendar dates without a snapshot; not automatically zero active loans.",
    )
    variable_columns = [
        "original_amount_cents",
        "payroll_cycle",
        "debtor_bank",
        "customer_tenure_months",
    ]
    variation = snapshots.groupby("loan_id")[variable_columns].nunique().gt(1).sum()
    audit.table(
        "attribute_variation",
        variation.rename("loans_with_multiple_values").rename_axis("attribute").reset_index(),
    )


def economic_tables(frames: dict[str, pd.DataFrame], attempts: pd.DataFrame, audit: Audit) -> None:
    clients = frames["clients"].sort_values("client_id")
    lender = summarize_attempts(attempts, ["client_id"]).set_index("client_id")
    lender = lender.reindex(clients.client_id)
    rate_cols = ["success_rate", "amount_recovery_rate"]
    for col in lender.columns.difference(rate_cols):
        lender[col] = lender[col].fillna(0).astype("int64")
    lender = lender.reset_index()
    audit.table("economics_by_lender", lender)
    weighted = lender.copy()
    # Distinct loans are also a loan-sample total estimate. Rates remain unchanged.
    for col in weighted.columns.difference(["client_id"] + rate_cols):
        weighted[col] = weighted[col] * audit.settings.sample_weight
    weighted["scope"] = "sampling_weighted_observed_period_full_book_estimate"
    audit.table("economics_weighted_full_book", weighted)
    # Exact commitment allocation in cents; these scenarios do not forecast future revenue.
    snapshots = frames["loan_snapshots"]
    opening = snapshots.loc[snapshots.snapshot_date.eq(snapshots.snapshot_date.min())]
    opening_balances = opening.groupby("client_id").outstanding_balance_cents.sum()
    scenarios = {
        "equal_lender_share": [1] * len(clients),
        "opening_observed_balance_share": [
            int(opening_balances.get(c, 0)) for c in clients.client_id
        ],
        "observed_a_usage_share_ex_post": lender.a_attempts.astype(int).tolist(),
    }
    coverage_rows = []
    total_expected_coverage = (
        int(lender.observed_contribution_units.sum()) * audit.settings.sample_weight
        - audit.settings.a_upfront_cents * 100
    )
    for name, weights in scenarios.items():
        allocated = allocate_cents(audit.settings.a_upfront_cents, weights)
        total = sum(weights)
        for i, row in lender.iterrows():
            contribution = int(row.observed_contribution_units) * audit.settings.sample_weight
            coverage_rows.append(
                {
                    "allocation_scenario": name,
                    "client_id": row.client_id,
                    "allocation_weight": weights[i] / total if total else 1 / len(weights),
                    "equal_fallback_used": total == 0,
                    "weighted_observed_contribution_units": contribution,
                    "allocated_full_a_commitment_cents": allocated[i],
                    "commitment_coverage_at_observed_cutoff_units": contribution
                    - allocated[i] * 100,
                    "is_completed_contract_margin": False,
                }
            )
        assert (
            sum(
                r["commitment_coverage_at_observed_cutoff_units"]
                for r in coverage_rows
                if r["allocation_scenario"] == name
            )
            == total_expected_coverage
        )
    audit.table("commitment_coverage_by_lender", pd.DataFrame(coverage_rows))

    def total_units(col: str) -> int:
        return int(attempts[col].sum())

    na, nb = total_units("a_attempts"), total_units("b_attempts")
    audit.metrics.update(
        {
            "attempt_start": str(attempts.attempt_date.min().date()),
            "attempt_end": str(attempts.attempt_date.max().date()),
            "sample_commission_revenue": format_fixed(total_units("commission_revenue_units"), 4),
            "sample_recorded_fees": format_fixed(total_units("recorded_fees_units"), 4),
            "sample_usage_margin": format_fixed(total_units("usage_margin_units"), 4),
            "sample_observed_contribution": format_fixed(
                total_units("observed_contribution_units"), 4
            ),
            "sample_a_attempts": na,
            "sample_b_attempts": nb,
            "nonpositive_usage_margin_lenders": int(lender.usage_margin_units.le(0).sum()),
            "weighted_a_utilization_fraction": na
            * audit.settings.sample_weight
            / audit.settings.a_allowance,
            "weighted_observed_commitment_coverage": format_fixed(total_expected_coverage, 4),
            "realized_full_window_margin": None,
            "may_june_forecast": None,
        }
    )
    totals = []
    for scope, factor in [
        ("observed_loan_sample", 1),
        ("weighted_full_book_estimate", audit.settings.sample_weight),
    ]:
        totals.append(
            {
                "scope": scope,
                "attempt_start": audit.metrics["attempt_start"],
                "attempt_end": audit.metrics["attempt_end"],
                "attempts": len(attempts) * factor,
                "a_attempts": na * factor,
                "b_attempts": nb * factor,
                "commission_revenue_units": total_units("commission_revenue_units") * factor,
                "recorded_fees_units": total_units("recorded_fees_units") * factor,
                "usage_margin_units": total_units("usage_margin_units") * factor,
                "observed_contribution_units": total_units("observed_contribution_units") * factor,
                "realized_full_window_margin": None,
            }
        )
    audit.table("economic_totals", pd.DataFrame(totals))
    for keys, name in [
        (["provider"], "legacy_by_provider"),
        (["dpd_band"], "legacy_by_dpd"),
        (["installment_count"], "legacy_by_installment_count"),
        (
            ["client_id", "provider", "dpd_band", "installment_count", "amount_band"],
            "legacy_segments",
        ),
    ]:
        audit.table(name, summarize_attempts(attempts, keys))
    audit.table(
        "fee_mapping",
        attempts.groupby(["provider", "fee_cents"], observed=True)
        .size()
        .rename("attempts")
        .reset_index(),
    )
    audit.table(
        "outcome_availability_boundary",
        attempts.groupby(
            ["attempt_date", "outcome_available_date_assumed"],
            observed=True,
        )
        .size()
        .rename("attempts")
        .reset_index(),
    )
    audit.check(
        "weighted_a_allowance_review",
        "warning",
        int(na * audit.settings.sample_weight > audit.settings.a_allowance),
        "Weighted observed A demand exceeds allowance; sampling estimate, not an exact full-book violation.",
    )
    # Reconcile monetary aggregations without floating-point tolerances.
    for col in [
        "commission_revenue_units",
        "recorded_fees_units",
        "usage_margin_units",
        "observed_contribution_units",
    ]:
        assert int(lender[col].sum()) == total_units(col), f"Lender reconciliation failed: {col}"


def run_analysis(settings: Settings) -> int:
    audit = Audit(settings)
    audit.metadata = {
        "created_at": datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(),
        "python": platform.python_version(),
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "sample_unit": "loan",
        "sample_weight": settings.sample_weight,
        "contract_start": settings.contract_start,
        "contract_end": settings.contract_end,
        "a_allowance_full_book": settings.a_allowance,
        "a_upfront_full_book": format_fixed(settings.a_upfront_cents, 2),
        "commission_rounding": "no per-attempt rounding; exact 0.0001 currency units",
        "example_limit": settings.example_limit,
        "inputs": {},
        "analysis_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "not_estimated": [
            "causal_provider_effects",
            "counterfactual_policy_value",
            "attainable_ceiling",
            "May-June activity",
            "sampling_confidence_intervals",
        ],
    }
    frames = parse_inputs(audit)
    if frames is None or not structural_checks(frames, audit):
        return audit.finish(complete=False)
    print("Joining dated loan states and checking installment plans...", flush=True)
    joined = join_attempts(frames, audit)
    if joined is None:
        return audit.finish(complete=False)
    plans = build_plans(joined, audit)
    print("Analyzing portfolio history, balances and observed legacy economics...", flush=True)
    portfolio_and_balances(frames, plans, joined, audit)
    economic_tables(frames, joined, audit)
    return audit.finish(complete=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data" / "raw")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="New output directory; existing directories are never overwritten.",
    )
    parser.add_argument(
        "--sample-weight", type=int, default=15, help="Loan inclusion weight (default: 15)."
    )
    parser.add_argument("--contract-start", default="2026-01-01")
    parser.add_argument("--contract-end", default="2026-06-30")
    parser.add_argument("--a-allowance", type=int, default=10_000_000)
    parser.add_argument(
        "--a-upfront", default="10000000.00", help="Full-book prepaid cost in currency units."
    )
    parser.add_argument("--example-limit", type=int, default=25)
    args = parser.parse_args(argv)
    upfront = money_to_cents(args.a_upfront)
    if (
        min(args.sample_weight, args.a_allowance, args.example_limit) <= 0
        or upfront is None
        or upfront < 0
    ):
        parser.error(
            "Weights, allowance and example limit must be positive; upfront must be valid nonnegative money."
        )
    try:
        start = pd.to_datetime(args.contract_start, format="%Y-%m-%d", errors="raise")
        end = pd.to_datetime(args.contract_end, format="%Y-%m-%d", errors="raise")
        if start > end:
            parser.error("Contract start must not exceed end.")
    except ValueError:
        parser.error("Contract dates must be valid YYYY-MM-DD.")
    stamp = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%Y%m%d_%H%M%S_%f")
    output = args.output_dir or PROJECT_ROOT / "reports" / "eda_belvo" / stamp
    settings = Settings(
        data_dir=args.data_dir.resolve(),
        output_dir=output.resolve(),
        sample_weight=args.sample_weight,
        contract_start=args.contract_start,
        contract_end=args.contract_end,
        a_allowance=args.a_allowance,
        a_upfront_cents=upfront,
        example_limit=args.example_limit,
    )
    try:
        return run_analysis(settings)
    except (OSError, ValueError, pd.errors.ParserError, AssertionError) as exc:
        print(f"EDA failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
