# ADR 0003: Minimal transactional persistence

Status: Accepted. Date: 2026-10-28.

Context: Concurrent jobs must not reserve the same capacity; interrupted work must recover.

Decision: Python and SQLite standard library. One transaction persists source versions,
active loan-day decisions, A reservations and outbox. Stable attempt identities survive retry.
A separate durable simulator registry models provider acknowledgements. No network inside
the store transaction.

Alternatives: CSV cannot atomically coordinate shared state; production server DB increases
setup without being needed for this local slice.

Consequences: Single writer, bounded lock timeout and local disk. No multi-host or real-provider
exactly-once guarantee. Unknown delivery retains capacity. Production needs shared transactional DB.
