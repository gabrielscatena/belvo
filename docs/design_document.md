# Smart Collections Engine

Senior Applied Data Scientist | Design and prototype | 29 October 2026

## 1. Decision, information and economics

For each loan in a received dated portfolio, choose no attempt or a complete same-day
plan: installment count, amounts and provider per installment. Submit on D; results arrive
D+1. Receipt time is unspecified. The date-only prototype conservatively uses labels
through D-2. Process portfolios on arrival; reconcile and report daily.

The business objective is absolute six-month net margin with positive expected margin
for every lender. Commission equals recovered amount times the DPD rate on submission:
15%, 20%, 25%, 30%, 40% or 50% across the specified bands. B costs 2 per attempt, including
failures. A has 10 million prepaid units expiring June 30, with no refund or rollover.
Contract margin subtracts the entire commitment once plus B fees. Consuming A creates no
second cash charge; an opportunity penalty belongs in selection, not again in expenses.

## 2. Restricted decision prototype

Enumerate no-attempt and 1-3 equal or cent-balanced installments at 25/50/75/100% of the
feasible total. Positive integer-cent amounts respect each lender cap and sum to no more
than the dated balance. Three installments is an MVP restriction, not a case requirement.
Pure-provider plans restrict an action space with almost no mixed-plan observations.

Smoothed empirical probabilities use lender, provider, DPD band, installment count and
coarse plan fraction. Require 100 cell attempts and use 100 pseudo-observations. Score
expected commission minus B cost, with a one-standard-error downside stress. This is not
a confidence guarantee. Summing marginal expectations requires no installment independence;
interference and alternative outcomes remain unidentified. Absolute amount, calendar and
observed history are omitted predictors: new diagnostics expose material model risk.

Selection begins with B/no-attempt choices and lender-priority A upgrades. Choose independent
per-loan score maxima if jointly feasible; otherwise improve choices using incremental A
capacity while preserving satisfied lender requirements. The scarcity heuristic proves no
global optimum or infeasibility. The lender check includes allocated full commitment,
known contribution and pending B fees; unknown recovery/future contribution are zero in
a stringent scenario. Report unmet requirements. Not charging cannot remove fixed cost.

<!-- PAGEBREAK -->

## 3. Architecture, state and operations

<!-- ARCHITECTURE -->

| Component | Responsibility and output |
|---|---|
| Receiver / validator | Preserve source versions and cap context; isolate invalid records; continue valid loans |
| Planner / scorer | Available information, cent-exact plans, supported estimates and reproducible reasons |
| Transactional store | One active loan-day decision, shared quota reservation, history and durable send intent |
| Simulated executor | Stable attempt identities, durable acknowledgement and uncertain-delivery reconciliation |

Python modules and a CLI run locally. SQLite is the smallest transactional authority
for this slice: unique keys, WAL, bounded waits and serialized writes. Score before locking;
select, reserve capacity and persist decisions/outbox atomically. Provider calls stay outside
the transaction. Unavailable state fails closed before submission. Runtime policy identity
includes selector version; immutable model hashes identify the fitted probabilities.

Capacity invariant: free = contracted - consumed - reserved, always nonnegative. Submission
moves reserved to consumed once; failed payment does not refund capacity. Unknown delivery
retains its reservation. Release only after proven non-submission. The durable simulator
fences terminal rejection against late senders; an empty lookup is not proof. Real provider
exactly-once behavior is not demonstrated.

Automatically revalidate corrections and atomically replace entirely unsent plans. Invalid
corrections or disappearance from a complete lender portfolio cancel unsent intents. Preserve
submitted/uncertain effects. Source revisions increase per lender/day; reject stale revisions
and conflicting reuse. Retain original payloads, cap context, decisions and model artifacts.
Separate policies/backward-date experiments use separate stores.

## 4. Production proposal and rollout

A receiver would enqueue portfolios; stateless planners, an outbox worker and a reconciler
would share a managed transactional database. SQLite is a local MVP choice. Add access
control, encryption, backups, retention, dead-letter handling and alerts. Persisted execution
outcomes must feed training and lender budgets; this feedback is not implemented. Arrival
order sacrifices global allocation; demand forecasts/opportunity pricing remain future work.

Progress through replay, shadow, capped randomized lender pilot and gradual rollout. Verify
provider idempotency and receipt timestamps first. Stop new intents on quota inconsistency,
reconciliation failures or lender losses; preserve pending reservations during rollback.
Cutoff and numeric latency SLO remain open. For 4,640 loans, three local runs measure
27.52s cold input/validation/fit plus planning/commit and 3.08s warm planning/commit median.
Dispatch/export/network are excluded; these timings are not a production percentile SLO.

<!-- PAGEBREAK -->

## 5. Findings and trust

Observed April legacy margin is **80,758.24** under the declared cost convention.
**Improved business margin is not established.** The prototype is operationally testable;
its response model does not justify the large candidate estimate or an achievable ceiling.

January-February train, March validates, and final probabilities use labels through March
30. April engineering corrections are disclosed post-inspection replays, not untouched
testing. No response-model hyperparameters were retuned. The 1-in-15 sample uses
floor(10M/15) A units and 10M/15 upfront; scaling by 15 is only a point extrapolation.

| April net margin, same population / fixed lender weights | Currency units |
|---|---:|
| Observed legacy | 80,758.24 |
| Same-model estimated legacy | 107,146.78 |
| Corrected-selector candidate scenario | 1,233,760.38 |
| Candidate downside stress score | 724,993.83 |
| Relaxed same-model ceiling | 1,257,322.98 |

All rows charge 30/181 of the same commitment and reconcile by lender. C11 is positive
in estimated April but negative in full-upfront Jan-Apr coverage. Missing May-June demand,
response uncertainty and cost allocation prevent a six-month profitability conclusion.
Alternative fixed lender weights and nominal usage diagnostics are published separately.

April has 140,710 loan-days across 6,233 loans. Candidate volume is 333,851 attempts versus
93,772 legacy; only 5.96% of loan-day actions match. Expanded amount/calendar cells contain
no training observations for 91,149 candidate attempts. On observed legacy actions, ordinary-
calendar-day commission is overestimated 27.6%; amount-bucket errors vary substantially.
A known-truth amount/calendar stress with provider-neutral response gives **2.43x** candidate
commission optimism. This is a structural counterexample, not Belvo's measured bias factor.

Twenty training-loan-cluster refits put fixed-action candidate margin at empirical
2.5-97.5 percentiles of 1.06M-1.52M. Tails are coarse. This excludes model misspecification,
confounding, policy reselection, future balances and demand. Neither refits nor the downside
stress establish a credible business-gain range. The relaxed fitted-model ceiling drops
capacity coupling/lender constraints; a realistic sequential six-month ceiling is unidentified.

April consumes 291,698 A units, leaving 141,410 after prior use. Every tested May-June
fixed-action continuation exceeds that remainder; infeasible margins remain null. Daily
selection enforces capacity but does not establish optimal contract-horizon allocation.
A scarcity price is configurable and zero in the frozen evaluation; forcing zero unused
units at expiry is not an optimality criterion.

Fresh locked setup, 105 tests, lint and dependency checks pass. Tests cover accounting,
selection, time availability, concurrency, recovery, uncertain submission, corrections and
expiry. **Recommendation: shadow only.** Validate response features and overlap on new
prospective evidence, close runtime feedback and test a capped randomized pilot before
claiming causal improvement. Reproduce via README; evidence: docs/09_results.md,
reports/evaluation/selector_v3, calibration_v1, refit_v1 and reports/validation/benchmark_v3.json.
