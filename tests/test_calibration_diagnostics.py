import json

import numpy as np
import pandas as pd
import pytest

from belvo.config import Protocol
from belvo.domain import Loan, Plan
from belvo.evaluation.diagnostics import (
    add_strata,
    amount_edges,
    calendar_type,
    calibration_slices,
    candidate_slices,
    history_features,
    score_attempts,
    support_counts,
)
from belvo.models.empirical import EmpiricalModel


def frame():
    return pd.DataFrame(
        [
            {
                "attempt_id": str(i),
                "loan_id": "L1",
                "attempt_date": day,
                "client_id": "C1",
                "provider": "A",
                "count": 1,
                "band": 15,
                "fraction": 4,
                "pure": True,
                "status": outcome,
                "amount_cents": 10000,
                "plan_total": 10000,
                "cap_cents": 10000,
                "balance_cents": 10000,
                "dpd": 0,
            }
            for i, (day, outcome) in enumerate(
                [
                    ("2026-02-01", "success"),
                    ("2026-03-01", "failed"),
                    ("2026-03-02", "failed"),
                    ("2026-03-03", "success"),
                ]
            )
        ]
    )


def test_failure_and_submission_features_respect_different_availability():
    result = history_features(frame(), 2).set_index("attempt_date")
    assert result.loc["2026-02-01", "recency_bucket"] == "no_observed_submission"
    assert result.loc["2026-03-02", "recency_bucket"] == "1_2_days"
    assert result.loc["2026-03-02", "observed_failure_bucket"] == "0_observed"
    assert result.loc["2026-03-03", "observed_failure_bucket"] == "1_2_observed"
    changed = frame()
    changed.loc[changed.attempt_date.eq("2026-03-02"), "status"] = "success"
    assert history_features(changed, 2).equals(history_features(frame(), 2))


def test_diagnostic_predictions_and_money_match_public_estimator():
    original = frame()
    model = EmpiricalModel(Protocol.load()).fit(original, "2026-02-27")
    scored = score_attempts(original, model, "2026-03-01", "2026-03-03")
    loan = Loan("L1", "C1", "2026-03-01", 10000, 10000, 0, "v1")
    expected = model.evaluate(loan, Plan((10000,), ("A",)))["expected_revenue"]
    assert scored.estimated_commission.sum() == pytest.approx(3 * expected)
    assert scored.observed_commission.sum() == 15
    scored["calendar"] = "month_start"
    scored["amount_bucket"] = 0
    scored["observed_failure_bucket"] = "0_observed"
    scored["recency_bucket"] = "1_2_days"
    slices = calibration_slices(scored, "validation")
    provider = slices.loc[slices.slice.eq("provider")].iloc[0]
    assert provider.observed_commission == 15
    assert provider.commission_error == pytest.approx(3 * expected - 15)


def test_amount_buckets_are_fixed_before_validation_and_calendar_is_only_a_proxy():
    old = frame()
    changed = pd.concat([old, old.iloc[:1].assign(attempt_date="2026-04-01", amount_cents=999999)])
    assert amount_edges(old, "2026-02-27") == amount_edges(changed, "2026-02-27")
    assert calendar_type("2026-01-03") == "other"
    assert calendar_type("2026-02-28") == "month_end"
    assert calendar_type("2026-03-15") == "midmonth"


def test_expanded_support_flags_missing_calendar_even_if_original_cell_exists():
    edges = [-np.inf, np.inf]
    training = add_strata(frame().iloc[:1].assign(provider="B"), edges)
    candidate = add_strata(frame().iloc[:1].assign(provider="B", attempt_date="2026-04-02"), edges)
    support = support_counts(training, candidate)
    assert support.provider_calendar_attempts.iloc[0] == 0
    assert support.joint_training_attempts.iloc[0] == 0
    rows = pd.DataFrame(
        [
            {
                "client_id": "C1",
                "day": "2026-04-02",
                "balance_cents": 10000,
                "cap_cents": 10000,
                "dpd": 0,
                "candidate_a": 0,
                "candidate_b": 1,
                "candidate_amounts_cents": json.dumps([10000]),
                "candidate_providers": json.dumps(["B"]),
            }
        ]
    )
    model = EmpiricalModel(Protocol.load()).fit(frame().iloc[:1].assign(provider="B"), "2026-02-27")
    report = candidate_slices(rows, training, edges, model)
    assert report.outside_calendar_support.sum() == 1
    assert report.attempts.sum() == 1
    empty = rows.assign(candidate_amounts_cents="[]", candidate_providers="[]", candidate_b=0)
    assert candidate_slices(empty, training, edges, model).empty


def test_empty_diagnostic_populations_produce_empty_tables():
    assert history_features(frame().iloc[:0], 2).empty
    model = EmpiricalModel(Protocol.load()).fit(frame(), "2026-02-27")
    scored = score_attempts(frame(), model, "2026-04-01", "2026-04-30")
    assert calibration_slices(scored, "test").empty


def test_recent_support_exposes_january_only_b_despite_nonzero_any_history():
    january = pd.concat([frame().iloc[:1]] * 120, ignore_index=True).assign(
        provider="B", attempt_date="2026-01-03"
    )
    future = january.assign(attempt_date="2026-04-03")
    model = EmpiricalModel(Protocol.load()).fit(january, "2026-03-30")
    rows = pd.DataFrame(
        [
            {
                "client_id": "C1",
                "day": "2026-04-02",
                "balance_cents": 10000,
                "cap_cents": 10000,
                "dpd": 0,
                "candidate_a": 0,
                "candidate_b": 1,
                "candidate_amounts_cents": "[10000]",
                "candidate_providers": '["B"]',
            }
        ]
    )
    report = candidate_slices(rows, pd.concat([january, future]), [-np.inf, np.inf], model).iloc[0]
    assert report.any_history_calendar_attempts == 120
    assert report.outside_calendar_support == 0
    assert report.zero_any_history_calendar_support == 0
    assert report.recent_calendar_training_attempts == 0
    assert report.recent_calendar_months_observed == 0
    assert report.recent_calendar_qualifying_months == 0
    assert report.weak_recent_calendar_support == 1
