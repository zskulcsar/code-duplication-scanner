# Copyright 2026 Zsolt Kulcsar and Contributors. Licensed under the EUPL-1.2 or later
"""Unit tests for the obfuscation CLI harness."""

import io
import re
from pathlib import Path

from cli.obfuscation_harness import run


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def test_ph5_obf_001_cli_requires_input_and_output_arguments() -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run([], stdout=stdout, stderr=stderr)

    assert exit_code == 2


def test_ph5_obf_002_cli_fails_when_input_path_is_missing(tmp_path: Path) -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run(
        ["--input", str(tmp_path / "missing"), "--output", str(tmp_path / "out")],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 2
    assert "Input path does not exist" in stderr.getvalue()


def test_ph5_obf_003_cli_fails_when_gitignore_is_missing(tmp_path: Path) -> None:
    input_path = tmp_path / "input"
    input_path.mkdir(parents=True, exist_ok=True)
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run(
        ["--input", str(input_path), "--output", str(tmp_path / "out")],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 2
    assert ".gitignore" in stderr.getvalue()


def test_ph5_obf_004_cli_fails_when_output_is_non_empty(tmp_path: Path) -> None:
    input_path = tmp_path / "input"
    output_path = tmp_path / "output"
    _write_file(input_path / ".gitignore", "")
    _write_file(output_path / "existing.txt", "hello")
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run(
        ["--input", str(input_path), "--output", str(output_path)],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 2
    assert "Output path must be empty" in stderr.getvalue()


def test_ph5_obf_005_cli_fails_when_input_and_output_overlap(tmp_path: Path) -> None:
    input_path = tmp_path / "input"
    output_path = input_path / "out"
    _write_file(input_path / ".gitignore", "")
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run(
        ["--input", str(input_path), "--output", str(output_path)],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 2
    assert "must not overlap" in stderr.getvalue()


def test_ph5_obf_006_cli_copy_excludes_git_and_root_gitignore(tmp_path: Path) -> None:
    input_path = tmp_path / "input"
    output_path = tmp_path / "output"
    _write_file(input_path / ".gitignore", "*.tmp\n")
    _write_file(input_path / ".git" / "config", "config")
    _write_file(input_path / "keep.txt", "keep")
    _write_file(input_path / "drop.tmp", "drop")
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run(
        ["--input", str(input_path), "--output", str(output_path)],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert not (output_path / ".git").exists()
    assert (output_path / "keep.txt").exists()
    assert not (output_path / "drop.tmp").exists()
    assert stderr.getvalue() == ""


def test_ph5_obf_007_cli_copy_respects_nested_gitignore(tmp_path: Path) -> None:
    input_path = tmp_path / "input"
    output_path = tmp_path / "output"
    _write_file(input_path / ".gitignore", "")
    _write_file(input_path / "pkg" / ".gitignore", "*.log\n")
    _write_file(input_path / "pkg" / "keep.py", "x = 1\n")
    _write_file(input_path / "pkg" / "drop.log", "secret\n")
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run(
        ["--input", str(input_path), "--output", str(output_path)],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert (output_path / "pkg" / "keep.py").exists()
    assert not (output_path / "pkg" / "drop.log").exists()
    assert stderr.getvalue() == ""


def test_ph5_obf_008_cli_transform_summary_reports_discovered_and_processed(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "input"
    output_path = tmp_path / "output"
    _write_file(input_path / ".gitignore", "")
    _write_file(input_path / "a.py", "x = 1\n")
    _write_file(input_path / "b.py", "y = 2\n")
    _write_file(input_path / "c.txt", "note\n")
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run(
        ["--input", str(input_path), "--output", str(output_path)],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    output = _strip_ansi(stdout.getvalue())
    assert "python_files_discovered=2" in output
    assert "python_files_processed=2" in output
    assert "python_files_unchanged=" in output
    assert stderr.getvalue() == ""


def test_ph5_obf_009_cli_fails_fast_when_transform_read_fails(
    tmp_path: Path, monkeypatch
) -> None:
    input_path = tmp_path / "input"
    output_path = tmp_path / "output"
    _write_file(input_path / ".gitignore", "")
    _write_file(input_path / "a.py", "x = 1\n")
    _write_file(input_path / "b.py", "y = 2\n")
    stdout = io.StringIO()
    stderr = io.StringIO()
    original_read_text = Path.read_text

    def _failing_read_text(path: Path, *args, **kwargs) -> str:
        if path.name == "a.py" and output_path in path.parents:
            raise OSError("read failure")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr("pathlib.Path.read_text", _failing_read_text)

    exit_code = run(
        ["--input", str(input_path), "--output", str(output_path)],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 2
    assert "Transform failed" in stderr.getvalue()
    assert (output_path / "b.py").exists()


def test_ph5_obf_010_cli_renders_phase_markers_and_summary_keys(tmp_path: Path) -> None:
    input_path = tmp_path / "input"
    output_path = tmp_path / "output"
    _write_file(input_path / ".gitignore", "")
    _write_file(input_path / "a.py", "x = 1\n")
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run(
        ["--input", str(input_path), "--output", str(output_path)],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    output = _strip_ansi(stdout.getvalue())
    assert "validation:start" in output
    assert "validation:done" in output
    assert "copy:start" in output
    assert "copy:done" in output
    assert "transform:start" in output
    assert "transform:done" in output
    assert "files_copied=" in output
    assert "dirs_created=" in output
    assert "paths_skipped_by_gitignore=" in output
    assert "paths_skipped_git_dir=" in output
    assert "python_files_discovered=" in output
    assert "python_files_processed=" in output
    assert "python_files_unchanged=" in output
    assert "status=success" in output
    assert stderr.getvalue() == ""


def test_ph6_obf_401_cli_transform_reports_obfuscation_counters(tmp_path: Path) -> None:
    input_path = tmp_path / "input"
    output_path = tmp_path / "output"
    _write_file(input_path / ".gitignore", "")
    _write_file(
        input_path / "a.py",
        "class Box:\n"
        "    def __init__(self, value):\n"
        "        self.value = value\n"
        "\n"
        "def run(name):\n"
        "    box = Box(name)\n"
        "    return f'v={box.value}'\n",
    )
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run(
        ["--input", str(input_path), "--output", str(output_path)],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    output = _strip_ansi(stdout.getvalue())
    assert "symbols_discovered=" in output
    assert "symbols_renamed=" in output
    assert "symbols_skipped_external=" in output
    assert "symbols_renamed_likely_local=" in output
    assert "dynamic_name_rewrites=" in output
    assert stderr.getvalue() == ""


def test_ph6_obf_402_cli_transform_tracks_likely_local_dynamic_rewrite(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "input"
    output_path = tmp_path / "output"
    _write_file(input_path / ".gitignore", "")
    _write_file(
        input_path / "a.py",
        "class Box:\n"
        "    def __init__(self):\n"
        "        self.value = 1\n"
        "\n"
        "def read(obj):\n"
        '    return getattr(obj, "value")\n',
    )
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run(
        ["--input", str(input_path), "--output", str(output_path)],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    output = _strip_ansi(stdout.getvalue())
    assert "symbols_renamed_likely_local=" in output
    assert "dynamic_name_rewrites=1" in output
    assert stderr.getvalue() == ""
