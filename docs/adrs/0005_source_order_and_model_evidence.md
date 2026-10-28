# ADR 0005: Ordered corrections and immutable model evidence

Status: Accepted for the local prototype. Date: 2026-10-28.

Context: A content hash detects equality, not recency. A delayed retry must not undo
a zero-balance correction or a portfolio withdrawal. Outcome IDs alone also fail to
identify a model when its explanatory inputs or parameters change.

Decision: Accept a positive upstream `source_revision` per lender/business day.
The first receipt may omit it (initial revision 1); subsequent changed contents must
provide a larger revision. Equal revisions permit only equal source contents, ignoring
CSV row order. Older revisions fail closed. Source heads, withdrawals, decisions and
reservations commit in the same transaction. Legitimate same-day reappearance requires
a new source revision, even if its contents match an earlier portfolio. Production must
obtain this sequence from the sender; local receipt time cannot establish source order.
This is an integration contract chosen for the MVP, not a field supplied by the case.

Historical attempts and snapshots are filtered before D before conversion/join checks.
Bad historical loan-day groups are excluded with source fields and reasons preserved;
affected current loans are quarantined, while unaffected loans continue. Incomplete lender
history makes its profitability check unavailable rather than falsely satisfied. No valid
training history produces explicit no-attempt decisions, never unsupported fallback debits.
Offline evaluation remains strict about invalid history. Schema/state failures still stop
the job. Pending outcomes do not enter training or their validation before availability.

Model identity covers all fitting features/outcomes, fitting cutoff, complete fitted
state, configuration and artifact-format version. Decisions reference that identity.
The complete artifact is persisted with the decisions in SQLite and exported under
`<state-stem>.models/<model_hash>.json`. Publishing is atomic; different contents cannot
replace an existing artifact. Restoring a model verifies its hash. Refit clears old cells.
Unsent decisions also track their model/budget basis: corrected history automatically
refreshes them, and loss of valid training cancels pending debits. Submitted/uncertain
effects remain protected. Source ordering and decision basis serve different purposes.

Alternatives: Automatically numbering arrivals would legitimize late retries. Blocking
all repeated content would also reject genuine reappearance. Overwriting one model file
would lose evidence needed to reproduce earlier decisions.

Consequences: Corrections need source ordering metadata. Old simulator stores without
source heads are deliberately rejected; preserve them and use a new simulation store.
No destructive migration is inferred. Model provenance format v2 changes identifiers,
not fitted probabilities, policy parameters or the frozen financial comparison.

Boundary: Outcomes can be recorded locally, but a full operational feedback loop into
training/budgets remains future work. The offline prototype uses supplied CSV history.
