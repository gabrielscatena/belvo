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
