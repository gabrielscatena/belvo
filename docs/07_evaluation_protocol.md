# Frozen evaluation protocol, version 2026-10-28-v1

Configuration: [protocol.json](../conf/protocol.json). Freeze before candidate fitting.
Changes after looking at April must be disclosed and invalidate its untouched-test status.

## Information and partitions

Training: January–February. Validation: March, for diagnostic calibration and any policy
selection. Final test: April, evaluated only after fixing the policy. Outcome dates alone
do not reveal intraday availability. Conservative default: at decision D, only attempts
through D−2 have usable outcomes. This deliberately withholds potentially available D−1
labels. Production must use actual `available_at <= cutoff`, not infer it from submission.
Balance/DPD and lender cap for D are known on receipt. Historical data is left-truncated.

Training labels must also be available at the fitting cutoff: fitting for March 1 uses
attempts through February 27. The frozen final model can refit through March 30 for April 1,
after validation choices are fixed. No April labels train the model or tune hyperparameters;
already available prior-April outcomes can enter the daily lender budget at D-2.

Audit disclosure: earlier EDA inspected all months, so this is a temporal holdout, not a
blind preregistered experiment. Engineering regression replays were repeated. Final review
corrected known pending-B fees in the lender check; no probability model was retuned,
and published monetary totals and daily unmet-constraint counts are unchanged. The simulator
was also hardened against reconciliation racing a late sender. These are disclosed fixes,
not additional independent test evidence.

Delivery corrections add ordered source revisions, point-in-time history quarantine and
immutable model provenance v2. The response estimator and frozen policy parameters are
unchanged. A new verification checkpoint preserves the original frozen_v1 artifacts;
model identifiers change because all fitting inputs/configuration are now covered.

Observed attempt/success counts: January 96,181/862; February 86,768/829;
March 93,380/895; April 93,772/856. These support a temporal evaluation but sparse
subgroups still require backoff and uncertainty reporting.

## Economic scope

Primary evaluation: April conditional one-step decisions on the same observed dated loan
states as legacy. Do not claim a sequential counterfactual rollout: a different recovery
policy would change later balances and portfolio membership. Every policy uses the same
population, commission schedule, fixed lender allocation, capacity convention and horizon.

Sample demonstration uses floor(10M/15) A units and upfront 10M/15 currency units. This is
a scaled scenario, not the actual contract or an exact solution for the unsampled book.
Full-book point estimates multiply sample flows by 15, retaining the full 10M commitment.
State must account for observed prior A use before April. Conservative reservations cover
uncertain submissions separately; no assumption that success is required to consume A.

Equal weights across the 12 contracted lenders fix each share of A before test. Equal
allocation is chosen for auditability, independent of candidate behavior and test outcomes.
Sensitivity: training-attempt weights, demand levels and quota scales; weights remain
identical across policies within each comparison. No refunds from choosing no-attempt.

Contract margin = commission − B fees − full allocated A upfront. Usage margin subtracting
historical per-attempt fees is a diagnostic, not another contract expense. A opportunity
cost is only a decision penalty. January–April contribution less full upfront is a coverage
diagnostic; May–June and final six-month profitability are unobserved and scenario-based.
For monthly comparison, show both contribution and a declared time allocation of upfront;
do not call a prorated month the final contract result.

## Candidate policy and acceptance

Finite plans: no-attempt or 1–3 installments; total collection target 25/50/75/100% of
min(balance, count × lender cap), rounded down to integer cents and distributed within
caps. Pure-provider plans initially have substantially more historical support than mixed
plans. Mixed providers are a later extension; provider per installment remains explicit.
No fabricated independence between simultaneous debits. Select whole plans with shared quota.

Report observed legacy money separately from model-estimated legacy/candidate, support
and calibration. Probability baselines must state observational confounding and backoff.
Uncertainty includes lender/loan dependence; resample loans, not independent installments.
Expected per-lender contract constraints use declared past/pending/future assumptions;
unsatisfied constraints block a production recommendation, not honest prototype reporting.

Ceiling: declare horizon, restricted plans, model and relaxations. A relaxed one-step upper
bound is not an attainable six-month profit guarantee. Heuristic failure is not proof of
infeasibility. No policy is approved for live use from offline projected uplift alone.

Acceptance: exact feasible cents/caps; no future-label use; capacity never negative; no
duplicate loan-day submission; margins reconcile by lender; identical financial convention;
all assumptions and failed lender constraints visible; clean executable reproduction.

## Post-inspection horizon and calendar sensitivities

The original protocol/results remain frozen. Additional April diagnostics vary cumulative
A release through June 30 (0.75/1/1.25 times an even release) and recent calendar admission.
Both candidate and filtered logged legacy get identical release/admission rules, with
separate consumption ledgers; whole logged plans are ranked without outcomes. Their
retained observed cash is subset accounting on fixed legacy states, not an observed or
identified counterfactual policy result. The original observed legacy benchmark remains.

Calendar admission uses only pure historical attempts available by the fitted cutoff:
at least 100 observations in at least one of the last two calendar months, separately
for each provider/date type. The cutoff month may be partial. This is a declared coverage
assumption, not a causal-support guarantee or retuned response model. Thresholds and
release rates are sensitivities; none was selected as an optimal policy using April.
