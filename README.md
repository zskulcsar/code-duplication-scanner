# Code Duplication Scanner

Simple Python CLI/TUI project for surfacing likely code duplication from source code.
Phase 1 builds an analysis model from Python files, normalizes code, and computes MD5 fingerprints.

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

## Display Note

The table view is best experienced on wide screens/terminals because signatures and normalized code can be long.
