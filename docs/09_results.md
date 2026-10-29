# Results and trust assessment

**Observed April legacy margin: 80,758.24. Improved business margin is not established.**
The local prototype produces feasible plans and coherent accounts, but its response model
is inadequate evidence for the large estimated gain. Shadow operation is recommended.

## Scope and revision

April contains 140,710 loan-days across 6,233 loans. Alternative outcomes are unobserved.
The response model uses labels through March 30 under D-2 availability; it was not retuned.
[Current output](../reports/evaluation/selector_v3/summary.json) uses selector
`economic_heuristic_v2`, correcting slack-capacity plan ordering. This is a **post-April-
inspection engineering replay**, not an independent test. Original [frozen_v1](../reports/evaluation/frozen_v1/results.md)
and [verified_v2](../reports/evaluation/verified_v2/results.md) remain preserved.

## Money under one declared convention

| April net margin, sampled portfolio | Original selector | Corrected selector |
|---|---:|---:|
| Observed legacy | 80,758.24 | 80,758.24 |
| Same-model estimated legacy | 107,146.78 | 107,146.78 |
| Candidate model scenario | 1,228,967.16 | 1,233,760.38 |
| Candidate downside stress | 713,158.07 | 724,993.83 |
| Relaxed same-model ceiling | 1,257,322.98 | 1,257,322.98 |

Every row uses the same population, April states, equal fixed lender weights and 30/181
of the commitment. [Lender totals](../reports/evaluation/selector_v3/per_client.csv) reconcile.
Multiplying by 15 gives only a sample-based full-book point extrapolation, not a constrained
full-book solution. Candidate minus estimated legacy is 1,126,613.59, not causal uplift.

Estimated legacy margin exceeds observation by 26,388.54 (32.7% of observed net margin).
On **commission revenue**, the same error is 12.0%; these percentages use different
denominators. A downside stress does not correct model misspecification.

## What the response model misses

[Stratified calibration](../reports/evaluation/calibration_v1/calibration_slices.csv)
reports March/April errors by provider, absolute amount, calendar, lender and available
observed history. Amount boundaries use pre-March data. Previous submissions are known
before D; failures respect D-2. Observed history is left-truncated, not lifetime history.
Calendar categories are proxies, not verified paydays. These features diagnose errors;
they have not been added to the estimator.

In April, ordinary-calendar-day commission is overestimated by 27.6%; month-end commission
is underestimated by 19.2%. Amount-bucket estimated/observed revenue ratios range 0.83-1.54.
B appears on 19 historical dates, including January 3, 6 and 9; the assertion that it occurs
only on the 1st/15th/16th/month-end is false. Calendar associations do not identify provider effects.

Candidate volume is 333,851 attempts versus 93,772 legacy (3.56x); only 5.96% of loan-day
actions match. [Expanded support](../reports/evaluation/calibration_v1/candidate_support.csv)
finds 91,149 candidate attempts with zero exact joint-cell observations and 150,640 below
100 observations, despite passing coarse model support. Zero counts warn of sparsity;
positive counts do not establish exchangeability or causal identification.

The [known-truth stress](../reports/validation/synthetic_stress_v1.json) varies success with
amount/calendar, makes providers equally effective and uses B only on calendar peaks in
legacy. Candidate commission is estimated at 2,653,794.82 versus true expectation
1,091,705.23 (**2.43x**). True expected candidate net margin is 741,549.99 versus legacy
108,220.30: the candidate still improves over this sparse legacy, while overstating its gain.
Synthetic bias does not quantify bias in Belvo's data. The synthetic oracle conditions on
frozen states and relaxes lender requirements; it is not a sequential contract ceiling.

## Uncertainty and ceiling

The original 400-loan-cluster resamples hold predictions fixed. Additional
[training-cluster refits](../reports/evaluation/refit_v1/summary.json) fit 20 models using
8,073 training-loan clusters, then rescore **fixed** candidate and legacy actions.

| Fixed-action estimate | Point | Empirical 2.5-97.5 percentiles |
|---|---:|---:|
| Candidate margin | 1,233,760.38 | 1,059,899.44-1,517,899.70 |
| Estimated legacy margin | 107,146.78 | 95,305.97-120,331.62 |
| Difference | 1,126,613.59 | 949,131.86-1,410,063.31 |

Twenty repetitions give coarse tails. Up to 2.712% of frozen candidate plans lose cell
support in a refit and remain scored, as disclosed. These intervals exclude structural
bias, confounding, policy reselection, future demand and counterfactual balances. They
are not business confidence intervals or a credible range for true uplift.

The relaxed fitted-model ceiling is 1,257,322.98, a 23,562.60 gap from the candidate.
It maximizes mean score on the restricted supported grid while dropping quota coupling
and lender constraints. This algebraic comparison is not a realistic achievable ceiling.
An observed-action hindsight bound has a different estimand and need not bracket unseen
candidate actions. A credible sequential six-month ceiling remains unidentified.

## Prepayment, lender profitability and continuation

A uses 291,698 units, leaving 141,410 after 233,558 prior observed submissions. April use
averages 9,723/day versus 4,759/day if the April 1 remainder were spread across 91 days.
Even pacing is a scenario, not an optimality criterion. All tested May-June fixed-action
continuations exceed capacity; their margins stay null. Demand-aware allocation is not implemented.

[Economic views](../reports/evaluation/economic_views_v1/README.md) distinguish:

- Equal fixed allocation and pretest-A-usage **fixed weights**, identical across policies.
- Own-policy usage weights as a sensitivity, not a fixed-weight comparison.
- Nominal per-use A pricing as a diagnostic, with unused commitment reconciled separately.
- Fixed-action opportunity penalties at lambda 0/0.25/0.5/1/2: accounting margin stays unchanged.
  This is score sensitivity, not reoptimization or a calibrated scarcity price.

C11 estimated April margin is +12,981.42 under equal allocation, +19,486.20 with fixed
pretest-use weights, and -7,432.48 under nominal per-use pricing. Full-upfront Jan-Apr
coverage remains negative. Lender conclusions depend on convention, response and missing
May-June demand: **six-month profitability is unproven**, not proved impossible. A's
purchase is sunk; reserving capacity may carry opportunity cost. Charging that penalty
again as a contract expense would double count.

## Decision

Submit an operational prototype with an **uncertain economic result**. Before rollout,
validate a response specification using amount/calendar/history on new or prospectively
held-out evidence, connect operational outcomes to budgets/training, test demand-aware
allocation and run a capped randomized pilot. Do not label a post-April augmented model
comparison as untouched testing or as a calibrated bias bound.
