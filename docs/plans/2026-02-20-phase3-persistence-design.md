# Phase 3 Persistence Wiring Design

## Objective

Phase 3 wires SQLite persistence into the existing pipeline so analysis and enrichment artifacts are stored for later browsing in the TUI.

This phase preserves current architecture constraints:

- Analyzer remains language-focused extraction logic.
- LLM client remains provider-focused intent generation logic.
- Persistence is introduced behind a pluggable interface with a SQLite implementation.

## Scope

In scope:

- New CLI command: `persist`.
- New `Persistence` abstraction and `SQLitePersistence` concrete implementation.
- End-to-end pipeline in command flow: analyze -> build -> enrich -> persist.
- Snapshot storage model with run metadata + record rows.

Out of scope:

- Migration framework.
- TUI browsing implementation.
- Multi-provider persistence backends.

## CLI Contract

Command:

`cds persist --path <src> --provider-url <url> --model <model> --db-path <sqlite-file> [--scope class,function,method,all] [--progress-batch-size N]`

Rules:

- `--db-path` is required.
- Parent directory for `--db-path` must already exist; if not, fail fast with exit code `2`.
- Enrichment is mandatory for `persist`.
- `--scope` and `--progress-batch-size` match `enrich-intent` behavior exactly.

## Architecture

### Components

- `Analyzer` + `PythonAnalyzer`: unchanged.
- `ModelBuilder`: unchanged contract.
- `LLMClient` + `OllamaClient`: unchanged contract.
- `Persistence` interface: storage-agnostic write contract.
- `SQLitePersistence`: SQLite implementation.
- CLI `persist` flow: orchestrates dependencies and execution.

### Orchestration

For phase 3, orchestration stays in CLI (thin but explicit), while persistence is injected through `Persistence`.

Execution order:

1. Validate CLI arguments.
2. Analyze source tree.
3. Build records.
4. Enrich intents.
5. Persist run metadata and records atomically.
6. Print one-line success summary.

## Persistence Contract

`Persistence` must support writing one run snapshot:

- Input:
  - Run context (`path`, provider/model, scope, batch size, timestamps).
  - Analyzer error summary.
  - Final list of records (including success/failed/skipped intent states).
- Output:
  - `run_id`
  - record count
  - failed intent count
  - analyzer error count
  - final run status

Status semantics:

- `completed`: no analyzer errors and no intent failures.
- `completed_with_errors`: analyzer and/or intent failures exist.
- `failed`: fatal persistence failure.

## SQLite Schema

### `runs`

- `id` INTEGER PRIMARY KEY
- `started_at` TEXT NOT NULL
- `finished_at` TEXT NOT NULL
- `root_path` TEXT NOT NULL
- `provider_url` TEXT NOT NULL
- `model` TEXT NOT NULL
- `scope` TEXT NOT NULL
- `progress_batch_size` INTEGER NOT NULL
- `status` TEXT NOT NULL
- `analyzer_error_count` INTEGER NOT NULL
- `intent_failed_count` INTEGER NOT NULL
- `record_count` INTEGER NOT NULL

### `records`

- `id` INTEGER PRIMARY KEY
- `run_id` INTEGER NOT NULL REFERENCES runs(id)
- `kind` TEXT NOT NULL
- `file_path` TEXT NOT NULL
- `signature` TEXT
- `start_line` INTEGER NOT NULL
- `end_line` INTEGER NOT NULL
- `raw_code` TEXT NOT NULL
- `normalized_code` TEXT NOT NULL
- `md5sum` TEXT NOT NULL
- `intent` TEXT
- `intent_status` TEXT NOT NULL
- `intent_error` TEXT

Indexes:

- `records(run_id)`
- `records(file_path)`
- `records(md5sum)`
- `records(intent_status)`

No cross-run deduplication in phase 3.

## Error Handling

- CLI validation failures: exit code `2`.
- Analyzer failures: recoverable, logged, counted in run metadata.
- LLM failures: per-record recoverable, persisted as `intent_status=failed`.
- DB errors: fatal for command, transaction rollback required.

## Output Behavior

On success, print one line to stdout containing:

- `run_id`
- `db_path`
- `record_count`
- `intent_failed_count`
- `analyzer_error_count`
- `status`

## Testing Strategy

TDD and testing anti-pattern constraints remain mandatory.

Minimum tests:

- `persist` CLI argument validation (`--db-path`, parent directory existence, scope, batch size).
- Successful end-to-end persist flow with deterministic fake LLM client.
- Best-effort persist behavior with mixed LLM success/failure.
- Run metadata correctness.
- Record row persistence correctness for all record fields.
- Transaction rollback on insert failure.
- Success summary line content.

## Implementation Notes

- Use `CREATE TABLE IF NOT EXISTS` only in phase 3.
- Do not add migration tooling yet.
- Keep interfaces minimal (YAGNI) and focus on stable contracts between CLI, enrichment, and persistence.
