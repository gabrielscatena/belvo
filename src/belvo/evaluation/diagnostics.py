"""Predefined calibration slices and overlap diagnostics, never a causal correction."""

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from belvo.config import Protocol, commission_percent
from belvo.domain import Loan, Plan
from belvo.models.calendar_support import CalendarSupport, calendar_type
from belvo.models.empirical import EmpiricalModel, fit_for_day, load_history

CELL = ["client_id", "provider", "count", "band", "fraction", "pure"]
SUPPORT = ["client_id", "provider", "count", "band", "fraction", "calendar", "amount_bucket"]


def amount_edges(frame, through):
    sample = frame.loc[frame.attempt_date.le(through), "amount_cents"]
    if sample.empty:
        raise ValueError("No pre-validation amounts for diagnostic buckets")
    cuts = np.unique(np.quantile(sample.astype(float), np.linspace(0, 1, 11)))[1:-1]
    return [-np.inf, *cuts.tolist(), np.inf]


def add_strata(frame, edges):
    result = frame.copy()
    result["calendar"] = result.attempt_date.map(calendar_type)
    result["amount_bucket"] = pd.cut(
        result.amount_cents, edges, labels=False, include_lowest=True
    ).astype(int)
    return result


def history_features(frame, delay):
    """Date-only known submissions through D-1, known failures through D-delay.

    Counts cover the observed window only: zero does not mean no lifetime history.
    """
    if frame.empty:
        return pd.DataFrame(
            columns=["loan_id", "attempt_date", "observed_failure_bucket", "recency_bucket"]
        )
    work = frame.assign(failed=frame.status.eq("failed").astype(int))
    events = (
        work.groupby(["loan_id", "attempt_date"], as_index=False)
        .agg(failures=("failed", "sum"))
        .sort_values(["loan_id", "attempt_date"])
    )
    events["ordinal"] = events.attempt_date.map(lambda x: date.fromisoformat(x).toordinal())
    events["failures"] = events.groupby("loan_id").failures.cumsum()
    left = events[["loan_id", "attempt_date", "ordinal"]].sort_values("ordinal")
    known = events[["loan_id", "ordinal", "failures"]].rename(columns={"ordinal": "available"})
    known["available"] += delay
    prior = pd.merge_asof(
        left,
        known.sort_values("available"),
        left_on="ordinal",
        right_on="available",
        by="loan_id",
        direction="backward",
    )
    submitted = events[["loan_id", "ordinal"]].rename(columns={"ordinal": "last_submission"})
    submitted["available"] = submitted.last_submission + 1
    prior = pd.merge_asof(
        prior.sort_values("ordinal"),
        submitted.sort_values("available"),
        left_on="ordinal",
        right_on="available",
        by="loan_id",
        direction="backward",
        suffixes=("", "_submission"),
    )
    failures = prior.failures.fillna(0)
    recency = prior.ordinal - prior.last_submission
    prior["observed_failure_bucket"] = np.select(
        [failures.eq(0), failures.le(2)], ["0_observed", "1_2_observed"], default="3plus_observed"
    )
    prior["recency_bucket"] = np.select(
        [recency.isna(), recency.le(2), recency.le(7)],
        ["no_observed_submission", "1_2_days", "3_7_days"],
        default="8plus_days",
    )
    return prior[["loan_id", "attempt_date", "observed_failure_bucket", "recency_bucket"]]


def score_attempts(frame, model, start, end):
    """Call the actual estimator once per equivalent fitted-cell key."""
    sample = frame.loc[frame.attempt_date.between(start, end)].copy()
    estimates = []
    for row in sample.drop_duplicates(CELL).itertuples():
        count = int(row.count)
        base, remainder = divmod(int(row.plan_total), count)
        amounts = tuple(base + (i < remainder) for i in range(count))
        providers = (row.provider,) * count
        if not row.pure:
            providers = providers[:-1] + ("B" if row.provider == "A" else "A",)
        loan = Loan(
            row.loan_id,
            row.client_id,
            row.attempt_date,
            int(row.balance_cents),
            int(row.cap_cents),
            int(row.dpd),
            "calibration",
        )
        estimate = model.estimate(loan, Plan(amounts, providers), row.provider)
        estimates.append(
            {key: getattr(row, key) for key in CELL}
            | {"prediction": estimate.mean, "coarse_supported": estimate.supported}
        )
    if sample.empty:
        return sample
    sample = sample.merge(pd.DataFrame(estimates), on=CELL, validate="many_to_one")
    sample["success"] = sample.status.eq("success").astype(int)
    sample["squared_error"] = (sample.prediction - sample.success) ** 2
    sample["observed_commission"] = sample.amount_cents / 100 * sample.band / 100 * sample.success
    sample["estimated_commission"] = (
        sample.amount_cents / 100 * sample.band / 100 * sample.prediction
    )
    return sample


def calibration_slices(scored, period):
    if scored.empty:
        return pd.DataFrame(
            columns=[
                "period",
                "slice",
                "segment",
                "attempts",
                "successes",
                "observed_commission",
                "estimated_commission",
            ]
        )
    records = []
    for columns in (
        ["provider"],
        ["amount_bucket"],
        ["calendar"],
        ["client_id"],
        ["observed_failure_bucket"],
        ["recency_bucket"],
        ["provider", "amount_bucket", "calendar"],
    ):
        for key, group in scored.groupby(columns, observed=True, sort=True):
            key = key if isinstance(key, tuple) else (key,)
            observed = float(group.observed_commission.sum())
            predicted = float(group.estimated_commission.sum())
            records.append(
                {
                    "period": period,
                    "slice": "+".join(columns),
                    "segment": "/".join(str(v) for v in key),
                    "attempts": len(group),
                    "successes": int(group.success.sum()),
                    "observed_success_rate": float(group.success.mean()),
                    "estimated_success_rate": float(group.prediction.mean()),
                    "brier": float(group.squared_error.mean()),
                    "observed_commission": observed,
                    "estimated_commission": predicted,
                    "commission_error": predicted - observed,
                    "estimated_to_observed_commission": predicted / observed if observed else None,
                }
            )
    return pd.DataFrame(records)


def support_counts(training, rows):
    joint = training.groupby(SUPPORT, observed=True).size().rename("joint_training_attempts")
    calendar = (
        training.groupby(["provider", "calendar"]).size().rename("provider_calendar_attempts")
    )
    return (
        rows.join(joint, on=SUPPORT)
        .join(calendar, on=["provider", "calendar"])
        .fillna({"joint_training_attempts": 0, "provider_calendar_attempts": 0})
    )


def candidate_slices(rows, frame, edges, model):
    """Inspect actual chosen debit amounts, not totals inferred from estimated revenue."""
    records = []
    for row in rows.itertuples():
        amounts = json.loads(row.candidate_amounts_cents)
        providers = json.loads(row.candidate_providers)
        for amount, provider in zip(amounts, providers, strict=True):
            total = sum(amounts)
            count = row.candidate_a + row.candidate_b
            fraction = min(
                4,
                max(
                    1, int(total * 4 / max(min(row.balance_cents, count * row.cap_cents), 1) + 0.5)
                ),
            )
            records.append(
                {
                    "client_id": row.client_id,
                    "provider": provider,
                    "count": count,
                    "band": commission_percent(row.dpd),
                    "fraction": fraction,
                    "attempt_date": row.day,
                    "amount_cents": amount,
                }
            )
    if not records:
        return pd.DataFrame(
            columns=[
                "provider",
                "calendar",
                "amount_bucket",
                "attempts",
                "mean_amount_cents",
                "any_history_calendar_attempts",
                "outside_calendar_support",
                "zero_any_history_calendar_support",
                "recent_calendar_training_attempts",
                "recent_calendar_months_observed",
                "recent_calendar_qualifying_months",
                "outside_recent_calendar_support",
                "weak_recent_calendar_support",
                "zero_joint_support",
                "below_100_joint_attempts",
            ]
        )
    actions = add_strata(pd.DataFrame(records), edges)
    train = add_strata(frame.loc[frame.attempt_date.le(model.fitted_through) & frame.pure], edges)
    actions = support_counts(train, actions)
    recent_support = CalendarSupport(frame, model.fitted_through)
    calendar_rows = []
    for row in (
        actions[["provider", "calendar", "attempt_date"]]
        .drop_duplicates(["provider", "calendar"])
        .itertuples()
    ):
        support = recent_support.check(row.provider, row.attempt_date)
        calendar_rows.append(
            {
                "provider": row.provider,
                "calendar": row.calendar,
                "recent_calendar_attempts": support["recent_attempts"],
                "recent_calendar_months": support["recent_months_observed"],
                "recent_calendar_qualifying_months": support["recent_qualifying_months"],
                "recent_calendar_admitted": support["admitted"],
            }
        )
    actions = actions.merge(
        pd.DataFrame(calendar_rows), on=["provider", "calendar"], validate="many_to_one"
    )
    report = actions.groupby(["provider", "calendar", "amount_bucket"], as_index=False).agg(
        attempts=("amount_cents", "size"),
        mean_amount_cents=("amount_cents", "mean"),
        any_history_calendar_attempts=("provider_calendar_attempts", "first"),
        outside_calendar_support=("provider_calendar_attempts", lambda x: int(x.eq(0).sum())),
        zero_any_history_calendar_support=(
            "provider_calendar_attempts",
            lambda x: int(x.eq(0).sum()),
        ),
        recent_calendar_training_attempts=("recent_calendar_attempts", "first"),
        recent_calendar_months_observed=("recent_calendar_months", "first"),
        recent_calendar_qualifying_months=("recent_calendar_qualifying_months", "first"),
        outside_recent_calendar_support=("recent_calendar_admitted", lambda x: int((~x).sum())),
        weak_recent_calendar_support=("recent_calendar_admitted", lambda x: int((~x).sum())),
        zero_joint_support=("joint_training_attempts", lambda x: int(x.eq(0).sum())),
        below_100_joint_attempts=("joint_training_attempts", lambda x: int(x.lt(100).sum())),
    )
    return report


def run(data, output, protocol, evaluation=None):
    output.mkdir(parents=True, exist_ok=False)
    frame = load_history(data)
    edges = amount_edges(frame, protocol.known_attempt_through(protocol.values["validation_start"]))
    frame = add_strata(frame, edges).merge(
        history_features(frame, protocol.values["outcome_delay_days"]),
        on=["loan_id", "attempt_date"],
        validate="many_to_one",
    )
    tables = []
    for period, start, end in (
        ("validation", protocol.values["validation_start"], protocol.values["validation_end"]),
        ("test", protocol.values["test_start"], protocol.values["test_end"]),
    ):
        model = fit_for_day(frame, protocol, start)
        tables.append(calibration_slices(score_attempts(frame, model, start, end), period))
    pd.concat(tables).to_csv(output / "calibration_slices.csv", index=False)
    pd.crosstab(frame.attempt_date, frame.provider).to_csv(output / "provider_by_date.csv")
    candidate_support_metadata = None
    if evaluation is not None:
        rows = pd.read_csv(evaluation / "loan_day_estimates.csv")
        model = EmpiricalModel.from_artifact(json.loads((evaluation / "model.json").read_text()))
        candidate_slices(rows, frame, edges, model).to_csv(
            output / "candidate_support.csv", index=False
        )
        support = CalendarSupport(frame, model.fitted_through)
        candidate_support_metadata = {
            "model_through": model.fitted_through,
            "recent_months": list(support.recent_months),
            "minimum_attempts_total_and_per_qualifying_month": support.minimum_attempts,
            "minimum_qualifying_months": support.minimum_months,
            "evaluation_dir": str(evaluation),
            "model_hash": model.model_hash,
        }
    metadata = {
        "amount_edges_cents": [v if np.isfinite(v) else None for v in edges],
        "buckets_fixed_through": protocol.known_attempt_through(
            protocol.values["validation_start"]
        ),
        "calendar_definition": "month_start=1,midmonth=15/16,month_end=last;others=other;not actual payday",
        "calendar_support_definition": {
            "outside_calendar_support": "compatibility alias for zero_any_history_calendar_support; zero does not establish adequate support",
            "zero_any_history_calendar_support": "count of candidate attempts with zero pure-plan provider/calendar exposures through model cutoff",
            "weak_recent_calendar_support": "count of candidate attempts failing >=100 pure exposures total and >=1 recent month containing >=100 exposures within last two calendar months through cutoff",
            "outside_recent_calendar_support": "alias for weak_recent_calendar_support",
            "recent_months": "two calendar months ending in cutoff month; latest month can be partial (February + March through March 30 for April model)",
            "restriction": "exposure-based sensitivity only, no response outcomes used and no causal guarantee",
        },
        "candidate_support": candidate_support_metadata,
        "history": "observed submissions before D, failures through D-delay; left-truncated",
        "warning": "Exploratory slices after April inspection; no model retuning, causal identification or calibrated bias range",
        "source_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in data.glob("*.csv")
        },
    }
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--config", default="conf/protocol.json")
    parser.add_argument("--evaluation-dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.data_dir, args.output, Protocol.load(args.config), args.evaluation_dir)
    print(args.output)


if __name__ == "__main__":
    main()
