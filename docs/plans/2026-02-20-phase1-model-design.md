# Phase 1 Model Design

## Objective

Phase 1 delivers a reliable model-building pipeline for Python source code and a minimal CLI harness for development validation.
This phase does not implement LLM intent generation or persistence yet.
`Record.intent` remains present in the model and is set to `None`.

The goal is to make extraction and model assembly deterministic, debuggable, and easy to extend later.

## Scope

In scope:

- Python source analysis only.
- Analyzer abstraction with one concrete implementation (`PythonAnalyzer`).
- Model assembly with normalization and MD5 generation.
- CLI harness under `src/cli` with `table` and `json` output.
- Best-effort analysis on parse errors.

Out of scope:

- Multi-language analyzer selection.
- LLM intent enrichment.
- SQLite persistence wiring.
- Textual TUI browsing.

## Architecture

### Components

- `Analyzer` (interface): language-agnostic contract for extracted code artifacts.
- `PythonAnalyzer` (implementation): parses Python files and extracts records in one pass.
- `ModelBuilder`: consumes analyzer output, normalizes code, computes hashes, builds `Record`.
- `Normalizer`: strips comment lines and docstring blocks from raw code.
- `CLI` (`src/cli`): statically wires `PythonAnalyzer` through `Analyzer`, runs model build, renders output.

### Dependency direction

- `CLI -> Analyzer` (interface)
- `CLI -> ModelBuilder`
- `PythonAnalyzer -> Analyzer` (implements contract)
- `ModelBuilder -> Normalizer`

No analyzer selection logic is implemented in phase 1.

## Analyzer Contract

Each analyzer output item must contain:

- `kind`: `file | class | function | method`
- `file_path`: path relative to project root
- `signature`: nullable exact declaration text
- `start_line`, `end_line`: raw block boundaries in original source
- `raw_code`: exact source block text

Rules:

- `signature=None` for `kind=file`.
- For class/function/method, signature must preserve source text exactly, including multiline declarations.
- `start_line` and `end_line` are raw source positions.
- Analyzer handles parsing and source slicing; ModelBuilder does not reslice source files.
- Best-effort behavior: per-file parse failure must be reported and processing continues.

## Phase 1 Record Shape

The assembled `Record` model in phase 1 must include:

- `kind`
- `file_path`
- `signature` (nullable)
- `start_line`, `end_line`
- `raw_code`
- `normalized_code`
- `md5sum`
- `intent` (`None` in phase 1)

No parent links (`parent_kind`, `parent_signature`) are included in phase 1.

## Normalization and Hashing

`normalized_code` is derived from `raw_code` by:

- removing comment-only lines
- removing docstring blocks

`md5sum` is computed from `normalized_code`.
Both `raw_code` and `normalized_code` are retained to support debugging.

## CLI Harness

Command shape:

`cds model-build --path <src> --format {table,json}`

Behavior:

- Runs phase 1 analyzer + model build pipeline.
- `table` format supports quick human inspection.
- `json` format supports deterministic test assertions and debug diffs.

## Error Handling

- Parser errors are isolated to the failing file.
- The run continues for remaining files.
- Errors must be surfaced in CLI output/logging so failures are traceable.

## Testing Strategy (Mandatory)

Testing discipline is mandatory across this phase:

- Follow strict TDD (`$test-driven-development`).
- Follow `$testing-anti-patterns`.
- Test real behavior, not mock behavior.
- Do not add test-only methods to production code.

Minimal coverage intent for phase 1 CLI harness:

- Verify command executes and returns expected basic output shape.
- Verify `--format table` and `--format json` behavior.
- Avoid a full end-to-end matrix in this phase.

Core coverage priorities:

- Analyzer output contract and multiline signature extraction.
- Raw boundary correctness (`start_line`, `end_line`).
- Normalizer behavior (comment/docstring stripping).
- Stable MD5 computation from normalized code.
- Best-effort continuation when a file fails to parse.
