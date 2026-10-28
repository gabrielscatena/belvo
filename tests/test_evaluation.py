import pandas as pd

from belvo.evaluation.offline import bootstrap_loans


def test_bootstrap_preserves_loan_clusters_and_fixed_expense():
    rows = pd.DataFrame(
        [
            {"loan_id": "L1", "candidate": 3, "legacy_estimated": 2, "legacy_observed": 1},
            {"loan_id": "L1", "candidate": 7, "legacy_estimated": 3, "legacy_observed": 4},
            {"loan_id": "L2", "candidate": 10, "legacy_estimated": 5, "legacy_observed": 5},
        ]
    )
    result = bootstrap_loans(rows, 4, repetitions=100)
    assert result["candidate_margin_interval"] == [16, 16]
    assert result["estimated_uplift_interval"] == [10, 10]


def test_bootstrap_is_reproducible_and_shifts_only_margin_with_fixed_cost():
    rows = pd.DataFrame(
        [
            {"loan_id": "L1", "candidate": 3, "legacy_estimated": 2, "legacy_observed": 1},
            {"loan_id": "L2", "candidate": 10, "legacy_estimated": 3, "legacy_observed": 5},
        ]
    )
    first = bootstrap_loans(rows, 0)
    second = bootstrap_loans(rows, 10)
    assert first["estimated_uplift_interval"] == second["estimated_uplift_interval"]
    assert [x - 10 for x in first["candidate_margin_interval"]] == second[
        "candidate_margin_interval"
    ]
