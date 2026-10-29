"""Refit training-loan bootstrap, conditional on frozen evaluated action compositions.

This adds parameter resampling variation to fixed-action model estimates. It does
not identify provider effects, repair misspecification, reselect policies or simulate
counterfactual future balances. Twenty replicates are a diagnostic, not a precise CI.
"""

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from belvo.config import Protocol
from belvo.domain import Loan, Plan
from belvo.models.empirical import EmpiricalModel, load_history


def cluster_bootstrap_samples(frame, through, *, repetitions=20, seed=42):
    """Resample whole training loans, retaining all their available pure-plan labels."""
    if type(repetitions) is not int or not 2 <= repetitions <= 1000:
        raise ValueError("Require 2 through 1000 bootstrap repetitions")
    training = frame.loc[frame.attempt_date.le(through) & frame.pure].reset_index(drop=True)
    groups = list(training.groupby("loan_id", sort=True).indices.values())
    if not groups:
        raise ValueError("No available training-loan clusters")
    rng = np.random.default_rng(seed)
    for _ in range(repetitions):
        sampled = rng.integers(len(groups), size=len(groups))
        positions = np.concatenate([groups[index] for index in sampled])
        yield training.iloc[positions].copy()


def score_composition(model, cases, fixed):
    """Both policies pay their B attempt costs and the identical fixed commitment."""
    candidate, legacy, unsupported, attempts = 0.0, 0.0, 0, 0
    for loan, candidate_plan, legacy_plan in cases:
        value = model.evaluate(loan, candidate_plan)
        candidate += value["contribution"]
        legacy += model.evaluate(loan, legacy_plan)["contribution"]
        unsupported += bool(candidate_plan.amounts) and not value["supported"]
        attempts += bool(candidate_plan.amounts)
    return {
        "candidate_estimated_margin": candidate - fixed,
        "legacy_estimated_margin": legacy - fixed,
        "estimated_uplift": candidate - legacy,
        "candidate_unsupported_plan_fraction": unsupported / attempts if attempts else 0,
    }


def refit(frame, cases, protocol, through, fixed, *, repetitions=20, seed=42):
    """Return fixed-action estimates for training-cluster refits and scoped intervals."""
    if not cases:
        raise ValueError("No frozen action compositions to score")
    if through > protocol.known_attempt_through(min(loan.day for loan, _, _ in cases)):
        raise ValueError("Training cutoff includes unavailable labels")
    point_model = EmpiricalModel(protocol).fit(frame, through)
    point = score_composition(point_model, cases, fixed)
    rows = []
    for replicate, sample in enumerate(
        cluster_bootstrap_samples(frame, through, repetitions=repetitions, seed=seed)
    ):
        model = EmpiricalModel(protocol).fit(sample, through)
        rows.append(
            {
                "replicate": replicate,
                "model_hash": model.model_hash,
                "training_rows": len(sample),
                "distinct_training_loans": int(sample.loan_id.nunique()),
                **score_composition(model, cases, fixed),
            }
        )
    draws = pd.DataFrame(rows)
    intervals = {
        column: dict(
            zip(
                ("p025", "median", "p975"),
                draws[column].quantile([0.025, 0.5, 0.975]).tolist(),
                strict=True,
            )
        )
        for column in ("candidate_estimated_margin", "legacy_estimated_margin", "estimated_uplift")
    }
    return draws, {
        "scope": "Training-loan cluster refits of fixed candidate and legacy action compositions",
        "training_through": through,
        "training_loans": int(
            frame.loc[frame.attempt_date.le(through) & frame.pure].loan_id.nunique()
        ),
        "repetitions": repetitions,
        "seed": seed,
        "fixed_cost": fixed,
        "point_model_hash": point_model.model_hash,
        "point_estimates": point,
        "parameter_resampling_intervals": intervals,
        "policy_reselection": False,
        "counterfactual_state_simulation": False,
        "warnings": [
            "Only training-cluster parameter resampling; conditional on the original action choices",
            "Excludes confounding, structural model error, future demand and policy-selection uncertainty",
            "Frozen legacy balances and action compositions; not a sequential or six-month confidence interval",
            "Small replication counts have substantial Monte Carlo error; interval widening is not guaranteed",
            "A refit may lose cell support; fixed actions are still scored and support loss is reported",
        ],
        "protocol": protocol.values,
    }


def frozen_cases(frame, rows):
    """Use saved candidate actions and observed legacy plans on the same loan-days."""
    required = {
        "loan_id",
        "client_id",
        "day",
        "balance_cents",
        "cap_cents",
        "dpd",
        "candidate_amounts_cents",
        "candidate_providers",
    }
    if not required.issubset(rows.columns):
        raise ValueError("Evaluation lacks frozen action columns; rerun the evaluator")
    relevant = frame.loc[frame.attempt_date.isin(rows.day.unique())]
    historical = {
        key: group.sort_values("installment_index")
        for key, group in relevant.groupby(["loan_id", "attempt_date"])
    }
    cases = []
    for row in rows.itertuples():
        loan = Loan(
            str(row.loan_id),
            str(row.client_id),
            str(row.day),
            int(row.balance_cents),
            int(row.cap_cents),
            int(row.dpd),
            "frozen-refit",
        )
        amounts = tuple(json.loads(row.candidate_amounts_cents))
        providers = tuple(json.loads(row.candidate_providers))
        if (
            len(amounts) != len(providers)
            or any(
                type(amount) is not int or amount <= 0 or amount > loan.cap for amount in amounts
            )
            or sum(amounts) > loan.balance
            or any(provider not in ("A", "B") for provider in providers)
        ):
            raise ValueError("Unsafe frozen action composition")
        candidate = Plan(amounts, providers)
        group = historical.get((loan.loan_id, loan.day))
        legacy = (
            Plan()
            if group is None
            else Plan(tuple(group.amount_cents.astype(int)), tuple(group.provider))
        )
        cases.append((loan, candidate, legacy))
    return cases


def run(data, evaluation, output, *, repetitions=20, seed=42):
    started = time.perf_counter()
    if output.exists():
        raise FileExistsError(output)
    summary = json.loads((evaluation / "summary.json").read_text(encoding="utf-8"))
    artifact = json.loads((evaluation / "model.json").read_text(encoding="utf-8"))
    saved_model = EmpiricalModel.from_artifact(artifact)
    protocol = Protocol(summary["protocol"])
    if protocol.values != saved_model.protocol.values:
        raise ValueError("Evaluation and saved model have different protocols")
    for name, expected in summary["source_sha256"].items():
        if hashlib.sha256((data / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Evaluation source changed: {name}")
    frame = load_history(data)
    cases = frozen_cases(
        frame,
        pd.read_csv(
            evaluation / "loan_day_estimates.csv",
            dtype={
                "loan_id": str,
                "client_id": str,
                "day": str,
            },
        ),
    )
    draws, result = refit(
        frame,
        cases,
        protocol,
        saved_model.fitted_through,
        summary["april_fixed_cost"],
        repetitions=repetitions,
        seed=seed,
    )
    if result["point_model_hash"] != saved_model.model_hash:
        raise ValueError("Refit data does not reproduce the saved model")
    for point, published in (
        ("candidate_estimated_margin", "candidate_estimated_april_margin"),
        ("legacy_estimated_margin", "legacy_estimated_april_margin"),
    ):
        if abs(result["point_estimates"][point] - summary[published]) > 0.0001:
            raise ValueError(f"Frozen actions do not reproduce {published}")
    output.mkdir(parents=True, exist_ok=False)
    draws.to_csv(output / "refit_draws.csv", index=False)
    result["evaluation_directory"] = str(evaluation)
    result["selector_version"] = summary.get("selector_version")
    result["source_sha256"] = summary["source_sha256"]
    result["frozen_actions_sha256"] = hashlib.sha256(
        (evaluation / "loan_day_estimates.csv").read_bytes()
    ).hexdigest()
    result["runtime_seconds"] = time.perf_counter() - started
    (output / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--evaluation-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    result = run(
        args.data_dir,
        args.evaluation_dir,
        args.output,
        repetitions=args.repetitions,
        seed=args.seed,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
