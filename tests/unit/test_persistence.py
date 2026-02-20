import sqlite3
from pathlib import Path

import pytest

from cds.model import Record
from cds.persistence import PersistRunInput, PersistenceError
from cds.database import SQLitePersistence


def _sample_record(
    *,
    kind: str = "function",
    file_path: str = "pkg/sample.py",
    signature: str | None = "def f() -> int:",
    intent: str | None = "Return a constant integer.",
    intent_status: str = "success",
    intent_error: str | None = None,
) -> Record:
    return Record(
        kind=kind,  # type: ignore[arg-type]
        file_path=file_path,
        signature=signature,
        start_line=1,
        end_line=2,
        raw_code="def f() -> int:\n    return 1",
        normalized_code="def f() -> int:\n    return 1",
        md5sum="abc123",
        intent=intent,
        intent_status=intent_status,
        intent_error=intent_error,
    )


def test_ph3_pers_001_sqlite_persistence_inserts_run_and_records(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "cds.sqlite"
    persistence = SQLitePersistence(db_path=db_path)
    records = [_sample_record(), _sample_record(kind="file", signature=None)]

    result = persistence.persist_run(
        PersistRunInput(
            root_path=str(tmp_path / "project"),
            provider_url="http://localhost:11434",
            model="qwen3-coder:latest",
            scope="class,function,method",
            progress_batch_size=10,
            analyzer_error_count=0,
            records=records,
        )
    )

    assert result.run_id > 0
    assert result.record_count == 2
    assert result.intent_failed_count == 0
    assert result.status == "completed"

    connection = sqlite3.connect(db_path)
    try:
        run_rows = connection.execute(
            "SELECT record_count, intent_failed_count, analyzer_error_count, status "
            "FROM runs WHERE id = ?",
            (result.run_id,),
        ).fetchall()
        assert run_rows == [(2, 0, 0, "completed")]
        record_rows = connection.execute(
            "SELECT kind, file_path, signature, intent_status FROM records WHERE run_id = ?",
            (result.run_id,),
        ).fetchall()
        assert len(record_rows) == 2
        assert ("file", "pkg/sample.py", None, "success") in record_rows
    finally:
        connection.close()


def test_ph3_pers_002_sqlite_persistence_marks_completed_with_errors(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "cds.sqlite"
    persistence = SQLitePersistence(db_path=db_path)
    records = [
        _sample_record(),
        _sample_record(
            signature="def g() -> int:",
            intent=None,
            intent_status="failed",
            intent_error="intent generation failed",
        ),
    ]

    result = persistence.persist_run(
        PersistRunInput(
            root_path=str(tmp_path / "project"),
            provider_url="http://localhost:11434",
            model="starcoder2:15b",
            scope="function",
            progress_batch_size=5,
            analyzer_error_count=1,
            records=records,
        )
    )

    assert result.status == "completed_with_errors"
    assert result.intent_failed_count == 1
    assert result.analyzer_error_count == 1


def test_ph3_pers_003_sqlite_persistence_rolls_back_on_insert_failure(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "cds.sqlite"
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS runs("
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
            ");"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS records("
            "id INTEGER PRIMARY KEY, "
            "run_id INTEGER NOT NULL"
            ");"
        )
        connection.commit()
    finally:
        connection.close()

    persistence = SQLitePersistence(db_path=db_path)
    records = [_sample_record()]

    with pytest.raises(PersistenceError):
        persistence.persist_run(
            PersistRunInput(
                root_path=str(tmp_path / "project"),
                provider_url="http://localhost:11434",
                model="qwen3-coder:latest",
                scope="function",
                progress_batch_size=5,
                analyzer_error_count=0,
                records=records,
            )
        )

    check = sqlite3.connect(db_path)
    try:
        run_count = check.execute("SELECT COUNT(*) FROM runs").fetchone()
        assert run_count == (0,)
    finally:
        check.close()
