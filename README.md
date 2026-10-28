# Smart Collections Engine

Senior Applied Data Scientist take-home: maximize absolute collection margin while respecting installment caps, Provider A's prepaid capacity and expiry, and profitability for every lender.

**Status:** working specifications and EDA implemented; decision-policy prototype, architecture and final evaluation pending.

## Approach and rationale — Context, Action, Result

| Step | Context | Action | Result |
|---|---|---|---|
| 1. Understand | Business constraints precede model selection. | Read the challenge and package README. | Identified decisions, delayed outcomes and sample/full-book boundaries. |
| 2. Visualize | Operations and economics needed a shared representation. | Created Mermaid [business](diagrams/business_flow.mmd), [entity](diagrams/entity_relationship.mmd) and [economic](diagrams/economic_flow.mmd) diagrams. | Made relationships, feedback and accounting explicit. |
| 3. Specify | Diagrams needed formal assumptions. | Wrote [01 Process](docs/01_business_process.md), [02 Domain](docs/02_domain_model.md), [03 Economics](docs/03_economic_model.md) and [04 Problem framing](docs/04_problem_framing.md). | Defined feasible plans, objectives and questions for EDA. |
| 4. Profile | A reusable tool already existed. | Imported my [EDA repository](https://github.com/gabrielscatena/EDA) using **Git subtree with squash**; ran the three CSVs under Python 3.12. | Obtained general HTML profiles and summaries without rebuilding the tool. |
| 5. Validate | Profiling alone misses business relationships. | Implemented [eda_belvo.py](scripts/eda_belvo.py), [analysis logic](src/belvo/data/eda.py) and regression tests. | Validated joins, installments, balances and observed economics to refine docs 01–04. |

AI assistance supported documentation, implementation and verification; reused and case-specific code remain identifiable.

## Initial evidence and limitations

The [package README](docs/provided/README.md) specifies a **1-in-15 loan sample**, observed **January–April 2026**. A's **10,000,000 transactions and upfront cost** apply to the full book for **January–June 2026**.

| Observed sample metric | Result |
|---|---:|
| Lenders / distinct loans | 12 / 10,714 |
| Loan snapshots / payment attempts | 561,659 / 370,101 |
| Commission revenue | 902,448.9620 |
| Recorded attempt fees | 427,295.0000 |
| Usage-priced margin diagnostic: revenue minus recorded fees | 475,153.9620 |

Amounts are abstract currency units. The usage-priced diagnostic excludes the cost of unused A capacity; it is **not final contract margin**. Three lenders have a negative diagnostic. Contract profitability also requires the missing May–June activity and an explicit upfront-cost allocation.

Implemented checks had **zero failures**. Adjacent-day balances reconciled with collections; **1,922 observation gaps** were analyzed separately. Code checks and **12 project tests** passed; an independent Decimal reconstruction confirmed commission and fees.

Local evidence: [EDA report](reports/eda_belvo/20261028_112854_444227/report.md), [lender economics](reports/eda_belvo/20261028_112854_444227/economics_by_lender.csv), and [input hashes/settings](reports/eda_belvo/20261028_112854_444227/run_metadata.json). These outputs and EDA implementation changes are not yet committed at this checkpoint.

Provider comparisons are observational; alternative actions lack observed outcomes. Legacy future balances cannot be reused unchanged as a validated new-policy simulation. **Policy uplift, attainable ceiling and final six-month margin remain unestablished.**

## Reproduce the current analyses

Place the original `clients.csv`, `loan_snapshots.csv` and `payment_attempts.csv` in `data/raw/` (excluded from Git). Use **Python 3.12**; the pinned profiler does not support 3.14. A local `.venv-eda` is already prepared. On a new machine, install Python 3.12 and run from the repository root:

```powershell
py -3.12 -m venv .venv-eda
& ./.venv-eda/Scripts/python.exe -m pip install -r conf/requirements-eda.txt
```

Then run in PowerShell, continuing only after successful commands:

```powershell
# General per-file profiles and summaries
& ./scripts/run_eda.ps1

# Cross-table validations and observed economic reconstruction
& ./.venv-eda/Scripts/python.exe ./scripts/eda_belvo.py

# Case-specific regression tests; no additional test dependency
& ./.venv-eda/Scripts/python.exe -m unittest discover -s tests -p test_eda_belvo.py -v
```

Outputs: `reports/eda/<run-id>/` and `reports/eda_belvo/<run-id>/`; inputs are preserved. Specific EDA exit codes: **0** no failed checks, **2** failed data checks, **1** runtime error. See [script instructions](scripts/README.md).

## Remaining challenge deliverables

| Requirement | Current state / next step |
|---|---|
| Design document, 2–4 pages | Consolidate working notes with architecture, risks, offline validation and rollout design. |
| Working daily decision prototype | Implement attempt/no-attempt, installment amounts/counts and provider assignments. |
| Offline comparison and results write-up | Compare candidate and legacy margins on matching scopes; report every lender and an attainable-ceiling estimate with uncertainty. |

This README provides execution instructions and an interim report. Final design and policy-evaluation requirements remain open. See [CHANGELOG.md](CHANGELOG.md) for chronology and timing provenance.
