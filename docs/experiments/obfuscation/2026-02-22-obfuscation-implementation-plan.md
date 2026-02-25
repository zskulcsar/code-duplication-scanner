# Obfuscation CLI Implementation Plan (2026-02-22)

## Objective

Deliver a standalone experimental CLI module `cli.obfuscation_harness` that:

- accepts `--input` and `--output`
- copies input project to output using `.gitignore`-driven filtering
- processes Python files in output with a placeholder no-op transform pipeline
- emits rich phase output with start/done markers and required summaries

No literal replacement rules are implemented in this phase.

## Scope

In scope:

- new standalone CLI module under `src/cli/`
- new Make target mirroring `run-cli` invocation style
- strict validation and fail-fast behavior agreed in brainstorm
- `.gitignore`-based filtering with nested `.gitignore` support
- placeholder transform pipeline with unchanged-file no-rewrite behavior
- full unit tests for validation, filtering, flow, and output summaries

Out of scope:

- actual literal obfuscation rules
- concurrency/workers
- JSON output mode
- rollback-on-error behavior

## Implementation Steps (TDD Order)

### Step 1: CLI Skeleton and Validation

Files:
- `src/cli/obfuscation_harness.py` (new)
- `tests/unit/test_obfuscation_harness.py` (new)

Work:
- create argument parser with required `--input`, `--output`
- add validation helpers:
  - input exists and is directory
  - input contains `.gitignore`
  - output not non-empty
  - input/output do not overlap
- return non-zero on validation failure with clear stderr messages

Tests first:
- missing input path
- input not directory
- missing `.gitignore`
- non-empty output rejection
- overlapping path rejection

### Step 2: Copy Phase With Gitignore Filtering

Files:
- `src/cli/obfuscation_harness.py`
- `tests/unit/test_obfuscation_harness.py`
- `pyproject.toml` (only if matcher dependency is added)

Work:
- implement recursive copy pipeline
- hard-exclude `.git`
- apply Git-style ignore matching for root and nested `.gitignore` files
- collect copy summary counters:
  - `files_copied`
  - `dirs_created`
  - `paths_skipped_by_gitignore`
  - `paths_skipped_git_dir`
  - `elapsed_ms`

Tests first:
- `.git` directory never copied
- root `.gitignore` patterns respected
- nested `.gitignore` patterns respected
- copied files/dirs and skipped counters are reported

### Step 3: Discovery + Placeholder Transform

Files:
- `src/cli/obfuscation_harness.py`
- `tests/unit/test_obfuscation_harness.py`

Work:
- discover `*.py` in output tree
- process discovered Python files sequentially
- run no-op `transform_source(content) -> content`
- skip rewriting unchanged files
- fail-fast on first read/write failure
- collect transform summary:
  - `python_files_discovered`
  - `python_files_processed`
  - `python_files_unchanged`
  - `elapsed_ms`

Tests first:
- discovered count equals number of Python files in copied output
- processed count equals discovered count in normal run
- unchanged files are not rewritten
- fail-fast on first file error returns non-zero

### Step 4: Rich Phase Output Contract

Files:
- `src/cli/obfuscation_harness.py`
- `tests/unit/test_obfuscation_harness.py`

Work:
- add rich output markers for each phase:
  - phase start
  - phase done
- render required summary fields for copy and transform phases
- print final status line (success/failure)

Tests first:
- output includes start/done markers
- output includes all required summary keys
- ordering is deterministic (validation -> copy -> transform -> final status)

### Step 5: Makefile Integration

Files:
- `Makefile`

Work:
- add `run-obfuscation-cli` target
- mirror `run-cli` environment style:
  - `PYTHONPATH=$(BE_SRC)`
  - `PYTHONPYCACHEPREFIX=$(CURDIR)/.pycache`
  - `uv run python -m cli.obfuscation_harness $(ARGS)`

Tests:
- no unit tests needed; validate command wiring manually with sample invocation.

## Proposed Test Cases

`tests/unit/test_obfuscation_harness.py` should include at least:

1. parser requires `--input` and `--output`
2. fails when input path missing
3. fails when `.gitignore` missing
4. fails when output non-empty
5. fails when input/output overlap
6. copy excludes `.git`
7. copy respects root `.gitignore`
8. copy respects nested `.gitignore`
9. transform discovers and processes expected Python file count
10. unchanged Python files are not rewritten
11. transform fail-fast exits non-zero on first file error
12. rich output includes required phase markers and summary fields

## Acceptance Criteria

- CLI module `cli.obfuscation_harness` is runnable through Make target.
- Validation behavior matches all agreed constraints.
- Copy behavior uses `.gitignore` as filtering source and excludes `.git`.
- Placeholder transform runs end-to-end and reports required counters.
- Rich phase output includes start/done markers and summary keys.
- New unit test suite passes.
- Existing unit tests remain green.

## Execution Notes

- Keep implementation single-threaded.
- Keep transform function isolated so literal rules can be added later without CLI flow changes.
- Do not introduce extra flags beyond `--input` and `--output` in this phase.
