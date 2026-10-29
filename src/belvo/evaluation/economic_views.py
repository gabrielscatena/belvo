"""Accounting sensitivities for frozen actions; no refitting or causal extrapolation."""

import argparse
import csv
import hashlib
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

from belvo.config import Protocol

ZERO = Decimal(0)
POLICIES = (
    ("legacy_observed", "legacy_observed", "legacy_a", "legacy_b"),
    ("legacy_estimated", "legacy_estimated", "legacy_a", "legacy_b"),
    ("candidate_estimated", "candidate", "candidate_a", "candidate_b"),
)
LAMBDAS = tuple(Decimal(x) for x in ("0", "0.25", "0.5", "1", "2"))


def number(value):
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("Non-finite economic input")
    return result


def count(value):
    result = number(value)
    if result < 0 or result != result.to_integral_value():
        raise ValueError("Attempt counts must be nonnegative integers")
    return int(result)


def normalized_weights(clients, counts):
    """Equal fallback if no A use; all weights are fixed before policy comparison."""
    total = sum(count(counts.get(client, 0)) for client in clients)
    if not total:
        return {client: Decimal(1) / len(clients) for client in clients}
    return {client: Decimal(count(counts.get(client, 0))) / total for client in clients}


def allocated_charges(fixed, weights):
    """Allocate one fixed charge exactly, retaining any Decimal residual in the last row."""
    fixed = number(fixed)
    if fixed < 0 or not weights:
        raise ValueError("A nonnegative fixed charge and nonempty lender scope are required")
    if any(number(weight) < 0 for weight in weights.values()):
        raise ValueError("Negative allocation weight")
    if abs(sum(weights.values(), ZERO) - 1) > Decimal("1e-20"):
        raise ValueError("Allocation weights must sum to one")
    result = {}
    clients = sorted(weights)
    for client in clients[:-1]:
        result[client] = fixed * weights[client]
    result[clients[-1]] = fixed - sum(result.values(), ZERO)
    return result


def allocation_views(rows, fixed, pretest_a):
    """Apply cash-cost allocations to identical frozen actions and lender populations."""
    clients = sorted(row["client_id"] for row in rows)
    if not clients or len(set(clients)) != len(clients):
        raise ValueError("Expected one row per lender")
    fixed = number(fixed)
    shared = {
        "equal_fixed_primary": normalized_weights(clients, {}),
        "pretest_A_use_fixed_weights": normalized_weights(clients, pretest_a),
    }
    output = []
    for policy, contribution_key, a_key, b_key in POLICIES:
        own_use = {row["client_id"]: count(row[a_key]) for row in rows}
        methods = shared | {
            "own_policy_A_use_diagnostic": normalized_weights(clients, own_use)
        }
        for method, weights in methods.items():
            charges = allocated_charges(fixed, weights)
            for row in sorted(rows, key=lambda row: row["client_id"]):
                client = row["client_id"]
                contribution = number(row[contribution_key])
                output.append(
                    {
                        "policy": policy,
                        "allocation": method,
                        "client_id": client,
                        "contribution_net_B_fees": contribution,
                        "a_units": count(row[a_key]),
                        "b_attempts": count(row[b_key]),
                        "allocation_weight": weights[client],
                        "allocated_fixed_A_cost": charges[client],
                        "accounting_margin": contribution - charges[client],
                    }
                )
            output.append(
                {
                    "policy": policy,
                    "allocation": method,
                    "client_id": "TOTAL",
                    "contribution_net_B_fees": sum(
                        (number(row[contribution_key]) for row in rows), ZERO
                    ),
                    "a_units": sum(count(row[a_key]) for row in rows),
                    "b_attempts": sum(count(row[b_key]) for row in rows),
                    "allocation_weight": Decimal(1),
                    "allocated_fixed_A_cost": fixed,
                    "accounting_margin": sum(
                        (number(row[contribution_key]) for row in rows), ZERO
                    )
                    - fixed,
                }
            )
    return output


def tariff_views(rows, fixed, tariff=Decimal(1)):
    """Historical 1*A tariff diagnostic; unlike cash allocation it can omit unused capacity."""
    fixed, tariff = number(fixed), number(tariff)
    if fixed < 0 or tariff < 0:
        raise ValueError("Negative economic cost")
    output = []
    for policy, contribution_key, a_key, _ in POLICIES:
        for row in rows:
            units = count(row[a_key])
            contribution = number(row[contribution_key])
            output.append(
                {
                    "policy": policy,
                    "client_id": row["client_id"],
                    "contribution_net_B_fees": contribution,
                    "a_units": units,
                    "tariff_A_charge": tariff * units,
                    "usage_priced_margin_diagnostic": contribution - tariff * units,
                }
            )
        units = sum(count(row[a_key]) for row in rows)
        contribution = sum((number(row[contribution_key]) for row in rows), ZERO)
        output.append(
            {
                "policy": policy,
                "client_id": "TOTAL",
                "contribution_net_B_fees": contribution,
                "a_units": units,
                "tariff_A_charge": tariff * units,
                "usage_priced_margin_diagnostic": contribution - tariff * units,
                "fixed_cost_minus_tariff_charges": fixed - tariff * units,
                "reconciled_cash_margin": contribution - fixed,
            }
        )
    return output


def lambda_views(rows, fixed, prices=LAMBDAS):
    """Holding actions fixed: shadow price changes scores, never invoice accounting."""
    fixed = number(fixed)
    output = []
    for policy, contribution_key, a_key, _ in POLICIES:
        contribution = sum((number(row[contribution_key]) for row in rows), ZERO)
        a_units = sum(count(row[a_key]) for row in rows)
        conservative = (
            sum((number(row["candidate_conservative"]) for row in rows), ZERO)
            if policy == "candidate_estimated"
            else None
        )
        for price in prices:
            price = number(price)
            if price < 0:
                raise ValueError("Opportunity price must be nonnegative")
            penalty = price * a_units
            output.append(
                {
                    "policy": policy,
                    "lambda_per_A_unit": price,
                    "a_units_fixed": a_units,
                    "shadow_penalty_not_cash": penalty,
                    "mean_contribution_score": contribution - penalty,
                    "conservative_contribution_score": None
                    if conservative is None
                    else conservative - penalty,
                    "shadow_adjusted_score_after_fixed_cost_not_cash": contribution
                    - fixed
                    - penalty,
                    "unchanged_accounting_margin": contribution - fixed,
                }
            )
    return output


def _write_csv(path, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run(evaluation_dir, data_dir, output, protocol):
    """Publish additive diagnostics without changing frozen evaluation artifacts."""
    evaluation_dir, data_dir, output = map(Path, (evaluation_dir, data_dir, output))
    summary_path = evaluation_dir / "summary.json"
    client_path = evaluation_dir / "per_client.csv"
    attempts_path = data_dir / "payment_attempts.csv"
    snapshots_path = data_dir / "loan_snapshots.csv"
    summary = json.loads(summary_path.read_text(encoding="utf-8"), parse_float=Decimal)
    decimal_protocol = json.loads(json.dumps(protocol.values), parse_float=Decimal)
    if summary["protocol"] != decimal_protocol:
        raise ValueError("Configuration differs from the frozen evaluation protocol")
    with client_path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    owners = {}
    with snapshots_path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if row["snapshot_date"] >= protocol.values["test_start"]:
                continue
            loan, client = row["loan_id"], row["client_id"]
            if loan in owners and owners[loan] != client:
                raise ValueError("Inconsistent pretest loan ownership")
            owners[loan] = client
    pretest = Counter()
    with attempts_path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if (
                protocol.values["contract_start"]
                <= row["attempt_date"]
                < protocol.values["test_start"]
                and row["provider"] == "A"
            ):
                if row["loan_id"] not in owners:
                    raise ValueError("Pretest A attempt has no known lender")
                pretest[owners[row["loan_id"]]] += 1
    with (data_dir / "clients.csv").open(newline="", encoding="utf-8") as stream:
        clients = {row["client_id"] for row in csv.DictReader(stream)}
    if clients != {row["client_id"] for row in rows} or not set(pretest).issubset(clients):
        raise ValueError("Lender populations differ between raw data and evaluated policies")
    if sum(pretest.values()) != summary["initial_a_consumed"]:
        raise ValueError("Pretest A consumption differs from evaluated opening capacity")
    for path in (attempts_path, snapshots_path, data_dir / "clients.csv"):
        expected_hash = summary.get("source_sha256", {}).get(path.name)
        if expected_hash and hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
            raise ValueError(f"{path.name} source differs from the frozen evaluation")
    fixed = number(summary["april_fixed_cost"])
    allocations = allocation_views(rows, fixed, pretest)
    tariffs = tariff_views(rows, fixed)
    prices = lambda_views(rows, fixed)
    # Create only after validation: never overwrite frozen outputs or previous diagnostic runs.
    output.mkdir(parents=True, exist_ok=False)
    _write_csv(output / "allocation_views.csv", allocations)
    _write_csv(output / "tariff_diagnostic.csv", tariffs)
    _write_csv(output / "fixed_action_lambda.csv", prices)
    metadata = {
        "scope": summary["scope"],
        "pretest_weight_window": {
            "start_inclusive": protocol.values["contract_start"],
            "end_exclusive": protocol.values["test_start"],
            "basis": "Submitted A attempts, independent of payment outcomes",
        },
        "pretest_A_units_by_lender": dict(sorted(pretest.items())),
        "fixed_period_A_cost": str(fixed),
        "source_sha256": {
            "summary.json": hashlib.sha256(summary_path.read_bytes()).hexdigest(),
            "per_client.csv": hashlib.sha256(client_path.read_bytes()).hexdigest(),
            "payment_attempts.csv": hashlib.sha256(attempts_path.read_bytes()).hexdigest(),
            "loan_snapshots.csv": hashlib.sha256(snapshots_path.read_bytes()).hexdigest(),
            "clients.csv": hashlib.sha256((data_dir / "clients.csv").read_bytes()).hexdigest(),
        },
        "warnings": [
            "Frozen actions and response model are unchanged; no policy reoptimization.",
            "Pretest weights are held identical across policies; own-policy weights are diagnostic.",
            "Tariff 1*A is not allocation of the same fixed prepaid cash commitment.",
            "Usage pricing omits unused commitment; the monthly residual can be negative.",
            "Subtracting that residual reconciles usage pricing to the allocated cash margin.",
            "Lambda is a decision penalty, never an additional accounting expense.",
            "No lambda was selected, no forecast fitted, and no six-month margin is identified.",
            "No forced June-30 capacity exhaustion target is imposed.",
            "April diagnostics do not create new untouched-test evidence.",
            "Six-decimal published per-lender inputs can differ from headline sums by rounding.",
        ],
    }
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (output / "README.md").write_text(
        "# Frozen-action economic diagnostics\n\n"
        "Accounting views use the same lender population and fixed monthly A commitment.\n"
        "Each allocation view reconciles with its TOTAL row; only lender attribution changes.\n"
        "Equal weights are primary. Pretest A-use weights are fixed across policies.\n"
        "Own-policy A-use weights change with the policy and are sensitivity diagnostics only.\n\n"
        "The tariff table subtracts nominal 1.0 per A attempt. It is a usage-priced diagnostic,\n"
        "not the prepaid cash margin. Its TOTAL residual bridges back to the same cash margin:\n"
        "usage-priced margin minus (fixed cost minus tariff charges). Under monthly accrual,\n"
        "this residual may be negative and is not physical unused allowance.\n\n"
        "The lambda table holds all actions fixed. Shadow-adjusted scores change while\n"
        "accounting margins remain unchanged. No opportunity price is added to cash expenses.\n"
        "No price is selected and no scarcity-aware policy has been reoptimized here.\n\n"
        "These are April conditional replay diagnostics, not causal gains or a six-month\n"
        "forecast. May-June admission, provider response and future balances remain unmodeled;\n"
        "no contract projection is invented and no requirement forces prepaid units to zero.\n"
        "Results inspected after April cannot be described as a new untouched test.\n",
        encoding="utf-8",
    )
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluation-dir", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("conf/protocol.json"))
    args = parser.parse_args()
    run(args.evaluation_dir, args.data_dir, args.output, Protocol.load(args.config))
    print(f"Economic diagnostics: {args.output}")


if __name__ == "__main__":
    main()
