# Copyright 2026 Zsolt Kulcsar and Contributors. Licensed under the EUPL-1.2 or later
"""Run experimental project obfuscation copy-and-transform flow."""

import argparse
import logging
import os
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

import pathspec
from obfuscation import RewriteError, analyze_project, build_rename_map, rewrite_source
from rich.console import Console
from rich.logging import RichHandler

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CopySummary:
    """Represent copy phase counters."""

    files_copied: int
    dirs_created: int
    paths_skipped_by_gitignore: int
    paths_skipped_git_dir: int
    elapsed_ms: int


@dataclass(frozen=True)
class TransformSummary:
    """Represent transform phase counters."""

    python_files_discovered: int
    python_files_processed: int
    python_files_unchanged: int
    symbols_discovered: int
    symbols_renamed: int
    symbols_skipped_external: int
    symbols_renamed_likely_local: int
    dynamic_name_rewrites: int
    elapsed_ms: int


class ValidationError(RuntimeError):
    """Represent user input validation failure."""


class TransformError(RuntimeError):
    """Represent transform phase failure."""


class IgnoreMatcher:
    """Match project paths against .gitignore patterns."""

    def __init__(self, spec: pathspec.GitIgnoreSpec) -> None:
        """Initialize matcher.

        Args:
            spec: Compiled gitignore matcher.
        """
        self._spec = spec

    @classmethod
    def from_project_root(cls, input_root: Path) -> "IgnoreMatcher":
        """Build matcher from root and nested .gitignore files.

        Args:
            input_root: Project root.

        Returns:
            Configured ignore matcher.

        Raises:
            OSError: If .gitignore files cannot be read.
            UnicodeDecodeError: If .gitignore files contain invalid UTF-8.
        """
        patterns: list[str] = []
        for ignore_path in sorted(input_root.rglob(".gitignore")):
            base = ignore_path.parent.relative_to(input_root).as_posix()
            if base == ".":
                base = ""
            lines = ignore_path.read_text(encoding="utf-8").splitlines()
            for line in lines:
                patterns.append(_translate_gitignore_line(line=line, base=base))
        spec = pathspec.GitIgnoreSpec.from_lines(patterns)
        return cls(spec=spec)

    def matches(self, relative_path: str, is_dir: bool) -> bool:
        """Check whether a path should be ignored.

        Args:
            relative_path: Project-relative POSIX path.
            is_dir: Whether the path is a directory.

        Returns:
            True when path should be ignored.
        """
        normalized = relative_path.replace(os.sep, "/").strip("/")
        if not normalized:
            return False
        if self._spec.match_file(normalized):
            return True
        if is_dir and self._spec.match_file(f"{normalized}/"):
            return True
        return False


def configure_logging(level: int = logging.INFO) -> None:
    """Configure application logging with Rich handler.

    Args:
        level: Logging severity threshold.
    """
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
    )


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser."""
    parser = argparse.ArgumentParser(prog="obfuscation")
    parser.add_argument("--input", required=True, help="Input Python project path.")
    parser.add_argument("--output", required=True, help="Output folder path.")
    return parser


def run(argv: list[str], stdout: TextIO, stderr: TextIO) -> int:
    """Run obfuscation command.

    Args:
        argv: CLI arguments.
        stdout: Standard output stream.
        stderr: Standard error stream.

    Returns:
        Exit code.
    """
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        logger.warning("Argument parsing failed (argv=%s)", argv)
        return 2

    console = Console(file=stdout, force_terminal=False, color_system="truecolor")
    _emit_marker(console=console, phase="validation", state="start")
    try:
        input_path, output_path = _validate_paths(
            input_path=Path(args.input), output_path=Path(args.output)
        )
    except ValidationError as exc:
        logger.warning("Validation failed (error=%s)", exc)
        stderr.write(f"{exc}\n")
        return 2
    _emit_marker(console=console, phase="validation", state="done")

    try:
        matcher = IgnoreMatcher.from_project_root(input_root=input_path)
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("Failed to read .gitignore files (error=%s)", exc)
        stderr.write(f"Failed to read .gitignore files: {exc}\n")
        return 2

    _emit_marker(console=console, phase="copy", state="start")
    try:
        copy_summary = _copy_project(
            input_root=input_path, output_root=output_path, matcher=matcher
        )
    except OSError as exc:
        logger.warning("Copy failed (error=%s)", exc)
        stderr.write(f"Copy failed: {exc}\n")
        return 2
    _emit_marker(console=console, phase="copy", state="done")
    _emit_summary(
        console=console,
        summary={
            "files_copied": copy_summary.files_copied,
            "dirs_created": copy_summary.dirs_created,
            "paths_skipped_by_gitignore": copy_summary.paths_skipped_by_gitignore,
            "paths_skipped_git_dir": copy_summary.paths_skipped_git_dir,
            "elapsed_ms": copy_summary.elapsed_ms,
        },
    )

    _emit_marker(console=console, phase="transform", state="start")
    try:
        transform_summary = _transform_python_files(output_root=output_path)
    except TransformError as exc:
        logger.warning("Transform failed (error=%s)", exc)
        stderr.write(f"Transform failed: {exc}\n")
        return 2
    _emit_marker(console=console, phase="transform", state="done")
    _emit_summary(
        console=console,
        summary={
            "python_files_discovered": transform_summary.python_files_discovered,
            "python_files_processed": transform_summary.python_files_processed,
            "python_files_unchanged": transform_summary.python_files_unchanged,
            "symbols_discovered": transform_summary.symbols_discovered,
            "symbols_renamed": transform_summary.symbols_renamed,
            "symbols_skipped_external": transform_summary.symbols_skipped_external,
            "symbols_renamed_likely_local": transform_summary.symbols_renamed_likely_local,
            "dynamic_name_rewrites": transform_summary.dynamic_name_rewrites,
            "elapsed_ms": transform_summary.elapsed_ms,
        },
    )
    console.print("status=success")
    return 0


def _emit_marker(console: Console, phase: str, state: str) -> None:
    console.print(f"{phase}:{state}")


def _emit_summary(console: Console, summary: dict[str, int]) -> None:
    fields = " ".join(f"{key}={value}" for key, value in summary.items())
    console.print(fields)


def _validate_paths(input_path: Path, output_path: Path) -> tuple[Path, Path]:
    """Validate required input and output path constraints.

    Args:
        input_path: Input path from user args.
        output_path: Output path from user args.

    Returns:
        Normalized absolute input and output paths.

    Raises:
        ValidationError: If path constraints are not met.
    """
    input_abs = input_path.resolve()
    output_abs = output_path.resolve()

    if not input_abs.exists():
        raise ValidationError(f"Input path does not exist: {input_abs}")
    if not input_abs.is_dir():
        raise ValidationError(f"Input path must be a directory: {input_abs}")
    if not (input_abs / ".gitignore").exists():
        raise ValidationError(f"Input path must contain .gitignore: {input_abs}")
    if output_abs.exists() and output_abs.is_dir() and any(output_abs.iterdir()):
        raise ValidationError(f"Output path must be empty: {output_abs}")
    if input_abs == output_abs:
        raise ValidationError("Input and output paths must not overlap")
    if input_abs in output_abs.parents or output_abs in input_abs.parents:
        raise ValidationError("Input and output paths must not overlap")
    return input_abs, output_abs


def _copy_project(
    input_root: Path, output_root: Path, matcher: IgnoreMatcher
) -> CopySummary:
    """Copy project tree while applying ignore rules.

    Args:
        input_root: Source project root.
        output_root: Target project root.
        matcher: Ignore matcher instance.

    Returns:
        Copy summary counters.
    """
    started = time.monotonic()
    output_root.mkdir(parents=True, exist_ok=True)
    files_copied = 0
    dirs_created = 0
    skipped_by_gitignore = 0
    skipped_git_dir = 0
    queue: list[Path] = [input_root]

    while queue:
        current = queue.pop(0)
        relative_current = current.relative_to(input_root)
        output_current = output_root / relative_current
        if relative_current != Path(".") and not output_current.exists():
            output_current.mkdir(parents=True, exist_ok=True)
            dirs_created += 1

        for child in sorted(current.iterdir(), key=lambda item: item.name):
            relative_child = child.relative_to(input_root)
            relative_child_text = relative_child.as_posix()
            if child.name == ".git" and child.is_dir():
                skipped_git_dir += 1
                continue

            is_dir = child.is_dir() if not child.is_symlink() else child.is_dir()
            if matcher.matches(relative_path=relative_child_text, is_dir=is_dir):
                skipped_by_gitignore += 1
                continue

            destination = output_root / relative_child
            if child.is_symlink():
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists() or destination.is_symlink():
                    destination.unlink()
                destination.symlink_to(os.readlink(child))
                files_copied += 1
                continue

            if child.is_dir():
                queue.append(child)
                if not destination.exists():
                    destination.mkdir(parents=True, exist_ok=True)
                    dirs_created += 1
                continue

            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(child, destination)
            files_copied += 1

    elapsed_ms = int(round((time.monotonic() - started) * 1000))
    return CopySummary(
        files_copied=files_copied,
        dirs_created=dirs_created,
        paths_skipped_by_gitignore=skipped_by_gitignore,
        paths_skipped_git_dir=skipped_git_dir,
        elapsed_ms=elapsed_ms,
    )


def _transform_python_files(output_root: Path) -> TransformSummary:
    """Process output Python files with placeholder no-op transform.

    Args:
        output_root: Output project root.

    Returns:
        Transform summary counters.

    Raises:
        TransformError: If processing any file fails.
    """
    started = time.monotonic()
    files = sorted(output_root.rglob("*.py"))
    discovered = len(files)
    processed = 0
    unchanged = 0
    symbols_renamed = 0
    likely_local_rewrites = 0
    dynamic_name_rewrites = 0

    index = analyze_project(project_root=output_root, files=files)
    rename_map = build_rename_map(index=index)
    symbols_discovered = len(rename_map.mapping)
    symbols_skipped_external = len(index.external_symbols)

    for file_path in files:
        try:
            source = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("Failed reading file (path=%s error=%s)", file_path, exc)
            raise TransformError(str(exc)) from exc
        try:
            rewrite_result = rewrite_source(
                source=source,
                rename_map=rename_map,
                index=index,
            )
        except RewriteError as exc:
            logger.warning("Failed rewriting file (path=%s error=%s)", file_path, exc)
            raise TransformError(str(exc)) from exc
        transformed = rewrite_result.transformed_source
        symbols_renamed += rewrite_result.symbols_renamed
        likely_local_rewrites += rewrite_result.likely_local_rewrites
        dynamic_name_rewrites += rewrite_result.dynamic_name_rewrites
        if rewrite_result.likely_local_rewrites > 0:
            logger.warning(
                "Applied likely-local rewrites",
                extra={
                    "path": str(file_path),
                    "count": rewrite_result.likely_local_rewrites,
                },
            )
        if transformed == source:
            unchanged += 1
            processed += 1
            continue
        tmp_path = file_path.with_suffix(f"{file_path.suffix}.tmp")
        try:
            tmp_path.write_text(transformed, encoding="utf-8")
            tmp_path.replace(file_path)
        except OSError as exc:
            logger.warning("Failed writing file (path=%s error=%s)", file_path, exc)
            raise TransformError(str(exc)) from exc
        processed += 1

    elapsed_ms = int(round((time.monotonic() - started) * 1000))
    return TransformSummary(
        python_files_discovered=discovered,
        python_files_processed=processed,
        python_files_unchanged=unchanged,
        symbols_discovered=symbols_discovered,
        symbols_renamed=symbols_renamed,
        symbols_skipped_external=symbols_skipped_external,
        symbols_renamed_likely_local=likely_local_rewrites,
        dynamic_name_rewrites=dynamic_name_rewrites,
        elapsed_ms=elapsed_ms,
    )


def _transform_source(source: str) -> str:
    """Apply placeholder no-op transform.

    Args:
        source: Source file content.

    Returns:
        Unchanged source content.
    """
    return source


def _translate_gitignore_line(line: str, base: str) -> str:
    """Translate one .gitignore line to root-relative pattern.

    Args:
        line: Original .gitignore line.
        base: Parent directory relative to project root.

    Returns:
        Root-relative pattern line.
    """
    if not base:
        return line
    if not line:
        return line
    if line.lstrip().startswith("#"):
        return line
    if line.startswith(r"\!") or line.startswith(r"\#"):
        return line
    is_negation = line.startswith("!")
    pattern = line[1:] if is_negation else line
    anchored = pattern.startswith("/")
    normalized_pattern = pattern[1:] if anchored else pattern
    prefixed = f"{base}/{normalized_pattern}" if normalized_pattern else base
    if anchored:
        prefixed = f"/{prefixed}"
    if is_negation:
        return f"!{prefixed}"
    return prefixed


def main() -> None:
    """Run obfuscation CLI."""
    configure_logging()
    exit_code = run(sys.argv[1:], stdout=sys.stdout, stderr=sys.stderr)
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
