# Copyright 2026 Zsolt Kulcsar and Contributors. Licensed under the EUPL-1.2 or later
"""Persitence SQLite implementation for run snapshots."""

import logging
import sqlite3

from datetime import datetime, timezone
from pathlib import Path

from cds.persistence import (
    PersistRunInput,
    PersistRunResult,
    PersistenceError,
    RunStatus,
)

logger = logging.getLogger(__name__)


class SQLitePersistence:
    """Persist run snapshots to a SQLite database."""

    def __init__(self, db_path: Path) -> None:
        """Initialize persistence backend.

        Args:
            db_path: SQLite database file path.
        """
        self._db_path = db_path

    def persist_run(self, payload: PersistRunInput) -> PersistRunResult:
        """Persist one run and all associated records atomically.

        Args:
            payload: Run payload to persist.

        Returns:
            Persisted run summary.

        Raises:
            PersistenceError: If schema setup or write operations fail.
        """
        record_count = len(payload.records)
        intent_failed_count = sum(
            1 for record in payload.records if record.intent_status == "failed"
        )
        status: RunStatus = (
            "completed_with_errors"
            if payload.analyzer_error_count > 0 or intent_failed_count > 0
            else "completed"
        )
        started_at = datetime.now(tz=timezone.utc).isoformat()
        finished_at = started_at

        connection = sqlite3.connect(self._db_path)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            self._ensure_schema(connection=connection)
            connection.execute("BEGIN")
            finished_at = datetime.now(tz=timezone.utc).isoformat()
            run_cursor = connection.execute(
                "INSERT INTO runs ("
                "started_at, finished_at, root_path, provider_url, model, scope, "
                "progress_batch_size, status, analyzer_error_count, intent_failed_count, record_count"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    started_at,
                    finished_at,
                    payload.root_path,
                    payload.provider_url,
                    payload.model,
                    payload.scope,
                    payload.progress_batch_size,
                    status,
                    payload.analyzer_error_count,
                    intent_failed_count,
                    record_count,
                ),
            )
            row_id = run_cursor.lastrowid
            if row_id is None:
                logger.warning(
                    f"SQLite did not return a run id (db_path={self._db_path})"
                )
                raise PersistenceError("SQLite did not return a run id.")
            run_id = int(row_id)
            connection.executemany(
                "INSERT INTO records ("
                "run_id, kind, file_path, signature, start_line, end_line, "
                "raw_code, normalized_code, md5sum, intent, intent_status, intent_error"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        run_id,
                        record.kind,
                        record.file_path,
                        record.signature,
                        record.start_line,
                        record.end_line,
                        record.raw_code,
                        record.normalized_code,
                        record.md5sum,
                        record.intent,
                        record.intent_status,
                        record.intent_error,
                    )
                    for record in payload.records
                ],
            )
            connection.commit()
            return PersistRunResult(
                run_id=run_id,
                record_count=record_count,
                intent_failed_count=intent_failed_count,
                analyzer_error_count=payload.analyzer_error_count,
                status=status,
            )
        except sqlite3.DatabaseError as exc:
            connection.rollback()
            logger.warning(
                f"SQLite persistence failed (db_path={self._db_path} error={exc})"
            )
            raise PersistenceError(str(exc)) from exc
        finally:
            connection.close()

    def _ensure_schema(self, connection: sqlite3.Connection) -> None:
        """Create required tables and indexes when missing.

        Args:
            connection: Open SQLite connection.
        """
        connection.execute(
            "CREATE TABLE IF NOT EXISTS runs ("
            "id INTEGER PRIMARY KEY, "
            "started_at TEXT NOT NULL, "
            "finished_at TEXT NOT NULL, "
            "root_path TEXT NOT NULL, "
            "provider_url TEXT NOT NULL, "
            "model TEXT NOT NULL, "
            "scope TEXT NOT NULL, "
            "progress_batch_size INTEGER NOT NULL, "
            "status TEXT NOT NULL, "
            "analyzer_error_count INTEGER NOT NULL, "
            "intent_failed_count INTEGER NOT NULL, "
            "record_count INTEGER NOT NULL"
            ")"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS records ("
            "id INTEGER PRIMARY KEY, "
            "run_id INTEGER NOT NULL REFERENCES runs(id), "
            "kind TEXT NOT NULL, "
            "file_path TEXT NOT NULL, "
            "signature TEXT, "
            "start_line INTEGER NOT NULL, "
            "end_line INTEGER NOT NULL, "
            "raw_code TEXT NOT NULL, "
            "normalized_code TEXT NOT NULL, "
            "md5sum TEXT NOT NULL, "
            "intent TEXT, "
            "intent_status TEXT NOT NULL, "
            "intent_error TEXT"
            ")"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_records_run_id ON records(run_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_records_file_path ON records(file_path)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_records_md5sum ON records(md5sum)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_records_intent_status ON records(intent_status)"
        )
