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

## EDA implementation and execution evidence

These tasks are now committed (through `e0dd7dc`). Active development durations were
not recorded and remain **N/R**.

| Task: Context → Action → Result | Development start | Development end | Development minutes | Evidence |
|---|---|---|---:|---|
| Resolve compatibility → isolate Python 3.12/add guarded runner → profiling works. | N/R | N/R | N/R | `conf/requirements-eda.txt`, `scripts/run_eda.ps1` |
| Validate assumptions → implement specific EDA/tests → 12 project tests pass; zero failed real-data checks. | N/R | N/R | N/R | `scripts/eda_belvo.py`, `src/belvo/data/eda.py`, `tests/test_eda_belvo.py` |
| Explain work → consolidate rationale/timeline → README and changelog. | N/R | N/R | N/R | Historical documentation milestone, now committed. |

| Executed analysis | Recorded start | Recorded end | Logged duration | Source / interpretation |
|---|---|---|---:|---|
| General profiling, three datasets | 11:12:07.936 | 11:12:48.745 | 0.68015 min (40.809s) | [First](reports/eda/20261028_111203_950/clients/eda_analysis.log) to [last](reports/eda/20261028_111203_950/payment_attempts/eda_analysis.log) log; excludes initial startup/install. Naive timestamps interpreted as local time. |
| Latest specific EDA | 11:28:54.445222 | N/R | N/R | [Metadata](reports/eda_belvo/20261028_112854_444227/run_metadata.json): initialization and completion status, no end timestamp. [Results](reports/eda_belvo/20261028_112854_444227/report.md). |

Do not sum runtime and development gaps as independent effort. Record future task starts/ends directly.

## Eight-stage implementation — elapsed checkpoints, 2026-10-28 (UTC-03)

Stages 1-7 end at the actual first-parent commit timestamp; subsequent stages start at
that previous checkpoint. Stage 1 starts at the recorded inspection time. These intervals
include tool execution, possible pauses and synchronization overhead; **they are not
measured active development effort**. Stage 8 ends at the recorded pre-commit verification.

| Stage | Start checkpoint | End checkpoint | Elapsed minutes | Context → Action → Result |
|---|---|---|---:|---|
| 1 | 14:09:30 | 14:14:38 | 5.13 | Resolve ambiguity → validate case/reviews, specify contracts/ADRs → explicit boundary (`89195e2`). |
| 2 | 14:14:38 | 14:16:10 | 1.53 | Prevent leakage → freeze temporal/economic protocol → 14 tests pass (`d42f27a`). |
| 3 | 14:16:10 | 14:18:01 | 1.85 | Exercise daily flow → implement validation/plans/export → 18 tests pass; 4,640 unique decisions (`5abb78a`). |
| 4 | 14:18:01 | 14:22:05 | 4.07 | Recover safely → add reservations/outbox/simulator → 26 tests pass (`faefccb`). |
| 5 | 14:22:05 | 14:26:59 | 4.90 | Compare plans → add supported scoring/lender constraints → 30 tests pass (`869121a`). |
| 6 | 14:26:59 | 14:39:40 | 12.68 | Challenge claims → replay April and audit money/uncertainty → 32 tests pass, explicit blockers (`eaa2f20`). |
| 7 | 14:39:40 | 14:49:42 | 10.03 | Verify operations → exercise processes/failures/corrections and benchmark → 44 tests pass, 8.95s cold / 2.52s warm (`08939ba`). |
| 8 | 14:49:42 | 15:09:56 | 20.23 | Consolidate delivery → finalize 3-page design, pinned environment, README and recovery review → 53 tests pass; economic totals reproduce exactly, PDF/links verified. |

Final review also corrected known pending-B fees in the conservative lender check and
fenced late simulated sends during reconciliation. Full model/lender-table reproduction
and daily diagnosis reconciliation show unchanged published economic totals. Model
hyperparameters were not retuned. Temporal holdout reuse and prior all-month EDA are
disclosed in the evaluation protocol; these replays are not independent experiments.

Delivery portability follow-up: mark PDF files as binary so Git cannot translate their
line endings on checkout. The committed PDF matches the rendered original byte-for-byte
and has three readable pages. No engine or economic result changed.

## CI portability fix

Linux Ruff reported EXE001 because `scripts/eda_belvo.py` had a shebang but Git mode
100644. Remove the unnecessary shebang: documented usage already invokes Python
explicitly. Ruff, the EDA CLI help command and all 53 tests pass locally. The Linux
workflow is checked separately after pushing; Windows lint alone is not CI evidence.


## Delivery review corrections - 2026-10-28 (UTC-03)

The attached review's figures were confirmed. No response model or frozen policy was retuned.
The first correction's active start was not recorded. Later intervals below are elapsed
commit/verification checkpoints, not measured active effort.

| Start checkpoint | End checkpoint | Elapsed minutes | Context -> Action -> Result | Evidence |
|---|---|---:|---|---|
| N/R | 16:03:49 | N/R | Unsafe retries/history -> add ordered revisions, isolated point-in-time validation and immutable models -> 70 tests, Linux CI passed. | `7e20d2f` |
| 16:03:49 | 16:12:24 | 8.58 | Corrected training -> refresh unsent model/budget-dependent decisions and cancel unsupported pending debits -> 71 tests, Linux CI passed. | `470ffc2` |
| 16:12:24 | 16:17:24 | 5.01 | Verify delivery -> reproduce April, real-day replay, model restoration, benchmark and 3-page design -> unchanged financial tables, explicit limitations. | Pre-commit verification; reports/validation/delivery_review.json |

Current benchmark: 25.39s cold, 2.93s warm planning/commit median, 4,640 loans.
The original frozen_v1 artifacts and original benchmark are preserved. Current model
provenance v2 and results are in verified_v2; fitted cells/probabilities are unchanged.
The cold measurement is slower than the original checkpoint and is not hidden by using
its old number. No production latency SLO or causal uplift is claimed.

## External review implementation - 2026-10-29 (UTC-03)

Elapsed checkpoints below include verification and tools; they are not measured active
work. Initial active start was not recorded. Original evaluation evidence is preserved.

| Stage | Start checkpoint | End checkpoint | Elapsed minutes | Context -> Action -> Result |
|---|---|---|---:|---|
| 1 - functional corrections | N/R | 07:57:16 | N/R | Slack-capacity plan ordering/setup failures -> versioned selector improvements and locked Makefile -> 15 new selection regressions; fresh setup/test/lint pass. |
| 2 - economic diagnostics | 07:57:16 | 07:57:56 | 0.68 | Unreliable economic evidence -> add exact-money tests, calendar/amount/history support, synthetic truth, training refits and cost views -> reproduced revised April with unchanged response model; causal gain remains unproven. |
