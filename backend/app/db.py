import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any


class Database:
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or os.environ.get("SQLITE_DB_PATH", "recall.db")
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS analyses (
                    analysis_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    alert_text TEXT NOT NULL,
                    memory_enabled INTEGER NOT NULL,
                    result_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS outcomes (
                    analysis_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    result TEXT NOT NULL,
                    notes TEXT NOT NULL,
                    retained_doc_id TEXT
                )
                """
            )
            conn.commit()

    def save_analysis(
        self,
        analysis_id: str,
        alert_text: str,
        memory_enabled: bool,
        result_data: dict[str, Any],
    ) -> None:
        now_str = datetime.now(timezone.utc).isoformat()
        res_json = json.dumps(result_data)
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO analyses (analysis_id, created_at, alert_text, memory_enabled, result_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (analysis_id, now_str, alert_text, 1 if memory_enabled else 0, res_json),
            )
            conn.commit()

    def get_analysis(self, analysis_id: str) -> dict[str, Any] | None:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM analyses WHERE analysis_id = ?", (analysis_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "analysis_id": row["analysis_id"],
                "created_at": row["created_at"],
                "alert_text": row["alert_text"],
                "memory_enabled": bool(row["memory_enabled"]),
                "result_data": json.loads(row["result_json"]),
            }

    def save_outcome(
        self,
        analysis_id: str,
        result: str,
        notes: str,
        retained_doc_id: str,
    ) -> bool:
        """
        Saves outcome idempotently. Returns True if saved new outcome, False if already existed.
        """
        now_str = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT result FROM outcomes WHERE analysis_id = ?", (analysis_id,)
            )
            existing = cursor.fetchone()
            if existing:
                return False  # Idempotent skip

            conn.execute(
                """
                INSERT INTO outcomes (analysis_id, created_at, result, notes, retained_doc_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (analysis_id, now_str, result, notes, retained_doc_id),
            )
            conn.commit()
            return True

    def get_outcome(self, analysis_id: str) -> dict[str, Any] | None:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM outcomes WHERE analysis_id = ?", (analysis_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "analysis_id": row["analysis_id"],
                "created_at": row["created_at"],
                "result": row["result"],
                "notes": row["notes"],
                "retained_doc_id": row["retained_doc_id"],
            }
