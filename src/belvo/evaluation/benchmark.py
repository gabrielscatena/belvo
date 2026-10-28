"""Measure local full-portfolio planning/commit latency; excludes simulated dispatch."""

import argparse
import json
import platform
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd

from belvo.config import Protocol
from belvo.domain import fingerprint
from belvo.models.empirical import fit_for_day, load_history
from belvo.optimization.select import EconomicSelector, zero_future_budget
from belvo.pipelines.daily import load_day
from belvo.state import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--date", default="2026-04-01")
    parser.add_argument("--config", default="conf/protocol.json")
    parser.add_argument("--output", type=Path, default=Path("reports/validation/benchmark_v2.json"))
    args = parser.parse_args()
    started = perf_counter()
    protocol = Protocol.load(args.config)
    history = load_history(
        args.data_dir, before=args.date, known_through=protocol.known_attempt_through(args.date)
    )
    model = fit_for_day(history, protocol, args.date)
    required = zero_future_budget(history, args.date, protocol)
    valid, rejected, raw = load_day(args.data_dir, args.date)
    preparation = perf_counter() - started
    initial = int((history.provider.eq("A") & history.attempt_date.lt(args.date)).sum())
    runtime = Path("artifacts/runtime").resolve()
    runtime.mkdir(parents=True, exist_ok=True)
    timings, hashes, quotas, commit_timings = [], [], [], []
    for _ in range(3):
        with tempfile.TemporaryDirectory(dir=runtime, prefix="benchmark_") as folder:
            start = perf_counter()
            selector = EconomicSelector(model, required)
            selector.prepare(valid, protocol)
            store = Store(Path(folder) / "engine.db", protocol, consumed=initial)
            commit_started = perf_counter()
            decisions = store.commit_day(
                valid,
                rejected,
                raw,
                args.date,
                selector,
                portfolio_clients={loan.client_id for loan in valid},
                source_revision=1,
                model_artifact=model.artifact() | {"model_hash": model.model_hash},
            )
            commit_timings.append(perf_counter() - commit_started)
            timings.append(perf_counter() - start)
            hashes.append(fingerprint(decisions))
            quotas.append(store.quota())
    if len(set(hashes)) != 1 or any(q["free"] < 0 for q in quotas):
        raise ValueError("Benchmark violated reproducibility or capacity")
    result = {
        "recorded_at": datetime.now().astimezone().isoformat(),
        "date": args.date,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "python": sys.version.split()[0],
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "scope": "Full received portfolio, economic selection plus durable commit; no dispatch/export",
        "loans": len(valid),
        "quarantined": len(rejected),
        "installment_candidates_max": 25,
        "cold_input_validation_fit_seconds": preparation,
        "planning_commit_seconds": timings,
        "transaction_seconds": commit_timings,
        "cold_total_seconds": preparation + timings[0],
        "warm_median_seconds": float(np.median(timings[1:])),
        "warning": "Three local runs, not a p95 SLO or production load test. Warm runs reuse data/model.",
        "decision_hash": hashes[0],
        "quota": quotas[0],
        "protocol": protocol.values,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
