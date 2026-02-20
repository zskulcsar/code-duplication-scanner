import io
import json
import re
import sqlite3
from pathlib import Path

from cds.llm_client import IntentGenerationError, LLMClient
from cds.analyzer import ExtractedSymbol
from cds.analyzers import PythonAnalyzer
from cds.model_builder import ModelBuilder
from cds.normalizer import normalize_code
from cli.cli_verification_harness import run


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


class _DeterministicLLMClient(LLMClient):
    def __init__(self, fail_on_calls: set[int] | None = None) -> None:
        self._fail_on_calls = fail_on_calls or set()
        self._calls = 0

    def generate_intent(self, code: str) -> str:
        self._calls += 1
        if self._calls in self._fail_on_calls:
            raise IntentGenerationError("intent generation failed")
        return f"intent::{len(code)}"


def test_ph1_mod_001_python_analyzer_extracts_multiline_signature_and_method_kind(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    source_file = project_root / "pkg" / "sample.py"
    _write_file(
        source_file,
        "\n".join(
            [
                "class Example:",
                '    """Class docs"""',
                "    def method(",
                "        self,",
                "        value: int,",
                "    ) -> int:",
                '        """Method docs"""',
                "        # local comment",
                "        return value",
                "",
                "def top_level(x: int) -> int:",
                "    return x",
            ]
        ),
    )

    analyzer = PythonAnalyzer()
    symbols, errors = analyzer.analyze(project_root)

    assert errors == []
    method_symbols = [s for s in symbols if s.kind == "method"]
    assert len(method_symbols) == 1
    method = method_symbols[0]
    assert method.signature == "\n".join(
        [
            "    def method(",
            "        self,",
            "        value: int,",
            "    ) -> int:",
        ]
    )
    assert method.start_line == 3
    assert method.end_line == 9


def test_ph1_mod_002_python_analyzer_is_best_effort_when_one_file_fails(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    _write_file(project_root / "ok.py", "def ok() -> int:\n    return 1\n")
    _write_file(project_root / "broken.py", "def broken(:\n    return 0\n")

    analyzer = PythonAnalyzer()
    symbols, errors = analyzer.analyze(project_root)

    assert any(symbol.signature == "def ok() -> int:" for symbol in symbols)
    assert len(errors) == 1
    assert "broken.py" in errors[0].file_path


def test_ph1_mod_003_model_builder_strips_comments_and_docstrings_before_md5() -> None:
    raw_code = "\n".join(
        [
            "def f() -> int:",
            '    """Function docs"""',
            "    # this comment should be removed",
            "    return 42",
        ]
    )
    symbols = [
        ExtractedSymbol(
            kind="function",
            file_path="a.py",
            signature="def f() -> int:",
            start_line=1,
            end_line=4,
            raw_code=raw_code,
        )
    ]

    records = ModelBuilder().build(symbols=symbols)

    assert len(records) == 1
    assert records[0].normalized_code == "def f() -> int:\n    return 42"
    assert records[0].intent is None
    assert records[0].md5sum


def test_ph1_mod_004_normalize_code_removes_module_docstring_and_comment_lines() -> (
    None
):
    normalized = normalize_code(
        "\n".join(
            [
                '"""Module docs"""',
                "",
                "# top comment",
                "x = 1",
            ]
        )
    )
    assert normalized == "x = 1"


def test_ph1_mod_005_cli_model_build_supports_json_output(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    _write_file(project_root / "example.py", "def ok() -> int:\n    return 1\n")
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run(
        ["model-build", "--path", str(project_root), "--format", "json"],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    payload = json.loads(_strip_ansi(stdout.getvalue()))
    assert "records" in payload
    assert isinstance(payload["records"], list)
    assert payload["records"]


def test_ph1_mod_006_cli_model_build_supports_table_output(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    _write_file(project_root / "example.py", "def ok() -> int:\n    return 1\n")
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run(
        ["model-build", "--path", str(project_root), "--format", "table"],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    compact_text = re.sub(r"[^a-zA-Z0-9_:.()-]+", "", _strip_ansi(stdout.getvalue()))
    assert "normalized_code" in compact_text
    assert "defok()-int:" in compact_text


def test_ph1_mod_007_cli_model_build_json_writes_to_output_file(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    output_path = tmp_path / "out" / "result.json"
    _write_file(project_root / "example.py", "def ok() -> int:\n    return 1\n")
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run(
        [
            "model-build",
            "--path",
            str(project_root),
            "--format",
            "json",
            "--output",
            str(output_path),
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stdout.getvalue() == ""
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert "records" in payload
    assert payload["records"]


def test_ph1_mod_008_cli_model_build_json_without_output_prints_json(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    _write_file(project_root / "example.py", "def ok() -> int:\n    return 1\n")
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run(
        ["model-build", "--path", str(project_root), "--format", "json"],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    payload = json.loads(_strip_ansi(stdout.getvalue()))
    assert "records" in payload
    assert payload["records"]


def test_ph2_mod_001_cli_enrich_intent_requires_provider_and_model(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    _write_file(project_root / "example.py", "def ok() -> int:\n    return 1\n")
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run(
        ["enrich-intent", "--path", str(project_root), "--format", "json"],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 2


def test_ph2_mod_002_cli_enrich_intent_default_scope_skips_file(
    tmp_path: Path, monkeypatch
) -> None:
    project_root = tmp_path / "project"
    _write_file(
        project_root / "sample.py",
        "\n".join(
            [
                "class C:",
                "    def m(self) -> int:",
                "        return 1",
                "",
                "def f() -> int:",
                "    return 2",
            ]
        ),
    )
    monkeypatch.setattr(
        "cli.cli_verification_harness.build_llm_client",
        lambda provider_url, model: _DeterministicLLMClient(),
    )
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run(
        [
            "enrich-intent",
            "--path",
            str(project_root),
            "--provider-url",
            "http://localhost:11434",
            "--model",
            "starcoder2:15b",
            "--format",
            "json",
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    payload = json.loads(_strip_ansi(stdout.getvalue()))
    file_records = [item for item in payload["records"] if item["kind"] == "file"]
    assert len(file_records) == 1
    assert file_records[0]["intent_status"] == "skipped"
    non_file = [item for item in payload["records"] if item["kind"] != "file"]
    assert all(item["intent_status"] == "success" for item in non_file)


def test_ph2_mod_003_cli_enrich_intent_best_effort_failure_marks_record(
    tmp_path: Path, monkeypatch
) -> None:
    project_root = tmp_path / "project"
    _write_file(
        project_root / "sample.py",
        "\n".join(
            [
                "def f() -> int:",
                "    return 2",
                "",
                "def g() -> int:",
                "    return 3",
            ]
        ),
    )
    monkeypatch.setattr(
        "cli.cli_verification_harness.build_llm_client",
        lambda provider_url, model: _DeterministicLLMClient(fail_on_calls={1}),
    )
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run(
        [
            "enrich-intent",
            "--path",
            str(project_root),
            "--provider-url",
            "http://localhost:11434",
            "--model",
            "starcoder2:15b",
            "--scope",
            "function",
            "--format",
            "json",
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    payload = json.loads(_strip_ansi(stdout.getvalue()))
    functions = [item for item in payload["records"] if item["kind"] == "function"]
    assert len(functions) == 2
    assert any(item["intent_status"] == "failed" for item in functions)
    assert any(item["intent_status"] == "success" for item in functions)


def test_ph2_mod_004_cli_enrich_intent_progress_logging_includes_eta_and_failed(
    tmp_path: Path, monkeypatch, caplog
) -> None:
    project_root = tmp_path / "project"
    _write_file(
        project_root / "sample.py",
        "\n".join(
            [
                "def a() -> int:",
                "    return 1",
                "",
                "def b() -> int:",
                "    return 2",
                "",
                "def c() -> int:",
                "    return 3",
            ]
        ),
    )
    monkeypatch.setattr(
        "cli.cli_verification_harness.build_llm_client",
        lambda provider_url, model: _DeterministicLLMClient(fail_on_calls={2}),
    )
    clock_values = iter([0.0, 2.0, 2.0, 5.0])
    monkeypatch.setattr(
        "cds.intent_enricher.time.monotonic",
        lambda: next(clock_values),
    )
    caplog.set_level("INFO")
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run(
        [
            "enrich-intent",
            "--path",
            str(project_root),
            "--provider-url",
            "http://localhost:11434",
            "--model",
            "starcoder2:15b",
            "--scope",
            "function",
            "--progress-batch-size",
            "2",
            "--format",
            "json",
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    progress_lines = [
        rec.message
        for rec in caplog.records
        if "intent_enrichment_progress" in rec.message
    ]
    assert len(progress_lines) >= 2
    assert any("failed=1" in line for line in progress_lines)
    assert any("eta_seconds=" in line for line in progress_lines)


def test_ph2_mod_005_cli_enrich_intent_scope_all_includes_file(
    tmp_path: Path, monkeypatch
) -> None:
    project_root = tmp_path / "project"
    _write_file(project_root / "sample.py", "def x() -> int:\n    return 1\n")
    monkeypatch.setattr(
        "cli.cli_verification_harness.build_llm_client",
        lambda provider_url, model: _DeterministicLLMClient(),
    )
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run(
        [
            "enrich-intent",
            "--path",
            str(project_root),
            "--provider-url",
            "http://localhost:11434",
            "--model",
            "starcoder2:15b",
            "--scope",
            "all",
            "--format",
            "json",
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    payload = json.loads(_strip_ansi(stdout.getvalue()))
    file_records = [item for item in payload["records"] if item["kind"] == "file"]
    assert len(file_records) == 1
    assert file_records[0]["intent_status"] == "success"


def test_ph3_mod_001_cli_persist_requires_db_path(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    _write_file(project_root / "example.py", "def ok() -> int:\n    return 1\n")
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run(
        [
            "persist",
            "--path",
            str(project_root),
            "--provider-url",
            "http://localhost:11434",
            "--model",
            "qwen3-coder:latest",
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 2


def test_ph3_mod_002_cli_persist_fails_when_db_parent_missing(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    _write_file(project_root / "example.py", "def ok() -> int:\n    return 1\n")
    db_path = tmp_path / "missing-dir" / "cds.sqlite"
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run(
        [
            "persist",
            "--path",
            str(project_root),
            "--provider-url",
            "http://localhost:11434",
            "--model",
            "qwen3-coder:latest",
            "--db-path",
            str(db_path),
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 2
    assert "Parent directory does not exist" in stderr.getvalue()


def test_ph3_mod_003_cli_persist_saves_snapshot_and_prints_summary(
    tmp_path: Path, monkeypatch
) -> None:
    project_root = tmp_path / "project"
    db_path = tmp_path / "db" / "cds.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _write_file(
        project_root / "sample.py",
        "\n".join(
            [
                "class C:",
                "    def m(self) -> int:",
                "        return 1",
                "",
                "def f() -> int:",
                "    return 2",
            ]
        ),
    )
    monkeypatch.setattr(
        "cli.cli_verification_harness.build_llm_client",
        lambda provider_url, model: _DeterministicLLMClient(),
    )
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run(
        [
            "persist",
            "--path",
            str(project_root),
            "--provider-url",
            "http://localhost:11434",
            "--model",
            "qwen3-coder:latest",
            "--db-path",
            str(db_path),
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    summary = stdout.getvalue()
    assert "run_id=" in summary
    assert "record_count=" in summary
    assert "status=completed" in summary
    assert stderr.getvalue() == ""

    connection = sqlite3.connect(db_path)
    try:
        run_count = connection.execute("SELECT COUNT(*) FROM runs").fetchone()
        record_count = connection.execute("SELECT COUNT(*) FROM records").fetchone()
        assert run_count == (1,)
        assert record_count == (4,)
    finally:
        connection.close()


def test_ph3_mod_004_cli_persist_marks_completed_with_errors(
    tmp_path: Path, monkeypatch
) -> None:
    project_root = tmp_path / "project"
    db_path = tmp_path / "db" / "cds.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _write_file(
        project_root / "sample.py",
        "\n".join(
            [
                "def f() -> int:",
                "    return 2",
                "",
                "def g() -> int:",
                "    return 3",
            ]
        ),
    )
    monkeypatch.setattr(
        "cli.cli_verification_harness.build_llm_client",
        lambda provider_url, model: _DeterministicLLMClient(fail_on_calls={1}),
    )
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run(
        [
            "persist",
            "--path",
            str(project_root),
            "--provider-url",
            "http://localhost:11434",
            "--model",
            "starcoder2:15b",
            "--db-path",
            str(db_path),
            "--scope",
            "function",
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert "status=completed_with_errors" in stdout.getvalue()

    connection = sqlite3.connect(db_path)
    try:
        status_row = connection.execute(
            "SELECT status, intent_failed_count FROM runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert status_row == ("completed_with_errors", 1)
    finally:
        connection.close()
