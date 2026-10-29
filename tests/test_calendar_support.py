import pandas as pd
import pytest

from belvo.config import Protocol
from belvo.domain import Loan, Plan
from belvo.models.calendar_support import CalendarSupport, CalendarSupportedModel
from belvo.models.empirical import EmpiricalModel


def history():
    records = []
    for provider, day in (
        ("B", "2026-01-03"),
        ("A", "2026-02-03"),
        ("A", "2026-03-03"),
        ("B", "2026-04-03"),
    ):
        for number in range(150):
            records.append(
                {
                    "attempt_id": f"{provider}-{day}-{number}",
                    "attempt_date": day,
                    "client_id": "C1",
                    "provider": provider,
                    "count": 1,
                    "band": 15,
                    "fraction": 4,
                    "pure": True,
                    "status": "failed" if number % 2 else "success",
                }
            )
    return pd.DataFrame(records)


def test_old_january_history_is_counted_but_does_not_admit_april_b_other():
    support = CalendarSupport(history(), "2026-03-30")
    result = support.check("B", "2026-04-02")
    assert result["any_history_attempts"] == 150
    assert result["recent_attempts"] == 0
    assert result["recent_months_observed"] == 0
    assert result["recent_qualifying_months"] == 0
    assert result["recent_months"] == ["2026-02", "2026-03"]
    assert result["admitted"] is False
    assert result["reason"] == "insufficient_recent_calendar_support"


def test_april_outcomes_cannot_change_admission_and_recent_a_is_admitted():
    original = history()
    original_result = CalendarSupport(original, "2026-03-30").check("A", "2026-04-02")
    changed = original.loc[original.attempt_date.lt("2026-04-01")].copy()
    changed["status"] = "success"
    assert CalendarSupport(changed, "2026-03-30").check("A", "2026-04-02") == original_result
    assert original_result["recent_attempts"] == 300
    assert original_result["recent_months_observed"] == 2
    assert original_result["recent_qualifying_months"] == 2
    assert original_result["admitted"] is True
    assert CalendarSupport(changed, "2026-03-30").check("B", "2026-04-02") == (
        CalendarSupport(original, "2026-03-30").check("B", "2026-04-02")
    )


def test_threshold_requires_one_qualifying_recent_month_and_pure_plans():
    frame = history()
    one_month = frame.loc[frame.attempt_date.ne("2026-03-03")]
    assert CalendarSupport(one_month, "2026-03-30").check("A", "2026-04-02")["admitted"]
    assert not CalendarSupport(one_month, "2026-03-30", minimum_months=2).check("A", "2026-04-02")[
        "admitted"
    ]
    too_small = pd.concat(
        [frame.loc[frame.attempt_date.eq(day)].head(20) for day in ("2026-02-03", "2026-03-03")]
    )
    assert not CalendarSupport(too_small, "2026-03-30").check("A", "2026-04-02")["admitted"]
    distributed = pd.concat(
        [frame.loc[frame.attempt_date.eq(day)].head(60) for day in ("2026-02-03", "2026-03-03")]
    )
    result = CalendarSupport(distributed, "2026-03-30").check("A", "2026-04-02")
    assert result["recent_attempts"] == 120
    assert result["recent_qualifying_months"] == 0
    assert not result["admitted"]
    impure = frame.assign(pure=False)
    assert CalendarSupport(impure, "2026-03-30").check("A", "2026-04-02")["recent_attempts"] == 0


def test_wrapper_preserves_estimates_and_exposes_rejection_reason():
    frame = history()
    model = EmpiricalModel(Protocol.load()).fit(frame, "2026-03-30")
    wrapper = CalendarSupportedModel(model, CalendarSupport(frame, model.fitted_through))
    loan = Loan("L1", "C1", "2026-04-02", 10000, 10000, 0, "v1")
    for provider, admitted in (("A", True), ("B", False)):
        plan = Plan((10000,), (provider,))
        original = model.evaluate(loan, plan)
        wrapped = wrapper.evaluate(loan, plan)
        assert original["supported"]
        assert wrapped["observational_cell_supported"]
        assert wrapped["calendar_supported"] is admitted
        assert wrapped["supported"] is admitted
        for key, value in original.items():
            if key != "supported":
                assert wrapped[key] == value
        assert wrapped["calendar_support"][provider]["admitted"] is admitted
    assert wrapper.model_hash == model.model_hash
    no_attempt = wrapper.evaluate(loan, Plan())
    assert no_attempt["supported"]
    assert no_attempt["calendar_supported"]
    assert no_attempt["calendar_support"] == {}
    assert no_attempt["calendar_support_reason"] == "no_attempt"


def test_calendar_support_validates_configuration_and_shared_cutoff():
    frame = history()
    with pytest.raises(ValueError, match="thresholds"):
        CalendarSupport(frame, "2026-03-30", months=1, minimum_months=2)
    model = EmpiricalModel(Protocol.load()).fit(frame, "2026-03-30")
    with pytest.raises(ValueError, match="same label cutoff"):
        CalendarSupportedModel(model, CalendarSupport(frame, "2026-03-29"))
    wrapped = CalendarSupportedModel(model, CalendarSupport(frame, "2026-03-30"))
    model.fit(frame, "2026-03-29")
    with pytest.raises(ValueError, match="same label cutoff"):
        wrapped.evaluate(Loan("L1", "C1", "2026-04-02", 10000, 10000, 0, "v1"), Plan())


def test_available_february_month_end_is_not_rejected_for_unavailable_march_31():
    frame = history().loc[lambda x: x.provider.eq("A")].assign(attempt_date="2026-02-28")
    result = CalendarSupport(frame, "2026-03-30").check("A", "2026-04-30")
    assert result["recent_attempts"] == 300
    assert result["recent_qualifying_months"] == 1
    assert result["admitted"]


def test_empty_history_does_not_admit_a_nonempty_plan():
    support = CalendarSupport(history().iloc[:0], "2026-03-30")
    assert support.check("A", "2026-04-03")["recent_attempts"] == 0
    assert not support.check("A", "2026-04-03")["admitted"]
