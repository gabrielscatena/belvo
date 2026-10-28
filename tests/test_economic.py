import json

import pandas as pd

from belvo.config import Protocol
from belvo.domain import Loan, Plan
from belvo.models.empirical import EmpiricalModel, fit_for_day
from belvo.optimization.select import EconomicSelector, zero_future_budget


def history():
    return pd.DataFrame(
        [
            {
                "attempt_id": str(i),
                "attempt_date": "2026-02-01",
                "status": "success" if i < 4 else "failed",
                "pure": True,
                "provider": "A",
                "count": 1,
                "band": 15,
                "client_id": "C1",
                "fraction": 4,
            }
            for i in range(200)
        ]
    )


def test_future_labels_cannot_change_fitted_probabilities():
    p = Protocol.load()
    frame = history()
    a = fit_for_day(frame, p, "2026-03-01")
    future = frame.assign(attempt_date="2026-03-01", status="success")
    b = fit_for_day(pd.concat([frame, future]), p, "2026-03-01")
    assert a.training_hash == b.training_hash and a.global_rate == b.global_rate
    loan = Loan("L1", "C1", "2026-03-01", 10000, 10000, 0, "v1")
    value = a.evaluate(loan, Plan((10000,), ("A",)))
    assert value["supported"] and value["score"] <= value["contribution"]
    assert 0 <= value["score"] <= 15


def test_opportunity_cost_is_not_an_accounting_expense():
    p = Protocol.load()
    loan = Loan("L1", "C1", "2026-03-01", 10000, 10000, 0, "v1")
    plan = Plan((10000,), ("A",))
    a = EmpiricalModel(p).fit(history(), "2026-02-27").evaluate(loan, plan)
    b = (
        EmpiricalModel(Protocol(p.values | {"a_opportunity_cost": "7"}))
        .fit(history(), "2026-02-27")
        .evaluate(loan, plan)
    )
    assert a["contribution"] == b["contribution"]
    assert abs(a["score"] - b["score"] - 7) < 1e-10


def test_shared_capacity_prioritizes_lender_constraint():
    class Scorer:
        def evaluate(self, loan, plan):
            contribution = sum(plan.amounts) / 100 * 0.1 - 2 * plan.b_units
            return {
                "score": contribution,
                "contribution": contribution,
                "conservative_contribution": contribution,
                "supported": True,
            }

    loans = [
        Loan("L1", "C1", "2026-04-01", 100000, 100000, 0, "v1"),
        Loan("L2", "C2", "2026-04-01", 10000, 10000, 0, "v1"),
    ]
    selector = EconomicSelector(Scorer(), {"C1": 0, "C2": 9})
    decisions, remaining = selector(loans, 1, Protocol.load())
    assert remaining == 0
    assert sum(r["plan"]["providers"].count("A") for r in decisions) == 1
    assert decisions[1]["plan"]["providers"] == ("A",)
    assert selector.report["C2"]["status"] == "satisfied_expected"
    impossible = EconomicSelector(Scorer(), {"C1": 10000, "C2": 10000})
    impossible(loans, 0, Protocol.load())
    assert all(r["status"] == "unmet_heuristic_constraint" for r in impossible.report.values())


def test_model_serialization_uses_json_native_scalars(tmp_path):
    model = EmpiricalModel(Protocol.load()).fit(history(), "2026-02-27")
    target = tmp_path / "model.json"
    model.save(target)
    assert json.loads(target.read_text())["fitted_through"] == "2026-02-27"


def test_pending_b_cost_is_known_even_when_its_outcome_is_unavailable():
    p = Protocol.load()
    frame = pd.DataFrame(
        [
            {
                "client_id": "C1",
                "attempt_date": "2026-03-30",
                "amount_cents": 10000,
                "band": 15,
                "status": "success",
                "provider": "A",
            },
            {
                "client_id": "C1",
                "attempt_date": "2026-03-31",
                "amount_cents": 10000,
                "band": 15,
                "status": "success",
                "provider": "B",
            },
        ]
    )
    budget = zero_future_budget(frame, "2026-04-01", p, clients=["C1", "C2"])
    assert abs(budget["C1"] - (float(p.sample_upfront) / 2 - 15 + 2 + 0.0001)) < 1e-8
    frame.loc[1, "status"] = "failed"
    assert budget == zero_future_budget(frame, "2026-04-01", p, clients=["C1", "C2"])
