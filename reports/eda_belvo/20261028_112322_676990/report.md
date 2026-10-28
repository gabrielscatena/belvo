# Belvo challenge-specific EDA

Analysis completed: **True**. Failed validation checks: **0**.

## Scope and reproducibility

- Inputs were read without modification, deduplication, clipping or imputation.
- File SHA-256 hashes, versions and settings are in `run_metadata.json`.
- Monetary input checks use exact cents. Commission and margin use integer units
  of 0.0001 currency units; commission is not rounded per attempt.
- Rates are descriptive fractions; provider differences are not causal effects.
- Counts in validation_checks.csv refer to the entity described by each check.
- Examples are bounded; affected counts refer to all detected cases.

## Validation findings

| Check | Severity | Status | Affected |
|---|---|---|---:|
| All implemented checks | - | pass | 0 |

## Observed legacy economics

- Observed attempt dates: 2026-01-01 through 2026-04-30.
- Sample commission revenue: **902448.9620**.
- Sample recorded attempt fees: **427295.0000**.
- Sample usage-priced margin diagnostic: **475153.9620**.
- Sample A / B attempts: **312,907 / 57,194**.
- Lenders with non-positive sample usage-priced diagnostic: **3**. This is not contract profitability.

The usage-priced diagnostic is commission minus recorded fees. It is not
the prepaid-contract margin: unused A capacity is not costed by usage fees.
Observed-period contribution excludes the already committed A payment and
subtracts recorded B charges; no A fee is subtracted a second time.

## Sample and contract boundary

- Loan inclusion weight: **15** (default from package README).
- A contract: **2026-01-01 to 2026-06-30**.
- Full-book A allowance: **10,000,000**.
- Full-book A upfront cost: **10000000.00**.
- Weighted observed-period A utilization estimate: **46.94%**.
- Weighted tables estimate additive full-book observed-period totals, not exact
  full-book realized values. Sampling uncertainty is not quantified here.
- Rates and individual payment amounts are not multiplied by the sample weight.
- Missing May-June activity is not forecast or fabricated by this script.
- `commitment_coverage_by_lender.csv` subtracts the entire committed A cost
  from weighted observed-period contribution under explicit allocation scenarios.
  It measures commitment coverage at the observed cutoff, not final six-month margin.
- Allocation scenarios use equal weights, opening observed portfolio balance
  shares, and ex-post A usage shares. Ex-post usage is descriptive only; it must
  not silently determine a prospective profitability constraint.
- Zero-denominator allocation scenarios fall back to equal weights.

## Balance and legacy-policy interpretation

- Adjacent-calendar-day balance residuals different from zero: **0**.
- Gaps between observed snapshots of the same loan: **1,922**.
- For adjacent days, residual = next balance - current balance + current-day
  successful collections. A nonzero residual is unexplained by these observed
  collections; it is not proof of an external payment, error, or adjustment.
- Gap transitions are separate: intervening activity is not observed for that loan.
- Loan exits at the last observed date are right-censored, not confirmed closures.
- A snapshot without an attempt means no observed attempt, not a known rejection reason.
- All-zero/all-success installment-plan frequencies are descriptive; no independence
  of installments is assumed, and provider success differences are not causal.
- History before the extract is left-truncated. The inferred next-day outcome
  availability date is not a provider arrival timestamp or a decision-cutoff guarantee.
- Legacy future snapshots already incorporate legacy collections. They are not a
  validated trajectory for an alternative multi-day policy.

## Evidence to refine docs 01-04

| Document | Evidence | Still unresolved |
|---|---|---|
| 01 Business process | daily_portfolio, loan_observability, validation_checks | Within-day cutoff, provider acceptance/idempotency guarantees |
| 02 Domain model | dataset_overview, validation_checks, balance_transition_summary | Unobserved history, external adjustments and account-level identity |
| 03 Economic model | economics_by_lender, economics_weighted_full_book, commitment_coverage_by_lender | Final contract profit, May-June, approved cost allocation |
| 04 Problem framing | legacy_segments, plan_patterns, loan_day_activity_summary | Counterfactual support, calibrated success models, dynamic transitions and optimum |

## Outputs

- [dataset_overview.csv](dataset_overview.csv)
- [plan_patterns.csv](plan_patterns.csv)
- [loan_day_activity_summary.csv](loan_day_activity_summary.csv)
- [balance_transition_summary.csv](balance_transition_summary.csv)
- [balance_transition_examples.csv](balance_transition_examples.csv)
- [snapshot_gap_events.csv](snapshot_gap_events.csv)
- [loan_observability.csv](loan_observability.csv)
- [daily_portfolio.csv](daily_portfolio.csv)
- [attribute_variation.csv](attribute_variation.csv)
- [economics_by_lender.csv](economics_by_lender.csv)
- [economics_weighted_full_book.csv](economics_weighted_full_book.csv)
- [commitment_coverage_by_lender.csv](commitment_coverage_by_lender.csv)
- [economic_totals.csv](economic_totals.csv)
- [legacy_by_provider.csv](legacy_by_provider.csv)
- [legacy_by_dpd.csv](legacy_by_dpd.csv)
- [legacy_by_installment_count.csv](legacy_by_installment_count.csv)
- [legacy_segments.csv](legacy_segments.csv)
- [fee_mapping.csv](fee_mapping.csv)
- [outcome_availability_boundary.csv](outcome_availability_boundary.csv)
- [validation_checks.csv](validation_checks.csv)

Detailed check explanations and example paths are in `validation_checks.csv`.
