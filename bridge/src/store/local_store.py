import json
import sqlite3
from pathlib import Path
from typing import Any


class BridgeLocalStore:
    """
    Durable local store for the WAAST360 Bridge running on Windows.
    Provides offline resilience: when the internet goes down, the Bridge
    retains pending jobs, retry queues, idempotency correlation keys,
    and diagnostic event logs in an embedded local SQLite database.
    """

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            data_dir = Path.home() / ".waast360" / "bridge"
            data_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = str(data_dir / "bridge_store.db")
        else:
            self.db_path = db_path
        self._mem_conn: sqlite3.Connection | None = None
        if self.db_path == ":memory:":
            self._mem_conn = sqlite3.connect(":memory:")
            self._mem_conn.row_factory = sqlite3.Row
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._mem_conn is not None:
            return self._mem_conn
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    correlation_id TEXT UNIQUE,
                    job_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL, -- PENDING, ACTIVE, COMPLETED, FAILED, UNKNOWN
                    retry_count INTEGER DEFAULT 0,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS posting_history (
                    correlation_id TEXT PRIMARY KEY,
                    voucher_reference TEXT,
                    voucher_number TEXT,
                    status TEXT NOT NULL,
                    result_json TEXT,
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS diagnostics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    details_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS tally_health_cache (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    is_online INTEGER NOT NULL,
                    version TEXT,
                    response_time_ms REAL,
                    capabilities_json TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.commit()

    # =========================================================================
    # JOB QUEUE MANAGEMENT
    # =========================================================================

    def enqueue_job(
        self, job_id: str, correlation_id: str, job_type: str, payload: dict[str, Any]
    ) -> bool:
        with self._get_connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO jobs (job_id, correlation_id, job_type, payload, status, retry_count, updated_at)
                    VALUES (?, ?, ?, ?, 'PENDING', 0, CURRENT_TIMESTAMP)
                    ON CONFLICT(job_id) DO UPDATE SET
                        status = excluded.status,
                        payload = excluded.payload,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (job_id, correlation_id, job_type, json.dumps(payload)),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def get_pending_jobs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT job_id, correlation_id, job_type, payload, status, retry_count, error_message, created_at, updated_at
                FROM jobs
                WHERE status IN ('PENDING', 'UNKNOWN')
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            return [
                {
                    "job_id": r["job_id"],
                    "correlation_id": r["correlation_id"],
                    "job_type": r["job_type"],
                    "payload": json.loads(r["payload"]),
                    "status": r["status"],
                    "retry_count": r["retry_count"],
                    "error_message": r["error_message"],
                    "created_at": r["created_at"],
                }
                for r in rows
            ]

    def update_job_status(
        self,
        job_id: str,
        status: str,
        error_message: str | None = None,
        increment_retry: bool = False,
    ):
        with self._get_connection() as conn:
            if increment_retry:
                conn.execute(
                    """
                    UPDATE jobs
                    SET status = ?, error_message = ?, retry_count = retry_count + 1, updated_at = CURRENT_TIMESTAMP
                    WHERE job_id = ?
                    """,
                    (status, error_message, job_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE jobs
                    SET status = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE job_id = ?
                    """,
                    (status, error_message, job_id),
                )
            conn.commit()

    # =========================================================================
    # IDEMPOTENCY & POSTING HISTORY
    # =========================================================================

    def record_posting_history(
        self,
        correlation_id: str,
        voucher_reference: str | None,
        voucher_number: str | None,
        status: str,
        result: dict[str, Any],
    ):
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO posting_history (correlation_id, voucher_reference, voucher_number, status, result_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(correlation_id) DO UPDATE SET
                    voucher_number = excluded.voucher_number,
                    status = excluded.status,
                    result_json = excluded.result_json
                """,
                (
                    correlation_id,
                    voucher_reference,
                    voucher_number,
                    status,
                    json.dumps(result),
                ),
            )
            conn.commit()

    def get_posting_history(self, correlation_id: str) -> dict[str, Any] | None:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM posting_history WHERE correlation_id = ?",
                (correlation_id,),
            )
            row = cursor.fetchone()
            if row:
                return {
                    "correlation_id": row["correlation_id"],
                    "voucher_reference": row["voucher_reference"],
                    "voucher_number": row["voucher_number"],
                    "status": row["status"],
                    "result": json.loads(row["result_json"]) if row["result_json"] else {},
                }
            return None

    # =========================================================================
    # DIAGNOSTICS & HEALTH CACHE
    # =========================================================================

    def log_diagnostic(self, event_type: str, message: str, details: dict[str, Any] | None = None):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO diagnostics (event_type, message, details_json) VALUES (?, ?, ?)",
                (event_type, message, json.dumps(details) if details else None),
            )
            conn.commit()

    def update_tally_health(
        self,
        is_online: bool,
        version: str,
        response_time_ms: float,
        capabilities: dict[str, Any],
    ):
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO tally_health_cache (id, is_online, version, response_time_ms, capabilities_json, updated_at)
                VALUES (1, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    is_online = excluded.is_online,
                    version = excluded.version,
                    response_time_ms = excluded.response_time_ms,
                    capabilities_json = excluded.capabilities_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    1 if is_online else 0,
                    version,
                    response_time_ms,
                    json.dumps(capabilities),
                ),
            )
            conn.commit()

    def get_last_tally_health(self) -> dict[str, Any] | None:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM tally_health_cache WHERE id = 1")
            row = cursor.fetchone()
            if row:
                return {
                    "is_online": bool(row["is_online"]),
                    "version": row["version"],
                    "response_time_ms": row["response_time_ms"],
                    "capabilities": json.loads(row["capabilities_json"])
                    if row["capabilities_json"]
                    else {},
                    "updated_at": row["updated_at"],
                }
            return None
