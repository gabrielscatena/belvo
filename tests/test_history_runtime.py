"""Exercise quarantine at the actual CLI boundary, not only the row validator."""

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

from belvo.data.history import load_history


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def dataset(root, *, bad_day="2026-04-01", bad_history=False):
    data = root / "data"
    data.mkdir()
    snapshots, attempts = [], []
    for i in range(200):
        snapshots.append(
            {
                "loan_id": f"H{i}",
                "client_id": "C1",
                "snapshot_date": "2026-02-01",
                "outstanding_balance": "100.00",
                "days_past_due": "0",
            }
        )
        attempts.append(
            {
                "attempt_id": f"A{i}",
                "loan_id": f"H{i}",
                "attempt_date": "2026-02-01",
                "amount": "10.00",
                "provider": "A",
                "status": "success" if i < 4 else "failed",
                "installment_count": "1",
                "installment_index": "1",
            }
        )
    snapshots += [
        {
            "loan_id": "L1",
            "client_id": "C1",
            "snapshot_date": "2026-04-01",
            "outstanding_balance": "10.00",
            "days_past_due": "0",
        },
        {
            "loan_id": "BAD",
            "client_id": "C1",
            "snapshot_date": bad_day,
            "outstanding_balance": "oops",
            "days_past_due": "0",
        },
    ]
    attempts.append(
        attempts[0]
        | {
            "attempt_id": "bad-attempt",
            "loan_id": "BAD",
            "attempt_date": bad_day,
        }
    )
    if bad_history:
        snapshots[0]["outstanding_balance"] = "oops"
        snapshots.append(snapshots[-2] | {"loan_id": "H0"})
    write_csv(data / "clients.csv", [{"client_id": "C1", "max_installment_amount": "10.00"}])
    write_csv(data / "loan_snapshots.csv", snapshots)
    write_csv(data / "payment_attempts.csv", attempts)
    return data


def run_pipeline(root, data, *extra, output_name="output"):
    output = root / output_name
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "belvo.pipelines.persistent",
            "--date",
            "2026-04-01",
            "--data-dir",
            str(data),
            "--state",
            str(root / "state.db"),
            "--provider-state",
            str(root / "provider.db"),
            "--policy",
            "economic",
            "--output",
            str(output),
            *extra,
        ],
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads((output / "decisions.json").read_text()), json.loads(
        (output / "run.json").read_text()
    )


@pytest.mark.parametrize("bad_day", ["2026-04-01", "2026-04-02"])
def test_bad_current_or_future_record_does_not_stop_a_valid_loan(tmp_path, bad_day):
    decisions, metadata = run_pipeline(tmp_path, dataset(tmp_path, bad_day=bad_day))
    by_id = {r["loan_id"]: r for r in decisions}
    assert by_id["L1"]["status"] == "attempt"
    if bad_day == "2026-04-01":
        assert by_id["BAD"]["status"] == "quarantined"
        assert not by_id["BAD"]["plan"]["amounts"]
    else:
        assert "BAD" not in by_id
    assert not metadata["history_quarantine"]


def test_invalid_history_is_audited_and_only_affected_loans_are_blocked(tmp_path):
    data = dataset(tmp_path, bad_day="2026-04-02", bad_history=True)
    decisions, metadata = run_pipeline(tmp_path, data)
    by_id = {r["loan_id"]: r for r in decisions}
    assert by_id["L1"]["status"] == "attempt"
    assert by_id["H0"]["reason"] == "invalid_history"
    assert by_id["L1"]["lender_constraint"]["status"] == "missing_lender_budget"
    assert len(metadata["history_quarantine"]) == 1
    from belvo.config import Protocol
    from belvo.state import Store

    with Store(tmp_path / "state.db", Protocol.load()).connect() as db:
        assert db.execute("SELECT count(*) FROM history_issues").fetchone()[0] == 1
        artifact = json.loads(db.execute("SELECT payload FROM models").fetchone()[0])
    assert artifact["model_hash"] == by_id["L1"]["economics"]["model_hash"]
    assert artifact == json.loads(Path(metadata["model_path"]).read_text())
    with pytest.raises(ValueError, match="Invalid historical"):
        load_history(data, before="2026-04-01")


def test_empty_valid_training_history_produces_explicit_no_attempt(tmp_path):
    data = dataset(tmp_path, bad_day="2026-04-02")
    rows = list(csv.DictReader((data / "loan_snapshots.csv").open()))
    for row in rows:
        if row["snapshot_date"] == "2026-02-01":
            row["outstanding_balance"] = "oops"
    write_csv(data / "loan_snapshots.csv", rows)
    decisions, metadata = run_pipeline(tmp_path, data)
    assert decisions[0]["reason"] == "no_available_training_history"
    assert not decisions[0]["plan"]["amounts"]
    assert metadata["model_hash"] is None
    assert len(metadata["history_quarantine"]) == 200


def test_unavailable_outcome_is_neither_used_nor_validated(tmp_path):
    data = dataset(tmp_path, bad_day="2026-03-31")
    snapshots = list(csv.DictReader((data / "loan_snapshots.csv").open()))
    snapshots[-1]["outstanding_balance"] = "100.00"
    attempts = list(csv.DictReader((data / "payment_attempts.csv").open()))
    attempts[-1]["status"] = "not-yet-available"
    write_csv(data / "loan_snapshots.csv", snapshots)
    write_csv(data / "payment_attempts.csv", attempts)
    first = load_history(data, before="2026-04-01", known_through="2026-03-30")
    attempts[-1]["status"] = "success"
    write_csv(data / "payment_attempts.csv", attempts)
    second = load_history(data, before="2026-04-01", known_through="2026-03-30")
    from belvo.config import Protocol
    from belvo.models.empirical import fit_for_day
    from belvo.optimization.select import zero_future_budget

    p = Protocol.load()
    assert (
        fit_for_day(first, p, "2026-04-01").model_hash
        == fit_for_day(second, p, "2026-04-01").model_hash
    )
    assert zero_future_budget(first, "2026-04-01", p) == zero_future_budget(second, "2026-04-01", p)


def test_a_bad_sibling_cannot_leave_a_partial_training_plan(tmp_path):
    data = dataset(tmp_path, bad_day="2026-04-02")
    attempts = list(csv.DictReader((data / "payment_attempts.csv").open()))
    attempts[0]["installment_count"] = "2"
    attempts.append(
        attempts[0]
        | {
            "attempt_id": "bad-sibling",
            "installment_index": "2",
            "amount": "oops",
        }
    )
    write_csv(data / "payment_attempts.csv", attempts)
    frame = load_history(data, before="2026-04-01", quarantine=True)
    assert "H0" not in set(frame.loan_id)
    assert len(frame.attrs["quarantine"]) == 2
    assert len(frame) == 199


def test_future_ambiguous_keys_do_not_affect_a_point_in_time_model(tmp_path):
    data = dataset(tmp_path, bad_day="2026-04-02")
    original = load_history(data, before="2026-04-01")
    attempts = list(csv.DictReader((data / "payment_attempts.csv").open()))
    attempts.append(attempts[0] | {"attempt_date": "2026-04-02", "amount": "oops"})
    write_csv(data / "payment_attempts.csv", attempts)
    from belvo.config import Protocol
    from belvo.models.empirical import fit_for_day

    changed = load_history(data, before="2026-04-01")
    p = Protocol.load()
    assert (
        fit_for_day(original, p, "2026-04-01").model_hash
        == fit_for_day(changed, p, "2026-04-01").model_hash
    )


def test_cli_stale_portfolio_cannot_dispatch_after_a_paid_correction(tmp_path):
    data = dataset(tmp_path)
    run_pipeline(tmp_path, data, "--source-revision", "1")
    original = list(csv.DictReader((data / "loan_snapshots.csv").open()))
    corrected = [
        r | {"outstanding_balance": "0.00"} if r["loan_id"] == "L1" else r for r in original
    ]
    write_csv(data / "loan_snapshots.csv", corrected)
    decisions, _ = run_pipeline(tmp_path, data, "--source-revision", "2", output_name="paid")
    assert next(r for r in decisions if r["loan_id"] == "L1")["status"] == "no_attempt"
    write_csv(data / "loan_snapshots.csv", original)
    retry = subprocess.run(
        [
            sys.executable,
            "-m",
            "belvo.pipelines.persistent",
            "--date",
            "2026-04-01",
            "--data-dir",
            str(data),
            "--state",
            str(tmp_path / "state.db"),
            "--provider-state",
            str(tmp_path / "provider.db"),
            "--policy",
            "economic",
            "--source-revision",
            "1",
            "--execute",
        ],
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert retry.returncode != 0 and "Stale source revision" in retry.stderr
    from belvo.config import Protocol
    from belvo.state import Store

    store = Store(tmp_path / "state.db", Protocol.load())
    assert store.quota()["reserved"] == 0
    assert all(a["state"] == "cancelled" for a in store.attempts())
