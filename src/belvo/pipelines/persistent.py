"""Stateful local motor with an explicitly simulated executor."""

import argparse
import json
from datetime import datetime
from pathlib import Path

from belvo.config import Protocol
from belvo.pipelines.daily import export, load_day, read_csv
from belvo.state import SimulatedProvider, Store, execute, reconcile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--config", default="conf/protocol.json")
    parser.add_argument("--state", type=Path, default=Path("artifacts/runtime/engine.sqlite"))
    parser.add_argument(
        "--provider-state", type=Path, default=Path("artifacts/runtime/simulator.sqlite")
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--reconcile", action="store_true")
    args = parser.parse_args()
    p = Protocol.load(args.config)
    attempts = read_csv(args.data_dir / "payment_attempts.csv", {"attempt_date", "provider"})
    consumed = sum(r["provider"] == "A" and r["attempt_date"] < args.date for r in attempts)
    store = Store(args.state, p, consumed=consumed)
    provider = SimulatedProvider(args.provider_state)
    if args.reconcile:
        reconcile(store, provider)
    valid, rejected, raw = load_day(args.data_dir, args.date)
    decisions = store.commit_day(valid, rejected, raw, args.date)
    if args.execute:
        execute(store, provider, args.date)
    output = Path("reports/pipeline") / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    export(
        output,
        decisions,
        raw,
        {"protocol": p.values, "quota": store.quota(), "state": str(args.state), "simulated": True},
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "quota": store.quota(),
                "decisions": len(decisions),
                "simulated": True,
            }
        )
    )


if __name__ == "__main__":
    main()
