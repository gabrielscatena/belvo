# Architecture and implementation boundary

The [specification](provided/CHALLENGE.md) is authoritative. Requirements, accepted
implementation choices, assumptions and production proposals are distinguished here
and in [risks](06_assumptions_and_risks.md). No real provider integration is included.

## Component contracts

| Component | Input | Responsibility / output |
|---|---|---|
| Ingestion | Dated full portfolio and lender caps | Preserve version; quarantine invalid/conflicting records with reasons |
| History | Attempts available before decision | Exclude pending/future labels; produce auditable point-in-time history |
| Planner | Valid balance, cap, DPD | Finite complete plans and no-attempt; positive cents, sum within balance |
| Selector | Plans, policy, shared quota, lender budget | One active loan-day decision with reason; report unmet financial constraints |
| Store | Versions, decisions, reservations | Atomically persist plan, A reservation and durable send intents |
| Simulated executor | Send intents with stable identities | Submit/reconcile, preserving ambiguous delivery state |
| Reconciler | Acknowledgements and D+1 outcomes | Transfer reserved to consumed once; report usage and financial margins |
| Offline evaluator | Frozen splits and legacy loan states | Observed legacy versus estimated candidate, support, uncertainty and scoped ceiling |

The motor ends at a persisted decision and intent. The executor owns submission, not
optimization. Process portfolios on arrival without waiting for all lenders; daily
reconciliation/reporting is separate. All installments are intended for D; missing D
does not authorize automatic D+1 dispatch. Exact operating cutoff remains open.

## Accepted MVP persistence

Python modules and CLI run locally. SQLite from the standard library is the single
transactional authority. BEGIN IMMEDIATE, unique keys, WAL and bounded lock waits
serialize writers. Unavailable state fails closed before submission. This trades
distributed throughput for simple recovery and low setup cost.

`free = contracted - consumed - reserved >= 0`. Confirmed submission transfers reserved
to consumed; failure never refunds it. Unknown delivery retains its reservation until
reconciliation. Only proven non-submission permits release. No network operation is
inside a database transaction. External exactly-once effects require provider cooperation;
the local simulator supports idempotent identities but proves no real-provider guarantee.

Corrected records may replace an entirely unsent plan atomically. Submitted or uncertain
attempts protect the loan-day from replacement. Invalid corrections cancel unsent intents.
All versions and validation flags remain audit evidence. Source payloads are never overwritten.

## Decision strategy and trade-offs

Start with a deterministic feasibility baseline. Add economic scoring only after documenting
its estimator and limitations. Arrival-order quota allocation is a heuristic, not a global
optimum. Lender expected profit includes a fixed share of prepaid A; positive scores alone
do not establish profitability. No-attempt does not erase fixed cost. Opportunity cost is
only a decision penalty, never another accounting charge or a duplicate scarcity penalty.

## Production proposal (not deployed)

A receiver would durably register arrivals and enqueue work. Stateless planners would use
a shared transactional database; separate outbox workers and a reconciler would communicate
with providers. Replace SQLite when multi-host operation is required. Add authentication,
encryption, backups, retention and alerts. No broker or production service is necessary for
the local slice. Measure whole-portfolio latency and contention before choosing worker count
or numeric SLO; seconds is a desired target, not a demonstrated guarantee.

Roll out through replay, shadow, capped lender pilot and staged expansion. Rollback stops
new intents, preserves reservations and reconciles pending delivery. Monitor quarantine,
duplicate identities, quota invariants, ambiguity, calibration and per-lender margins.

See [ADRs](adrs/README.md) and [milestones](implementation_progress.md). Cutoff, receipt
guarantees, production infrastructure and real provider semantics remain open.
