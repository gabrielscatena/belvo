# Smart Collections Engine

Senior Applied Data Scientist | Design and prototype | 28 October 2026

## 1. Decision and economic objective

For each loan in a received dated portfolio, choose no attempt or a complete same-day
plan: installment amounts, count and provider for every installment. Outcomes arrive D+1;
the brief does not specify receipt time. The date-only prototype conservatively uses
outcomes through D-2. Portfolios are processed on arrival; daily reconciliation is separate.

Maximize absolute six-month net margin, with positive expected margin for every lender.
Commission is recovered amount times the DPD rate on submission day: 15%, 20%, 25%, 30%,
40%, 50% for the specified age bands. B costs 2 per attempt, including failures. A has
10 million prepaid transactions expiring June 30, paid upfront without refund or rollover.
Contract margin subtracts the entire A commitment once and all B fees; A use does not
create a second charge. Prepaid capacity is a hard constraint. Opportunity cost is
configurable but zero in the frozen run; estimating a nonzero price remains future work.

## 2. Restricted, explainable prototype

Generate no-attempt and 1-3 equal or cent-balanced installments at 25/50/75/100% of the
feasible total. Every amount is a positive integer number of cents, at most the lender cap;
their sum cannot exceed the dated balance. Three installments is an MVP bound, not a case
requirement. Pure-provider plans restrict an action space with almost no mixed-plan history.

Smoothed empirical probabilities condition on lender, provider, DPD band, installment count
and coarse total-plan fraction. Use 100 pseudo-observations and require 100 cell attempts
for selectable plans. Score expected commission minus B cost, with a one-standard-error
downside stress. This stress is not a confidence guarantee. Summing marginal expectations
does not require independent installments; interference remains unidentified by this data.

Start with best B/no-attempt choices; allocate A upgrades by gain per unit, prioritizing
lender deficits. Recompute feasible alternatives against locked capacity. The heuristic
does not guarantee a global optimum or certify infeasibility. The lender check includes
allocated fixed cost, known contribution and known pending B fees; pending recovery and
future contribution are zero in the explicit stringent default scenario. Report unmet
requirements. No-attempt cannot remove fixed cost or guarantee a profitable contract.

<!-- PAGEBREAK -->

## 3. Minimal architecture and reliable state

| Component | Responsibility and output |
|---|---|
| Receiver / validator | Preserve source versions and cap context; quarantine invalid records, continue valid loans |
| Planner / scorer | Point-in-time information, cent-exact plans, supported estimates and reproducible reasons |
| Transactional store | One active loan-day decision, shared quota reservation, decision history and outbox |
| Simulated executor | Stable attempt identities, durable acknowledgement, uncertain delivery and reconciliation |
| Offline reporting | Legacy and estimated candidate money; operational outcome feedback is future work |

Python modules and a CLI run locally. SQLite supplies the smallest transactional authority
needed for this slice: unique keys, WAL, bounded waits and a serialized write transaction.
Score candidates before locking; reserve quota, decision and send intents atomically. No
provider call is inside the transaction. Unavailable state fails closed before submission.

Capacity invariant: free = contracted - consumed - reserved, always nonnegative. Confirmed
submission transfers reserved to consumed once; failure does not refund it. Unknown delivery
retains its reservation. Release only after proven non-submission. The separate durable
simulator supports idempotent identities and fences definitively rejected sends against late
arrival; real provider exactly-once behavior is not proved. An empty query is not proof.

Automatically revalidate corrections. Replace entirely unsent plans atomically; cancel
remaining unsent intents after invalid corrections or disappearance from a complete lender
portfolio. Preserve uncertain/submitted effects and prevent another loan-day plan. Reappearance
is allowed when prior intents were proven unsent. Reject backward-date use of live state;
use separate stores for experiments. Source revisions increase per lender/day: reject stale
updates and conflicting reuse of a revision; genuine reappearance needs a new revision.
Original payloads, decisions and immutable hash-addressed models remain auditable.

## 4. Production proposal and rollout

A durable receiver would enqueue received portfolios; stateless planners, an outbox worker
and a reconciler would use a shared managed transactional database. SQLite is a local MVP
choice, not a multi-host deployment. Add authentication, encryption, retention, backups,
dead-letter handling and alerts. Arrival-order allocation sacrifices global optimization;
opportunity pricing and future demand forecasts would be approximations, not guarantees.

Roll out through replay, shadow, a capped lender pilot and gradual expansion. Stop new
intents on duplicate keys, quota inconsistency, reconciliation failures or lender losses;
retain pending reservations during rollback. Verify provider idempotency and actual receipt
timestamps first. Exact cutoff and numeric latency SLO remain open. The desired latency
is seconds, measured locally rather than promised for production.

<!-- PAGEBREAK -->

## 5. Evidence, economics and trust

Train on January-February, inspect March validation, freeze the policy before April.
The final estimator refits through March 30; April labels never train it. Full engineering
regression replays are disclosed; no hyperparameters were retuned on April. Data contains
a 1-in-15 loan sample; use floor(10M/15) capacity and 10M/15 upfront as a sample scenario.
Hold lender allocation equal and fixed across policies. Scale flows by 15 only as full-book
point extrapolation. May-June is unobserved; history is left-truncated.

| April net margin under allocated monthly prepaid-cost convention - sampled portfolio | Amount |
|---|---:|
| Observed legacy | 80,758.24 |
| Same-model estimated legacy | 107,146.78 |
| Estimated candidate | 1,228,967.16 |
| Conservative candidate stress | 713,158.07 |
| Relaxed supported-plan model ceiling | 1,257,322.98 |

These figures allocate 30/181 of upfront cost. Lender amounts reconcile with totals.
All estimated April lender margins are positive, but C11 remains negative under full
upfront Jan-Apr coverage. Six-month lender profitability is therefore unestablished.
The candidate's gap to the relaxed model ceiling is 28,355.82; this is not proof of an
achievable sequential ceiling. The relaxation ignores quota coupling and lender constraints.

April evaluation has 140,710 loan-days and 6,233 loans. Outcomes of alternative actions
are not observed. Only 5.59% of candidate loan-day actions exactly match legacy; coarse
bin counts are not causal support. Monetary calibration error is material. The large
same-model uplift is 1,121,820.38; it is not demonstrated business value. Candidate volume
is 318,115 attempts versus 93,772 legacy (3.39x), adding extrapolation and interference risk.
Loan-cluster bootstrap intervals
condition on the fitted model and exclude response bias and future-state uncertainty.

Candidate A use is 275,962 units, leaving 157,146 after prior usage. Every tested May-June
continuation exceeds that remainder; infeasible projection margins are null. Daily execution
can fall back to B/no-attempt, but future economic allocation needs refinement. Reusing legacy
future balances permits conditional one-step comparison, not a causal sequential simulation.

Operational tests cover concurrent writers/dispatch, restart, unknown sends, corrections,
expiry and unavailable state. For 4,640 loans: measured cold preparation plus planning/commit
25.39s; warm planning/commit median 2.93s. Three local runs are not a percentile SLO; dispatch
and network are excluded. A clean environment reproduces the package and tests.

**Recommendation: shadow only.** Resolve lender-level calibration and action support, collect
arrival timestamps, and run a capped randomized pilot before claiming causal uplift or live
profitability. Sources and reproduction: README, docs/provided/CHALLENGE.md, docs/07_evaluation_protocol.md,
reports/evaluation/verified_v2 and reports/validation/benchmark_v2.json. Full ADRs and risks are in docs.
