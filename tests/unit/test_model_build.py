import io
import json
import re
from pathlib import Path

from cds.analyzer import ExtractedSymbol
from cds.model_builder import ModelBuilder
from cds.normalizer import normalize_code
from cds.python_analyzer import PythonAnalyzer
from cli.cli_verification_harness import run


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


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
