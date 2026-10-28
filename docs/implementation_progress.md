# Implementation milestones

Each stage is validated, committed and pushed separately. CHANGELOG records measured
implementation intervals, excluding commit/push overhead. The on-screen checklist is
updated after successful synchronization.

1. Architecture and ADRs: contracts formalized; Python/SQLite decision justified.
2. Protocol and economic configuration: frozen v1, conservative D−2 history, temporal holdout and equal lender cost weights.
3. Local pipeline: cent-exact plans, versioned quarantine, deterministic baseline and exports.
4. State, reservations and recovery: transactional SQLite, stable intents, simulated executor and reconciliation.
5. Economic selection: supported empirical plan scoring, shared-quota heuristic, explicit lender constraints and provenance.
6. Candidate / legacy evaluation: pending.
7. Concurrency, failure and performance: pending.
8. Final delivery: pending.
