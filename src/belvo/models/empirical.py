"""Smoothed observational probabilities conditional on the complete historical plan."""

import json
import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from belvo.config import Protocol, commission_percent
from belvo.data.history import load_history
from belvo.domain import Loan, Plan, fingerprint

__all__ = ["EmpiricalModel", "Estimate", "fit_for_day", "load_history"]


def fraction_bin(total: int, feasible: int) -> int:
    return min(4, max(1, int(total * 4 / max(feasible, 1) + 0.5)))


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
        self.model_hash = ""
        self._estimate_cache = {}

    def fit(self, frame: pd.DataFrame, through: str):
        self._estimate_cache.clear()
        self.cells.clear()
        self.parents.clear()
        sample = frame.loc[frame.attempt_date.le(through) & frame.pure].copy()
        if sample.empty:
            raise ValueError("No available training labels; use the deterministic baseline")
        if not sample.status.isin(["success", "failed"]).all():
            raise ValueError("Invalid training outcome")
        sample["y"] = sample.status.eq("success").astype(int)
        self.global_rate = float(sample.y.mean())
        self.fitted_through = through
        features = [
            "attempt_id",
            "attempt_date",
            "client_id",
            "provider",
            "count",
            "band",
            "fraction",
            "status",
            "pure",
        ]
        training = sample[features].sort_values("attempt_id")
        self.training_hash = fingerprint(json.loads(training.to_json(orient="records")))
        for columns, target in (
            (["provider", "count", "band"], self.parents),
            (["client_id", "provider", "count", "band", "fraction"], self.cells),
        ):
            for key, group in sample.groupby(columns, sort=True):
                native_key = tuple(v.item() if hasattr(v, "item") else v for v in key)
                target[native_key] = (int(group.y.sum()), len(group))
        self.model_hash = fingerprint(self.artifact())
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
            "model_hash": self.model_hash,
        }

    def artifact(self):
        return {
            "format": "belvo.empirical.v2",
            "fitted_through": self.fitted_through,
            "global_rate": self.global_rate,
            "training_hash": self.training_hash,
            "protocol": self.protocol.values,
            "cells": [[list(k), list(v)] for k, v in self.cells.items()],
            "parents": [[list(k), list(v)] for k, v in self.parents.items()],
        }

    @classmethod
    def from_artifact(cls, obj):
        payload = {k: v for k, v in obj.items() if k != "model_hash"}
        if (
            payload.get("format") != "belvo.empirical.v2"
            or fingerprint(payload) != obj["model_hash"]
        ):
            raise ValueError("Invalid or corrupted model artifact")
        model = cls(Protocol(payload["protocol"]))
        model.fitted_through = payload["fitted_through"]
        model.global_rate = payload["global_rate"]
        model.training_hash = payload["training_hash"]
        model.model_hash = obj["model_hash"]
        model.cells = {tuple(k): tuple(v) for k, v in payload["cells"]}
        model.parents = {tuple(k): tuple(v) for k, v in payload["parents"]}
        return model

    def save(self, path: Path):
        """Publish a complete immutable artifact, including under concurrent writers."""
        obj = self.artifact() | {"model_hash": self.model_hash}
        if fingerprint(self.artifact()) != self.model_hash:
            raise ValueError("Model changed after fitting")
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(json.dumps(obj, indent=2).encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        try:
            try:
                if os.name == "nt":
                    os.rename(temporary, path)  # Windows rename atomically refuses replacement.
                else:
                    os.link(temporary, path)
            except FileExistsError:
                if json.loads(path.read_text(encoding="utf-8")) != obj:
                    raise ValueError("Refusing to overwrite a different model artifact") from None
        finally:
            temporary.unlink(missing_ok=True)


def fit_for_day(frame, protocol, day, *, allow_empty=False):
    fit_start = (
        protocol.values["validation_start"]
        if day <= protocol.values["validation_end"]
        else protocol.values["test_start"]
    )
    fit_end = (
        protocol.values["train_end"]
        if day <= protocol.values["validation_end"]
        else protocol.values["validation_end"]
    )
    cutoff = min(
        protocol.known_attempt_through(day), protocol.known_attempt_through(fit_start), fit_end
    )
    if allow_empty and not (frame.attempt_date.le(cutoff) & frame.pure).any():
        return None
    return EmpiricalModel(protocol).fit(frame, cutoff)
