"""SQLite-backed job records and a single background worker thread.

Lifecycle: queued -> running -> succeeded | failed | cancelled.
Cancelling a queued job cancels it at once; cancelling a running job sets a flag that
the computation checks between steps. Jobs left 'running' by a server restart are
marked failed on startup; jobs still 'queued' are put back on the queue. Logs contain job ids and states only - never request
parameters (which can include coordinates).
"""

from __future__ import annotations

import hashlib
import json
import logging
import queue
import sqlite3
import threading
import traceback
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from paf_core.errors import JobCancelled, PafError

log = logging.getLogger("paf_api.jobs")

FINAL = {"succeeded", "failed", "cancelled"}
Runner = Callable[[dict, Callable[[float, str], None], Callable[[], bool]], dict]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStore:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(db_path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._db.execute(
                """CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, status TEXT NOT NULL,
                    progress REAL NOT NULL DEFAULT 0, message TEXT NOT NULL DEFAULT '',
                    params TEXT NOT NULL, result TEXT, error TEXT,
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    created TEXT NOT NULL, updated TEXT NOT NULL)"""
            )
            cols = {r[1] for r in self._db.execute("PRAGMA table_info(jobs)")}
            for col in ("fingerprint", "idempotency_key"):  # migration for databases created by v0.1.0
                if col not in cols:
                    self._db.execute(f"ALTER TABLE jobs ADD COLUMN {col} TEXT")
            self._db.commit()

    def _exec(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            rows = self._db.execute(sql, args).fetchall()
            self._db.commit()
            return rows

    @staticmethod
    def fingerprint(kind: str, params: dict) -> str:
        return hashlib.sha256((kind + json.dumps(params, sort_keys=True)).encode()).hexdigest()

    def create(self, kind: str, params: dict, idempotency_key: str | None = None) -> str:
        jid = uuid.uuid4().hex
        t = _now()
        self._exec("INSERT INTO jobs (id, kind, status, params, created, updated, fingerprint, idempotency_key) "
                   "VALUES (?,?,?,?,?,?,?,?)",
                   (jid, kind, "queued", json.dumps(params), t, t, self.fingerprint(kind, params), idempotency_key))
        return jid

    def find_active(self, fingerprint: str) -> dict | None:
        rows = self._exec("SELECT * FROM jobs WHERE fingerprint = ? AND status IN ('queued','running') "
                          "ORDER BY created LIMIT 1", (fingerprint,))
        return dict(rows[0]) if rows else None

    def find_by_key(self, key: str) -> dict | None:
        rows = self._exec("SELECT * FROM jobs WHERE idempotency_key = ? ORDER BY created DESC LIMIT 1", (key,))
        return dict(rows[0]) if rows else None

    def count_active(self) -> int:
        return self._exec("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running')")[0][0]

    def queued_ids(self) -> list[str]:
        return [r["id"] for r in self._exec("SELECT id FROM jobs WHERE status = 'queued' ORDER BY created")]

    def purge_older_than(self, days: float) -> int:
        """Delete finished jobs (and their results) last updated more than ``days`` ago."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = self._exec("SELECT id FROM jobs WHERE status IN ('succeeded','failed','cancelled') AND updated < ?",
                          (cutoff,))
        self._exec("DELETE FROM jobs WHERE status IN ('succeeded','failed','cancelled') AND updated < ?", (cutoff,))
        return len(rows)

    def ping(self) -> bool:
        try:
            self._exec("SELECT 1")
            return True
        except sqlite3.Error:
            return False

    def get(self, jid: str) -> dict | None:
        rows = self._exec("SELECT * FROM jobs WHERE id = ?", (jid,))
        return dict(rows[0]) if rows else None

    def list(self, limit: int = 50) -> list[dict]:
        return [dict(r) for r in self._exec("SELECT * FROM jobs ORDER BY created DESC LIMIT ?", (limit,))]

    def update(self, jid: str, **fields: Any) -> None:
        cols = ", ".join(f"{k} = ?" for k in fields)
        self._exec(f"UPDATE jobs SET {cols}, updated = ? WHERE id = ?", (*fields.values(), _now(), jid))

    def request_cancel(self, jid: str) -> dict | None:
        job = self.get(jid)
        if job is None or job["status"] in FINAL:
            return job
        if job["status"] == "queued":
            self.update(jid, status="cancelled", cancel_requested=1, message="Cancelled before start")
        else:
            self.update(jid, cancel_requested=1, message="Cancellation requested")
        return self.get(jid)

    def cancel_requested(self, jid: str) -> bool:
        rows = self._exec("SELECT cancel_requested FROM jobs WHERE id = ?", (jid,))
        return bool(rows and rows[0][0])

    def mark_interrupted(self) -> int:
        rows = self._exec("SELECT id FROM jobs WHERE status IN ('running')")
        for r in rows:
            self.update(r["id"], status="failed", error=json.dumps(
                {"code": "interrupted", "message": "The server stopped while this job was running. Submit it again."}))
        return len(rows)

    def close(self) -> None:
        with self._lock:
            self._db.close()


class Worker:
    def __init__(self, store: JobStore, runner: Runner):
        self.store, self.runner = store, runner
        self._q: "queue.Queue[str | None]" = queue.Queue()
        self._thread = threading.Thread(target=self._loop, name="paf-worker", daemon=True)

    def start(self) -> None:
        self._thread.start()

    @property
    def alive(self) -> bool:
        return self._thread.is_alive()

    def stop(self) -> None:
        self._q.put(None)
        self._thread.join(timeout=10)

    def submit(self, jid: str) -> None:
        self._q.put(jid)

    def _loop(self) -> None:
        while (jid := self._q.get()) is not None:
            self._run(jid)

    def _run(self, jid: str) -> None:
        job = self.store.get(jid)
        if job is None or job["status"] != "queued":
            return
        self.store.update(jid, status="running", message="Started")
        log.info("job %s running", jid)

        def progress(fraction: float, message: str) -> None:
            self.store.update(jid, progress=max(0.0, min(1.0, float(fraction))), message=message[:200])

        try:
            result = self.runner(json.loads(job["params"]), progress, lambda: self.store.cancel_requested(jid))
            self.store.update(jid, status="succeeded", progress=1.0, message="Done", result=json.dumps(result))
            log.info("job %s succeeded", jid)
        except JobCancelled:
            self.store.update(jid, status="cancelled", message="Cancelled")
            log.info("job %s cancelled", jid)
        except PafError as exc:
            self.store.update(jid, status="failed", error=json.dumps({"code": type(exc).__name__, "message": str(exc)}))
            log.info("job %s failed: %s", jid, type(exc).__name__)
        except Exception:  # noqa: BLE001 - report safely, keep the worker alive
            log.error("job %s crashed:\n%s", jid, traceback.format_exc())
            self.store.update(jid, status="failed", error=json.dumps(
                {"code": "internal_error", "message": "Unexpected server error; see server log."}))
