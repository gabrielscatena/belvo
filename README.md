# Smart Collections Engine

Senior Applied Data Scientist take-home. A local decision engine maximizes estimated absolute collection margin under installment caps and shared prepaid capacity, with explicit lender profitability diagnostics.

**Delivery:** working prototype, offline evaluation, operational tests and a [three-page design](output/pdf/design_document.pdf) ([editable source](docs/design_document.md)). **Live rollout is not approved:** estimated gains are observational, C11 fails full-cost Jan-Apr coverage, and May-June demand remains unresolved.

## Run the prototype

Use **Python 3.12**. Put the provided `clients.csv`, `loan_snapshots.csv` and `payment_attempts.csv` in `data/raw/` (excluded from Git). From the repository root, run each command after the previous one succeeds:

```powershell
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r conf/requirements-mvp.lock -e ".[mvp]"

# Daily economic decisions; simulated state, no external API calls
& .\.venv\Scripts\python.exe -m belvo.pipelines.persistent --date 2026-04-01 --policy economic --state artifacts/runtime/review_economic.sqlite --provider-state artifacts/runtime/review_provider.sqlite

# Frozen temporal offline comparison (several minutes)
& .\.venv\Scripts\python.exe -m belvo.evaluation.offline

# Invariants, concurrency, recovery and code checks
& .\.venv\Scripts\python.exe -m pytest -q --basetemp tests/.pytest_tmp
& .\.venv\Scripts\python.exe -m ruff check .
```

The daily command exports one decision/status per received loan, installment amounts in cents, providers, reason, economic support and lender constraints to `reports/pipeline/<run>/`. Original versions and cap context are retained. Invalid loans produce no new debit. A complete corrected portfolio can additionally report withdrawn loans. `--client C01` limits the full-portfolio scope. Add `--execute` for the **durable simulator**, or `--reconcile` to resolve its unknown submissions. Real provider integration is deliberately absent.

Reusing state is an idempotent replay, not a new experiment. Different policies or backward-date experiments require separate state paths. State is initialized with observed historical A submissions before the requested day. See [runbook](docs/08_runbook.md) for baseline, EDA, benchmark and recovery details.

## Results and how much to trust them

[Full results](docs/09_results.md), [per-lender money](reports/evaluation/frozen_v1/per_client.csv), [calibration and uncertainty](reports/evaluation/frozen_v1/summary.json), [sensitivity](reports/evaluation/frozen_v1/sensitivities.csv).

| April net margin, sample currency units | Amount |
|---|---:|
| Observed legacy | 80,758.24 |
| Same-model estimated legacy | 107,146.78 |
| Estimated candidate | 1,228,967.16 |
| Conservative candidate stress | 713,158.07 |
| Relaxed supported-plan model ceiling | 1,257,322.98 |

Identical April states, lender weights and **30/181 of prepaid cost** are used for every row. The candidate consumes 275,962 A units, leaving 157,146 after prior use. Lender margins reconcile with the total. Positive estimated April margins do not establish six-month profitability: **C11 remains negative when the whole commitment is charged in Jan-Apr coverage**.

The large estimated uplift is **not established business value**. Only 5.59% of candidate loan-day actions exactly match legacy; coarse support cells do not identify causal provider/amount effects. The model already overstates observed legacy margin by 26,388.54. The candidate is the best feasible restricted policy found; the 28,355.82 gap to a relaxed model ceiling is conditional on that response model. A true sequential six-month ceiling is not identifiable here. Loan bootstrap excludes model bias and future-state uncertainty.

May-June is unobserved. All tested fixed-composition continuation demands exceed remaining quota; their projected margins are null. The daily selector enforces capacity and can choose B/no-attempt, but future economic allocation needs refinement. Sample weight 15 provides a full-book point extrapolation, not an exact full-book optimization.

## Architecture and verification

Python modules + local SQLite keep the MVP small. Candidate scoring precedes the write lock; selection, quota reservation, decision and outbox persist atomically. A separate simulated executor uses stable identities. Payment failures consume A; unknown delivery retains reservations until authoritative reconciliation. Corrected records are revalidated automatically; sent/uncertain effects cannot be overwritten.

[Architecture](docs/05_architecture.md), [ADRs](docs/adrs/README.md), [risks](docs/06_assumptions_and_risks.md), [frozen protocol](docs/07_evaluation_protocol.md), [operational evidence](docs/10_validation.md).

Local benchmark for **4,640 loans**: **8.95 s** cold input/validation/fitting plus planning/commit; **2.52 s** warm planning/commit median. Three runs produced identical decisions. These measurements exclude dispatch/export/network and are not a production SLO. Tests cover independent-process quota contention, concurrent dispatch, interruption, uncertain submissions, expiry, corrections and state failure. The final clean-environment evidence is in [validation](reports/validation/clean_environment.json).

Production is a proposal: shared transactional database, receiver, planner workers, outbox and reconciliation. Rollout starts in shadow, then a capped randomized pilot after calibration/support and lender profitability are addressed. Rollback stops new intents while retaining pending reservations.

## Rationale — Context, Action, Result

| Step | Context → Action → Result |
|---|---|
| Understand | Read the case and data README → establish economic objective, D/D+1 and sample/contract boundaries. |
| Visualize | Create Mermaid business, entity and economic diagrams → make flow, constraints and accounting visible. |
| Formalize | Write docs 01-04 → separate business objective, decision variables, assumptions and open questions. |
| Profile | Import the existing [EDA tool](https://github.com/gabrielscatena/EDA) via **Git subtree with squash** → quickly profile all three datasets under Python 3.12. |
| Validate | Build case-specific EDA → verify keys, joins, installment limits, balance evolution and lender economics. |
| Implement | Record ADRs and freeze protocol → deliver a transactional daily motor, economic heuristic and reproducible comparison. |
| Challenge claims | Audit support, calibration, quota scenarios and failures → publish limitations and decline live approval. |

Initial EDA: 12 lenders, 10,714 loans, 561,659 snapshots and 370,101 attempts. Commission 902,448.9620; recorded fees 427,295; usage-priced diagnostic 475,153.9620. That diagnostic is not contract margin. [EDA evidence](reports/eda_belvo/20261028_112854_444227/report.md) includes 1,922 observation gaps and reconciled adjacent-day balances.

AI tools assisted documentation, code and verification. Reused code remains in `tools/eda`; project-owned code is under `src/belvo`. [CHANGELOG](CHANGELOG.md) records commit checkpoints without presenting elapsed gaps as measured active effort. The [case specification](docs/provided/CHALLENGE.md) defines the deliverables.
