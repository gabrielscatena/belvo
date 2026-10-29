"""Post-inspection quota/admission sensitivities on fixed legacy loan states.

This is neither a six-month forecast nor an estimate of causal improvement. The
original observed legacy benchmark is retained separately from filtered log replay.
"""

import argparse
import hashlib
import json
from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from time import perf_counter

import pandas as pd

from belvo.config import Protocol, commission_percent
from belvo.domain import Loan, Plan, cents
from belvo.models.calendar_support import CalendarSupport, CalendarSupportedModel, calendar_type
from belvo.models.empirical import fit_for_day, load_history
from belvo.optimization.select import EconomicSelector, zero_future_budget


@dataclass(frozen=True)
class ReleaseSchedule:
    """Release a fixed opening balance cumulatively; unspent units carry forward."""

    opening_units: int
    start: str
    end: str
    multiplier: Decimal | None = Decimal(1)

    def __post_init__(self):
        if type(self.opening_units) is not int or self.opening_units < 0:
            raise ValueError("Opening capacity must be a nonnegative integer")
        if date.fromisoformat(self.end) < date.fromisoformat(self.start):
            raise ValueError("Release window ends before it starts")
        if self.multiplier is not None and (not self.multiplier.is_finite() or self.multiplier < 0):
            raise ValueError("Release multiplier must be finite and nonnegative")

    def released(self, day):
        start, end, current = map(date.fromisoformat, (self.start, self.end, day))
        if current < start:
            return 0
        if self.multiplier is None:
            return self.opening_units
        elapsed = (min(current, end) - start).days + 1
        days = (end - start).days + 1
        return min(self.opening_units, int(self.opening_units * self.multiplier * elapsed / days))

    def available(self, day, used):
        if type(used) is not int or not 0 <= used <= self.opening_units:
            raise ValueError("Invalid cumulative consumption")
        if not self.start <= day <= self.end:
            return 0
        return max(0, self.released(day) - used)


def admit_logged_plans(plans_by_loan, quota, *, day, seed=42, support=None):
    """Retain entire logged plans in a stable, outcome-independent hash order.

    Rejected plans become no-attempt. No installment is split, rerouted, or selected
    using its observed result. Retained observed money is subset accounting, not
    a counterfactual outcome for this hypothetical filtered policy.
    """
    if type(quota) is not int or quota < 0:
        raise ValueError("Invalid admission capacity")
    selected = {key: Plan() for key in plans_by_loan}
    report = {"quota_rejected_plans": 0, "calendar_rejected_plans": 0}
    ordered = sorted(
        plans_by_loan,
        key=lambda key: hashlib.sha256(f"{seed}|{day}|{key}".encode()).hexdigest(),
    )
    for key in ordered:
        plan = plans_by_loan[key]
        if support is not None and not all(
            support.check(provider, day)["admitted"] for provider in set(plan.providers)
        ):
            report["calendar_rejected_plans"] += 1
        elif plan.a_units > quota:
            report["quota_rejected_plans"] += 1
        else:
            selected[key] = plan
            quota -= plan.a_units
    return selected, quota, report


class CachedModel:
    """Share a day's immutable money calculations across sensitivity variants."""

    def __init__(self, model):
        self.model = model
        self.cache = {}

    def __getattr__(self, name):
        return getattr(self.model, name)

    def evaluate(self, loan, plan):
        key = loan, plan
        if key not in self.cache:
            self.cache[key] = self.model.evaluate(loan, plan)
        return self.cache[key]


def observed_contribution(history, loan, protocol):
    return float(
        (
            history.amount_cents
            / 100
            * commission_percent(loan.dpd)
            / 100
            * history.status.eq("success")
        ).sum()
        - history.provider.eq("B").sum() * float(protocol.values["b_fee"])
    )


def evaluate_horizon(data: Path, output: Path, protocol: Protocol):
    started = perf_counter()
    output.mkdir(parents=True, exist_ok=False)
    frame = load_history(data)
    client_frame = pd.read_csv(data / "clients.csv", dtype=str)
    clients = sorted(client_frame.client_id)
    caps = {row.client_id: cents(row.max_installment_amount) for row in client_frame.itertuples()}
    start, end = protocol.values["test_start"], protocol.values["test_end"]
    model = fit_for_day(frame, protocol, start)
    model.save(output / "model.json")
    support = CalendarSupport(frame, through=model.fitted_through)
    prior_units = int(frame.loc[frame.attempt_date.lt(start)].provider.eq("A").sum())
    opening = max(0, protocol.sample_capacity - prior_units)
    rates = {
        "unpaced": None,
        "paced_0.75": Decimal("0.75"),
        "paced_1.00": Decimal(1),
        "paced_1.25": Decimal("1.25"),
    }
    schedules = {
        name: ReleaseSchedule(opening, start, protocol.values["contract_end"], rate)
        for name, rate in rates.items()
    }
    variants = {
        f"{name}__calendar_{'on' if gate else 'off'}": {
            "schedule": schedule,
            "gate": gate,
            "candidate_used": 0,
            "legacy_used": 0,
        }
        for name, schedule in schedules.items()
        for gate in (False, True)
    }
    snapshots = pd.read_csv(data / "loan_snapshots.csv", dtype=str)
    snapshots = snapshots.loc[snapshots.snapshot_date.between(start, end)]
    historical = {
        key: group.sort_values("installment_index")
        for key, group in frame.loc[frame.attempt_date.between(start, end)].groupby(
            ["loan_id", "attempt_date"]
        )
    }
    totals = {name: {client: defaultdict(float) for client in clients} for name in variants}
    daily = []
    original = defaultdict(float)
    for day, group in snapshots.groupby("snapshot_date", sort=True):
        loans = [
            Loan(
                row.loan_id,
                row.client_id,
                day,
                cents(row.outstanding_balance),
                caps[row.client_id],
                int(row.days_past_due),
                "horizon",
            )
            for row in group.itertuples()
        ]
        lookup = {loan.loan_id: loan for loan in loans}
        logged = {
            loan.loan_id: Plan(tuple(history.amount_cents.astype(int)), tuple(history.provider))
            for loan in loans
            if (history := historical.get((loan.loan_id, day))) is not None
        }
        legacy_values = {}
        for key, plan in logged.items():
            loan = lookup[key]
            observed = observed_contribution(historical[key, day], loan, protocol)
            legacy_values[key] = observed, model.evaluate(loan, plan)["contribution"]
            original[loan.client_id] += observed
        cache = CachedModel(model)
        gated = CalendarSupportedModel(cache, support)
        # Keep the original conditional lender check identical across variants.
        required = zero_future_budget(frame, day, protocol, clients=clients)
        # The public selector API caches prepared plans; quota allocation is local
        # to each call. Reuse that immutable preparation for the four schedules.
        selectors = {
            False: EconomicSelector(cache, required),
            True: EconomicSelector(gated, required),
        }
        for name, state in variants.items():
            schedule = state["schedule"]
            available = schedule.available(day, state["candidate_used"])
            selector = selectors[state["gate"]]
            decisions, leftover = selector(loans, available, protocol)
            candidate_today = available - leftover
            state["candidate_used"] += candidate_today
            legacy_available = schedule.available(day, state["legacy_used"])
            retained, remaining, rejections = admit_logged_plans(
                logged,
                legacy_available,
                day=day,
                seed=protocol.values["seed"],
                support=support if state["gate"] else None,
            )
            legacy_today = legacy_available - remaining
            state["legacy_used"] += legacy_today
            candidate_b_today = 0
            for decision in decisions:
                values = totals[name][decision["client_id"]]
                values["candidate_contribution"] += decision["economics"]["contribution"]
                values["candidate_conservative_contribution"] += decision["economics"][
                    "conservative_contribution"
                ]
                values["candidate_a_units"] += decision["plan"]["providers"].count("A")
                values["candidate_b_units"] += decision["plan"]["providers"].count("B")
                candidate_b_today += decision["plan"]["providers"].count("B")
                if state["gate"] and not decision["economics"]["calendar_supported"]:
                    raise ValueError("Candidate violates recent-calendar admission")
            legacy_b_today = 0
            for key, plan in retained.items():
                if not plan.amounts:
                    continue
                values = totals[name][lookup[key].client_id]
                observed, estimated = legacy_values[key]
                values["retained_logged_observed_contribution"] += observed
                values["retained_logged_estimated_contribution"] += estimated
                values["retained_logged_a_units"] += plan.a_units
                values["retained_logged_b_units"] += plan.b_units
                legacy_b_today += plan.b_units
            for policy in ("candidate", "legacy"):
                if state[f"{policy}_used"] > schedule.released(day):
                    raise ValueError("Consumption exceeds cumulative release")
            daily.append(
                {
                    "variant": name,
                    "day": day,
                    "loans": len(loans),
                    "released_a": schedule.released(day),
                    "candidate_a_today": candidate_today,
                    "retained_logged_a_today": legacy_today,
                    "candidate_b_today": candidate_b_today,
                    "retained_logged_b_today": legacy_b_today,
                    "candidate_other_b_today": candidate_b_today
                    if calendar_type(day) == "other"
                    else 0,
                    "retained_logged_other_b_today": legacy_b_today
                    if calendar_type(day) == "other"
                    else 0,
                    "candidate_cumulative_a": state["candidate_used"],
                    "retained_logged_cumulative_a": state["legacy_used"],
                    "candidate_physical_remaining_a": opening - state["candidate_used"],
                    "retained_logged_physical_remaining_a": opening - state["legacy_used"],
                    "unmet_lender_constraints": sum(
                        item["status"] != "satisfied_expected" for item in selector.report.values()
                    ),
                    **rejections,
                }
            )
        print(f"Horizon sensitivities scored {day}: {len(loans)} loans, 8 variants", flush=True)
    days = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    contract_days = (
        date.fromisoformat(protocol.values["contract_end"])
        - date.fromisoformat(protocol.values["contract_start"])
    ).days + 1
    fixed = float(protocol.sample_upfront) * days / contract_days
    per_client, aggregates = [], []
    contribution_columns = (
        "candidate",
        "candidate_conservative",
        "retained_logged_observed",
        "retained_logged_estimated",
    )
    unit_columns = (
        "candidate_a_units",
        "candidate_b_units",
        "retained_logged_a_units",
        "retained_logged_b_units",
    )
    for name, values_by_client in totals.items():
        for client in clients:
            values = values_by_client[client]
            row = {
                "variant": name,
                "client_id": client,
                "allocated_fixed_A_cost": fixed / len(clients),
                "original_observed_legacy_margin": original[client] - fixed / len(clients),
            }
            for prefix in contribution_columns:
                row[prefix + "_margin"] = values[prefix + "_contribution"] - fixed / len(clients)
            row |= {column: int(values[column]) for column in unit_columns}
            per_client.append(row)
        selected_rows = [row for row in per_client if row["variant"] == name]
        aggregate = {
            "variant": name,
            "calendar_gate": variants[name]["gate"],
            "released_a_at_test_end": variants[name]["schedule"].released(end),
        }
        for column in (
            "allocated_fixed_A_cost",
            "original_observed_legacy_margin",
            *(prefix + "_margin" for prefix in contribution_columns),
            *unit_columns,
        ):
            aggregate[column] = sum(row[column] for row in selected_rows)
        aggregate["same_model_conditional_difference"] = (
            aggregate["candidate_margin"] - aggregate["retained_logged_estimated_margin"]
        )
        aggregate["candidate_share_opening_a"] = (
            aggregate["candidate_a_units"] / opening if opening else 0
        )
        for column in (
            "candidate_other_b_today",
            "retained_logged_other_b_today",
            "quota_rejected_plans",
            "calendar_rejected_plans",
        ):
            aggregate[column.removesuffix("_today")] = sum(
                row[column] for row in daily if row["variant"] == name
            )
        aggregates.append(aggregate)
    pd.DataFrame(daily).to_csv(output / "daily.csv", index=False)
    pd.DataFrame(per_client).to_csv(output / "per_client.csv", index=False, float_format="%.6f")
    pd.DataFrame(aggregates).to_csv(output / "scenarios.csv", index=False, float_format="%.6f")
    summary = {
        "scope": "Post-inspection April conditional quota/admission sensitivities; not a contract forecast",
        "selector_version": EconomicSelector.version,
        "model_hash": model.model_hash,
        "model_through": model.fitted_through,
        "initial_a_consumed": prior_units,
        "prior_capacity_overage": prior_units > protocol.sample_capacity,
        "opening_a_remaining": opening,
        "release_start": start,
        "release_end": protocol.values["contract_end"],
        "april_fixed_cost": fixed,
        "original_observed_legacy_margin": sum(original.values()) - fixed,
        "calendar_admission": [
            support.check(provider, f"{start[:7]}-{day:02d}")
            for provider in ("A", "B")
            for day in (1, 2, 15, monthrange(int(start[:4]), int(start[5:7]))[1])
        ],
        "runtime_seconds": perf_counter() - started,
        "scenarios": aggregates,
        "protocol": protocol.values,
        "source_sha256": {
            name: hashlib.sha256((data / name).read_bytes()).hexdigest()
            for name in ("clients.csv", "loan_snapshots.csv", "payment_attempts.csv")
        },
        "limitations": [
            "Same fixed cumulative release schedule for both policies; independent consumption ledgers and unspent carryover.",
            "Opening capacity and schedule fixed at test start, not dynamically renormalized from later use.",
            "0.75 reserves a quarter through expiry; 1.25 releases earlier and still clips at total capacity.",
            "Logged plans admitted whole by hash(seed, day, loan_id), never observed outcomes or revenue.",
            "Retained logged observed margin is accounting for a selected subset, not its counterfactual policy value.",
            "Calendar sensitivity gates both policies using only pretest pure-plan exposure; causal support remains unproved.",
            "All variants use the original daily lender budgets from supplied legacy history, not simulated candidate feedback.",
            "Legacy future snapshots are held fixed; changes to future balances or portfolio exits are not simulated.",
            "Identical monthly prepaid allocation cancels in differences; pacing is not an extra accounting cost.",
            "No causal decomposition attributes the original gap to front-loading, targeting or response-model bias.",
            "May-June demand and outcomes are absent; no optimal pacing or six-month profit is established.",
        ],
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (output / "README.md").write_text(
        "# Horizon and recent-calendar sensitivities\n\n"
        + summary["scope"]
        + ". The original observed benchmark is preserved in every row.\n\n"
        + "See scenarios.csv, daily.csv and per_client.csv. Both policies receive the same "
        "cumulative release and calendar admission. Filtered legacy money is a retained-log "
        "accounting diagnostic, not measured counterfactual improvement.\n\n"
        + "\n".join("- " + item for item in summary["limitations"])
        + "\n",
        encoding="utf-8",
    )
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--config", default="conf/protocol.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evaluate_horizon(args.data_dir, args.output, Protocol.load(args.config))


if __name__ == "__main__":
    main()
