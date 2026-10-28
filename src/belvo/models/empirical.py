"""Smoothed observational probabilities conditional on the complete historical plan."""

import json
import math
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from belvo.config import Protocol, commission_percent
from belvo.domain import Loan, Plan, cents, fingerprint


def fraction_bin(total: int, feasible: int) -> int:
    return min(4, max(1, int(total * 4 / max(feasible, 1) + 0.5)))


def load_history(data: Path) -> pd.DataFrame:
    a = pd.read_csv(data / "payment_attempts.csv", dtype=str)
    s = pd.read_csv(data / "loan_snapshots.csv", dtype=str)
    c = pd.read_csv(data / "clients.csv", dtype=str)
    if a.attempt_id.duplicated().any() or s.duplicated(["loan_id", "snapshot_date"]).any():
        raise ValueError("Ambiguous historical keys; run the EDA audit")
    a = a.merge(
        s[["loan_id", "snapshot_date", "client_id", "outstanding_balance", "days_past_due"]],
        left_on=["loan_id", "attempt_date"],
        right_on=["loan_id", "snapshot_date"],
        validate="many_to_one",
        how="left",
    )
    a = a.merge(c, on="client_id", validate="many_to_one", how="left")
    if a.outstanding_balance.isna().any() or a.max_installment_amount.isna().any():
        raise ValueError("Unattributable history")
    for source, target in (
        ("amount", "amount_cents"),
        ("outstanding_balance", "balance_cents"),
        ("max_installment_amount", "cap_cents"),
    ):
        a[target] = a[source].map(cents)
    a["count"] = a.installment_count.astype(int)
    a["dpd"] = a.days_past_due.astype(int)
    a["band"] = a.dpd.map(commission_percent)
    groups = a.groupby(["loan_id", "attempt_date"])
    a["plan_total"] = groups.amount_cents.transform("sum")
    a["pure"] = groups.provider.transform("nunique").eq(1)
    a["fraction"] = [
        fraction_bin(t, min(b, n * cap))
        for t, b, n, cap in zip(a.plan_total, a.balance_cents, a["count"], a.cap_cents, strict=True)
    ]
    return a


@dataclass(frozen=True)
class Estimate:
    mean: float
    conservative: float
    n: int
    supported: bool
    level: str


class EmpiricalModel:
    def __init__(self, protocol: Protocol):
        self.protocol = protocol
        self.cells, self.parents = {}, {}
        self.fitted_through = ""
        self.global_rate = 0.0
        self.training_hash = ""
        self._estimate_cache = {}

    def fit(self, frame: pd.DataFrame, through: str):
        self._estimate_cache.clear()
        sample = frame.loc[frame.attempt_date.le(through) & frame.pure].copy()
        if sample.empty:
            raise ValueError("No available training labels; use the deterministic baseline")
        if not sample.status.isin(["success", "failed"]).all():
            raise ValueError("Invalid training outcome")
        sample["y"] = sample.status.eq("success").astype(int)
        self.global_rate = float(sample.y.mean())
        self.fitted_through = through
        self.training_hash = fingerprint(sample[["attempt_id", "status"]].values.tolist())
        for columns, target in (
            (["provider", "count", "band"], self.parents),
            (["client_id", "provider", "count", "band", "fraction"], self.cells),
        ):
            for key, group in sample.groupby(columns, sort=True):
                native_key = tuple(v.item() if hasattr(v, "item") else v for v in key)
                target[native_key] = (int(group.y.sum()), len(group))
        return self

    def estimate(self, loan: Loan, plan: Plan, provider: str) -> Estimate:
        if self.fitted_through > self.protocol.known_attempt_through(loan.day):
            raise ValueError("Future labels in model")
        count = len(plan.amounts)
        band = commission_percent(loan.dpd)
        fraction = fraction_bin(sum(plan.amounts), min(loan.balance, count * loan.cap))
        key = (loan.client_id, provider, count, band, fraction, len(set(plan.providers)) == 1)
        if key in self._estimate_cache:
            return self._estimate_cache[key]
        parent_s, parent_n = self.parents.get((provider, count, band), (0, 0))
        strength = self.protocol.values["prior_strength"]
        prior = (parent_s + strength * self.global_rate) / (parent_n + strength)
        successes, n = self.cells.get((loan.client_id, provider, count, band, fraction), (0, 0))
        mean = (successes + strength * prior) / (n + strength)
        uncertainty = math.sqrt(mean * (1 - mean) / (n + strength + 1))
        lower = max(0.0, mean - self.protocol.values["conservative_z"] * uncertainty)
        supported = n >= self.protocol.values["min_cell_attempts"] and len(set(plan.providers)) == 1
        result = Estimate(mean, lower, n, supported, "cell" if supported else "backoff")
        self._estimate_cache[key] = result
        return result

    def evaluate(self, loan: Loan, plan: Plan) -> dict:
        estimates = [self.estimate(loan, plan, provider) for provider in plan.providers]
        rate = commission_percent(loan.dpd) / 100
        mean = sum(m / 100 * rate * e.mean for m, e in zip(plan.amounts, estimates, strict=True))
        lower = sum(
            m / 100 * rate * e.conservative for m, e in zip(plan.amounts, estimates, strict=True)
        )
        b_cost = float(self.protocol.values["b_fee"]) * plan.b_units
        opportunity = float(self.protocol.values["a_opportunity_cost"]) * plan.a_units
        return {
            "expected_revenue": mean,
            "conservative_revenue": lower,
            "contribution": mean - b_cost,
            "conservative_contribution": lower - b_cost,
            "score": lower - b_cost - opportunity,
            "supported": all(e.supported for e in estimates),
            "min_cell_n": min((e.n for e in estimates), default=0),
            "model_through": self.fitted_through,
            "training_hash": self.training_hash,
        }

    def save(self, path: Path):
        obj = {
            "fitted_through": self.fitted_through,
            "global_rate": self.global_rate,
            "training_hash": self.training_hash,
            "protocol": self.protocol.values,
            "cells": [[list(k), list(v)] for k, v in self.cells.items()],
            "parents": [[list(k), list(v)] for k, v in self.parents.items()],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def fit_for_day(frame, protocol, day):
    fit_start = (
        protocol.values["validation_start"]
        if day <= protocol.values["validation_end"]
        else protocol.values["test_start"]
    )
    cutoff = min(protocol.known_attempt_through(day), protocol.known_attempt_through(fit_start))
    return EmpiricalModel(protocol).fit(frame, cutoff)
