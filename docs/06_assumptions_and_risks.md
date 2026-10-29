# Assumptions, risks and validation

| Kind | Statement | Evidence / consequence / validation |
|---|---|---|
| Requirement | Decide/submit all installments on D; outcomes D+1 | [Case](provided/CHALLENGE.md); precise receipt time absent |
| Requirement | Maximize absolute margin; every lender profitable | Include allocated full prepaid expense |
| Requirement | A has 10M prepaid units expiring June 30; B costs 2 per attempt | Failures consume quota / incur fees; no refund |
| Accepted | Process received portfolios; daily reconciliation | Order-dependent quota allocation can lose global value |
| Accepted | Quarantine individual bad records; automatically revalidate corrections | Version-specific flags; no debit from invalid data |
| Accepted | Python and local transactional SQLite | Low setup cost; single writer and local-disk limitation |
| Accepted | Unknown submissions retain capacity | Idempotent simulator; no external exactly-once claim |
| Assumption | Date-only outcomes use conservative availability delay | Frozen in protocol; exclude current/future labels |
| Assumption | MVP uses at most three installments and finite amount grid | Case examples are not a hard maximum; restricted action space |
| Assumption | Weight 15 extrapolates sampled loan trajectories | Not an exact full-book constrained optimization |
| Assumption | Lender cost weights fixed before test | Same weights for all policies; sensitivity analysis |
| Risk | Provider and amount effects confounded by legacy selection | Support/calibration diagnostics; no causal uplift claim |
| Risk | Installments can compete for funds | Condition on complete plan; sum marginal expectations without assuming independence |
| Risk | Candidate actions change future balances | Primary comparison is conditional one-step replay, not a causal rollout |
| Risk | May/June absent; history left-truncated | Separate observation, scaling and projection; no six-month realized result |
| Risk | Expected profit may realize a loss | Report uncertainty and unmet lender constraints |
| Risk | Heuristic fails to find profitable allocation | Report unmet constraint, never proven infeasibility |
| Open | Cutoff, timezone, late arrivals and exact latency target | Production receipt timestamps and declared benchmark volume required |
| Open | Real provider idempotency and reconciliation contract | Verify before real debits |
| Accepted | Monotonic source revisions per lender/day | Corrected source contents need a higher revision; late retries cannot overwrite newer state |
| Open | Obtain upstream source ordering metadata | CLI accepts a revision; the case CSVs do not provide one |
| Open | Operational outcome feedback into training/budgets | Local outcomes can be recorded; offline fitting uses supplied CSV history |
| Proposal | Shared production DB, receiver and execution worker | Describe deployment only; not infrastructure delivered |

Schema/state failures fail the job before sending; isolated invalid rows do not. Missing
identities remain quarantined source records rather than invented loans. Invalid corrections
cancel unsent plans; submitted/uncertain plans remain reconcilable and cannot be replaced.

The case specifies submission on D and results on D+1; precise receipt times are absent.
Use the portable checked-in specification. Competition between collection agencies is a
discussion hypothesis, not a case requirement.

The response model omits absolute amount, calendar and observed history. Stratified
calibration and a known-truth stress expose consequential model risk without identifying
a causal bias correction. Demand-aware allocation and runtime outcome feedback remain
open; six-month profitability and an achievable sequential ceiling are unestablished.
