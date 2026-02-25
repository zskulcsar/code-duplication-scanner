# Obfuscation CLI Design (2026-02-22)

## Confirmed CLI Baseline

We use a standalone CLI module at `src/cli/obfuscation_harness.py`, invoked with:
`uv run python -m cli.obfuscation_harness --input <path> --output <path>`.

The flow is two-phase:
1. Copy input tree to output.
2. Process Python files in output.

Path and safety constraints:
- `--input` must exist and be a directory.
- `--output` must not be a non-empty directory.
- input/output must not overlap.
- `.gitignore` must exist in input.
- Filtering source is `.gitignore` (with nested `.gitignore` semantics) plus hard exclusion of `.git`.

Execution and failure behavior:
- v1 is single-threaded.
- Transform phase is fail-fast on first read/transform/write error.
- Partial output is retained on failure (no rollback).

Output contract:
- rich text output (no JSON)
- phase start/done markers
- copy and transform summaries
- transform summary includes at least discovered and processed file counts

## Obfuscation Rule Set

Goal: the obfuscated project should remain executable and preserve behavior.

Symbol renaming scope:
- Build one global symbol map for the entire project.
- Rename in-project declarations and references consistently across files.
- Include class names, function/method names, parameters, locals, and project-declared class members.
- Public API names are not preserved in v1; they are obfuscated if declared in-project.
- Never rename dunder names (for example `__init__`, `__str__`, `__enter__`).
- Do not rename symbols resolved to external dependencies (stdlib/third-party).

String and f-string handling:
- Plain string literal text must remain unchanged.
- In f-strings, keep static text unchanged.
- In f-strings, obfuscate identifiers inside `{...}` expressions based on the rename map.
- Replacements inside normal quoted strings are invalid behavior.

Attribute and dynamic name handling:
- Rename attribute names only when declared in project code.
- Leave external attributes unchanged.
- For `getattr`, `setattr`, and `hasattr`, rewrite the `"name"` string argument only when static analysis indicates the target object is project-declared and the name resolves to a renamed project attribute.
- If resolution is uncertain, rename when likely project-local.

## Analysis and Rewrite Architecture

Use a two-pass project transform:
1. Index pass: parse all Python files and build a symbol graph for declarations, references, imports, class members, and dynamic name usage sites.
2. Rewrite pass: apply consistent renames using AST/CST-aware rewriting so semantics are preserved, with strict handling for strings and f-strings as defined above.

Post-transform correctness gates:
- each rewritten file must parse
- transformed project should report warnings for uncertain-but-renamed decisions
- report counters for discovered/renamed/skipped symbols and files changed

## Testing Scope

Keep deterministic static/transform tests and remove runtime parity execution tests for now.

Required test coverage:
- symbol classification (project-local vs external)
- plain string literals unchanged
- f-string static text unchanged and expression rewrites applied
- attribute rename policy (project-declared only)
- `getattr`/`setattr`/`hasattr` rewrite policy
- dunder exclusion
- multi-file global-map consistency
- parser/validation and fail-fast behavior
