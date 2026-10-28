# Work log and changelog

**Date:** 2026-10-28. **Timezone:** America/Sao_Paulo (UTC−03:00).

The case recommends **6–8 hours**, not an explicit timesheet. This log adds the available timing evidence.

## Timing method

Git rows use **first-parent committer timestamps**. Start means the previous checkpoint, **not a measured task start**; gaps include possible pauses or overlapping work. Imported subtree history is counted only at integration. **N/R = not recorded**, never zero. Tool runtime is separate from development effort; total effort is unknown.

## Committed milestones

Elapsed values are **minutes:seconds between checkpoints**, grouped by task.

| Start checkpoint | End checkpoint | Elapsed (min:sec) | Context → Action → Result | Git evidence |
|---|---|---:|---|---|
| N/R | N/R | N/R | Understand → read the case/README → identify constraints. | Author's account; no reading commit. |
| N/R | 09:46:43 | N/R | Start → initialize repository → first checkpoint. | `7c7370b` |
| 09:46:43 | 10:03:15 | 16:32 | Organize → apply scaffold → Python project layout. | `cbaa860`, `5066f02` |
| 10:03:15 | 10:16:44 | 13:29 | Visualize → refine business flow and scaffold permissions → explicit operations. | `3e0f058`, `ca8eb02`, `d33e40e` |
| 10:16:44 | 10:23:11 | 06:27 | Model data → create ER diagram → relationships mapped. | `aa52c5b` |
| 10:23:11 | 10:56:46 | 33:35 | Formalize → develop docs 01–04/economic diagram → constraints and assumptions specified. | `38ea2ee` |
| 10:56:46 | 10:58:31 | 01:45 | Reuse → import EDA with subtree/squash → profiling tool available. | `d196e8a` (includes squash `0e51ede`). |

**Commit span: 71min48s (71.80 minutes)**, excluding unmeasured work before/after these commits. This is not total effort.

Reproduce the committed chronology with:

```text
git log --first-parent --reverse --date=iso-strict --format="%h %cI %s"
```

## Unreleased — working-tree tasks and execution evidence

Local tasks without new project commits; development durations are **N/R**.

| Task: Context → Action → Result | Development start | Development end | Development minutes | Evidence |
|---|---|---|---:|---|
| Resolve compatibility → isolate Python 3.12/add guarded runner → profiling works. | N/R | N/R | N/R | `conf/requirements-eda.txt`, `scripts/run_eda.ps1` |
| Validate assumptions → implement specific EDA/tests → 12 project tests pass; zero failed real-data checks. | N/R | N/R | N/R | `scripts/eda_belvo.py`, `src/belvo/data/eda.py`, `tests/test_eda_belvo.py` |
| Explain work → consolidate rationale/timeline → README and changelog. | N/R | N/R | N/R | Current documentation changes. |

| Executed analysis | Recorded start | Recorded end | Logged duration | Source / interpretation |
|---|---|---|---:|---|
| General profiling, three datasets | 11:12:07.936 | 11:12:48.745 | 0.68015 min (40.809s) | [First](reports/eda/20261028_111203_950/clients/eda_analysis.log) to [last](reports/eda/20261028_111203_950/payment_attempts/eda_analysis.log) log; excludes initial startup/install. Naive timestamps interpreted as local time. |
| Latest specific EDA | 11:28:54.445222 | N/R | N/R | [Metadata](reports/eda_belvo/20261028_112854_444227/run_metadata.json): initialization and completion status, no end timestamp. [Results](reports/eda_belvo/20261028_112854_444227/report.md). |

Do not sum runtime and development gaps as independent effort. Record future task starts/ends directly.

## Eight-stage implementation — measured local intervals, 2026-10-28 (UTC-03)

Intervals include implementation and verification; exclude commit/push overhead. These
are measured work intervals, not estimates inferred from commits.

| Stage | Start | End | Minutes | Context → Action → Result |
|---|---|---|---:|---|
| 1 | 14:09:30 | 14:14:28 | 4.97 | Resolve architecture ambiguity → validate case/reviews and specify contracts/ADRs → minimal transactional boundary and explicit assumptions. |
| 2 | 14:14:37 | 14:15:59 | 1.37 | Prevent evaluation leakage → freeze temporal/economic protocol and boundary tests → 14 tests pass, lender allocation fixed before test. |
| 3 | 14:16:09 | 14:17:42 | 1.55 | Exercise daily flow → implement cent-exact plans/quarantine/export → 18 tests pass; April 1 produces 4,640 unique loan decisions, no invalid records. |
| 4 | 14:17:52 | 14:22:08 | 4.27 | Recover safely → add atomic reservations/outbox, durable simulator and reconciliation → 26 tests pass including unknown delivery, correction and rollback. |
| 5 | 14:22:13 | 14:26:16 | 4.05 | Compare complete plans → add empirical scoring, support guards and lender-priority quota allocation → 30 tests pass; 4,640 economic decisions generated with 9,076 reserved A units. |
