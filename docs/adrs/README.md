# Architecture decisions

Implementation choices under the authorized eight-stage plan; technologies were not
already selected during the voice discussion.

| ADR | Status | Decision |
|---|---|---|
| [0001](0001_processing_boundary.md) | Accepted | Arrival processing; separate execution/reconciliation |
| [0002](0002_versioned_validation.md) | Accepted | Versioned quarantine and automatic validation |
| [0003](0003_local_transactional_store.md) | Accepted | Python/SQLite, atomic reservation and outbox |
