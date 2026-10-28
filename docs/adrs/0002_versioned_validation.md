# ADR 0002: Versioned validation

Status: Accepted. Date: 2026-10-28.

Context: Invalid records must not block valid loans; corrected data must return automatically.

Decision: Preserve payload/content hash and validation reasons per version. Quarantine
conflicting duplicate loan-day keys. Automatically validate corrections. Before dispatch,
replace/cancel plans atomically; submitted/uncertain plans cannot create a second loan-day plan.

Alternatives: Whole-lot rejection blocks valid loans; overwrite loses audit; manual release
does not scale.

Consequences: Extra history storage; critical schema/state failures fail closed. Retention
and access controls remain production work.
