"""Point-in-time historical joins, with explicit per-loan quarantine evidence."""

import json
from datetime import date
from pathlib import Path

import pandas as pd

from belvo.config import commission_percent
from belvo.domain import cents


def _canonical_day(value):
    try:
        return date.fromisoformat(value).isoformat() == value
    except (TypeError, ValueError):
        return False


def _convert(value, *, positive=False, integer=False):
    try:
        if integer:
            if not isinstance(value, str) or not value.isascii() or not value.isdigit():
                return None
            number = int(value)
        else:
            number = cents(value)
        return number if number >= int(positive) else None
    except (TypeError, ValueError):
        return None


def load_history(data: Path, *, before=None, quarantine=False, known_through=None):
    """Exclude D/future rows before conversion; strict by default for offline audits.

    Runtime callers retain pending submissions for their known fees, but validate
    outcomes only through known_through. Invalid loan-day groups cannot train a
    partial plan. Their source fields/reasons are returned in DataFrame.attrs.
    """
    if before is not None and not _canonical_day(before):
        raise ValueError("History cutoff must use YYYY-MM-DD")
    if known_through is not None and (
        not _canonical_day(known_through) or (before is not None and known_through >= before)
    ):
        raise ValueError("Known outcomes must precede the decision date")
    frames = {}
    for name, required in (
        (
            "payment_attempts",
            {
                "attempt_id",
                "loan_id",
                "attempt_date",
                "amount",
                "provider",
                "status",
                "installment_count",
                "installment_index",
            },
        ),
        (
            "loan_snapshots",
            {"loan_id", "snapshot_date", "client_id", "outstanding_balance", "days_past_due"},
        ),
        ("clients", {"client_id", "max_installment_amount"}),
    ):
        frame = pd.read_csv(data / f"{name}.csv", dtype=str, keep_default_na=False)
        if not required.issubset(frame.columns):
            raise ValueError(f"Missing historical schema in {name}.csv")
        frames[name] = frame
    a, s, c = (frames[k] for k in ("payment_attempts", "loan_snapshots", "clients"))
    if before is not None:
        # Do not parse money, join or check duplicate keys outside the information set.
        a = a.loc[a.attempt_date.lt(before) | ~a.attempt_date.map(_canonical_day)].copy()
        s = s.loc[s.snapshot_date.lt(before) | ~s.snapshot_date.map(_canonical_day)].copy()
    duplicate_attempt = a.attempt_id.duplicated(keep=False)
    a["history_error"] = duplicate_attempt.map({True: "duplicate_attempt_id", False: ""})
    s = s.loc[~s.duplicated(["loan_id", "snapshot_date"], keep=False)]
    c = c.loc[~c.client_id.duplicated(keep=False)]
    a = a.merge(
        s[["loan_id", "snapshot_date", "client_id", "outstanding_balance", "days_past_due"]],
        left_on=["loan_id", "attempt_date"],
        right_on=["loan_id", "snapshot_date"],
        validate="many_to_one",
        how="left",
    ).merge(
        c[["client_id", "max_installment_amount"]],
        on="client_id",
        validate="many_to_one",
        how="left",
    )
    source_columns = list(a.columns)

    def flag(mask, reason):
        a.loc[mask, "history_error"] += ";" + reason

    flag(~a.attempt_date.map(_canonical_day), "invalid_attempt_date")
    flag(a.attempt_id.eq("") | a.loan_id.eq(""), "missing_identity")
    flag(a.client_id.isna() | a.client_id.eq(""), "missing_or_ambiguous_snapshot")
    flag(~a.provider.isin(["A", "B"]), "invalid_provider")
    known = True if known_through is None else a.attempt_date.le(known_through)
    flag(known & ~a.status.isin(["success", "failed"]), "invalid_available_outcome")
    for source, target, options in (
        ("amount", "amount_cents", {"positive": True}),
        ("outstanding_balance", "balance_cents", {}),
        ("max_installment_amount", "cap_cents", {"positive": True}),
        ("installment_count", "count", {"positive": True, "integer": True}),
        ("installment_index", "index", {"positive": True, "integer": True}),
        ("days_past_due", "dpd", {"integer": True}),
    ):
        # Object dtype prevents failed conversions from rounding valid cents to floats.
        a[target] = pd.Series(
            [_convert(v, **options) for v in a[source]], index=a.index, dtype=object
        )
        flag(a[target].isna(), "invalid_" + source)
    ready = a.loc[a.history_error.eq("")]
    groups = ready.groupby(["loan_id", "attempt_date"])
    shape = groups.agg(
        n=("count", "size"),
        declared=("count", "first"),
        declarations=("count", "nunique"),
        indices=("index", "nunique"),
        first=("index", "min"),
        last=("index", "max"),
        total=("amount_cents", "sum"),
        balance=("balance_cents", "first"),
    )
    invalid = shape.index[
        shape.n.ne(shape.declared)
        | shape.declarations.ne(1)
        | shape.indices.ne(shape.n)
        | shape["first"].ne(1)
        | shape["last"].ne(shape.n)
        | shape.total.gt(shape.balance)
    ]
    flag(
        pd.MultiIndex.from_frame(a[["loan_id", "attempt_date"]]).isin(invalid),
        "invalid_historical_plan",
    )
    flag(
        ready.amount_cents.gt(ready.cap_cents).reindex(a.index, fill_value=False),
        "historical_cap_exceeded",
    )
    # Any bad installment invalidates its complete loan-day, never just one sibling.
    bad_group = (
        a.history_error.ne("").groupby([a.loan_id, a.attempt_date], dropna=False).transform("any")
    )
    flag(bad_group & a.history_error.eq(""), "invalid_sibling_installment")
    bad = a.loc[a.history_error.ne(""), source_columns]
    issues = json.loads(bad.to_json(orient="records"))
    if issues and not quarantine:
        raise ValueError(f"Invalid historical records: {len(issues)}; run the EDA audit")
    a = a.loc[a.history_error.eq("")].copy()
    for field in ("amount_cents", "balance_cents", "cap_cents", "count", "index", "dpd"):
        a[field] = a[field].map(int)
    a["band"] = a.dpd.map(commission_percent)
    groups = a.groupby(["loan_id", "attempt_date"])
    a["plan_total"] = groups.amount_cents.transform("sum")
    a["pure"] = groups.provider.transform("nunique").eq(1)
    a["fraction"] = [
        min(4, max(1, int(t * 4 / max(min(b, n * cap), 1) + 0.5)))
        for t, b, n, cap in zip(a.plan_total, a.balance_cents, a["count"], a.cap_cents, strict=True)
    ]
    a = a.drop(columns=["history_error", "index"])
    a.attrs["quarantine"] = issues
    return a
