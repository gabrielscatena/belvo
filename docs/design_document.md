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

| Evidence, sampled portfolio | Finding |
|---|---:|
| Observed April legacy net margin | 80,758.24 |
| Demonstrated improvement / sequential ceiling | Not established |
| April A use / remaining April 1 capacity | 67.35% |
| April share of remaining contract days | 30 / 91 |
| Ordinary-day B attempts / supporting history | 36,568 / 665, January only |

Observed margin charges 30/181 of upfront and reconciles by lender. Candidate use anticipates
capacity relative to an even schedule. Identical fixed costs cancel in the policy difference;
future opportunity cost is unmeasured. C11's full-upfront Jan-Apr coverage is negative;
May-June demand and cost attribution prevent a final lender-profitability conclusion.

April has 140,710 loan-days across 6,233 loans. Candidate volume is 333,851 attempts versus
93,772 legacy; only 5.96% of loan-day actions match. Expanded amount/calendar cells contain
no training observations for 91,149 candidate attempts. On observed legacy actions, ordinary-
calendar-day commission is overestimated 27.6%; amount-bucket errors vary substantially.
A known-truth amount/calendar stress with provider-neutral response gives **2.43x** candidate
commission optimism. This is a structural counterexample, not Belvo's measured bias factor.

Twenty training-cluster refits quantify conditional parameter variation only; detailed
percentiles and model-only money estimates stay in the results appendix. They exclude
misspecification, confounding, policy reselection, future balances and demand. The fitted-model
relaxation is not a realistic achievable ceiling; the sequential contract ceiling is unidentified.

New sensitivities release capacity cumulatively through June at 0.75/1/1.25 times an even
schedule, independently for both policies. Neutral release admits at most 142,782 A units
in April. A recent-calendar gate excludes January-only coverage. Filtered logged actions
are hypothetical replay, not observed legacy. These comparisons test chosen budgets,
not optimal pacing or a contract forecast.
Capacity remains protected between days; forcing zero unused units at expiry proves no optimum.
Neutral pacing plus recent admission gives negative estimated April margins for C07 and C11.

Fresh locked setup, 119 tests, lint and dependency checks pass. Tests cover accounting,
selection, time availability, concurrency, recovery, uncertain submission, corrections and
expiry. **Recommendation: shadow only.** Validate response features and overlap on new
prospective evidence, close runtime feedback and test a capped randomized pilot before
claiming causal improvement. Reproduce via README; evidence: docs/09_results.md,
reports/evaluation/horizon_v1, calibration_v2 and reports/validation/benchmark_v3.json.
