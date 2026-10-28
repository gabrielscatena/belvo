# Operational verification

The project tests exercise independent-process capacity contention, concurrent dispatch,
duplicate loan-day requests, timeout before/after provider acceptance, crash after acceptance,
restart and repeated reconciliation, failed-payment quota consumption, invalid/corrected
records, lender-cap corrections, portfolio disappearance/reappearance, expiry, state outage,
policy separation and transactional rollback. Missing identities cannot collide with real
loan IDs. Versions include snapshot and cap context, not just the snapshot payload.

Full-portfolio correction is explicitly scoped by lender. Missing loans cancel only unsent
intents; uncertain/submitted effects remain. `--client` narrows a complete lender portfolio;
default CLI treats the supplied daily file as complete for all clients in clients.csv.
Incremental row updates must not be labeled full portfolios. State rejects backward business
dates; historical experiments use separate databases. Decision events, receipt timestamps,
original payloads and stable attempt identities provide auditability.

Economic scoring is prepared before taking the write lock; quota allocation and durable
intents still commit atomically. SQLite serializes writers; a lock timeout fails safely,
not with a second authority or a guessed quota. External acceptance is simulated with a
separate durable registry; absence is definitive only in this simulator. A real provider
must offer authoritative reconciliation before any reservation is released.

[Measured benchmark](../reports/validation/benchmark.json): three local runs on 4,640
April 1 loans, at most 25 candidate plans each. Report cold CSV/validation/fitting separately
from planning plus durable commit, and lock-held transaction time separately. Dispatch,
network, export and production arrival/concurrency are outside this measurement. Two warm
runs are descriptive, not a percentile estimate or a contractual latency guarantee.

Reproduce with `python -m belvo.evaluation.benchmark` and `python -m pytest -q`.
Financial evidence and unresolved deployment blockers are in [results](09_results.md).

Recorded result: **44 tests pass**. Whole-portfolio cold preparation/fit plus planning/commit:
**8.95 seconds**; warm planning/commit median **2.52 seconds**. Transaction intervals:
0.86–0.90 seconds. Three runs produced the same decision hash and nonnegative free capacity.
