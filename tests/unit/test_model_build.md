* [x] **PH1_MOD_001** Python analyzer extracts multiline method signature with raw boundaries
- Description: Validate that analyzer returns a `method` symbol with exact multiline signature text and original `start_line` and `end_line`.
- Expected: One method symbol is present, signature matches source formatting, and boundaries match raw source positions.

* [x] **PH1_MOD_002** Python analyzer continues when one file fails to parse
- Description: Validate best-effort behavior when a valid Python file and an invalid Python file are analyzed together.
- Expected: Symbols are returned for valid files, one analyzer error is reported for the invalid file, and processing continues.

* [x] **PH1_MOD_003** Model builder normalizes code before MD5 computation
- Description: Validate that function-level docstrings and comment-only lines are removed before hash generation and that `intent` remains `None`.
- Expected: `normalized_code` contains only executable code lines, `md5sum` is populated, and `intent` is `None`.

* [x] **PH1_MOD_004** Normalizer removes module docstrings and comment lines
- Description: Validate that normalization removes standalone docstring blocks and comment-only lines while preserving code lines.
- Expected: Output contains only non-comment, non-docstring code lines.

* [x] **PH1_MOD_005** CLI model-build supports JSON output
- Description: Validate the `model-build` command with `--format json` returns a JSON payload containing records.
- Expected: Exit code is zero and JSON output includes a non-empty `records` list.

* [x] **PH1_MOD_006** CLI model-build supports table output
- Description: Validate the `model-build` command with `--format table` prints tabular headers and record rows.
- Expected: Exit code is zero and output includes `kind`, `file_path`, and `signature` columns.

* [x] **PH1_MOD_007** CLI model-build JSON output can be written to a file
- Description: Validate that `--output <path>` writes raw JSON payload to the target file when `--format json` is used.
- Expected: Exit code is zero, stdout remains empty, and the output file contains a JSON object with non-empty `records`.

* [x] **PH1_MOD_008** CLI model-build JSON output prints to stdout when no output file is set
- Description: Validate that JSON is printed to stdout when `--format json` is used without `--output`.
- Expected: Exit code is zero and stdout contains a JSON object with non-empty `records`.

* [x] **PH2_MOD_001** CLI enrich-intent requires provider and model
- Description: Validate that `enrich-intent` fails fast when `--provider-url` and `--model` are missing.
- Expected: Exit code is `2` and command does not proceed with enrichment.

* [x] **PH2_MOD_002** CLI enrich-intent default scope enriches symbols and skips file records
- Description: Validate default `--scope` behavior (`class,function,method`) so file records remain skipped while other symbols are enriched.
- Expected: File records have `intent_status=skipped`; class/function/method records have `intent_status=success`.

* [x] **PH2_MOD_003** CLI enrich-intent marks failed records in best-effort mode
- Description: Validate that enrichment continues when one LLM call fails and failed records keep `intent=None` with failure metadata.
- Expected: Exit code is zero, at least one function record is `failed`, and another function record is `success`.

* [x] **PH2_MOD_004** CLI enrich-intent emits batch progress logs with failure count and ETA
- Description: Validate structured progress logging after configured batch intervals with `completed`, `total`, `failed`, and `eta_seconds`.
- Expected: Progress logs are emitted at least twice, include `failed` count, and include `eta_seconds`.

* [x] **PH2_MOD_005** CLI enrich-intent scope all includes file-level enrichment
- Description: Validate that `--scope all` enriches file records in addition to class/function/method records.
- Expected: File record exists and has `intent_status=success`.

* [x] **PH2_MOD_007** LLM client builder selects OpenAI client for OpenAI provider URL
- Description: Validate that `build_llm_client` returns the OpenAI-backed client implementation when the provider URL targets OpenAI.
- Expected: Returned client instance is `OpenAIClient`.

* [x] **PH2_MOD_008** OpenAI client uses gpt-5.2-codex and reads response output text
- Description: Validate that OpenAI client intent generation calls Responses API with `gpt-5.2-codex` and returns `output_text`.
- Expected: Generated intent equals mocked `output_text`, and request model is exactly `gpt-5.2-codex`.

* [x] **PH2_MOD_009** OpenAI client normalizes short OpenAI provider URL
- Description: Validate that providing `openai.com` as provider URL resolves to the canonical OpenAI API base URL before client initialization.
- Expected: OpenAI client is initialized with `https://api.openai.com/v1` and intent generation succeeds.

* [x] **PH2_MOD_010** OpenAI client rejects malformed provider URL
- Description: Validate that malformed OpenAI provider URLs fail fast with a clear initialization error.
- Expected: `IntentGenerationError` is raised and contains an invalid-provider-url message.

* [x] **PH3_MOD_001** CLI persist requires db path argument
- Description: Validate that `persist` fails fast when `--db-path` is missing.
- Expected: Exit code is `2` and execution does not proceed to analysis/enrichment.

* [x] **PH3_MOD_002** CLI persist fails when db parent directory does not exist
- Description: Validate that `persist` rejects a database path when the parent directory is absent.
- Expected: Exit code is `2` and stderr contains a parent-directory validation error.

* [x] **PH3_MOD_003** CLI persist saves snapshot and prints run summary
- Description: Validate successful end-to-end persist flow with deterministic enrichment and SQLite writes.
- Expected: Exit code is `0`, stdout summary includes run metadata fields, and database contains one run with matching record inserts.

* [x] **PH3_MOD_004** CLI persist reports completed_with_errors when enrichment partially fails
- Description: Validate best-effort persist behavior where one intent generation fails while others succeed.
- Expected: Exit code is `0`, run summary status is `completed_with_errors`, and persisted run metadata includes non-zero failed intent count.

* [x] **PH4_MOD_001** CLI dup-check requires run-id argument
- Description: Validate that `dup-check` fails fast when `--run-id` is omitted.
- Expected: Exit code is `2`.

* [x] **PH4_MOD_002** CLI dup-check returns no-findings for missing run ID
- Description: Validate that `dup-check` emits a no-findings message and exits successfully when the requested run ID has no records.
- Expected: Exit code is `0` and stdout indicates no duplication findings.

* [x] **PH4_MOD_003** CLI dup-check renders exact and fuzzy duplication tables
- Description: Validate that `dup-check` prints both exact and fuzzy duplication sections with group/member score columns.
- Expected: Exit code is `0` and output includes exact/fuzzy section titles plus group metadata and md5 overlap indicators.
