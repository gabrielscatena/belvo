"""Known-response stress test; synthetic truth is never supplied to the fitted model.

Run ``python -m belvo.evaluation.synthetic --output artifacts/runtime/synthetic_probe``.
The default generator reproduces the external probe's provider-neutral response and
payday-confounded legacy assignments. This tests failure modes, not the bias on Belvo
data. Evaluation holds the legacy snapshots fixed: it is not a sequential rollout.
"""

import argparse
import json
import math
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from belvo.config import Protocol, commission_percent
from belvo.domain import Loan, Plan, cents, plans
from belvo.models.empirical import fit_for_day, load_history
from belvo.optimization.select import EconomicSelector, zero_future_budget


def is_payday(day: str | date) -> bool:
    day = date.fromisoformat(day) if isinstance(day, str) else day
    return day.day in (1, 15, 16) or (day + timedelta(days=1)).month != day.month


def true_probability(truth: dict, client: str, amount_cents: int, day: str) -> float:
    """Provider has no effect in this DGP; every attempt has its own amount response."""
    return truth["base"][client] * (2 if is_payday(day) else 1) * math.exp(-amount_cents / 150000)


def generate(
    output: Path,
    *,
    n_loans: int = 2400,
    seed: int = 7,
    n_clients: int = 12,
    start: str = "2026-01-01",
    end: str = "2026-04-30",
) -> tuple[Path, dict]:
    """Create a new isolated fixture, with latent truth outside its CSV directory.

    Existing outputs are refused, including data/raw and frozen report directories.
    Generated original_amount is the actual initial balance, not a placeholder.
    """
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if n_loans < 1 or n_clients < 1 or last < first:
        raise ValueError("Require positive fixture sizes and an ordered date range")
    output.mkdir(parents=True, exist_ok=False)
    data = output / "data"
    data.mkdir()
    rng = np.random.default_rng(seed)
    clients = [f"C{i:02d}" for i in range(1, n_clients + 1)]
    caps = dict(zip(clients, rng.choice([800, 1200, 1500, 2000, 3000], n_clients), strict=True))
    base = dict(zip(clients, rng.uniform(0.010, 0.030, n_clients), strict=True))
    truth = {
        "seed": seed,
        "loans": n_loans,
        "clients": n_clients,
        "start": start,
        "end": end,
        "response": "base[lender] * payday_multiplier * exp(-amount / 1500)",
        "provider_effect": 0,
        "base": {k: float(v) for k, v in base.items()},
        "caps": {k: int(v) for k, v in caps.items()},
    }
    loans = pd.DataFrame(
        {
            "loan_id": [f"L{i:05d}" for i in range(n_loans)],
            "client_id": rng.choice(clients, n_loans),
            "balance": np.round(rng.lognormal(8.3, 0.6, n_loans), 2),
            "dpd0": rng.integers(0, 120, n_loans),
        }
    )
    balances = dict(zip(loans.loan_id, loans.balance, strict=True))
    snapshots, attempts = [], []
    for offset in range((last - first).days + 1):
        day = first + timedelta(days=offset)
        payday = is_payday(day)
        for loan in loans.itertuples():
            balance = balances[loan.loan_id]
            if balance <= 0:
                continue
            snapshots.append(
                (
                    day.isoformat(),
                    loan.loan_id,
                    loan.client_id,
                    f"{balance:.2f}",
                    int(loan.dpd0 + offset),
                    f"{loan.balance:.2f}",
                )
            )
            if rng.random() > (0.75 if payday else 0.25):
                continue
            count = int(rng.integers(1, 4))
            fraction = float(rng.choice([0.25, 0.5, 0.75, 1.0]))
            total = int(min(balance, count * caps[loan.client_id]) * fraction * 100)
            if total < count:
                continue
            regular, remainder = divmod(total, count)
            provider = ("B" if rng.random() < 0.5 else "A") if payday else "A"
            collected = 0
            for index in range(count):
                amount = regular + (index < remainder)
                success = rng.random() < true_probability(
                    truth, loan.client_id, amount, day.isoformat()
                )
                collected += amount if success else 0
                attempts.append(
                    (
                        f"T{len(attempts) + 1}",
                        loan.loan_id,
                        day.isoformat(),
                        index + 1,
                        count,
                        f"{amount / 100:.2f}",
                        provider,
                        "success" if success else "failed",
                        "1.00" if provider == "A" else "2.00",
                    )
                )
            balances[loan.loan_id] = round(balance - collected / 100, 2)
    pd.DataFrame(
        {"client_id": clients, "max_installment_amount": [f"{caps[c]:.2f}" for c in clients]}
    ).to_csv(data / "clients.csv", index=False)
    pd.DataFrame(
        snapshots,
        columns=[
            "snapshot_date",
            "loan_id",
            "client_id",
            "outstanding_balance",
            "days_past_due",
            "original_amount",
        ],
    ).assign(payroll_cycle="monthly", debtor_bank="bank_1", customer_tenure_months=12).to_csv(
        data / "loan_snapshots.csv", index=False
    )
    pd.DataFrame(
        attempts,
        columns=[
            "attempt_id",
            "loan_id",
            "attempt_date",
            "installment_index",
            "installment_count",
            "amount",
            "provider",
            "status",
            "fee",
        ],
    ).to_csv(data / "payment_attempts.csv", index=False)
    (output / "truth.json").write_text(json.dumps(truth, indent=2), encoding="utf-8")
    return data, truth


def true_commission(truth: dict, loan: Loan, plan: Plan) -> float:
    return sum(
        amount
        / 100
        * commission_percent(loan.dpd)
        / 100
        * true_probability(truth, loan.client_id, amount, loan.day)
        for amount in plan.amounts
    )


def score(data: Path, truth: dict, protocol: Protocol) -> dict:
    """Replay the real selector and score it using a separate known response.

    The oracle searches the configured pure-provider amount grid on legacy states.
    It relaxes historical support and lender budgets. Its quota feasibility is
    explicitly checked rather than inferred from a per-loan maximization.
    """
    frame = load_history(data)
    settings = protocol.values
    model = fit_for_day(frame, protocol, settings["test_start"])
    caps = {
        r.client_id: cents(r.max_installment_amount)
        for r in pd.read_csv(data / "clients.csv", dtype=str).itertuples()
    }
    train = frame.loc[frame.attempt_date.le(model.fitted_through)].copy()
    train["payday"] = train.attempt_date.map(is_payday)
    support = train.groupby(["client_id", "provider", "payday"]).size().to_dict()
    initial_a = int(frame.loc[frame.attempt_date.lt(settings["test_start"])].provider.eq("A").sum())
    initial_quota = max(0, protocol.sample_capacity - initial_a)
    quota = initial_quota
    historical = {
        key: group.sort_values("installment_index")
        for key, group in frame.groupby(["loan_id", "attempt_date"])
    }
    snapshots = pd.read_csv(data / "loan_snapshots.csv", dtype=str)
    snapshots = snapshots.loc[
        snapshots.snapshot_date.between(settings["test_start"], settings["test_end"])
    ]
    totals = defaultdict(float)
    by_client = {client: defaultdict(float) for client in caps}
    b_fee = float(settings["b_fee"])
    for day, group in snapshots.groupby("snapshot_date", sort=True):
        loans = [
            Loan(
                r.loan_id,
                r.client_id,
                day,
                cents(r.outstanding_balance),
                caps[r.client_id],
                int(r.days_past_due),
                "synthetic",
            )
            for r in group.itertuples()
        ]
        selector = EconomicSelector(model, zero_future_budget(frame, day, protocol, clients=caps))
        decisions, quota = selector(loans, quota, protocol)
        lookup = {decision["loan_id"]: decision for decision in decisions}
        for loan in loans:
            decision = lookup[loan.loan_id]
            plan = Plan(tuple(decision["plan"]["amounts"]), tuple(decision["plan"]["providers"]))
            values = {
                "candidate_estimated_commission": decision["economics"]["expected_revenue"],
                "candidate_true_expected_commission": true_commission(truth, loan, plan),
                "candidate_a": plan.a_units,
                "candidate_b": plan.b_units,
                "candidate_attempts_without_calendar_support": sum(
                    support.get((loan.client_id, provider, is_payday(day)), 0) == 0
                    for provider in plan.providers
                ),
                "candidate_nonpayday_b": plan.b_units if not is_payday(day) else 0,
                "candidate_b_without_calendar_support": sum(
                    provider == "B"
                    and support.get((loan.client_id, provider, is_payday(day)), 0) == 0
                    for provider in plan.providers
                ),
            }
            options = [
                option
                for option in plans(
                    loan, settings["amount_fractions"], settings["max_installments"]
                )
                if not option.a_units or protocol.a_available(day)
            ]
            oracle = max(
                options,
                key=lambda option: true_commission(truth, loan, option) - b_fee * option.b_units,
            )
            values["unrestricted_grid_oracle_contribution"] = (
                true_commission(truth, loan, oracle) - b_fee * oracle.b_units
            )
            values["unrestricted_grid_oracle_a_units"] = oracle.a_units
            values["oracle_plans_without_model_support"] = int(
                bool(oracle.amounts) and not model.evaluate(loan, oracle)["supported"]
            )
            values["oracle_attempts_without_calendar_support"] = sum(
                support.get((loan.client_id, provider, is_payday(day)), 0) == 0
                for provider in oracle.providers
            )
            legacy = historical.get((loan.loan_id, day))
            if legacy is not None:
                old_plan = Plan(tuple(legacy.amount_cents.astype(int)), tuple(legacy.provider))
                values |= {
                    "legacy_estimated_commission": model.evaluate(loan, old_plan)[
                        "expected_revenue"
                    ],
                    "legacy_true_expected_commission": true_commission(truth, loan, old_plan),
                    "legacy_observed_commission": float(
                        (
                            legacy.amount_cents
                            / 100
                            * commission_percent(loan.dpd)
                            / 100
                            * legacy.status.eq("success")
                        ).sum()
                    ),
                    "legacy_a": old_plan.a_units,
                    "legacy_b": old_plan.b_units,
                }
            for key, value in values.items():
                totals[key] += value
                by_client[loan.client_id][key] += value
    if snapshots.empty:
        raise ValueError("No synthetic snapshots in the evaluation window")
    days = (
        date.fromisoformat(settings["test_end"]) - date.fromisoformat(settings["test_start"])
    ).days + 1
    contract_days = (
        date.fromisoformat(settings["contract_end"])
        - date.fromisoformat(settings["contract_start"])
    ).days + 1
    fixed = float(protocol.sample_upfront) * days / contract_days

    def add_money(values, allocated_fixed):
        for policy in ("candidate", "legacy"):
            fees = b_fee * values.get(policy + "_b", 0)
            kinds = ("estimated", "true_expected")
            if policy == "legacy":
                kinds += ("observed",)
            for kind in kinds:
                key = f"{policy}_{kind}_commission"
                values[f"{policy}_{kind}_margin"] = values.get(key, 0) - fees - allocated_fixed
        values["unrestricted_grid_oracle_margin"] = (
            values.get("unrestricted_grid_oracle_contribution", 0) - allocated_fixed
        )

    add_money(totals, fixed)
    for values in by_client.values():
        add_money(values, fixed / len(caps))
    return {
        "scope": "Known-response conditional one-step stress on legacy states, not Belvo uplift",
        "seed": truth.get("seed"),
        "selector_version": getattr(EconomicSelector, "version", "economic_heuristic_v1"),
        "model_hash": model.model_hash,
        "model_through": model.fitted_through,
        "evaluation_days": days,
        "loan_days": len(snapshots),
        "fixed_cost": fixed,
        "initial_a_consumed": initial_a,
        "initial_a_available": initial_quota,
        "remaining_a": quota,
        "prior_capacity_overage": initial_a > protocol.sample_capacity,
        "totals": dict(totals),
        "per_client": {client: dict(values) for client, values in by_client.items()},
        "oracle": {
            "scope": "Pure-provider configured grid; relaxed historical support and lender budgets",
            "sequential": False,
            "historical_support_enforced": False,
            "lender_budgets_enforced": False,
            "capacity_feasible": totals["unrestricted_grid_oracle_a_units"] <= initial_quota,
            "all_plans_have_model_cell_support": totals["oracle_plans_without_model_support"] == 0,
            "all_attempts_have_calendar_support": (
                totals["oracle_attempts_without_calendar_support"] == 0
            ),
            "warning": "Only a known-DGP same-state bound; not a six-month achievable ceiling",
        },
        "support_warning": "Provider/calendar counts diagnose overlap, not causal identification",
        "protocol": settings,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--loans", type=int, default=2400)
    parser.add_argument("--clients", type=int, default=12)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--start", default="2026-01-01")
    parser.add_argument("--end", default="2026-04-30")
    parser.add_argument("--config", default="conf/protocol.json")
    args = parser.parse_args()
    data, truth = generate(
        args.output,
        n_loans=args.loans,
        seed=args.seed,
        n_clients=args.clients,
        start=args.start,
        end=args.end,
    )
    result = score(data, truth, Protocol.load(args.config))
    (args.output / "stress.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "totals": result["totals"]}, indent=2))


if __name__ == "__main__":
    main()
