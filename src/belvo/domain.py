"""Immutable loan inputs and cent-exact complete collection plans."""

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from decimal import Decimal


def cents(value: str) -> int:
    if not re.fullmatch(r"\d+(?:\.\d{1,2})?", str(value)):
        raise ValueError("Expected nonnegative amount with at most two decimal places")
    return int(Decimal(str(value)) * 100)


def fingerprint(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class Loan:
    loan_id: str
    client_id: str
    day: str
    balance: int
    cap: int
    dpd: int
    version: str


@dataclass(frozen=True)
class Plan:
    amounts: tuple[int, ...] = ()
    providers: tuple[str, ...] = ()

    @property
    def a_units(self) -> int:
        return self.providers.count("A")

    @property
    def b_units(self) -> int:
        return self.providers.count("B")

    def payload(self) -> dict:
        return asdict(self)


def plans(loan: Loan, fractions=("0.25", "0.50", "0.75", "1.00"), max_count=3):
    result = {Plan()}
    for count in range(1, max_count + 1):
        for fraction in fractions:
            total = int(min(loan.balance, count * loan.cap) * Decimal(fraction))
            if total < count:
                continue
            base, remainder = divmod(total, count)
            amounts = tuple(base + (i < remainder) for i in range(count))
            if min(amounts) <= 0 or max(amounts) > loan.cap or sum(amounts) > loan.balance:
                raise ValueError("Unsafe plan configuration")
            for provider in ("A", "B"):
                result.add(Plan(amounts, (provider,) * count))
    return sorted(result, key=lambda p: (len(p.amounts), p.amounts, p.providers))
