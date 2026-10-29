# Local runbook

Use Python 3.12 (general EDA dependencies do not support Python 3.14). From repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r conf/requirements-mvp.lock -e ".[mvp]"
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
python -m belvo.pipelines.persistent --date 2026-04-01 --state artifacts/runtime/delivery_baseline.sqlite --provider-state artifacts/runtime/delivery_baseline_provider.sqlite --execute
python -m belvo.pipelines.persistent --date 2026-04-01 --state artifacts/runtime/delivery_baseline.sqlite --provider-state artifacts/runtime/delivery_baseline_provider.sqlite --reconcile --execute
```

These commands use a durable **simulated** provider, not an API. On first initialization,
historical A submissions before the requested day seed consumed capacity. Existing state
is never reseeded. Reuse the same state for subsequent days/retries. A new experiment needs
a new `--state` and `--provider-state`; never delete live state to clear reservations.

```powershell
python -m belvo.pipelines.persistent --date 2026-04-01 --policy economic --state artifacts/runtime/delivery_economic.sqlite --provider-state artifacts/runtime/delivery_provider.sqlite
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
`reports/evaluation/verified_v2`; the original checkpoint remains in `frozen_v1`. Do not overwrite either checkpoint. No April labels train
the policy. Results are conditional model estimates; consult the rollout blockers.

```powershell
python -m belvo.evaluation.benchmark
```

Persistent input is a **complete portfolio** for all lenders, or for `--client C01`.
Corrections that omit a previously planned loan cancel its unsent intents. Reservations
for uncertain attempts remain. Distinct policies require distinct state; backward-date
replay also requires separate state. Cap-source changes are included in version identities.

## Corrections and reproducible models

Use `--source-revision 1` for the initial portfolio and increase it for every authoritative
same-day correction or withdrawal, for example `--client C01 --source-revision 2`.
The revision must come from the source, not be incremented when retrying transmission.
Retries keep the same revision and contents; changed contents at the same revision or an
older revision fail before committing. Omitting the flag supports the first receipt and
identical retries only. A reappearance matching an old portfolio still needs a new revision.
`--output <new-directory>` optionally fixes the export destination.

Preserve earlier simulator stores. Stores with decisions but no source-order metadata
cannot establish recency; run these corrections in new `--state` / `--provider-state` paths.

Economic history excludes D and future rows before parsing money or joining snapshots.
Invalid historical loan-days are recorded in `history_issues` and exported in run metadata.
Affected current loans produce no debit; unaffected loans continue. Lenders with incomplete
history report an unavailable budget. Without valid training labels, the economic policy
returns `no_available_training_history` and no attempts.

Model artifacts are immutable in `<state-stem>.models/<model_hash>.json` and also stored
transactionally in the `models` table. Every scored decision references its model hash.
Restore with `EmpiricalModel.from_artifact(json.loads(path.read_text()))`; the hash is checked.
The simulator's stored outcomes do not automatically train the model or update lender
budgets; supplied CSV history remains the offline source. A complete feedback loop is future work.

Changes in the fitted model or lender budget refresh entirely unsent decisions automatically.
If valid training disappears, pending unsubmitted debits are canceled in favor of explicit
no-attempt decisions. Existing submitted/uncertain effects remain protected.

## Post-review diagnostics and reproduction

The current selector is `economic_heuristic_v2`. Existing state bound to `economic-v1`
must remain preserved: use new state/provider paths for the corrected policy. Original
`frozen_v1`, `verified_v2` and benchmark checkpoints are historical, not overwritten.
Current conditional estimates are in `reports/evaluation/selector_v3`.

After installing the MVP, the following shell-neutral commands reproduce the review.
Use NEW output directories; the saved evaluation path below must be generated first.
Raw loan-day action exports are intentionally Git-ignored and are regenerated by evaluation.

```text
python -m belvo.evaluation.offline --output reports/evaluation/local_review
python -m belvo.evaluation.diagnostics --evaluation-dir reports/evaluation/local_review --output reports/evaluation/local_calibration
python -m belvo.evaluation.economic_views --evaluation-dir reports/evaluation/local_review --output reports/evaluation/local_economic_views
python -m belvo.evaluation.refit --evaluation-dir reports/evaluation/local_review --output reports/evaluation/local_refit --repetitions 20 --seed 42
python -m belvo.evaluation.synthetic --output artifacts/runtime/local_synthetic --loans 2400 --seed 7
python -m belvo.evaluation.benchmark --output reports/validation/local_benchmark.json
```

Diagnostics publish aggregate calibration, calendar/amount support, allocation conventions
and fixed-action scarcity penalties. Refit rescores frozen actions; it does not reselect
policies. Synthetic truth is separate from generated CSVs and never used for training.
The synthetic command writes a NEW directory and refuses existing data. These commands
need several minutes on the full supplied files. None establishes causal uplift or a
six-month forecast; consult docs/09_results.md before interpreting their outputs.

With Python 3.12 selected, `make setup`, `make test` and `make lint` use the same interpreter
through `PYTHON`; override it explicitly when needed, for example
`make PYTHON=.venv/bin/python test`. The setup target installs the lock and MVP extras.
