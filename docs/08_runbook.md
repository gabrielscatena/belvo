# Local runbook

Use Python 3.12 (general EDA dependencies do not support Python 3.14). From repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,data]"
.\.venv\Scripts\python.exe -m belvo.pipelines.daily --date 2026-04-01
.\.venv\Scripts\python.exe -m pytest -q
```

Put the three provided CSVs in `data/raw`. Daily outputs include decisions CSV/JSON,
preserved source payload versions and run metadata. One output row per identified loan;
missing identities are explicit quarantined source records. Do not reuse an output folder.
`--a-capacity` supplies available units to the standalone feasibility demonstration; it
does not infer remaining quota from a real account. Persistent operation is a separate
command added with the transactional state milestone. No real debits are submitted.

```powershell
python -m belvo.pipelines.persistent --date 2026-04-01 --execute
python -m belvo.pipelines.persistent --date 2026-04-01 --reconcile --execute
```

These commands use a durable **simulated** provider, not an API. On first initialization,
historical A submissions before the requested day seed consumed capacity. Existing state
is never reseeded. Reuse the same state for subsequent days/retries. A new experiment needs
a new `--state` and `--provider-state`; never delete live state to clear reservations.

```powershell
python -m belvo.pipelines.persistent --date 2026-04-01 --policy economic --state artifacts/runtime/economic.sqlite --provider-state artifacts/runtime/economic_provider.sqlite
```

The economic command fits only available pre-April labels, saves model provenance and
exports expected economics and lender constraint statuses. It does not execute unless
`--execute` is supplied. The default lender horizon check assumes zero pending/future
contribution; unmet constraints are expected warnings, not proof of infeasibility.

```powershell
python -m belvo.evaluation.offline
```

The evaluator takes several minutes on the full CSVs. It writes model provenance,
monthly/per-lender margins, calibration, cluster uncertainty, daily capacity and scenario
tables to a new `reports/evaluation/<run-id>` directory. Published frozen results are in
`reports/evaluation/frozen_v1`; do not overwrite that checkpoint. No April labels train
the policy. Results are conditional model estimates; consult the rollout blockers.

```powershell
python -m belvo.evaluation.benchmark
```

Persistent input is a **complete portfolio** for all lenders, or for `--client C01`.
Corrections that omit a previously planned loan cancel its unsent intents. Reservations
for uncertain attempts remain. Distinct policies require distinct state; backward-date
replay also requires separate state. Cap-source changes are included in version identities.
