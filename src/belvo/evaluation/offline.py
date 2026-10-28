"""Conditional one-step replay, observed accounting and explicitly scoped model ceiling."""

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from belvo.config import Protocol, commission_percent
from belvo.domain import Loan, Plan, cents, plans
from belvo.models.empirical import fit_for_day, load_history
from belvo.optimization.select import EconomicSelector, zero_future_budget


def calibration(frame, model, start, end):
    groups = frame.loc[frame.attempt_date.between(start, end)].groupby(["loan_id", "attempt_date"])
    values = defaultdict(list)
    for (_, day), group in groups:
        first = group.iloc[0]
        loan = Loan(
            first.loan_id,
            first.client_id,
            day,
            int(first.balance_cents),
            int(first.cap_cents),
            int(first.dpd),
            "calibration",
        )
        group = group.sort_values("installment_index")
        plan = Plan(tuple(group.amount_cents.astype(int)), tuple(group.provider))
        for row in group.itertuples():
            p = model.estimate(loan, plan, row.provider)
            values[row.provider].append((p.mean, int(row.status == "success"), p.supported))
    result = []
    for provider, rows in sorted(values.items()):
        array = np.asarray(rows, dtype=float)
        result.append(
            {
                "provider": provider,
                "attempts": len(rows),
                "observed_success_rate": float(array[:, 1].mean()),
                "predicted_success_rate": float(array[:, 0].mean()),
                "brier": float(((array[:, 0] - array[:, 1]) ** 2).mean()),
                "supported_fraction": float(array[:, 2].mean()),
            }
        )
    return result


def bootstrap_loans(rows, fixed, seed=42, repetitions=400):
    cluster = rows.groupby("loan_id")[["candidate", "legacy_estimated", "legacy_observed"]].sum()
    matrix = cluster.to_numpy()
    rng = np.random.default_rng(seed)
    totals = np.array(
        [
            matrix[rng.integers(len(matrix), size=len(matrix))].sum(axis=0)
            for _ in range(repetitions)
        ]
    )
    return {
        "unit": "loan trajectory",
        "repetitions": repetitions,
        "candidate_margin_interval": np.quantile(totals[:, 0] - fixed, [0.025, 0.975]).tolist(),
        "estimated_uplift_interval": np.quantile(
            totals[:, 0] - totals[:, 1], [0.025, 0.975]
        ).tolist(),
        "warning": "Conditional resampling variation only; excludes causal/model/arrival uncertainty",
    }


def audit_outputs(output: Path):
    """Reconcile published totals and expose the limits most relevant to rollout."""
    summary = json.loads((output / "summary.json").read_text())
    lenders = pd.read_csv(output / "per_client.csv", index_col="client_id")
    rows = pd.read_csv(output / "loan_day_estimates.csv")
    for total, column in (
        ("legacy_observed_april_margin", "legacy_observed_april_margin"),
        ("candidate_estimated_april_margin", "candidate_april_margin"),
        ("relaxed_model_april_ceiling", "model_relaxed_upper_april_margin"),
    ):
        if abs(float(lenders[column].sum()) - summary[total]) > 0.0001:
            raise ValueError(f"Lender totals do not reconcile: {column}")
    if (
        summary["candidate_estimated_april_margin"]
        > summary["relaxed_model_april_ceiling"] + 0.0001
    ):
        raise ValueError("Candidate exceeds its declared model relaxation")
    summary["lender_bootstrap"] = {
        client: bootstrap_loans(group, summary["april_fixed_cost"] / len(lenders))
        for client, group in rows.groupby("client_id")
    }
    summary["estimated_gap_to_relaxed_ceiling"] = (
        summary["relaxed_model_april_ceiling"] - summary["candidate_estimated_april_margin"]
    )
    summary["legacy_estimated_margin_error"] = (
        summary["legacy_estimated_april_margin"] - summary["legacy_observed_april_margin"]
    )
    summary["rollout_approved"] = False
    summary["rollout_blockers"] = [
        f"Exact legacy action match {summary['exact_legacy_action_match_fraction']:.2%}; coarse cells are not causal support",
        f"Legacy monetary calibration error {summary['legacy_estimated_margin_error']:.2f}; model bias remains unquantified",
        f"Nonpositive full-upfront coverage lenders {summary['negative_candidate_lenders_coverage']}; six-month profit is unestablished",
        "May-June continuation depends on absent data and remaining capacity; see scenario flags",
        "Different actions change future balances; this is not a sequential intervention evaluation",
    ]
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    report = output / "results.md"
    marker = "\n## Rollout decision\n"
    text = report.read_text(encoding="utf-8").split(marker)[0]
    text += marker + "\n**Not approved for live use.**\n\n"
    text += f"Exact action match is {summary['exact_legacy_action_match_fraction']:.2%}; "
    text += "historical bin support is substantially weaker than intervention identification.\n"
    text += f"Legacy monetary margin error is {summary['legacy_estimated_margin_error']:,.2f}. "
    text += "The very large projected uplift is not established business value.\n"
    text += f"Nonpositive full-upfront coverage lenders: {summary['negative_candidate_lenders_coverage']}.\n"
    text += "May-June continuation scenarios that exceed quota are explicitly marked infeasible;\n"
    text += "they cannot justify a constant-composition contract projection.\n"
    text += (
        "The best feasible restricted one-step policy is only a model-based achievable estimate;\n"
    )
    text += "the true sequential six-month ceiling cannot be identified from this legacy dataset.\n"
    report.write_text(text, encoding="utf-8")
    return summary


def evaluate(data: Path, output: Path, protocol: Protocol):
    output.mkdir(parents=True, exist_ok=False)
    frame = load_history(data)
    clients = sorted(pd.read_csv(data / "clients.csv", dtype=str).client_id)
    final_model = fit_for_day(frame, protocol, protocol.values["test_start"])
    validation_model = fit_for_day(frame, protocol, protocol.values["validation_start"])
    final_model.save(output / "model.json")
    diagnostics = {
        "validation": calibration(
            frame,
            validation_model,
            protocol.values["validation_start"],
            protocol.values["validation_end"],
        ),
        "test": calibration(
            frame, final_model, protocol.values["test_start"], protocol.values["test_end"]
        ),
    }
    print("Validation and test calibration complete", flush=True)
    snapshots = pd.read_csv(data / "loan_snapshots.csv", dtype=str)
    caps = {
        r.client_id: cents(r.max_installment_amount)
        for r in pd.read_csv(data / "clients.csv", dtype=str).itertuples()
    }
    selected = snapshots.loc[
        snapshots.snapshot_date.between(protocol.values["test_start"], protocol.values["test_end"])
    ].copy()
    prior = frame.loc[frame.attempt_date.lt(protocol.values["test_start"])]
    initial_consumed = int(prior.provider.eq("A").sum())
    quota = max(0, protocol.sample_capacity - initial_consumed)
    prior_overage = initial_consumed > protocol.sample_capacity
    baseline_groups = {
        key: group
        for key, group in frame.loc[
            frame.attempt_date.between(protocol.values["test_start"], protocol.values["test_end"])
        ].groupby(["loan_id", "attempt_date"])
    }
    rows, daily, exact_matches = [], [], 0
    for day, group in selected.groupby("snapshot_date", sort=True):
        loans = [
            Loan(
                r.loan_id,
                r.client_id,
                day,
                cents(r.outstanding_balance),
                caps[r.client_id],
                int(r.days_past_due),
                "offline",
            )
            for r in group.itertuples()
        ]
        selector = EconomicSelector(final_model, zero_future_budget(frame, day, protocol))
        decisions, quota = selector(loans, quota, protocol)
        lookup = {r["loan_id"]: r for r in decisions}
        daily.append(
            {
                "day": day,
                "loans": len(loans),
                "remaining_a": quota,
                "unmet_lender_constraints": sum(
                    r["status"] != "satisfied_expected" for r in selector.report.values()
                ),
            }
        )
        print(f"Scoring {day}: {len(loans)} loans; A remaining {quota}", flush=True)
        for loan in loans:
            decision = lookup[loan.loan_id]
            candidate = decision["economics"]
            best_mean = max(
                (
                    final_model.evaluate(loan, p)["contribution"]
                    for p in plans(
                        loan,
                        protocol.values["amount_fractions"],
                        protocol.values["max_installments"],
                    )
                    if (not p.a_units or protocol.a_available(day))
                    and (not p.amounts or final_model.evaluate(loan, p)["supported"])
                ),
                default=0,
            )
            historical = baseline_groups.get((loan.loan_id, day))
            observed, estimated, a_legacy, b_legacy, exact = 0.0, 0.0, 0, 0, False
            if historical is not None:
                historical = historical.sort_values("installment_index")
                legacy_plan = Plan(
                    tuple(historical.amount_cents.astype(int)), tuple(historical.provider)
                )
                observed = float(
                    (
                        historical.amount_cents
                        / 100
                        * commission_percent(loan.dpd)
                        / 100
                        * historical.status.eq("success")
                    ).sum()
                    - float(protocol.values["b_fee"]) * historical.provider.eq("B").sum()
                )
                estimated = final_model.evaluate(loan, legacy_plan)["contribution"]
                a_legacy, b_legacy = legacy_plan.a_units, legacy_plan.b_units
                exact = list(legacy_plan.amounts) == list(decision["plan"]["amounts"]) and list(
                    legacy_plan.providers
                ) == list(decision["plan"]["providers"])
            elif not decision["plan"]["amounts"]:
                exact = True
            exact_matches += exact
            rows.append(
                {
                    "loan_id": loan.loan_id,
                    "client_id": loan.client_id,
                    "day": day,
                    "legacy_observed": observed,
                    "legacy_estimated": estimated,
                    "candidate": candidate["contribution"],
                    "candidate_conservative": candidate["conservative_contribution"],
                    "model_relaxed_upper": best_mean,
                    "candidate_a": decision["plan"]["providers"].count("A"),
                    "candidate_b": decision["plan"]["providers"].count("B"),
                    "legacy_a": a_legacy,
                    "legacy_b": b_legacy,
                    "candidate_supported": candidate["supported"],
                }
            )
    row_frame = pd.DataFrame(rows)
    days = (
        date.fromisoformat(protocol.values["test_end"])
        - date.fromisoformat(protocol.values["test_start"])
    ).days + 1
    contract_days = (
        date.fromisoformat(protocol.values["contract_end"])
        - date.fromisoformat(protocol.values["contract_start"])
    ).days + 1
    april_fixed = float(protocol.sample_upfront) * days / contract_days
    by_client = row_frame.groupby("client_id").sum(numeric_only=True).reindex(clients, fill_value=0)
    for column in (
        "legacy_observed",
        "legacy_estimated",
        "candidate",
        "candidate_conservative",
        "model_relaxed_upper",
    ):
        by_client[column + "_april_margin"] = by_client[column] - april_fixed / len(clients)
    # Full commitment applied once to Jan-March observed contribution plus April estimate.
    prior_contrib = (
        prior.assign(
            contribution=prior.amount_cents / 100 * prior.band / 100 * prior.status.eq("success")
            - prior.provider.eq("B") * float(protocol.values["b_fee"])
        )
        .groupby("client_id")
        .contribution.sum()
    )
    by_client["candidate_jan_apr_coverage"] = (
        prior_contrib.reindex(clients, fill_value=0)
        + by_client.candidate
        - float(protocol.sample_upfront) / len(clients)
    )
    by_client["legacy_jan_apr_coverage"] = (
        prior_contrib.reindex(clients, fill_value=0)
        + by_client.legacy_observed
        - float(protocol.sample_upfront) / len(clients)
    )
    by_client.to_csv(output / "per_client.csv", float_format="%.6f")
    pd.DataFrame(daily).to_csv(output / "daily.csv", index=False)
    # Do not publish all loan-level payloads; reproducible cluster inputs stay local.
    row_frame.to_csv(output / "loan_day_estimates.csv", index=False)
    summary = {
        "scope": "April conditional one-step replay on legacy states, sample scale",
        "test_days": days,
        "loan_days": len(rows),
        "loans": int(row_frame.loan_id.nunique()),
        "model_through": final_model.fitted_through,
        "initial_a_consumed": initial_consumed,
        "remaining_a": quota,
        "prior_capacity_overage": prior_overage,
        "april_fixed_cost": april_fixed,
        "legacy_observed_april_margin": float(by_client.legacy_observed_april_margin.sum()),
        "legacy_estimated_april_margin": float(by_client.legacy_estimated_april_margin.sum()),
        "candidate_estimated_april_margin": float(by_client.candidate_april_margin.sum()),
        "candidate_conservative_april_margin": float(
            by_client.candidate_conservative_april_margin.sum()
        ),
        "relaxed_model_april_ceiling": float(by_client.model_relaxed_upper_april_margin.sum()),
        "candidate_a_units": int(by_client.candidate_a.sum()),
        "candidate_b_units": int(by_client.candidate_b.sum()),
        "exact_legacy_action_match_fraction": exact_matches / len(rows),
        "negative_candidate_lenders_april": by_client.index[
            by_client.candidate_april_margin.le(0)
        ].tolist(),
        "negative_candidate_lenders_coverage": by_client.index[
            by_client.candidate_jan_apr_coverage.le(0)
        ].tolist(),
        "candidate_jan_apr_coverage": float(by_client.candidate_jan_apr_coverage.sum()),
        "legacy_jan_apr_coverage": float(by_client.legacy_jan_apr_coverage.sum()),
        "ceiling_scope": "Restricted supported-plan mean upper bound, relaxing A capacity and lender constraints. Not a causal or six-month achievable guarantee.",
        "calibration": diagnostics,
        "bootstrap": bootstrap_loans(row_frame, april_fixed, protocol.values["seed"]),
        "protocol": protocol.values,
        "source_sha256": {
            name: hashlib.sha256((data / name).read_bytes()).hexdigest()
            for name in ("clients.csv", "loan_snapshots.csv", "payment_attempts.csv")
        },
    }
    sensitivities = []
    for demand in (0.5, 1.0, 1.5):
        for capacity_scale in (0.0, 0.5, 1.0, 1.5):
            required = int(by_client.candidate_a.sum() * demand)
            available = int(protocol.sample_capacity * capacity_scale) - initial_consumed
            valid = available >= required
            sensitivities.append(
                {
                    "kind": "April frozen-action volume/quota stress (no reoptimization)",
                    "demand_multiplier": demand,
                    "capacity_multiplier": capacity_scale,
                    "capacity_satisfied": valid,
                    "required_a": required,
                    "estimated_margin": float(by_client.candidate.sum()) * demand - april_fixed
                    if valid
                    else None,
                }
            )
    training = frame.loc[frame.attempt_date.le("2026-02-27")].groupby("client_id").size()
    for allocation in ("equal_lenders", "training_attempts"):
        weights = (
            pd.Series(1 / len(clients), index=clients)
            if allocation == "equal_lenders"
            else training.reindex(clients, fill_value=0) / training.sum()
        )
        for client in clients:
            sensitivities.append(
                {
                    "kind": "Fixed-action allocation sensitivity",
                    "allocation": allocation,
                    "client_id": client,
                    "estimated_margin": float(
                        by_client.loc[client, "candidate"] - april_fixed * weights[client]
                    ),
                }
            )
    pd.DataFrame(sensitivities).to_csv(output / "sensitivities.csv", index=False)
    may_june = []
    for demand in (0.5, 1.0, 1.5):
        future_a = int(by_client.candidate_a.sum() / days * 61 * demand)
        possible = future_a <= quota
        may_june.append(
            {
                "demand_multiplier": demand,
                "future_days": 61,
                "assumption": "Repeat April fixed-action daily composition; not a dynamic forecast",
                "future_a_units": future_a,
                "capacity_satisfied": possible,
                "candidate_contract_margin_projection": float(
                    by_client.candidate_jan_apr_coverage.sum()
                    + by_client.candidate.sum() / days * 61 * demand
                )
                if possible
                else None,
            }
        )
    summary["may_june_scenarios"] = may_june
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    report = [
        "# Offline results",
        "",
        summary["scope"],
        "",
        "| April margin, currency units | Sample | Full-book ×15 point estimate |",
        "|---|---:|---:|",
    ]
    for label, key in (
        ("Observed legacy", "legacy_observed_april_margin"),
        ("Estimated legacy", "legacy_estimated_april_margin"),
        ("Estimated candidate", "candidate_estimated_april_margin"),
        ("Conservative candidate stress", "candidate_conservative_april_margin"),
        ("Relaxed model ceiling", "relaxed_model_april_ceiling"),
    ):
        report.append(f"| {label} | {summary[key]:,.2f} | {summary[key] * 15:,.2f} |")
    report += [
        "",
        "The month allocates 30/181 of the fixed prepaid commitment equally by lender.",
        "This is a monthly reporting convention, not final contract profitability.",
        "",
        f"Nonpositive candidate lenders (April): {summary['negative_candidate_lenders_april']}.",
        f"Nonpositive lenders with full fixed cost in Jan–Apr coverage: {summary['negative_candidate_lenders_coverage']}.",
        "See per_client.csv; all lender amounts sum to their reported total.",
        "",
        "The candidate is estimated, not observed. Provider selection is confounded;",
        "coarse support bins and repeated snapshots cannot identify intervention effects.",
        "The ceiling relaxes constraints under the fitted model and restricted plans;",
        "it is not a certified achievable sequential/contract ceiling.",
        "Loan bootstrap intervals capture sampling variation conditional on the model;",
        "they exclude causal/model uncertainty. May–June is absent; projections that",
        "exceed quota have no reported margin and require reoptimization.",
        "",
        "Do not deploy solely from these results. Lender constraint warnings and",
        "out-of-policy action mismatch are production blockers, not hidden exceptions.",
    ]
    (output / "results.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    summary = audit_outputs(output)
    print(
        json.dumps(
            {
                key: summary[key]
                for key in (
                    "candidate_estimated_april_margin",
                    "legacy_observed_april_margin",
                    "relaxed_model_april_ceiling",
                    "negative_candidate_lenders_april",
                    "remaining_a",
                )
            }
        )
    )
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--config", default="conf/protocol.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or Path("reports/evaluation") / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    evaluate(args.data_dir, output, Protocol.load(args.config))


if __name__ == "__main__":
    main()
