# Code Duplication Scanner Design

## Purpose

This project provides a simple CLI application that surfaces likely code duplication from source code.
The first implementation targets Python code only, with a design that can extend to additional languages later.

The goal is not to prove semantic equivalence. The goal is to produce high-signal duplication candidates for human review.

The main idea here is that instead of identifying duplicates by pure textual match, we'll use LLM to summarize the behaviour of the code or code pieces (ie.: providing `intent`) and we'll use this intent to produce high-signal candidates. 

## Product Shape

The application is a `textual`-based TUI, launched from the command line.
The CLI accepts a `--path` argument that points to the source tree to analyze.

Initial flow:

1. User runs the application with `--path`.
2. The application scans and analyzes source files. `Record.intent` is derived from an LLM call during this phase.
3. The analysis result is persisted to SQLite.
4. The TUI allows browsing findings.

The browsing UX is intentionally undefined for now. The requirement is to provide a way to inspect findings once analysis and persistence complete.

## Analysis Model

The analysis uses the domain model defined in `src/cds/model.py`.
The analyzer parses source files, builds the corresponding object structure, and stores that structure in SQLite.

## Architecture Direction

### Source Code Analyzers

To support future multi-language support, the codebase should define:

- An analyzer abstraction layer (language-agnostic contract).
- A concrete Python analyzer implementation.

New language support should be added by implementing the analyzer contract, without changing core application flow (CLI -> analyze -> persist -> browse).

Each source analyzer must iterate over every source file and extract:

- `file_path`: path relative to the project root.
- `file_md5`: MD5 hash of file-level bare code lines.
- `file_intent`: short intent summary generated from file-level bare code lines.
- For each class:
- `class_signature`: class signature.
- `class_md5`: MD5 hash of class bare code lines.
- `class_intent`: short intent summary generated from class bare code lines.
- For each function or method:
- `fun_signature`: function or method signature.
- `fun_md5`: MD5 hash of function or method bare code lines.
- `fun_intent`: short intent summary generated from function or method bare code lines.

Normalization and position rules:

- Strip comment lines before hashing and before generating intent.
- Generate intent from bare code lines only, so comments and documentation do not bias LLM output.
- Record original `start_line` and `end_line` positions from the source file, including code lines, for precise identification.

### LLM Integration

Intent generation must use a pluggable LLM interface.
The first connector should target Ollama.
The design must support additional connectors later (for example, cloud or remote model providers) without changing analyzer core logic.

## Implementation Phases

Testing discipline across all phases:

- TDD is mandatory in every implementation phase.
- The of the `$test-driven-development` and `$testing-anti-patterns` skills is mandatory in every phase.
- Tests must validate real behavior and avoid mock-driven assertions or test-only production APIs.

1. Class model builder plus CLI test harness
- Build the source-code-to-class-model pipeline.
- Provide a CLI interface under `src/cli` to inspect and validate model output during development.
- Keep CLI harness tests minimal: enough TDD coverage to verify the development workflow and key outputs, not a full end-to-end test matrix.

2. Intent enrichment from the class model
- Use the class model as input to LLM intent generation.
- Reuse the same CLI interface for development-time verification.

3. Persistence wiring
- Integrate the SQLite persistence layer for analyzed and enriched model data.

4. Textual TUI
- Build the `textual`-based TUI layer for browsing findings.

## Design Intent to Preserve

- Keep a simple, deterministic batch analyzer.
- Keep Python as the initial language target while designing for extension.
- Keep LLM integration behind an abstraction layer, with Ollama as the initial implementation.
- Keep TDD mandatory across all implementation phases.
- Keep usage of `$test-driven-development` and `$testing-anti-patterns` mandatory across all implementation phases.
- Keep tests focused on real behavior, and avoid mock-behavior assertions and test-only production APIs.
- Persist analysis artifacts to SQLite before opening interactive browsing.
- Keep a clear separation between analysis, persistence, and presentation (TUI). See the MVC pattern.
