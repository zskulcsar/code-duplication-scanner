# Phase 2 Intent Enrichment Design

## Objective

Phase 2 adds LLM-based intent enrichment to the phase-1 analysis pipeline.
The system should enrich selected records with intent text while preserving deterministic extraction and best-effort execution.

This phase must keep the analyzer and LLM concerns separated:

- Analyzer pipeline builds records from source code.
- LLM integration enriches those records with intent.

## Scope

In scope:

- New CLI command: `enrich-intent`.
- Pluggable LLM client abstraction.
- Ollama-backed concrete client implementation.
- Scope-based record selection for enrichment.
- Batch progress logging with ETA.
- Best-effort per-record failure handling.

Out of scope:

- Persistence layer wiring.
- Textual TUI integration.
- Provider registry/auto-discovery.

## CLI Contract

Command:

`cds enrich-intent --path <src> --provider-url <url> --model <model> [--scope ...] [--progress-batch-size N] --format {table,json} [--output <path>]`

Rules:

- `--provider-url` is required.
- `--model` is required.
- `--scope` accepts comma-separated values from `class,function,method,all`.
- Default scope is `class,function,method`.
- `all` means all scopes and overrides other scope tokens.
- `--progress-batch-size` defaults to `10` and must be `> 0`.

## Architecture

### Components

- `Analyzer` + `PythonAnalyzer`: reused from phase 1.
- `ModelBuilder`: reused to produce base records (`intent=None`).
- `LLMClient` interface: provider-agnostic intent generation contract.
- `OllamaClient`: concrete implementation using `--provider-url` and `--model`.
- `IntentEnricher`: orchestration service that applies LLM calls to selected records.
- CLI (`src/cli`): wires dependencies and renders output.

### Responsibility split

- Parsing/slicing/normalization/hash remains in analyzer/model builder stack.
- Intent generation remains in LLM client + enrich service.
- CLI does orchestration, validation, and output formatting.

## Record Enrichment Contract

Phase 2 adds enrichment metadata to record output:

- `intent: str | None`
- `intent_status: str` (for example: `success`, `failed`, `skipped`)
- `intent_error: str | None`

Behavior:

- Successful enrichment sets `intent` and `intent_status=success`.
- Failed enrichment keeps `intent=None`, sets `intent_status=failed`, and sets `intent_error`.
- Non-selected records keep `intent=None`, with `intent_status=skipped`.

## Progress Indicator

Progress must be emitted as structured log lines (no live progress bar).

Trigger:

- Emit one line every `progress_batch_size` completed calls.
- Emit one final line at completion.

Fields:

- `completed`
- `total`
- `failed`
- `percent`
- `eta_seconds`

Rules:

- `completed` includes both successful and failed calls.
- `total` is computed from selected records after scope filtering.
- `failed` counts failed LLM calls.
- `percent = completed / total * 100` (or `100.0` when `total=0`).
- `eta_seconds` uses cumulative rolling average across all completed batches.

ETA calculation:

1. Measure elapsed seconds per emitted batch interval.
2. Keep cumulative average of all observed batch durations.
3. Derive average seconds per call from cumulative batch average.
4. `eta_seconds = remaining_calls * avg_seconds_per_call`.

Zero-work edge case:

- If `total=0`, emit one completion line with:
- `completed=0`
- `total=0`
- `failed=0`
- `percent=100.0`
- `eta_seconds=0`

## Output Rules

- `--format table`: show `intent` only for enrichment state.
- `--format json`: include full enrichment fields (`intent`, `intent_status`, `intent_error`).
- `--output` applies to JSON only:
- If set, write raw JSON payload to file.
- If not set, print JSON to console.

## Error Handling

- Analyzer errors remain best-effort and are surfaced as warnings.
- LLM failures are per-record and non-fatal.
- Invalid CLI inputs (scope/batch-size/provider/model) fail fast with exit code `2`.
- Output file write failures for JSON fail safely with warning + exit code `2`.

## Testing Strategy (Mandatory)

Follow strict TDD and testing anti-pattern constraints.

Minimum test coverage for phase 2:

- CLI argument validation for `enrich-intent`.
- Scope parsing/defaults/`all` override.
- LLM success path enrichment.
- LLM failure path with `intent=None` and error metadata.
- Progress line emission at configured batch intervals.
- ETA calculation with cumulative rolling average.
- JSON output with and without `--output`.
- Table output includes `intent` and excludes status/error columns.
