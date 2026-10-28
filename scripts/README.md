# Scripts

Place operational commands here (data preparation, training, evaluation, batch execution).
Keep business logic in `src/` and import it from your scripts.

## CSV profiling

`run_eda.ps1` runs the vendored `tools/eda/eda_report.py` with the isolated
`.venv-eda` Python 3.12 environment. The upstream pinned profiling version does
not support Python 3.14. Install `conf/requirements-eda.txt` in that environment;
this CSV-only workflow skips Evidently and does not need the YData SDK.

```powershell
# Setup on a machine with Python 3.12 registered with the Windows launcher:
py -3.12 -m venv .venv-eda
if ($LASTEXITCODE -ne 0) { throw 'Environment creation failed.' }
uv pip install --python .venv-eda/Scripts/python.exe -r conf/requirements-eda.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }

# Run all three datasets; no environment activation is needed:
& ./scripts/run_eda.ps1

# Or smoke-check only the small clients table:
& ./scripts/run_eda.ps1 -Datasets clients
```

Each run writes to `reports/eda/<run-id>/<dataset>/`. Success is printed only
after both the HTML profile and summary exist for every requested dataset.
Input CSVs are read without being overwritten; the upstream tool may convert
column types in memory. These are per-file profiles, not cross-table business
validation or counterfactual policy evaluation.

## Belvo-specific cross-table EDA

Run from the repository root with the existing EDA environment (only pandas and
NumPy are required; this analysis does not import YData or Evidently):

```powershell
& ./.venv-eda/Scripts/python.exe ./scripts/eda_belvo.py
```

The CLI reads `data/raw/{clients,loan_snapshots,payment_attempts}.csv` and creates
a new `reports/eda_belvo/<run-id>/` directory containing `report.md`, CSV evidence,
bounded examples, `metrics.json`, and reproducibility metadata with input hashes.
It never modifies inputs or overwrites an existing output directory.

```powershell
# Explicit paths and configuration (defaults match the supplied package):
& ./.venv-eda/Scripts/python.exe ./scripts/eda_belvo.py `
    --data-dir ./data/raw `
    --output-dir ./reports/eda_belvo/manual_run `
    --sample-weight 15 `
    --contract-start 2026-01-01 --contract-end 2026-06-30 `
    --a-allowance 10000000 --a-upfront 10000000.00

# Focused regression tests, with no additional test dependency:
& ./.venv-eda/Scripts/python.exe -m unittest discover -s tests -p test_eda_belvo.py -v
```

Checks cover schema and exact monetary precision; primary/foreign keys; stable
loan ownership and same-day joins; installment completeness, caps and dated
balances; statuses, provider fees and dates; snapshot gaps and adjacent-day
balance residuals. Descriptive tables cover observed attempt/no-attempt days,
installment/provider patterns, action-support segments, portfolio activity and
legacy economics by lender, provider and DPD.

Money uses exact cents and commission precision of 0.0001 without per-attempt
rounding. Economics distinguish the observed loan sample, 15x-weighted
observed-period full-book estimates, and explicit fixed-cost allocation
scenarios. Commitment coverage subtracts the full prepaid cost from weighted
observed-period contribution; it is **not a completed six-month margin**.
No May-June forecast, causal provider effect, policy improvement or attainable
ceiling is inferred. A balance residual is not automatically an external payment.

Exit codes: **0** analysis completed without failed validation checks (review
warnings can remain); **2** data checks failed (inspect `report.md` and
`validation_checks.csv`); **1** runtime failure. Structural/attribution failures
stop dependent economics, while historical cap/group violations are reported
without clipping the observed payments. Defaults and all overrides are recorded.
