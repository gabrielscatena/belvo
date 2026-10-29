# Smart Collections Engine

Senior Applied Data Scientist take-home: a local collection engine, transactional execution simulator and offline economic evaluation.

**Finding:** April legacy net margin is **80,758.24** under the sample/monthly cost convention. The prototype generates feasible, auditable plans, but **improvement and six-month lender profitability are not demonstrated**. A known-truth stress test exposes response-model bias; candidate estimates are conditional scenarios, not deployment evidence.

Start with the [three-page design](output/pdf/design_document.pdf), [results](docs/09_results.md) and [review findings](docs/11_external_review.md). The [case specification](docs/provided/CHALLENGE.md) defines the submission requirements.

## Run

Use **Python 3.12**. Place the supplied `clients.csv`, `loan_snapshots.csv` and `payment_attempts.csv` in `data/raw/` (Git ignores them). Run from the repository root, stopping on any failure.

PowerShell:

```powershell
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r conf/requirements-mvp.lock -e ".[mvp]"
& .\.venv\Scripts\python.exe -m belvo.pipelines.persistent --date 2026-04-01 --policy economic --state artifacts/runtime/review_v3.sqlite --provider-state artifacts/runtime/provider_v3.sqlite
& .\.venv\Scripts\python.exe -m belvo.evaluation.offline
& .\.venv\Scripts\python.exe -m pytest -q --basetemp tests/.pytest_tmp
& .\.venv\Scripts\python.exe -m ruff check .
```

Bash:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
make setup
python -m belvo.pipelines.persistent --date 2026-04-01 --policy economic --state artifacts/runtime/review_v3.sqlite --provider-state artifacts/runtime/provider_v3.sqlite
python -m belvo.evaluation.offline
make test lint
```

The daily command exports one decision/status per received loan to `reports/pipeline/<run>/`: installments, cents, providers, reason, provenance and unmet lender constraints. Invalid records produce no debit. Add `--execute` for durable **simulated** dispatch and `--reconcile` for unknown submissions; no external provider is contacted. Offline evaluation takes several minutes and writes a new timestamped directory.

Use separate state for each policy/version or backward-date experiment. Retries retain source revision and contents; authoritative same-day corrections increase `--source-revision` per lender/day. `--client C01` scopes a complete portfolio. Preserve earlier state and outputs. Diagnostic commands and recovery: [runbook](docs/08_runbook.md).

## Findings

The original [frozen evaluation](reports/evaluation/frozen_v1/results.md) and [verified reproduction](reports/evaluation/verified_v2/results.md) remain intact. New evaluations are disclosed post-inspection sensitivities with the same fitted response model, not new untouched tests.

| Evidence, sampled portfolio | Finding |
|---|---:|
| Observed April legacy net margin | 80,758.24 |
| Demonstrated candidate improvement | Not established |
| April A use / April 1 remaining capacity | 291,698 / 433,108 = 67.35% |
| April days / remaining contract days | 30 / 91 |
| B attempts on ordinary calendar days | 36,568 |
| Historical B observations on those date types | 665, all in January |

The observed margin subtracts 30/181 of A's upfront commitment with equal fixed lender weights. Monthly comparisons do not establish contract-horizon value: the candidate spends 67% of the remaining capacity in 33% of the remaining days. The same fixed expense cancels in a policy difference; future opportunity cost remains unmeasured. C11's full-upfront Jan-Apr coverage is negative, without proving final six-month infeasibility.

Three checks explain why the apparent gain is not a business forecast:

- **Model adequacy:** [real-data calibration](reports/evaluation/calibration_v1/calibration_slices.csv) overestimates commission on April ordinary calendar days by 27.6%; amount-bucket errors are uneven. The estimator omits absolute amount, calendar and observed loan history as predictors.
- **Action support:** only 5.96% of candidate loan-day actions exactly match legacy. Of 333,851 candidate attempts, 91,149 have zero expanded joint-cell observations. A nonzero calendar count concealed January-only B coverage; [revised diagnostics](reports/evaluation/calibration_v2/candidate_support.csv) distinguish any-history counts from recent monthly support.
- **Known truth:** [synthetic stress](reports/validation/synthetic_stress_v1.json) makes providers equally effective while success varies with amount/calendar. Estimated candidate commission is **2.43 times** true expected commission. This demonstrates a failure mode, not Belvo's bias factor. The candidate still beats the sparse synthetic legacy under that generator.

[Horizon sensitivities](reports/evaluation/horizon_v1/summary.json) compare unrestricted capacity with cumulative daily budgets at 0.75/1/1.25 times even release through June 30, with and without recent-calendar admission. Both policies receive the same schedule in separate quota ledgers. Filtering logged legacy actions creates a hypothetical replay, never a replacement for observed legacy. These are April diagnostics, not six-month forecasts.

Pacing alone shifts more attempts into unsupported B calendar categories; combining it with recent admission materially reduces the model estimate. **C07 and C11 become negative in estimated April margin under even release plus admission.** No variant establishes the business objective or is selected for production.

Conditional money estimates, refit percentiles and the algebraic model bound remain in [results](docs/09_results.md) for audit. None supplies a credible causal gain range or realistic sequential ceiling. Contract-wide capacity is enforced cumulatively; optimal pacing and operational learning/budget feedback remain open. [Economic views](reports/evaluation/economic_views_v1/README.md) separate cost allocations and opportunity penalties.

## Architecture and verification

Receiver/validation → planner/scorer → SQLite decisions, quota and outbox → durable simulated executor. Offline fitting/reporting reads supplied CSV history. Python and SQLite keep the MVP small; [architecture](docs/05_architecture.md), [ADRs](docs/adrs/README.md) and [risks](docs/06_assumptions_and_risks.md) describe boundaries.

Selection, reservations and send intents commit atomically. Stable identities prevent duplicate simulated effects. Failed payments consume A; unknown delivery retains reservations until authoritative reconciliation. Corrections are automatically revalidated; submitted/uncertain effects stay protected. Immutable source versions and model hashes explain each decision.

**119 tests pass** in a newly installed Python 3.12 environment through the corrected Makefile; Ruff and dependency checks pass. Tests cover money, selection, availability, concurrent reservations/dispatch, recovery, duplicates, corrections and expiry. [Validation](docs/10_validation.md) separates current evidence from historical checkpoints. For 4,640 loans: **27.52s cold** and **3.08s warm planning/commit median**; dispatch/export/network are excluded. Three local runs are not a production SLO.

Recommendation: shadow only, then lender-level calibration/support work and a capped randomized pilot before a live improvement claim.

## Rationale — Context, Action, Result

| Step | Context → Action → Result |
|---|---|
| Understand | Read case/data README → define decision, D/D+1 and sample/contract boundaries. |
| Visualize | Create Mermaid business, entity and economic diagrams → expose flow and constraints. |
| Formalize | Write docs 01-04 → state variables, economics, assumptions and open questions. |
| Profile | Import existing [EDA tool](https://github.com/gabrielscatena/EDA) with **Git subtree / squash** → profile all three datasets under Python 3.12. |
| Validate | Add case-specific EDA → check keys, joins, caps, balances and lender economics. |
| Implement | Record ADRs/protocol → build decisions, transactional state and economic comparison. |
| Challenge | Reproduce external probes → fix selector/setup; add calibration, truth stress, refits and economic views; retain unresolved limits. |

Initial EDA: 12 lenders, 10,714 loans, 561,659 snapshots, 370,101 attempts. [EDA evidence](reports/eda_belvo/20261028_112854_444227/report.md) separates usage diagnostics from contract margin. AI tools assisted documentation, code and verification. Reused code stays in `tools/eda`; project code is in `src/belvo`. [CHANGELOG](CHANGELOG.md) records checkpoints without treating commit gaps as measured active effort.
