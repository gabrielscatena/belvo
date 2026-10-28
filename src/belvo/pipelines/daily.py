"""Daily file contract; standalone feasibility baseline, never a profit claim."""

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

from belvo.config import Protocol
from belvo.domain import Loan, Plan, cents, fingerprint, plans


def read_csv(path: Path, required: set[str]) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"Missing required columns in {path.name}: {sorted(required)}")
        rows = list(reader)
        for row in rows:
            if None in row:
                row["__csv_error"] = "extra_csv_fields"
                row["__extra_values"] = row.pop(None)
        return rows


def load_day(data: Path, day: str):
    if date.fromisoformat(day).isoformat() != day:
        raise ValueError("Decision date must use YYYY-MM-DD")
    clients = read_csv(data / "clients.csv", {"client_id", "max_installment_amount"})
    caps = {}
    counts = Counter(r["client_id"] for r in clients)
    for row in clients:
        try:
            cap = cents(row["max_installment_amount"])
            if cap > 0 and counts[row["client_id"]] == 1:
                caps[row["client_id"]] = cap
        except ValueError:
            continue
    rows = read_csv(
        data / "loan_snapshots.csv",
        {
            "loan_id",
            "client_id",
            "snapshot_date",
            "outstanding_balance",
            "days_past_due",
        },
    )
    selected = []
    for row in rows:
        try:
            if date.fromisoformat(row["snapshot_date"]).isoformat() != row["snapshot_date"]:
                raise ValueError("Noncanonical date")
        except (ValueError, TypeError):
            selected.append(row)  # preserve unassignable records as quarantine evidence
            continue
        if row["snapshot_date"] == day:
            selected.append(row)
    cap_sources = defaultdict(list)
    for row in clients:
        cap_sources[row["client_id"]].append(row)
    return validate(selected, caps, day, cap_sources)


def validate(rows: list[dict], caps: dict, day: str, cap_sources=None):
    groups = defaultdict(list)
    raw = []
    for index, row in enumerate(rows):
        context = {
            "cap_cents": caps.get(row.get("client_id")),
            "cap_sources": (cap_sources or {}).get(row.get("client_id")),
        }
        version = fingerprint({"snapshot": row, "context": context})
        raw.append({"source_index": index, "version": version, "payload": row, "context": context})
        key = (0, row["loan_id"]) if row.get("loan_id") else (1, str(index))
        groups[key].append((row, version))
    valid, rejected = [], []
    for key, entries in sorted(groups.items()):
        row, version = entries[0]
        errors = []
        if row.get("__csv_error"):
            errors.append(row["__csv_error"])
        if not row.get("loan_id"):
            errors.append("missing_loan_id")
        if len(entries) > 1:
            errors.append("duplicate_loan_day")
        if row.get("snapshot_date") != day:
            errors.append("invalid_snapshot_date")
        if row.get("client_id") not in caps:
            errors.append("unknown_client_or_invalid_cap")
        try:
            balance = cents(row["outstanding_balance"])
            if not re_integer(row["days_past_due"]):
                raise ValueError("Invalid DPD")
            dpd = int(row["days_past_due"])
        except (ValueError, TypeError, KeyError):
            errors.append("invalid_balance_or_dpd")
            balance, dpd = 0, 0
        if errors:
            rejected.append(
                {
                    "loan_id": row.get("loan_id"),
                    "client_id": row.get("client_id"),
                    "day": day,
                    "version": version,
                    "status": "quarantined",
                    "reason": ";".join(errors),
                    "plan": Plan().payload(),
                    "source_versions": [v for _, v in entries],
                }
            )
        else:
            valid.append(
                Loan(
                    row["loan_id"],
                    row["client_id"],
                    day,
                    balance,
                    caps[row["client_id"]],
                    dpd,
                    version,
                )
            )
    return valid, rejected, raw


def re_integer(value):
    return isinstance(value, str) and value.isascii() and value.isdigit()


def known_history(data: Path, day: str, protocol: Protocol):
    cutoff = protocol.known_attempt_through(day)
    rows = read_csv(data / "payment_attempts.csv", {"attempt_date", "loan_id", "status"})
    # Filter before reading labels: current/future labels must not enter features.
    return [r for r in rows if r["attempt_date"] <= cutoff]


def baseline(valid: list[Loan], quota: int, protocol: Protocol):
    decisions = []
    for loan in sorted(valid, key=lambda x: x.loan_id):
        candidates = plans(
            loan, protocol.values["amount_fractions"], protocol.values["max_installments"]
        )
        provider = "A" if quota > 0 and protocol.a_available(loan.day) else "B"
        eligible = [p for p in candidates if len(p.amounts) == 1 and p.providers == (provider,)]
        plan = max(eligible, key=lambda p: sum(p.amounts)) if eligible else Plan()
        quota -= plan.a_units
        decisions.append(
            {
                "loan_id": loan.loan_id,
                "client_id": loan.client_id,
                "day": loan.day,
                "version": loan.version,
                "status": "attempt" if plan.amounts else "no_attempt",
                "reason": "feasibility_baseline" if plan.amounts else "zero_balance",
                "plan": plan.payload(),
            }
        )
    return decisions, quota


def export(output: Path, decisions: list[dict], raw: list[dict], metadata: dict):
    output.mkdir(parents=True, exist_ok=False)
    for name, obj in (
        ("decisions.json", decisions),
        ("source_versions.json", raw),
        ("run.json", metadata),
    ):
        (output / name).write_text(json.dumps(obj, indent=2), encoding="utf-8")
    with (output / "decisions.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "loan_id",
                "client_id",
                "day",
                "status",
                "reason",
                "installments",
                "amounts_cents",
                "providers",
                "version",
            ],
        )
        writer.writeheader()
        for row in decisions:
            writer.writerow(
                {k: row[k] for k in ("loan_id", "client_id", "day", "status", "reason", "version")}
                | {
                    "installments": len(row["plan"]["amounts"]),
                    "amounts_cents": json.dumps(row["plan"]["amounts"]),
                    "providers": json.dumps(row["plan"]["providers"]),
                }
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--date", required=True)
    parser.add_argument("--config", default="conf/protocol.json")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--a-capacity", type=int)
    args = parser.parse_args()
    protocol = Protocol.load(args.config)
    quota = protocol.sample_capacity if args.a_capacity is None else args.a_capacity
    if quota < 0:
        parser.error("A capacity must be nonnegative")
    valid, rejected, raw = load_day(args.data_dir, args.date)
    decisions, remaining = baseline(valid, quota, protocol)
    decisions += rejected
    metadata = {
        "day": args.date,
        "protocol": protocol.values,
        "policy": "feasibility-v1",
        "valid": len(valid),
        "quarantined": len(rejected),
        "a_remaining": remaining,
        "known_attempts": len(known_history(args.data_dir, args.date, protocol)),
        "history_through": protocol.known_attempt_through(args.date),
        "source_hash": fingerprint(raw),
        "decisions_hash": fingerprint(decisions),
    }
    output = args.output or Path("reports/pipeline") / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    export(output, decisions, raw, metadata)
    print(
        json.dumps(
            {
                "output": str(output),
                "valid": len(valid),
                "quarantined": len(rejected),
                "a_remaining": remaining,
            }
        )
    )


if __name__ == "__main__":
    main()
