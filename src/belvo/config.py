"""Frozen date-only evaluation conventions; monetary configuration uses Decimal."""

import json
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path


@dataclass(frozen=True)
class Protocol:
    values: dict

    @classmethod
    def load(cls, path: str | Path = "conf/protocol.json") -> "Protocol":
        values = json.loads(Path(path).read_text(encoding="utf-8"))
        if values["outcome_delay_days"] < 1 or values["sample_weight"] < 1:
            raise ValueError("Unsafe outcome delay or sample weight")
        if not (
            values["train_end"]
            < values["validation_start"]
            <= values["validation_end"]
            < values["test_start"]
            <= values["test_end"]
        ):
            raise ValueError("Temporal partitions overlap")
        if values["full_a_capacity"] < 0 or Decimal(values["full_a_upfront"]) < 0:
            raise ValueError("Negative contract")
        return cls(values)

    def known_attempt_through(self, decision_date: str) -> str:
        return (
            date.fromisoformat(decision_date) - timedelta(days=self.values["outcome_delay_days"])
        ).isoformat()

    @property
    def sample_capacity(self) -> int:
        return self.values["full_a_capacity"] // self.values["sample_weight"]

    @property
    def sample_upfront(self) -> Decimal:
        return Decimal(self.values["full_a_upfront"]) / self.values["sample_weight"]

    def a_available(self, day: str) -> bool:
        return self.values["contract_start"] <= day <= self.values["contract_end"]


def commission_percent(dpd: int) -> int:
    if dpd < 0:
        raise ValueError("DPD must be nonnegative")
    for upper, percent in ((5, 15), (15, 20), (30, 25), (60, 30), (90, 40)):
        if dpd <= upper:
            return percent
    return 50
