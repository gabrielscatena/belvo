"""Local transactional authority. External submission is deliberately outside its transaction."""

import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import asdict
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
CREATE TABLE IF NOT EXISTS decision_events(
 id TEXT PRIMARY KEY,payload TEXT NOT NULL,recorded_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS batches(
 id TEXT PRIMARY KEY,day TEXT NOT NULL,received_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS source_heads(
 day TEXT,scope TEXT,revision INTEGER NOT NULL,content_hash TEXT NOT NULL,
 PRIMARY KEY(day,scope));
CREATE TABLE IF NOT EXISTS history_issues(
 id TEXT PRIMARY KEY,day TEXT,payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS models(id TEXT PRIMARY KEY,payload TEXT NOT NULL);
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

    def bind_policy(self, identity):
        with self.transaction() as db:
            db.execute("INSERT OR IGNORE INTO meta VALUES('policy',?)", (identity,))
            if db.execute("SELECT value FROM meta WHERE key='policy'").fetchone()[0] != identity:
                raise ValueError("Use separate state for a different policy")

    def bind_provider(self, identity):
        with self.transaction() as db:
            db.execute("INSERT OR IGNORE INTO meta VALUES('provider',?)", (identity,))
            if db.execute("SELECT value FROM meta WHERE key='provider'").fetchone()[0] != identity:
                raise ValueError("Provider registry was replaced; restore it before reconciliation")

    @staticmethod
    def _save_decision(db, row):
        payload = json.dumps(row)
        db.execute(
            "INSERT OR IGNORE INTO decision_events(id,payload) VALUES(?,?)",
            (fingerprint(row), payload),
        )
        db.execute(
            "INSERT OR REPLACE INTO decisions VALUES(?,?,?,?)",
            (row["loan_id"], row["day"], row["version"], payload),
        )

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

    @staticmethod
    def _register_source(db, valid, rejected, raw, day, clients, revision):
        """Content identifies a retry; only the source can order distinct corrections."""
        if revision is not None and (type(revision) is not int or revision < 1):
            raise ValueError("Source revision must be a positive integer")
        if (
            db.execute("SELECT 1 FROM decisions LIMIT 1").fetchone()
            and not db.execute("SELECT 1 FROM source_heads LIMIT 1").fetchone()
        ):
            raise ValueError("Legacy state has no source ordering; use a new simulation store")
        entries = [
            (
                r["payload"].get("client_id"),
                r["payload"].get("loan_id"),
                {"snapshot": r["payload"], "context": r.get("context")},
            )
            for r in raw
        ] or [
            (r["client_id"], r["loan_id"], r)
            for r in [*(asdict(loan) for loan in valid), *rejected]
        ]
        scopes = {}
        for client, loan_id, payload in entries:
            if loan_id:
                scopes.setdefault("loan:" + loan_id, []).append(payload)
        for client in clients or ():
            scopes["client:" + client] = [p for c, _, p in entries if c == client]
        for old in db.execute("SELECT payload FROM decisions WHERE day=?", (day,)):
            previous = json.loads(old["payload"])
            if clients is not None and previous["client_id"] in clients:
                scopes.setdefault("loan:" + previous["loan_id"], [])
        identities = {}
        for scope, payloads in sorted(scopes.items()):
            identity = fingerprint(sorted(payloads, key=fingerprint))
            old = db.execute(
                "SELECT revision,content_hash FROM source_heads WHERE day=? AND scope=?",
                (day, scope),
            ).fetchone()
            # No source sequence is invented from local receipt time or a content hash.
            number = revision if revision is not None else old["revision"] if old else 1
            if old and number < old["revision"]:
                raise ValueError("Stale source revision; latest portfolio remains authoritative")
            if old and number == old["revision"] and identity != old["content_hash"]:
                raise ValueError("Changed payload requires a higher source revision")
            db.execute(
                "INSERT OR REPLACE INTO source_heads VALUES(?,?,?,?)",
                (day, scope, number, identity),
            )
            identities[scope] = [number, identity]
        return fingerprint([day, identities])

    def commit_day(
        self,
        valid,
        rejected,
        raw,
        day,
        selector=None,
        portfolio_clients=None,
        source_revision=None,
        history_issues=(),
        model_artifact=None,
        decision_basis=None,
    ):
        selector = selector or baseline
        if decision_basis is None and model_artifact is not None:
            decision_basis = model_artifact["model_hash"]
        with self.transaction() as db:
            latest = db.execute("SELECT value FROM meta WHERE key='latest_day'").fetchone()
            if latest and day < latest[0]:
                raise ValueError("Cannot rewind live state; replay into a separate database")
            batch = self._register_source(
                db, valid, rejected, raw, day, portfolio_clients, source_revision
            )
            for issue in history_issues:
                db.execute(
                    "INSERT OR IGNORE INTO history_issues VALUES(?,?,?)",
                    (fingerprint([day, issue]), day, json.dumps(issue)),
                )
            if model_artifact is not None:
                identity = model_artifact["model_hash"]
                if (
                    fingerprint({k: v for k, v in model_artifact.items() if k != "model_hash"})
                    != identity
                ):
                    raise ValueError("Invalid model identity")
                db.execute(
                    "INSERT OR IGNORE INTO models VALUES(?,?)",
                    (identity, json.dumps(model_artifact)),
                )
            db.execute("INSERT OR REPLACE INTO meta VALUES('latest_day',?)", (day,))
            db.execute("INSERT OR IGNORE INTO batches(id,day) VALUES(?,?)", (batch, day))
            withdrawals = []
            if portfolio_clients is not None:
                present = {loan.loan_id for loan in valid} | {r["loan_id"] for r in rejected}
                existing = db.execute(
                    "SELECT payload FROM decisions WHERE day=?", (day,)
                ).fetchall()
                for old in existing:
                    value = json.loads(old["payload"])
                    if value["client_id"] in portfolio_clients and value["loan_id"] not in present:
                        self._cancel_unsent(db, value["loan_id"], day)
                        value = value | {
                            "status": "withdrawn",
                            "reason": "absent_from_corrected_full_portfolio",
                            "plan": {"amounts": [], "providers": []},
                        }
                        self._save_decision(db, value)
                        withdrawals.append(value)
            by_id = {r["loan_id"]: r for r in rejected if r["loan_id"]}
            valid_ids = {loan.loan_id for loan in valid}
            for entry in raw:
                key = entry["payload"].get("loan_id")
                error = by_id.get(key, {})
                db.execute(
                    "INSERT OR IGNORE INTO versions VALUES(?,?)",
                    (
                        entry["version"],
                        json.dumps(
                            {"snapshot": entry["payload"], "context": entry.get("context")},
                            sort_keys=True,
                        ),
                    ),
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
                elif (
                    old
                    and old["version"] == loan.version
                    and (
                        decision_basis is None
                        or json.loads(old["payload"]).get("decision_basis") == decision_basis
                    )
                    and json.loads(old["payload"])["status"] not in ("withdrawn", "quarantined")
                    and (
                        not json.loads(old["payload"])["plan"]["amounts"]
                        or db.execute(
                            "SELECT count(*) FROM attempts WHERE loan_id=? AND day=? "
                            "AND state='ready'",
                            (loan.loan_id, day),
                        ).fetchone()[0]
                        > 0
                    )
                ):
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
                if (
                    model_artifact is not None
                    and row.get("economics", {}).get("model_hash") != identity
                ):
                    raise ValueError("Decision must reference its persisted model")
                amounts, providers = row["plan"]["amounts"], row["plan"]["providers"]
                if (
                    len(amounts) != len(providers)
                    or len(amounts) > self.protocol.values["max_installments"]
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
                if decision_basis is not None:
                    row["decision_basis"] = decision_basis
                self._save_decision(db, row)
                for index, (amount, provider) in enumerate(
                    zip(row["plan"]["amounts"], row["plan"]["providers"], strict=True)
                ):
                    aid = fingerprint([row["loan_id"], day, row["version"], row["plan"], index])
                    base_id, generation = aid, 0
                    while previous := db.execute(
                        "SELECT state FROM attempts WHERE id=?", (aid,)
                    ).fetchone():
                        if previous["state"] != "cancelled":
                            raise ValueError("Attempt identity already active")
                        generation += 1
                        aid = fingerprint([base_id, generation])
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
                    self._save_decision(db, row)
                reported_rejections.append(row)
            return result + selected + reported_rejections + withdrawals

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
            db.execute("CREATE TABLE IF NOT EXISTS rejected(id TEXT PRIMARY KEY)")
            db.execute("CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT)")
            db.execute("INSERT OR IGNORE INTO metadata VALUES('identity',?)", (str(uuid.uuid4()),))
            self.identity = db.execute(
                "SELECT value FROM metadata WHERE key='identity'"
            ).fetchone()[0]

    def submit(self, attempt):
        payload = json.dumps(
            {k: attempt[k] for k in ("id", "loan_id", "day", "provider", "amount")}, sort_keys=True
        )
        with sqlite3.connect(self.path, timeout=10, factory=ClosingConnection) as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM rejected WHERE id=?", (attempt["id"],)).fetchone():
                return False
            old = db.execute("SELECT payload FROM accepted WHERE id=?", (attempt["id"],)).fetchone()
            if old and old[0] != payload:
                raise ValueError("Idempotency key reused with different payload")
            db.execute("INSERT OR IGNORE INTO accepted VALUES(?,?)", (attempt["id"], payload))
            return True

    def resolve(self, aid):
        """Atomically acknowledge acceptance or fence this identity against late acceptance."""
        with sqlite3.connect(self.path, timeout=10, factory=ClosingConnection) as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM accepted WHERE id=?", (aid,)).fetchone():
                return True
            db.execute("INSERT OR IGNORE INTO rejected VALUES(?)", (aid,))
            return False

    def exists(self, aid):
        with sqlite3.connect(self.path, factory=ClosingConnection) as db:
            return bool(db.execute("SELECT 1 FROM accepted WHERE id=?", (aid,)).fetchone())


def execute(store: Store, provider: SimulatedProvider, day, fault=None):
    store.bind_provider(provider.identity)
    count = 0
    while (attempt := store.claim(day)) is not None:
        if fault == "timeout_before":
            store.delivery(attempt["id"], None)
            return count
        accepted = provider.submit(attempt)
        if fault == "crash_after":
            raise RuntimeError("Simulated process interruption after external acceptance")
        store.delivery(attempt["id"], None if accepted and fault == "timeout_after" else accepted)
        count += 1
        if fault:
            return count
    return count


def reconcile(store: Store, provider: SimulatedProvider):
    store.bind_provider(provider.identity)
    for row in store.attempts():
        if row["state"] in ("sending", "unknown"):
            # Absence alone is unsafe even in a strongly consistent registry: a sender
            # may still be in flight. The simulator fences rejected identities atomically.
            # Real providers without this facility must retain unknown reservations.
            store.delivery(row["id"], provider.resolve(row["id"]))
