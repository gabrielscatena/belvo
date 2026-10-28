"""Stateful local motor with an explicitly simulated executor."""

import argparse
import json
from datetime import date, datetime
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
    parser.add_argument("--policy", choices=["baseline", "economic"], default="baseline")
    parser.add_argument("--client", help="Restrict to this lender's full daily portfolio")
    args = parser.parse_args()
    try:
        if date.fromisoformat(args.date).isoformat() != args.date:
            raise ValueError("Noncanonical date")
    except ValueError:
        parser.error("Date must use YYYY-MM-DD")
    p = Protocol.load(args.config)
    attempts = read_csv(args.data_dir / "payment_attempts.csv", {"attempt_date", "provider"})
    consumed = sum(r["provider"] == "A" and r["attempt_date"] < args.date for r in attempts)
    store = Store(args.state, p, consumed=consumed)
    store.bind_policy(args.policy + "-v1")
    provider = SimulatedProvider(args.provider_state)
    store.bind_provider(provider.identity)
    if args.reconcile:
        reconcile(store, provider)
    valid, rejected, raw = load_day(args.data_dir, args.date)
    client_rows = read_csv(args.data_dir / "clients.csv", {"client_id"})
    portfolio_clients = {args.client} if args.client else {r["client_id"] for r in client_rows}
    if args.client:
        if args.client not in {r["client_id"] for r in client_rows}:
            parser.error("Unknown lender")
        valid = [loan for loan in valid if loan.client_id == args.client]
        rejected = [r for r in rejected if r["client_id"] == args.client]
        raw = [r for r in raw if r["payload"].get("client_id") == args.client]
    selector = None
    if args.policy == "economic":
        from belvo.models.empirical import fit_for_day, load_history
        from belvo.optimization.select import EconomicSelector, zero_future_budget

        history = load_history(args.data_dir)
        model = fit_for_day(history, p, args.date)
        selector = EconomicSelector(
            model,
            zero_future_budget(
                history, args.date, p, clients={r["client_id"] for r in client_rows}
            ),
        )
        selector.prepare(valid, p)
        model.save(args.state.with_suffix(".model.json"))
    decisions = store.commit_day(valid, rejected, raw, args.date, selector, portfolio_clients)
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
