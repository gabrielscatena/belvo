# Architecture decisions

Implementation choices under the authorized eight-stage plan; technologies were not
already selected during the voice discussion.

| ADR | Status | Decision |
|---|---|---|
| [0001](0001_processing_boundary.md) | Accepted | Arrival processing; separate execution/reconciliation |
| [0002](0002_versioned_validation.md) | Accepted | Versioned quarantine and automatic validation |
| [0003](0003_local_transactional_store.md) | Accepted | Python/SQLite, atomic reservation and outbox |
| [0004](0004_economic_policy.md) | Accepted for prototype | Empirical plan probabilities and constrained greedy selection |
| [0005](0005_source_order_and_model_evidence.md) | Accepted for prototype | Ordered source corrections, isolated history and immutable model evidence |
| [0006](0006_review_corrections.md) | Accepted for prototype | Versioned selection correction and post-review economic diagnostics |
