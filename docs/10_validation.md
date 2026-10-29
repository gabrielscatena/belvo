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
separate durable registry. Reconciliation atomically records either acceptance or a terminal
rejection that fences late senders; absence alone is insufficient, even with consistent reads.
A retry after definitive rejection gets a new generation identity. Ordinary retries of an
active attempt keep their identity. A real provider without definitive rejection/cancellation
must keep unknown reservations rather than infer non-submission from an empty query.
The engine binds the simulator registry identity; replacing a lost registry cannot silently
turn earlier accepted/unknown submissions into negative acknowledgements.

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

Final delivery verification: **53 tests pass in a fresh isolated environment**, including
the late-sender/reconciliation race and replaced simulator registry. Model JSON, lender
table and all six reported economic/capacity totals reproduce exactly. The final pending-B
fee diagnostic correction changes no published daily unmet-lender counts. See
[clean environment evidence](../reports/validation/clean_environment.json).


## Delivery correction checkpoint

The original 44/53-test and performance figures above are historical checkpoints.
Current isolated verification passes **71 tests**, including real CLI regressions for
stale portfolios after a zero-balance correction, current/future invalid records,
whole-plan quarantine, unavailable labels, concurrent source revisions, immutable model
publication/restoration, and rejection of unordered legacy simulator state. Ruff and
compatibility checks for all 14 locked packages also pass.

Source ordering and model evidence are specified in ADR 0005. The response estimator,
action grid and policy hyperparameters remain frozen. Model provenance format v2 changes
identifiers; the original frozen_v1 checkpoint remains preserved. Current reproduction and
[delivery evidence](../reports/validation/delivery_review.json) preserve the original artifacts.
The [current benchmark](../reports/validation/benchmark_v2.json) measures 25.39s cold and
2.93s warm median, including ordered source registration and immutable model persistence.
This cold run is slower than the original checkpoint; do not present the old 8.95s as current.
Cold preparation rechecks the supplied CSV history; warm planning reuses a prepared model.
These are three local samples and exclude dispatch/export, with no percentile SLO claim.

## External-review correction checkpoint - 2026-10-29

Current isolated verification: **105 tests passed in 26.94s**, Ruff clean, and `pip check`
reports no dependency conflicts. A NEW Python 3.12.14 virtual environment installed the
locked requirements plus `.[mvp]` via `make setup`; `make test` and `make lint` then passed
with that same interpreter. Linux CI remains a separate remote check after push.

New tests include independent exact-money offline evaluation (commission 65, B fees 4,
fixed cost 1, candidate margin 60), failed-attempt fees, lender reconciliation, selector
slack/scarcity behavior, calibration availability, synthetic truth isolation and refit
point-estimate reconstruction. No raw provided or synthetic CSVs are committed.

The [current benchmark](../reports/validation/benchmark_v3.json) uses selector
`economic_heuristic_v2`: 4,640 loans, cold 27.52s, warm planning/commit median 3.08s,
transaction intervals 1.30-1.49s. Three independent stores produce the same decision hash
and nonnegative quota. Input/validation/fitting is 23.85s of cold execution. Dispatch,
export, network and production arrival patterns remain outside scope.

[Current evaluation](../reports/evaluation/selector_v3/summary.json) preserves the original
fitted response model exactly while changing selection; original checkpoints remain.
The parameter-refit point reproduces current headline margins within 0.000001. Synthetic
stress and expanded real-data calibration expose unresolved response inadequacy; test
success is engineering evidence, not evidence of causal economic gain. See ADR 0006 and
the [claim-by-claim review](11_external_review.md).

## Follow-up horizon and admission verification - 2026-10-29

Current full suite: **119 tests passed in 26.19s** through the Makefile; Ruff and dependency
checks pass. Six focused horizon regressions also pass after sharing immutable daily
scoring across variants. Tests cover integer cumulative release, carryover/expiry, complete
status-independent logged-plan admission, exact money, failed B fees and prior overage.

[Eight real-data scenarios](../reports/evaluation/horizon_v1/summary.json) completed in
275.75s. All 240 daily rows respect independent candidate/legacy release and physical
capacity invariants. The 96 lender/scenario rows reconcile to their scenario totals.
The unrestricted control reproduces selector_v3 with the identical model and source hashes;
all earlier checkpoints remain unchanged. Recent admission eliminates ordinary-day B in
all gated scenarios. Twenty-one primary/ADR documents have no broken local links; all
three final PDF pages were rendered and visually checked.

Neutral release plus admission has negative estimated April margins for C07/C11. These
are reported outcomes, not a failed test hidden by changing the rule. Detailed checks are
in [follow-up evidence](../reports/validation/followup_review_v1.json). No scenario proves
causal improvement, optimal pacing or six-month profitability; runtime defaults are unchanged.
