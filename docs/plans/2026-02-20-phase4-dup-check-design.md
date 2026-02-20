# Phase 4 Duplication Check Design

## Objective

Phase 4 adds duplication detection on persisted analysis artifacts and surfaces findings through the existing CLI.

This phase focuses on practical, high-signal duplication candidates for human review and does not introduce TUI behavior.

## Scope

In scope:

- New CLI command: `dup-check`.
- Duplication detection over persisted run records in SQLite.
- Two-stage matching:
  - exact match by `md5sum`
  - fuzzy match by `Levenshtein.ratio(intent, intent)`
- Table-only output.

Out of scope:

- JSON output for duplication checks.
- TUI browsing.
- Multi-run comparison logic.

## CLI Contract

Command:

`cds dup-check --db-path <sqlite-file> --run-id <int> [--intent-threshold <0..1>]`

Rules:

- `--db-path` is required.
- `--run-id` is required.
- `--intent-threshold` is optional, default `0.85`, valid range `[0.0, 1.0]`.

Run-id behavior:

- No pre-validation that `run_id` exists.
- Query directly for the requested run.
- If no records are returned for the requested run id, emit warning, print no-findings message, and exit `0`.

## Matching Scope and Rules

Eligible records:

- Only `function` and `method` records.

General rules:

- Never match a record with itself.
- Fuzzy stage compares all eligible non-self pairs.

### Stage 1: Exact Match

- Build edges where `md5sum` is equal.
- Build connected components from those edges.
- Each component of size >= 2 is an exact duplication group.

### Stage 2: Fuzzy Intent Match

- Compute `Levenshtein.ratio(intent_a, intent_b)` for each eligible pair.
- Include pair when ratio >= threshold.
- Include ratio == 1.0 matches.
- Track whether md5 also matches (`md5_match` marker).
- Build connected components from fuzzy edges.
- Each component of size >= 2 is a fuzzy duplication group.

## Output Behavior

Format:

- Table-only output in phase 4.

Tables:

1. Exact groups table.
2. Fuzzy groups table.

Layout model:

- Same layout style for both tables.
- Group-based presentation using connected components.
- One row per member in a group (group-id driven layout).

Required member context:

- `group_id`
- `record_id`
- `kind`
- `file_path`
- `signature`
- `start_line`
- `end_line`

Fuzzy-specific context:

- Intent similarity ratio context for the group/member.
- Marker indicating md5 overlap exists in the fuzzy relationship context.

No-findings behavior:

- Print clear no-findings message and exit `0`.

## Architecture

Components:

- CLI `dup-check` command for argument validation, orchestration, and table rendering.
- SQLite read path to load records for a given `run_id`.
- `DuplicationChecker` service for exact/fuzzy graph construction and connected-component grouping.

Data flow:

1. Validate CLI args.
2. Load records for `run_id`.
3. Filter to function/method records.
4. Execute exact and fuzzy grouping.
5. Render two tables.

## Error Handling

- Invalid threshold or invalid db path: fail fast, exit `2`.
- Requested run id with no records: warning + no-findings output + exit `0`.
- Recoverable record data issues (for example missing intent): warn and continue best-effort.

## Testing Strategy

TDD and testing anti-pattern constraints remain mandatory.

Minimum tests:

- CLI arg validation for `dup-check` (`--db-path`, `--run-id`, threshold bounds).
- No-records-for-run behavior (warning + exit `0`).
- Exact md5 grouping behavior.
- Fuzzy intent grouping behavior with threshold.
- No self-match guarantee.
- Fuzzy md5-overlap marker behavior.
- Table output contains exact and fuzzy sections.

## Implementation Notes

- Reuse existing SQLite persistence schema from phase 3.
- Keep matching deterministic and implementation scope minimal (YAGNI/KISS).
