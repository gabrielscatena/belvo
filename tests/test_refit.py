import pandas as pd
import pytest

from belvo.config import Protocol
from belvo.domain import Loan, Plan
from belvo.evaluation.refit import cluster_bootstrap_samples, frozen_cases, refit


def history():
    rows = []
    for loan, provider, successes in (
        ("A1", "A", 4),
        ("A2", "A", 1),
        ("B1", "B", 3),
        ("B2", "B", 0),
    ):
        for index in range(5):
            rows.append(
                {
                    "loan_id": loan,
                    "attempt_id": f"{loan}-{index}",
                    "attempt_date": "2026-03-01",
                    "client_id": "C1",
                    "provider": provider,
                    "status": "success" if index < successes else "failed",
                    "pure": True,
                    "count": 1,
                    "band": 15,
                    "fraction": 4,
                }
            )
    return pd.DataFrame(rows)


def cases():
    return [
        (
            Loan("X", "C1", "2026-04-02", 10000, 10000, 0, "v1"),
            Plan((10000,), ("A",)),
            Plan((10000,), ("B",)),
        )
    ]


def test_resampling_retains_whole_loan_clusters_and_available_dates():
    frame = history()
    future = frame.assign(attempt_id=lambda x: "future-" + x.attempt_id, attempt_date="2026-04-01")
    samples = list(
        cluster_bootstrap_samples(pd.concat([frame, future]), "2026-03-30", repetitions=4, seed=7)
    )
    repeat = list(cluster_bootstrap_samples(frame, "2026-03-30", repetitions=4, seed=7))
    for sample, repeated in zip(samples, repeat, strict=True):
        pd.testing.assert_frame_equal(sample, repeated)
        assert len(sample) == len(frame)
        assert sample.attempt_date.eq("2026-03-01").all()
        for loan, group in sample.groupby("loan_id"):
            multiplicities = group.attempt_id.value_counts()
            assert len(multiplicities) == 5 and multiplicities.nunique() == 1
            assert set(group.attempt_id) == set(frame.loc[frame.loan_id.eq(loan), "attempt_id"])
    with pytest.raises(ValueError, match="repetitions"):
        list(cluster_bootstrap_samples(frame, "2026-03-30", repetitions=1))


def test_refit_reproducibility_future_labels_and_fixed_cost_shift():
    frame = history()
    protocol = Protocol.load()
    draws, result = refit(frame, cases(), protocol, "2026-03-30", 3, repetitions=8, seed=9)
    future = frame.assign(attempt_date="2026-04-01", status="success")
    unchanged, _ = refit(
        pd.concat([frame, future]), cases(), protocol, "2026-03-30", 3, repetitions=8, seed=9
    )
    pd.testing.assert_frame_equal(draws, unchanged)
    shifted, shifted_result = refit(
        frame, cases(), protocol, "2026-03-30", 7, repetitions=8, seed=9
    )
    assert shifted.estimated_uplift.tolist() == draws.estimated_uplift.tolist()
    for column in ("candidate_estimated_margin", "legacy_estimated_margin"):
        assert shifted[column].tolist() == pytest.approx((draws[column] - 4).tolist())
        for quantile in ("p025", "median", "p975"):
            assert shifted_result["parameter_resampling_intervals"][column][
                quantile
            ] == pytest.approx(result["parameter_resampling_intervals"][column][quantile] - 4)
    assert result["training_loans"] == 4
    assert not result["policy_reselection"] and not result["counterfactual_state_simulation"]
    with pytest.raises(ValueError, match="unavailable"):
        refit(frame, cases(), protocol, "2026-04-01", 3, repetitions=2)


def test_frozen_cases_rejects_unsafe_actions_and_handles_no_legacy_action():
    rows = pd.DataFrame(
        [
            {
                "loan_id": "X",
                "client_id": "C1",
                "day": "2026-04-02",
                "balance_cents": 10000,
                "cap_cents": 5000,
                "dpd": 0,
                "candidate_amounts_cents": "[5000, 5000]",
                "candidate_providers": '["A", "B"]',
            }
        ]
    )
    empty_history = pd.DataFrame(columns=["loan_id", "attempt_date", "installment_index"])
    actual = frozen_cases(empty_history, rows)
    assert actual[0][1] == Plan((5000, 5000), ("A", "B"))
    assert actual[0][2] == Plan()
    with pytest.raises(ValueError, match="Unsafe"):
        frozen_cases(empty_history, rows.assign(candidate_amounts_cents="[6000, 4000]"))
