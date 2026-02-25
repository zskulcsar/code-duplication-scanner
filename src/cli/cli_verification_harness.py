# Copyright 2026 Zsolt Kulcsar and Contributors. Licensed under the EUPL-1.2 or later
"""CLI verification harness for model build and intent enrichment."""

import argparse
import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path
from typing import TextIO, cast

from rich.console import Console
from rich.logging import RichHandler
from rich.style import Style
from rich.table import Table

from cds.analyzer import AnalyzerError, SymbolKind
from cds.analyzers import PythonAnalyzer
from cds.database import SQLitePersistence
from cds.duplication import DuplicationGroup, DuplicationResult, DuplicationChecker
from cds.intent_enricher import IntentEnricher
from cds.llm_client import LLMClient
from cds.llm import OPENAI_CODEX_MODEL, OllamaClient, OpenAIClient
from cds.model import Record
from cds.model_builder import ModelBuilder
from cds.persistence import (
    PersistRunInput,
    Persistence,
    PersistenceError,
)

logger = logging.getLogger(__name__)

TABLE_COLUMN_RATIOS: dict[str, int] = {
    "kind": 1,
    "file_path": 1,
    "signature": 7,
    "normalized_code": 10,
    "start_line": 1,
    "end_line": 1,
    "md5sum": 2,
}

GROUP_TABLE_COLUMN_RATIOS: dict[str, int] = {
    "group_id": 1,
    "record_id": 1,
    "kind": 1,
    "file_path": 2,
    "signature": 3,
    "intent": 4,
    "normalized_code": 5,
    "start_line": 1,
    "end_line": 1,
    "best_ratio": 1,
    "avg_ratio": 1,
    "md5_overlap": 1,
}

ALL_SCOPES: set[SymbolKind] = {"file", "class", "function", "method"}
DEFAULT_ENRICH_SCOPES: set[SymbolKind] = {"class", "function", "method"}
ROOT_OPTION_FLAGS: tuple[str, ...] = ("--path", "--format", "--output")


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
    """Build the top-level CLI parser.

    Returns:
        Configured argument parser instance.
    """
    parser = argparse.ArgumentParser(prog="cds")
    parser.add_argument("--path", required=False, help="Root path to analyze.")
    parser.add_argument(
        "--format",
        choices=("table", "json"),
        default="table",
        help="Output format.",
    )
    parser.add_argument(
        "--output",
        required=False,
        help="Optional output file path for raw JSON when --format json is used.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    model_build_parser = subparsers.add_parser("model-build")
    model_build_parser.add_argument(
        "--analyzer-workers",
        type=int,
        default=4,
        help="Number of analyzer worker threads.",
    )

    enrich_intent_parser = subparsers.add_parser("enrich-intent")
    enrich_intent_parser.add_argument(
        "--provider-url", required=True, help="Provider API endpoint URL."
    )
    enrich_intent_parser.add_argument(
        "--model", required=True, help="Provider model name."
    )
    enrich_intent_parser.add_argument(
        "--scope",
        default="class,function,method",
        help="Scope list from class,function,method,all.",
    )
    enrich_intent_parser.add_argument(
        "--progress-batch-size",
        type=int,
        default=10,
        help="Emit progress line every N completed LLM calls.",
    )
    enrich_intent_parser.add_argument(
        "--analyzer-workers",
        type=int,
        default=4,
        help="Number of analyzer worker threads.",
    )
    enrich_intent_parser.add_argument(
        "--enricher-workers",
        type=int,
        default=4,
        help="Number of intent enricher worker threads.",
    )
    persist_parser = subparsers.add_parser("persist")
    persist_parser.add_argument(
        "--provider-url", required=True, help="Provider API endpoint URL."
    )
    persist_parser.add_argument("--model", required=True, help="Provider model name.")
    persist_parser.add_argument(
        "--db-path", required=True, help="SQLite database file path."
    )
    persist_parser.add_argument(
        "--scope",
        default="class,function,method",
        help="Scope list from class,function,method,all.",
    )
    persist_parser.add_argument(
        "--progress-batch-size",
        type=int,
        default=10,
        help="Emit progress line every N completed LLM calls.",
    )
    persist_parser.add_argument(
        "--analyzer-workers",
        type=int,
        default=4,
        help="Number of analyzer worker threads.",
    )
    persist_parser.add_argument(
        "--enricher-workers",
        type=int,
        default=4,
        help="Number of intent enricher worker threads.",
    )
    dup_check_parser = subparsers.add_parser("dup-check")
    dup_check_parser.add_argument(
        "--db-path", required=True, help="SQLite database file path."
    )
    dup_check_parser.add_argument("--run-id", required=True, type=int, help="Run id.")
    dup_check_parser.add_argument(
        "--intent-threshold",
        required=False,
        type=float,
        default=0.85,
        help="Intent Levenshtein ratio threshold in [0.0, 1.0].",
    )
    return parser


def run(argv: list[str], stdout: TextIO, stderr: TextIO) -> int:
    """Run CLI command.

    Args:
        argv: CLI arguments.
        stdout: Standard output stream.
        stderr: Standard error stream.

    Returns:
        Exit code.
    """
    parser = build_parser()
    normalized_argv = _normalize_root_options(argv=argv)
    try:
        args = parser.parse_args(normalized_argv)
    except SystemExit:
        logger.warning(f"Argument parsing failed (argv={argv})")
        return 2
    if args.command == "model-build":
        return _run_model_build(args=args, stdout=stdout, stderr=stderr)
    if args.command == "enrich-intent":
        return _run_enrich_intent(args=args, stdout=stdout, stderr=stderr)
    if args.command == "persist":
        return _run_persist(args=args, stdout=stdout, stderr=stderr)
    if args.command == "dup-check":
        return _run_dup_check(args=args, stdout=stdout, stderr=stderr)

    logger.warning(f"Unsupported command (command={args.command})")
    stderr.write(f"Unsupported command: {args.command}\n")
    return 2


def _normalize_root_options(argv: list[str]) -> list[str]:
    """Move root options before subcommand for argparse compatibility.

    Args:
        argv: Raw CLI argument vector.

    Returns:
        Normalized argument vector with root options before the subcommand.
    """
    root_tokens: list[str] = []
    remaining_tokens: list[str] = []
    index = 0
    while index < len(argv):
        token = argv[index]
        if token in ROOT_OPTION_FLAGS:
            root_tokens.append(token)
            if index + 1 < len(argv):
                root_tokens.append(argv[index + 1])
                index += 2
                continue
        if any(token.startswith(f"{flag}=") for flag in ROOT_OPTION_FLAGS):
            root_tokens.append(token)
            index += 1
            continue
        remaining_tokens.append(token)
        index += 1
    return root_tokens + remaining_tokens


def _run_model_build(args: argparse.Namespace, stdout: TextIO, stderr: TextIO) -> int:
    """Run model-build command.

    Args:
        args: Parsed CLI arguments.
        stdout: Standard output stream.
        stderr: Standard error stream.

    Returns:
        Exit code.
    """
    if not args.path:
        logger.warning("Path argument is required for model-build")
        stderr.write("Path is required for model-build\n")
        return 2
    root_path = Path(args.path)
    if not root_path.exists():
        logger.warning(f"Path does not exist (path={root_path})")
        stderr.write(f"Path does not exist: {root_path}\n")
        return 2
    if args.analyzer_workers <= 0:
        logger.warning(
            f"Invalid analyzer worker count (analyzer_workers={args.analyzer_workers})"
        )
        stderr.write("analyzer-workers must be > 0\n")
        return 2

    analyzer = PythonAnalyzer(max_workers=args.analyzer_workers)
    symbols, errors = analyzer.analyze(root_path)
    logger.info(
        f"Model build completed (path={root_path} records={len(symbols)} errors={len(errors)})"
    )
    records = ModelBuilder().build(symbols=symbols)
    _write_errors(errors=errors, stderr=stderr)
    if args.format == "json":
        if args.output:
            try:
                _write_json_file(
                    records=records, errors=errors, output_path=Path(args.output)
                )
            except OSError as exc:
                logger.warning(
                    f"Failed to write JSON output file (output_path={args.output} error={exc})"
                )
                stderr.write(f"Failed to write JSON output file: {args.output}\n")
                return 2
        else:
            _write_json(records=records, errors=errors, stdout=stdout)
    else:
        _write_table(
            records=records, root_path=root_path, stdout=stdout, include_intent=False
        )
    return 0


def _run_enrich_intent(
    args: argparse.Namespace,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    """Run enrich-intent command.

    Args:
        args: Parsed CLI arguments.
        stdout: Standard output stream.
        stderr: Standard error stream.

    Returns:
        Exit code.
    """
    if not args.path:
        logger.warning("Path argument is required for enrich-intent")
        stderr.write("Path is required for enrich-intent\n")
        return 2
    root_path = Path(args.path)
    if not root_path.exists():
        logger.warning(f"Path does not exist (path={root_path})")
        stderr.write(f"Path does not exist: {root_path}\n")
        return 2
    if args.progress_batch_size <= 0:
        logger.warning(
            f"Invalid progress batch size (progress_batch_size={args.progress_batch_size})"
        )
        stderr.write("progress-batch-size must be > 0\n")
        return 2
    if args.analyzer_workers <= 0:
        logger.warning(
            f"Invalid analyzer worker count (analyzer_workers={args.analyzer_workers})"
        )
        stderr.write("analyzer-workers must be > 0\n")
        return 2
    if args.enricher_workers <= 0:
        logger.warning(
            f"Invalid enricher worker count (enricher_workers={args.enricher_workers})"
        )
        stderr.write("enricher-workers must be > 0\n")
        return 2

    try:
        scopes = parse_scopes(args.scope)
    except ValueError as exc:
        logger.warning(f"Invalid scope argument (scope={args.scope} error={exc})")
        stderr.write(f"Invalid scope: {args.scope}\n")
        return 2

    analyzer = PythonAnalyzer(max_workers=args.analyzer_workers)
    symbols, errors = analyzer.analyze(root_path)
    records = ModelBuilder().build(symbols=symbols)

    llm_client = build_llm_client(provider_url=args.provider_url, model=args.model)
    enriched = IntentEnricher(
        llm_client=llm_client,
        progress_batch_size=args.progress_batch_size,
        max_workers=args.enricher_workers,
    ).enrich(records=records, scopes=scopes)

    logger.info(
        f"Intent enrichment completed (path={root_path} records={len(enriched)} errors={len(errors)})"
    )
    _write_errors(errors=errors, stderr=stderr)
    if args.format == "json":
        if args.output:
            try:
                _write_json_file(
                    records=enriched, errors=errors, output_path=Path(args.output)
                )
            except OSError as exc:
                logger.warning(
                    f"Failed to write JSON output file (output_path={args.output} error={exc})"
                )
                stderr.write(f"Failed to write JSON output file: {args.output}\n")
                return 2
        else:
            _write_json(records=enriched, errors=errors, stdout=stdout)
    else:
        _write_table(
            records=enriched, root_path=root_path, stdout=stdout, include_intent=True
        )
    return 0


def _run_persist(args: argparse.Namespace, stdout: TextIO, stderr: TextIO) -> int:
    """Run persist command.

    Args:
        args: Parsed CLI arguments.
        stdout: Standard output stream.
        stderr: Standard error stream.

    Returns:
        Exit code.
    """
    if not args.path:
        logger.warning("Path argument is required for persist")
        stderr.write("Path is required for persist\n")
        return 2
    root_path = Path(args.path)
    if not root_path.exists():
        logger.warning(f"Path does not exist (path={root_path})")
        stderr.write(f"Path does not exist: {root_path}\n")
        return 2
    if args.progress_batch_size <= 0:
        logger.warning(
            f"Invalid progress batch size (progress_batch_size={args.progress_batch_size})"
        )
        stderr.write("progress-batch-size must be > 0\n")
        return 2
    if args.analyzer_workers <= 0:
        logger.warning(
            f"Invalid analyzer worker count (analyzer_workers={args.analyzer_workers})"
        )
        stderr.write("analyzer-workers must be > 0\n")
        return 2
    if args.enricher_workers <= 0:
        logger.warning(
            f"Invalid enricher worker count (enricher_workers={args.enricher_workers})"
        )
        stderr.write("enricher-workers must be > 0\n")
        return 2
    db_path = Path(args.db_path)
    if not db_path.parent.exists():
        logger.warning(f"Parent directory does not exist (db_path={db_path})")
        stderr.write(f"Parent directory does not exist: {db_path.parent}\n")
        return 2
    try:
        scopes = parse_scopes(args.scope)
    except ValueError as exc:
        logger.warning(f"Invalid scope argument (scope={args.scope} error={exc})")
        stderr.write(f"Invalid scope: {args.scope}\n")
        return 2

    analyzer = PythonAnalyzer(max_workers=args.analyzer_workers)
    symbols, errors = analyzer.analyze(root_path)
    records = ModelBuilder().build(symbols=symbols)

    llm_client = build_llm_client(provider_url=args.provider_url, model=args.model)
    enriched = IntentEnricher(
        llm_client=llm_client,
        progress_batch_size=args.progress_batch_size,
        max_workers=args.enricher_workers,
    ).enrich(records=records, scopes=scopes)
    _write_errors(errors=errors, stderr=stderr)

    persistence = build_persistence(db_path=db_path)
    try:
        result = persistence.persist_run(
            PersistRunInput(
                root_path=str(root_path),
                provider_url=args.provider_url,
                model=args.model,
                scope=args.scope,
                progress_batch_size=args.progress_batch_size,
                analyzer_error_count=len(errors),
                records=enriched,
            )
        )
    except PersistenceError as exc:
        logger.warning(f"Persist command failed (db_path={db_path} error={exc})")
        stderr.write(f"Persistence failed: {exc}\n")
        return 2

    logger.info(
        f"Persist command completed (path={root_path} db_path={db_path} "
        f"records={result.record_count} status={result.status})"
    )
    stdout.write(
        "persisted "
        f"run_id={result.run_id} "
        f"db_path={db_path} "
        f"record_count={result.record_count} "
        f"intent_failed_count={result.intent_failed_count} "
        f"analyzer_error_count={result.analyzer_error_count} "
        f"status={result.status}\n"
    )
    return 0


def _run_dup_check(args: argparse.Namespace, stdout: TextIO, stderr: TextIO) -> int:
    """Run dup-check command.

    Args:
        args: Parsed CLI arguments.
        stdout: Standard output stream.
        stderr: Standard error stream.

    Returns:
        Exit code.
    """
    if args.format != "table":
        logger.warning(f"dup-check does not support format (format={args.format})")
        stderr.write("dup-check supports only table format\n")
        return 2
    if args.intent_threshold < 0.0 or args.intent_threshold > 1.0:
        logger.warning(
            f"Invalid intent threshold (intent_threshold={args.intent_threshold})"
        )
        stderr.write("intent-threshold must be between 0.0 and 1.0\n")
        return 2
    db_path = Path(args.db_path)
    if not db_path.exists():
        logger.warning(f"DB path does not exist (db_path={db_path})")
        stderr.write(f"DB path does not exist: {db_path}\n")
        return 2

    persistence = build_sqlite_persistence(db_path=db_path)
    try:
        records = persistence.load_records_for_run(run_id=args.run_id)
    except PersistenceError as exc:
        logger.warning(
            f"Failed to load run records (db_path={db_path} run_id={args.run_id} error={exc})"
        )
        stderr.write(f"Failed to load run records: {exc}\n")
        return 2
    if not records:
        logger.warning(
            f"No records found for run id (db_path={db_path} run_id={args.run_id})"
        )
        stdout.write(f"No duplication findings for run_id={args.run_id}\n")
        return 0

    checker = DuplicationChecker(intent_threshold=args.intent_threshold)
    result = checker.check(records=records)
    if not result.exact_groups and not result.fuzzy_groups:
        stdout.write(f"No duplication findings for run_id={args.run_id}\n")
        return 0
    _write_duplication_tables(result=result, stdout=stdout)
    return 0


def parse_scopes(scope_arg: str) -> set[SymbolKind]:
    """Parse CLI scope argument to record kinds.

    Args:
        scope_arg: Comma-separated scope values.

    Returns:
        Selected record kinds.

    Raises:
        ValueError: If scope tokens are invalid.
    """
    tokens = [part.strip() for part in scope_arg.split(",") if part.strip()]
    if not tokens:
        return set(DEFAULT_ENRICH_SCOPES)
    valid = {"class", "function", "method", "all"}
    invalid = sorted({token for token in tokens if token not in valid})
    if invalid:
        raise ValueError(f"Unsupported scopes: {', '.join(invalid)}")
    if "all" in tokens:
        return set(ALL_SCOPES)
    return cast(set[SymbolKind], set(tokens))


def build_llm_client(provider_url: str, model: str) -> LLMClient:
    """Create the configured LLM client.

    Args:
        provider_url: Provider endpoint URL.
        model: Model name.

    Returns:
        Configured LLM client.
    """
    normalized_provider_url = provider_url.strip().lower()
    if "openai.com" in normalized_provider_url or normalized_provider_url == "openai":
        return OpenAIClient(
            provider_url=provider_url,
            model=OPENAI_CODEX_MODEL,
        )
    return OllamaClient(provider_url=provider_url, model=model)


def build_persistence(db_path: Path) -> Persistence:
    """Create the configured persistence backend.

    Args:
        db_path: SQLite database path.

    Returns:
        Configured persistence backend.
    """
    return SQLitePersistence(db_path=db_path)


def build_sqlite_persistence(db_path: Path) -> SQLitePersistence:
    """Create SQLite persistence backend.

    Args:
        db_path: SQLite database path.

    Returns:
        SQLite persistence backend.
    """
    return SQLitePersistence(db_path=db_path)


def _write_errors(errors: list[AnalyzerError], stderr: TextIO) -> None:
    """Write analyzer errors to stderr.

    Args:
        errors: Recoverable analyzer errors.
        stderr: Standard error stream.
    """
    for error in errors:
        stderr.write(f"analyzer_error: {error}\n")


def _write_json(
    records: list[Record], errors: list[AnalyzerError], stdout: TextIO
) -> None:
    """Write records and errors in JSON format.

    Args:
        records: Built records.
        errors: Recoverable analyzer errors.
        stdout: Standard output stream.
    """
    payload = {
        "records": [asdict(record) for record in records],
        "errors": [asdict(error) for error in errors],
    }
    console = Console(file=stdout, force_terminal=False, color_system="truecolor")
    console.print(
        json.dumps(payload, indent=2, sort_keys=True),
        markup=False,
        highlight=False,
        soft_wrap=True,
    )


def _write_json_file(
    records: list[Record], errors: list[AnalyzerError], output_path: Path
) -> None:
    """Write raw JSON payload to an output file.

    Args:
        records: Built records.
        errors: Recoverable analyzer errors.
        output_path: Target file path.

    Raises:
        OSError: If directory creation or file writing fails.
    """
    payload = {
        "records": [asdict(record) for record in records],
        "errors": [asdict(error) for error in errors],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )


def _write_table(
    records: list[Record],
    root_path: Path,
    stdout: TextIO,
    include_intent: bool,
) -> None:
    """Write records as a tab-separated table.

    Args:
        records: Built records.
        root_path: Root path used for analysis.
        stdout: Standard output stream.
        include_intent: Whether to include the intent column.
    """
    console = Console(file=stdout, force_terminal=False, color_system="truecolor")
    records_by_file: dict[str, list[Record]] = {}
    for record in records:
        records_by_file.setdefault(record.file_path, []).append(record)

    for file_path in sorted(records_by_file):
        full_path = str((root_path / file_path).resolve())
        console.rule(f"{full_path}", style=Style(color="cyan"), characters="-")
        table = Table(show_header=True, show_lines=True, expand=True)
        table.add_column("kind", ratio=TABLE_COLUMN_RATIOS["kind"], overflow="fold")
        table.add_column(
            "file_path",
            ratio=TABLE_COLUMN_RATIOS["file_path"],
            overflow="fold",
        )
        table.add_column(
            "signature",
            ratio=TABLE_COLUMN_RATIOS["signature"],
            overflow="fold",
        )
        table.add_column(
            "normalized_code",
            ratio=TABLE_COLUMN_RATIOS["normalized_code"],
            overflow="fold",
        )
        if include_intent:
            table.add_column("intent", ratio=3, overflow="fold")
        table.add_column(
            "start_line",
            ratio=TABLE_COLUMN_RATIOS["start_line"],
            justify="right",
            overflow="fold",
        )
        table.add_column(
            "end_line",
            ratio=TABLE_COLUMN_RATIOS["end_line"],
            justify="right",
            overflow="fold",
        )
        table.add_column("md5sum", ratio=TABLE_COLUMN_RATIOS["md5sum"], overflow="fold")
        for record in records_by_file[file_path]:
            row = [
                str(record.kind),
                str(record.file_path),
                str(record.signature),
                str(record.normalized_code),
            ]
            if include_intent:
                row.append(str(record.intent))
            row.extend(
                [str(record.start_line), str(record.end_line), str(record.md5sum)]
            )
            table.add_row(*row)
        console.print(table)


def _write_duplication_tables(result: DuplicationResult, stdout: TextIO) -> None:
    """Write duplication results in table format.

    Args:
        result: Duplication findings.
        stdout: Standard output stream.
    """
    console = Console(file=stdout, force_terminal=False, color_system="truecolor")
    _write_group_section(
        title="Exact Duplication Groups",
        groups=result.exact_groups,
        console=console,
    )
    _write_group_section(
        title="Fuzzy Duplication Groups",
        groups=result.fuzzy_groups,
        console=console,
    )
    _write_group_section(
        title="Normalized Code Fuzzy Duplication Groups",
        groups=result.normalized_code_fuzzy_groups,
        console=console,
    )


def _write_group_section(
    title: str, groups: list[DuplicationGroup], console: Console
) -> None:
    """Write one duplication section with member rows per group.

    Args:
        title: Section title.
        groups: Duplication groups to render.
        console: Output console.
    """
    console.rule(title, style=Style(color="cyan"), characters="-")
    if not groups:
        console.print("No groups")
        return
    show_normalized_code = groups[0].match_type == "normalized_code_fuzzy"
    for group in groups:
        console.rule(
            f"group_id={group.group_id} members={len(group.members)} "
            f"pairs={group.pair_count} md5_overlap_pairs={group.md5_overlap_pairs}",
            style=Style(color="green"),
            characters="-",
        )
        table = Table(
            show_header=True,
            show_lines=True,
            expand=True,
            highlight=True,
            header_style="bold",
        )
        table.add_column(
            "group_id",
            ratio=GROUP_TABLE_COLUMN_RATIOS["group_id"],
            justify="right",
            overflow="fold",
        )
        table.add_column(
            "record_id",
            ratio=GROUP_TABLE_COLUMN_RATIOS["record_id"],
            justify="right",
            overflow="fold",
        )
        table.add_column(
            "kind",
            ratio=GROUP_TABLE_COLUMN_RATIOS["kind"],
            overflow="fold",
        )
        table.add_column(
            "file_path",
            ratio=GROUP_TABLE_COLUMN_RATIOS["file_path"],
            overflow="fold",
        )
        table.add_column(
            "signature",
            ratio=GROUP_TABLE_COLUMN_RATIOS["signature"],
            overflow="fold",
        )
        if show_normalized_code:
            table.add_column(
                "normalized_code",
                ratio=GROUP_TABLE_COLUMN_RATIOS["normalized_code"],
                overflow="fold",
            )
        else:
            table.add_column(
                "intent",
                ratio=GROUP_TABLE_COLUMN_RATIOS["intent"],
                overflow="fold",
            )
        table.add_column(
            "start_line",
            ratio=GROUP_TABLE_COLUMN_RATIOS["start_line"],
            justify="right",
            overflow="fold",
        )
        table.add_column(
            "end_line",
            ratio=GROUP_TABLE_COLUMN_RATIOS["end_line"],
            justify="right",
            overflow="fold",
        )
        table.add_column(
            "best_ratio",
            ratio=GROUP_TABLE_COLUMN_RATIOS["best_ratio"],
            justify="right",
            overflow="fold",
        )
        table.add_column(
            "avg_ratio",
            ratio=GROUP_TABLE_COLUMN_RATIOS["avg_ratio"],
            justify="right",
            overflow="fold",
        )
        table.add_column(
            "md5_overlap",
            ratio=GROUP_TABLE_COLUMN_RATIOS["md5_overlap"],
            overflow="fold",
        )
        for member in group.members:
            table.add_row(
                str(member.group_id),
                str(member.record_id),
                str(member.kind),
                str(member.file_path),
                str(member.signature),
                (
                    str(member.normalized_code)
                    if show_normalized_code
                    else str(member.intent)
                ),
                str(member.start_line),
                str(member.end_line),
                f"{member.best_ratio:.4f}",
                f"{member.avg_ratio:.4f}",
                "yes" if member.md5_overlap else "no",
            )
        console.print(table)


def main() -> None:
    """Run the CLI application and exit."""
    configure_logging()
    exit_code = run(sys.argv[1:], stdout=sys.stdout, stderr=sys.stderr)
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
