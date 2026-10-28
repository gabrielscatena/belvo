# ADR 0001: Processing boundary

Status: Accepted. Date: 2026-10-28.

Context: Daily portfolios, submission D, outcomes D+1; user prioritizes processing on arrival.

Decision: Local motor validates/plans received portfolios; store commits intents; separate
simulated executor submits. Reconciliation and reporting run daily. Do not wait for other lenders.

Alternatives: Global daily batch improves joint allocation but delays arrivals; streaming
infrastructure adds unjustified scope for a laptop prototype.

Consequences: Transactional capacity is safe but arrival order is not globally optimal.
Exact cutoff and numeric latency target remain open.
