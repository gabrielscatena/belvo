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

## Evidence and its limits

The original [frozen evaluation](reports/evaluation/frozen_v1/results.md) and [verified reproduction](reports/evaluation/verified_v2/results.md) remain intact. The [current replay](reports/evaluation/selector_v3/results.md) fixes selection after April inspection, with **identical fitted response probabilities**. It is an engineering revision, not a new untouched holdout.

| April net margin, sampled portfolio, same allocated prepaid expense | Currency units |
|---|---:|
| Observed legacy | 80,758.24 |
| Same-model estimated legacy | 107,146.78 |
| Candidate scenario after selector correction | 1,233,760.38 |
| Candidate downside stress score | 724,993.83 |
| Relaxed same-model ceiling | 1,257,322.98 |

All rows subtract 30/181 of the same A commitment with equal fixed lender weights. [Per-lender amounts](reports/evaluation/selector_v3/per_client.csv) reconcile. C11 is positive in this estimated April view but negative in Jan-Apr coverage with the whole commitment charged; this does not prove six-month infeasibility.

Three checks explain why the apparent gain is not a business forecast:

- **Model adequacy:** [real-data calibration](reports/evaluation/calibration_v1/calibration_slices.csv) overestimates commission on April ordinary calendar days by 27.6%; amount-bucket errors are uneven. The estimator omits absolute amount, calendar and observed loan history as predictors.
- **Action support:** only 5.96% of candidate loan-day actions exactly match legacy. Of 333,851 candidate attempts, 91,149 have zero training observations in the expanded lender/provider/plan/DPD/fraction/calendar/amount cell. Coarse support does not establish causal overlap.
- **Known truth:** [synthetic stress](reports/validation/synthetic_stress_v1.json) makes providers equally effective while success varies with amount/calendar. Estimated candidate commission is **2.43 times** true expected commission. This demonstrates a failure mode, not Belvo's bias factor. The candidate still beats the sparse synthetic legacy under that generator.

[Training-cluster refits](reports/evaluation/refit_v1/summary.json) add parameter variation: fixed-action candidate margin spans 1.06M-1.52M across empirical 2.5-97.5 percentiles. Twenty refits give coarse tails; these are not business confidence bounds and exclude structural bias, confounding and changed future balances. No causal uplift or realistic sequential ceiling is established.

A uses 291,698 April units, leaving 141,410 after prior observed consumption. Tested May-June continuations exceed that remainder; infeasible projections stay null. Daily capacity is enforced; demand-aware pacing and operational learning/budget feedback remain open. [Economic views](reports/evaluation/economic_views_v1/README.md) separate fixed-cost allocation, usage diagnostics and opportunity penalties without double counting.

## Architecture and verification

Receiver/validation → planner/scorer → SQLite decisions, quota and outbox → durable simulated executor. Offline fitting/reporting reads supplied CSV history. Python and SQLite keep the MVP small; [architecture](docs/05_architecture.md), [ADRs](docs/adrs/README.md) and [risks](docs/06_assumptions_and_risks.md) describe boundaries.

Selection, reservations and send intents commit atomically. Stable identities prevent duplicate simulated effects. Failed payments consume A; unknown delivery retains reservations until authoritative reconciliation. Corrections are automatically revalidated; submitted/uncertain effects stay protected. Immutable source versions and model hashes explain each decision.

**105 tests pass** in a newly installed Python 3.12 environment through the corrected Makefile; Ruff and dependency checks pass. Tests cover money, selection, availability, concurrent reservations/dispatch, recovery, duplicates, corrections and expiry. [Validation](docs/10_validation.md) separates current evidence from historical checkpoints. For 4,640 loans: **27.52s cold** and **3.08s warm planning/commit median**; dispatch/export/network are excluded. Three local runs are not a production SLO.

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
