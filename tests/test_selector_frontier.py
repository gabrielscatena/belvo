"""Policy-value regressions with known finite plan scores, independent of response fitting."""

import pytest

from belvo.config import Protocol
from belvo.domain import Loan
from belvo.optimization.select import EconomicSelector


class KnownValues:
    def __init__(self, values):
        self.values = values

    def evaluate(self, loan, plan):
        value = self.values.get(loan.loan_id, {}).get(plan.a_units, -100)
        if not plan.amounts:
            value = 0
        score, contribution = value if isinstance(value, tuple) else (value, value)
        return {
            "score": score,
            "contribution": contribution,
            "conservative_contribution": contribution,
            "supported": True,
        }


def portfolio():
    return [
        Loan("L1", "C1", "2026-04-01", 30000, 10000, 0, "v1"),
        Loan("L2", "C2", "2026-04-01", 30000, 10000, 0, "v1"),
    ]


def protocol():
    original = Protocol.load()
    return Protocol(original.values | {"amount_fractions": ["1.00"]})


def test_slack_capacity_selects_total_value_instead_of_best_value_per_unit():
    selector = EconomicSelector(KnownValues({"L1": {1: 2, 2: 5.4, 3: 7.2}}))
    decisions, remaining = selector(portfolio()[:1], 10000, protocol())
    assert decisions[0]["economics"]["score"] == 7.2
    assert decisions[0]["plan"]["providers"] == ("A", "A", "A")
    assert remaining == 9997


def test_jointly_feasible_independent_maxima_meet_lender_requirements():
    selector = EconomicSelector(
        KnownValues({"L1": {1: 2, 2: 5.4, 3: 7.2}, "L2": {1: 3, 2: 6, 3: 8}}),
        {"C1": 6, "C2": 7},
    )
    decisions, remaining = selector(portfolio(), 6, protocol())
    assert sum(d["economics"]["score"] for d in decisions) == 15.2
    assert remaining == 0
    assert all(r["status"] == "satisfied_expected" for r in selector.report.values())


def test_scarcity_keeps_capacity_aware_allocation_instead_of_absolute_greedy():
    selector = EconomicSelector(KnownValues({"L1": {1: 2, 3: 10}, "L2": {2: 9}}))
    decisions, remaining = selector(portfolio(), 3, protocol())
    # Absolute-gain sorting would spend all three units on L1 and obtain only 10.
    assert sum(d["economics"]["score"] for d in decisions) == 11
    assert remaining == 0


def test_frontier_replacement_improves_an_already_selected_a_plan():
    selector = EconomicSelector(
        KnownValues({"L1": {1: 2, 2: 5.4, 3: 7.2}}), {"C1": 100}
    )
    decisions, remaining = selector(portfolio()[:1], 10000, protocol())
    assert decisions[0]["economics"]["score"] == 7.2
    assert remaining == 9997
    assert selector.report["C1"]["status"] == "unmet_heuristic_constraint"


def test_score_improvement_does_not_reverse_a_satisfied_lender_requirement():
    selector = EconomicSelector(
        KnownValues({"L1": {1: (1, 1), 2: (5.4, 20), 3: (7.2, 18)}}), {"C1": 19}
    )
    decisions, remaining = selector(portfolio()[:1], 10000, protocol())
    assert decisions[0]["economics"]["score"] == 5.4
    assert remaining == 9998
    assert selector.report["C1"]["status"] == "satisfied_expected"


def test_lender_priority_survives_larger_unconstrained_gain_elsewhere():
    selector = EconomicSelector(
        KnownValues({"L1": {1: 100}, "L2": {1: 1}}), {"C1": 0, "C2": 1}
    )
    decisions, remaining = selector(portfolio(), 1, protocol())
    assert decisions[0]["status"] == "no_attempt"
    assert decisions[1]["economics"]["score"] == 1
    assert selector.report["C2"]["status"] == "satisfied_expected"
    assert remaining == 0


def test_constraint_phase_preserves_accounting_contribution_separate_from_oc_score():
    selector = EconomicSelector(KnownValues({"L1": {1: (-7, 3)}}), {"C1": 3})
    decisions, remaining = selector(portfolio()[:1], 2, protocol())
    assert decisions[0]["economics"]["score"] == -7
    assert decisions[0]["economics"]["contribution"] == 3
    assert selector.report["C1"]["status"] == "satisfied_expected"
    assert remaining == 1


def test_order_and_ties_are_deterministic():
    values = {"L1": {1: 5, 2: 8}, "L2": {1: 5, 2: 8}}
    forward = EconomicSelector(KnownValues(values))(portfolio(), 2, protocol())
    reverse = EconomicSelector(KnownValues(values))(portfolio()[::-1], 2, protocol())
    assert forward == reverse


@pytest.mark.parametrize("quota", range(7))
def test_capacity_is_conserved_at_every_supply_level(quota):
    selector = EconomicSelector(
        KnownValues({"L1": {1: 2, 2: 5.4, 3: 7.2}, "L2": {1: 3, 2: 6, 3: 8}})
    )
    decisions, remaining = selector(portfolio(), quota, protocol())
    used = sum(d["plan"]["providers"].count("A") for d in decisions)
    assert 0 <= remaining <= quota
    assert used + remaining == quota
