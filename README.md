# Code Duplication Scanner

Simple Python CLI/TUI project for surfacing likely code duplication from source code.
The current implementation supports:
- Phase 1: build an analysis model from Python files, normalize code, and compute MD5 fingerprints.
- Phase 2: enrich records with LLM-generated intent summaries for selected symbol scopes.

## Requirements

- Python `>=3.11`
- `uv`
- `make`

## Build

```bash
make venv
```

## Usage

Run directly:

```bash
PYTHONPATH=src uv run python -m cli.cli_verification_harness model-build --path ./src --format table
```

Use Makefile helper:

```bash
make run-cli ARGS="model-build --path ./src --format table"
```

JSON output to terminal:

```bash
make run-cli ARGS="model-build --path ./src --format json"
```

JSON output to file:

```bash
make run-cli ARGS="model-build --path ./src --format json --output ./tmp/model.json"
```

## Intent Enrichment

Run enrichment in table mode (includes `intent`):

```bash
make run-cli ARGS="enrich-intent --path ./src --provider-url http://llm.shibuya.local:11434 --model qwen3-coder:latest --scope class,function,method --format table"
```

Run enrichment in JSON mode:

```bash
make run-cli ARGS="enrich-intent --path ./src --provider-url http://llm.shibuya.local:11434 --model qwen3-coder:latest --scope class,function,method --format json --output ./tmp/enriched.json"
```

Useful enrichment flags:
- `--scope class,function,method,all` to control which symbol kinds are enriched (`all` means all scopes).
- `--progress-batch-size N` to print progress/ETA every N completed LLM calls (default: `10`).

Model notes from current testing:
- `qwen3-coder:latest` worked very well.
- `starcoder2:15b` produced weaker results and failed frequently.

## Display Note

The table view is best experienced on wide screens/terminals because signatures and normalized code can be long.
