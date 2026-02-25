# Obfuscation Rules Implementation Plan (2026-02-22)

## Objective

Implement the obfuscation transform phase in `cli.obfuscation_harness` so that transformed Python projects follow the finalized rules in `docs/experiments/obfuscation/DESIGN.md`.

Primary goals:
- build one global symbol map across the project
- obfuscate in-project symbols consistently across files
- preserve plain string literal text
- obfuscate only expressions inside f-string `{...}` segments
- rename project-declared attributes (not external attributes)
- support `getattr` / `setattr` / `hasattr` string-name rewrites under project-local rules
- never rename dunder names
- keep deterministic, rich phase reporting

Runtime behavioral parity execution tests are explicitly out of scope for this phase.

## Scope

In scope:
- project-wide analysis pass for symbol indexing and ownership classification
- project-wide deterministic rename map generation
- rewrite pass for definitions/references/attributes/f-string expressions/dynamic name calls
- uncertain-resolution handling: rename when likely project-local, with warnings
- strict parser validation gates before and after rewrite
- transform-phase rich summary expansion for obfuscation counters
- unit and integration tests for static transform correctness

Out of scope:
- executing original vs obfuscated project for parity validation
- rollback mechanism for partially transformed output
- new CLI flags beyond existing `--input` and `--output`
- multithreaded transform execution

## Architecture and Components

### Component Split

- `cli.obfuscation_harness`:
  - orchestrates validation/copy/discovery/transform/reporting
- `obfuscation.analyzer` (new module):
  - parses files
  - builds symbol graph and ownership metadata
  - collects dynamic access sites
- `obfuscation.mapper` (new module):
  - produces deterministic global rename map
  - tracks rename provenance (`resolved_local`, `likely_local`)
- `obfuscation.rewriter` (new module):
  - applies source-to-source edits with AST/CST-aware logic
  - enforces string/f-string constraints

### Data Contracts

- `ProjectIndex`
  - declarations by file and symbol kind
  - import ownership hints
  - attribute ownership map
  - dynamic call sites (`getattr`/`setattr`/`hasattr`)
- `RenameMap`
  - original symbol -> obfuscated symbol
  - scope info
  - provenance confidence
- `TransformSummary` (expanded)
  - existing counters
  - `symbols_discovered`
  - `symbols_renamed`
  - `symbols_skipped_external`
  - `symbols_renamed_likely_local`
  - `dynamic_name_rewrites`

## Implementation Steps (Mandatory TDD Order)

### Step 1: Symbol Model and Index Pass

Files:
- `src/obfuscation/analyzer.py` (new)
- `tests/unit/test_obfuscation_analyzer.py` (new)
- `tests/unit/test_obfuscation_analyzer.md` (new)

Tests first:
1. indexes module/class/function/method declarations
2. captures parameter/local bindings
3. records class member declarations
4. excludes dunder declarations from rename candidates
5. classifies external import symbols as non-project

Implementation:
- build AST-based project index from discovered Python files
- include per-symbol location metadata for diagnostics
- explicit exception handling with warning logs on recoverable file-level issues

### Step 2: Deterministic Global Rename Map

Files:
- `src/obfuscation/mapper.py` (new)
- `tests/unit/test_obfuscation_mapper.py` (new)
- `tests/unit/test_obfuscation_mapper.md` (new)

Tests first:
1. stable rename output for same index input
2. one shared map across multi-file project
3. no dunder keys in map
4. external symbols never mapped
5. uncertain-but-likely-local symbols are mapped and flagged

Implementation:
- deterministic token strategy for obfuscated names
- enforce collision avoidance
- store provenance tags for reporting

### Step 3: Core Rewrite for Definitions and References

Files:
- `src/obfuscation/rewriter.py` (new)
- `tests/unit/test_obfuscation_rewriter.py` (new)
- `tests/unit/test_obfuscation_rewriter.md` (new)

Tests first:
1. rewrites in-project definitions and references consistently
2. leaves external references unchanged
3. preserves parseability after rewrite
4. preserves plain string literals exactly
5. never rewrites dunder names

Implementation:
- apply renames to identifier-bearing syntax nodes
- maintain explicit guardrails for string literals and unsupported nodes
- fail fast on unrecoverable rewrite errors

### Step 4: f-string and Dynamic Name Rules

Files:
- `src/obfuscation/rewriter.py`
- `tests/unit/test_obfuscation_rewriter.py`
- `tests/unit/test_obfuscation_rewriter.md`

Tests first:
1. f-string static text unchanged
2. identifiers inside f-string expression blocks are rewritten
3. `getattr(obj, "name")` rewrites `"name"` only when object resolves/likely-resolves project-local
4. same policy for `setattr` and `hasattr`
5. unresolved dynamic sites follow likely-local policy and are counted as such

Implementation:
- parse/transform f-string expression parts only
- implement dynamic-call argument rewrite policy with ownership checks
- emit warnings for likely-local decisions

### Step 5: Attribute Ownership Rules

Files:
- `src/obfuscation/analyzer.py`
- `src/obfuscation/rewriter.py`
- `tests/integration/test_obfuscation_cross_file.py` (new)
- `tests/integration/test_obfuscation_cross_file.md` (new)

Tests first:
1. project-declared attribute names are rewritten at declaration and usage sites
2. external attribute names remain unchanged
3. cross-file class/member references use consistent global mapping

Implementation:
- enhance ownership inference for attribute targets
- apply rename only when declared in project or likely-local per policy

### Step 6: Harness Integration and Reporting

Files:
- `src/cli/obfuscation_harness.py`
- `tests/unit/test_obfuscation_harness.py`
- `tests/unit/test_obfuscation_harness.md`

Tests first:
1. transform phase invokes analyze -> map -> rewrite pipeline
2. summary includes new obfuscation counters
3. warning counts/messages surface for likely-local renames
4. phase ordering and start/done markers remain deterministic

Implementation:
- wire new modules into transform phase
- keep fail-fast behavior
- preserve existing copy/filter contracts

## Acceptance Criteria

- Global rename map is generated once per project and used consistently.
- In-project symbols are obfuscated; external dependency symbols are left untouched.
- Plain string literal text is unchanged.
- f-string expression blocks are obfuscated; static f-string text is unchanged.
- Project-declared attributes are obfuscated; external attributes are untouched.
- `getattr` / `setattr` / `hasattr` name rewriting follows project-local/likely-local policy.
- Dunder names are never obfuscated.
- Transform output remains parseable.
- Rich transform summary includes required counters and warning visibility.
- New and existing tests pass through mandated make targets.

## Verification Sequence

For each TDD iteration:
1. run targeted failing test via `make` test target
2. implement minimal code to pass
3. rerun targeted tests
4. run `make fmt-py`
5. run `make lint-py`
6. run `make tc-py`
7. run full tests via `make` target
8. perform manual code review

## Risks and Mitigations

- Risk: aggressive likely-local renaming may introduce runtime mismatches.
  - Mitigation: provenance tagging, warnings, deterministic mapping, focused dynamic-call tests.
- Risk: AST-only rewrite can damage formatting-sensitive constructs.
  - Mitigation: token-aware rewrite boundaries, strict parse-after-rewrite checks.
- Risk: cross-file ownership inference errors.
  - Mitigation: integration tests with multi-module class/member usage.
