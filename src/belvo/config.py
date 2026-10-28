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
        for key in (
            "outcome_delay_days",
            "sample_weight",
            "full_a_capacity",
            "max_installments",
            "min_cell_attempts",
            "prior_strength",
        ):
            if type(values[key]) is not int or values[key] < (0 if key == "full_a_capacity" else 1):
                raise ValueError(f"Invalid integer setting: {key}")
        for key in (
            "contract_start",
            "contract_end",
            "train_end",
            "validation_start",
            "validation_end",
            "test_start",
            "test_end",
        ):
            if date.fromisoformat(values[key]).isoformat() != values[key]:
                raise ValueError(f"Noncanonical date: {key}")
        for key in ("full_a_upfront", "b_fee", "a_opportunity_cost", "conservative_z"):
            number = Decimal(str(values[key]))
            if not number.is_finite() or number < 0:
                raise ValueError(f"Invalid nonnegative number: {key}")
        if not values["amount_fractions"] or any(
            not 0 < Decimal(f) <= 1 for f in values["amount_fractions"]
        ):
            raise ValueError("Amount fractions must be in (0,1]")
        if values["allocation"] != "equal_lenders":
            raise ValueError(
                "Only equal_lenders selection is implemented; other allocations are sensitivities"
            )
        if not values["contract_start"] <= values["train_end"] < values["contract_end"]:
            raise ValueError("Invalid contract window")
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
