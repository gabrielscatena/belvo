"""Local transactional authority. External submission is deliberately outside its transaction."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from belvo.config import Protocol
from belvo.domain import fingerprint
from belvo.pipelines.daily import baseline


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS quota(
 id INTEGER PRIMARY KEY CHECK(id=1), total INTEGER NOT NULL,
 consumed INTEGER NOT NULL CHECK(consumed>=0), reserved INTEGER NOT NULL CHECK(reserved>=0),
 CHECK(total>=consumed+reserved));
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS versions(
 hash TEXT PRIMARY KEY,payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS receipts(
 batch TEXT,source_index INTEGER,version TEXT,status TEXT,reason TEXT,
 PRIMARY KEY(batch,source_index));
CREATE TABLE IF NOT EXISTS decisions(
 loan_id TEXT,day TEXT,version TEXT,payload TEXT NOT NULL,PRIMARY KEY(loan_id,day));
CREATE TABLE IF NOT EXISTS attempts(
 id TEXT PRIMARY KEY,loan_id TEXT,day TEXT,provider TEXT,amount INTEGER CHECK(amount>0),
 state TEXT CHECK(state IN ('ready','sending','unknown','submitted','cancelled')),
 outcome TEXT CHECK(outcome IN ('success','failed') OR outcome IS NULL),
 available_on TEXT);
CREATE INDEX IF NOT EXISTS attempt_dispatch ON attempts(state,day,id);
CREATE INDEX IF NOT EXISTS attempt_loan_day ON attempts(loan_id,day,state);
"""


class Store:
    def __init__(self, path: Path, protocol: Protocol, consumed=0, capacity=None):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path, self.protocol = path, protocol
        total = protocol.sample_capacity if capacity is None else capacity
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(SCHEMA)
            db.execute("INSERT OR IGNORE INTO quota VALUES(1,?,?,0)", (total, consumed))
            identity = fingerprint(protocol.values)
            db.execute("INSERT OR IGNORE INTO meta VALUES('protocol',?)", (identity,))
            if db.execute("SELECT value FROM meta WHERE key='protocol'").fetchone()[0] != identity:
                raise ValueError("State belongs to a different protocol; use a new database")
            if db.execute("SELECT total FROM quota").fetchone()[0] != total:
                raise ValueError("Cannot change contracted capacity of existing state")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10, factory=ClosingConnection)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA synchronous=FULL")
        return db

    @contextmanager
    def transaction(self):
        db = self.connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def quota(self, db=None):
        if db is None:
            with self.connect() as conn:
                return self.quota(conn)
        row = dict(db.execute("SELECT * FROM quota WHERE id=1").fetchone())
        row["free"] = row["total"] - row["reserved"] - row["consumed"]
        return row

    def _cancel_unsent(self, db, loan_id, day):
        count = db.execute(
            "SELECT count(*) FROM attempts WHERE loan_id=? AND day=? "
            "AND state='ready' AND provider='A'",
            (loan_id, day),
        ).fetchone()[0]
        db.execute(
            "UPDATE attempts SET state='cancelled' WHERE loan_id=? AND day=? AND state='ready'",
            (loan_id, day),
        )
        db.execute("UPDATE quota SET reserved=reserved-? WHERE id=1", (count,))

    def commit_day(self, valid, rejected, raw, day, selector=None):
        selector = selector or baseline
        with self.transaction() as db:
            batch = fingerprint(raw)
            by_id = {r["loan_id"]: r for r in rejected if r["loan_id"]}
            valid_ids = {loan.loan_id for loan in valid}
            for entry in raw:
                key = entry["payload"].get("loan_id")
                error = by_id.get(key, {})
                db.execute(
                    "INSERT OR IGNORE INTO versions VALUES(?,?)",
                    (entry["version"], json.dumps(entry["payload"], sort_keys=True)),
                )
                db.execute(
                    "INSERT OR IGNORE INTO receipts VALUES(?,?,?,?,?)",
                    (
                        batch,
                        entry["source_index"],
                        entry["version"],
                        "valid" if key in valid_ids else "quarantined",
                        error.get("reason", "missing_identity" if not key else ""),
                    ),
                )
            # Previous-day intents cannot be sent late. Unknown/sending attempts remain reserved.
            expired = db.execute(
                "SELECT DISTINCT loan_id,day FROM attempts WHERE state='ready' AND day<?", (day,)
            ).fetchall()
            for row in expired:
                self._cancel_unsent(db, row["loan_id"], row["day"])
            pending, result = [], []
            for loan in valid:
                old = db.execute(
                    "SELECT * FROM decisions WHERE loan_id=? AND day=?", (loan.loan_id, day)
                ).fetchone()
                unsafe = db.execute(
                    "SELECT count(*) FROM attempts WHERE loan_id=? "
                    "AND (state IN ('sending','unknown') OR "
                    "(day=? AND state='submitted'))",
                    (loan.loan_id, day),
                ).fetchone()[0]
                if unsafe:
                    if old and old["version"] != loan.version:
                        self._cancel_unsent(db, loan.loan_id, day)
                    value = (
                        json.loads(old["payload"])
                        if old
                        else {
                            "loan_id": loan.loan_id,
                            "client_id": loan.client_id,
                            "day": day,
                            "version": loan.version,
                            "plan": {"amounts": [], "providers": []},
                        }
                    )
                    value = value | {
                        "status": "protected",
                        "reason": "submission_requires_reconciliation",
                    }
                    result.append(value)
                elif old and old["version"] == loan.version:
                    result.append(json.loads(old["payload"]))
                else:
                    self._cancel_unsent(db, loan.loan_id, day)
                    pending.append(loan)
            selected, _ = selector(pending, self.quota(db)["free"], self.protocol)
            loans_by_id = {loan.loan_id: loan for loan in pending}
            if {r.get("loan_id") for r in selected} != set(loans_by_id) or len(selected) != len(
                pending
            ):
                raise ValueError("Selector must return exactly one decision per pending loan")
            for row in selected:
                loan = loans_by_id[row["loan_id"]]
                amounts, providers = row["plan"]["amounts"], row["plan"]["providers"]
                if (
                    len(amounts) != len(providers)
                    or any(p not in ("A", "B") for p in providers)
                    or any(type(m) is not int or not 0 < m <= loan.cap for m in amounts)
                    or sum(amounts) > loan.balance
                    or row.get("version") != loan.version
                    or ("A" in providers and not self.protocol.a_available(day))
                ):
                    raise ValueError("Selector returned an invalid plan")
            requested = sum(r["plan"]["providers"].count("A") for r in selected)
            if requested > self.quota(db)["free"]:
                raise ValueError("Selector attempted quota overbooking")
            db.execute("UPDATE quota SET reserved=reserved+? WHERE id=1", (requested,))
            for row in selected:
                db.execute(
                    "INSERT OR REPLACE INTO decisions VALUES(?,?,?,?)",
                    (row["loan_id"], day, row["version"], json.dumps(row)),
                )
                for index, (amount, provider) in enumerate(
                    zip(row["plan"]["amounts"], row["plan"]["providers"], strict=True)
                ):
                    aid = fingerprint([row["loan_id"], day, row["version"], row["plan"], index])
                    db.execute(
                        "INSERT INTO attempts VALUES(?,?,?,?,?, 'ready',NULL,NULL)",
                        (aid, row["loan_id"], day, provider, amount),
                    )
            reported_rejections = []
            for row in rejected:
                if not row["loan_id"]:
                    reported_rejections.append(row)
                    continue
                unsafe = db.execute(
                    "SELECT count(*) FROM attempts WHERE loan_id=? AND day=? "
                    "AND state IN ('sending','unknown','submitted')",
                    (row["loan_id"], day),
                ).fetchone()[0]
                if unsafe:
                    self._cancel_unsent(db, row["loan_id"], day)
                    row = row | {
                        "status": "protected_invalid_correction",
                        "reason": row["reason"] + ";existing_submission_preserved",
                    }
                else:
                    self._cancel_unsent(db, row["loan_id"], day)
                    db.execute(
                        "INSERT OR REPLACE INTO decisions VALUES(?,?,?,?)",
                        (row["loan_id"], day, row["version"], json.dumps(row)),
                    )
                reported_rejections.append(row)
            return result + selected + reported_rejections

    def claim(self, day):
        with self.transaction() as db:
            row = db.execute(
                "SELECT * FROM attempts WHERE state='ready' AND day=? ORDER BY id LIMIT 1", (day,)
            ).fetchone()
            if not row:
                return None
            db.execute("UPDATE attempts SET state='sending' WHERE id=?", (row["id"],))
            return dict(row)

    def delivery(self, aid, accepted):
        """accepted: True confirmed, False proven not submitted, None uncertain."""
        with self.transaction() as db:
            row = db.execute("SELECT * FROM attempts WHERE id=?", (aid,)).fetchone()
            if not row:
                raise ValueError("Unknown attempt")
            if row["state"] in ("submitted", "cancelled"):
                return
            if row["state"] not in ("sending", "unknown"):
                raise ValueError("Attempt must be claimed before delivery")
            target = "unknown" if accepted is None else "submitted" if accepted else "cancelled"
            if accepted is not None and row["provider"] == "A":
                db.execute(
                    "UPDATE quota SET reserved=reserved-1, consumed=consumed+? WHERE id=1",
                    (int(accepted),),
                )
            db.execute("UPDATE attempts SET state=? WHERE id=?", (target, aid))

    def outcome(self, aid, status, available_on):
        with self.transaction() as db:
            row = db.execute("SELECT * FROM attempts WHERE id=?", (aid,)).fetchone()
            if not row or row["state"] != "submitted" or available_on <= row["day"]:
                raise ValueError("Outcome requires confirmed submission and D+1 availability")
            if row["outcome"] and (row["outcome"], row["available_on"]) != (status, available_on):
                raise ValueError("Conflicting outcome must be investigated")
            db.execute(
                "UPDATE attempts SET outcome=?,available_on=? WHERE id=?",
                (status, available_on, aid),
            )

    def attempts(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM attempts ORDER BY id")]


class SimulatedProvider:
    """Durable registry in a separate database models external idempotent acceptance."""

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path, factory=ClosingConnection) as db:
            db.execute("CREATE TABLE IF NOT EXISTS accepted(id TEXT PRIMARY KEY,payload TEXT)")

    def submit(self, attempt):
        payload = json.dumps(
            {k: attempt[k] for k in ("id", "loan_id", "day", "provider", "amount")}, sort_keys=True
        )
        with sqlite3.connect(self.path, timeout=10, factory=ClosingConnection) as db:
            old = db.execute("SELECT payload FROM accepted WHERE id=?", (attempt["id"],)).fetchone()
            if old and old[0] != payload:
                raise ValueError("Idempotency key reused with different payload")
            db.execute("INSERT OR IGNORE INTO accepted VALUES(?,?)", (attempt["id"], payload))

    def exists(self, aid):
        with sqlite3.connect(self.path, factory=ClosingConnection) as db:
            return bool(db.execute("SELECT 1 FROM accepted WHERE id=?", (aid,)).fetchone())


def execute(store: Store, provider: SimulatedProvider, day, fault=None):
    count = 0
    while (attempt := store.claim(day)) is not None:
        if fault == "timeout_before":
            store.delivery(attempt["id"], None)
            return count
        provider.submit(attempt)
        if fault == "crash_after":
            raise RuntimeError("Simulated process interruption after external acceptance")
        store.delivery(attempt["id"], None if fault == "timeout_after" else True)
        count += 1
        if fault:
            return count
    return count


def reconcile(store: Store, provider: SimulatedProvider):
    for row in store.attempts():
        if row["state"] in ("sending", "unknown"):
            # Simulator registry is authoritative. Real APIs need definitive evidence,
            # not merely absence from an eventually-consistent query.
            store.delivery(row["id"], provider.exists(row["id"]))
