* [x] **PH5_OBF_001** CLI requires `--input` and `--output`
- Description: Validate that running the obfuscation CLI without required arguments fails during argument parsing.
- Expected: Exit code is `2`.

* [x] **PH5_OBF_002** CLI fails when input path is missing
- Description: Validate that the command rejects a non-existent input directory.
- Expected: Exit code is `2` and stderr contains `Input path does not exist`.

* [x] **PH5_OBF_003** CLI fails when `.gitignore` is missing
- Description: Validate that the command requires `.gitignore` in the input project root.
- Expected: Exit code is `2` and stderr references `.gitignore`.

* [x] **PH5_OBF_004** CLI fails when output directory is non-empty
- Description: Validate that the command rejects an output directory that already contains files.
- Expected: Exit code is `2` and stderr contains `Output path must be empty`.

* [x] **PH5_OBF_005** CLI fails when input and output paths overlap
- Description: Validate that the command rejects path overlap between input and output directories.
- Expected: Exit code is `2` and stderr contains `must not overlap`.

* [x] **PH5_OBF_006** Copy phase excludes `.git` and root `.gitignore` matches
- Description: Validate that copy excludes `.git` content and root-level ignored files while copying non-ignored files.
- Expected: Exit code is `0`, `.git` is absent in output, ignored files are absent, non-ignored files are present.

* [x] **PH5_OBF_007** Copy phase respects nested `.gitignore`
- Description: Validate that ignore rules in nested `.gitignore` files apply to files beneath that nested directory.
- Expected: Exit code is `0`, nested ignored files are absent, nested non-ignored files are present.

* [x] **PH5_OBF_008** Transform summary reports discovered and processed files
- Description: Validate that transform summary includes discovered, processed, and unchanged Python file counts.
- Expected: Exit code is `0`, stdout contains `python_files_discovered`, `python_files_processed`, and `python_files_unchanged` with expected values.

* [x] **PH5_OBF_009** Transform phase fails fast on first read failure
- Description: Validate fail-fast behavior when reading one discovered Python file fails during transform.
- Expected: Exit code is `2`, stderr contains `Transform failed`, and partial output remains present.

* [x] **PH5_OBF_010** CLI renders phase markers and required summary keys
- Description: Validate that the command prints start/done markers and required summary keys for validation, copy, and transform phases.
- Expected: Exit code is `0`, stdout contains all required markers and summary keys, and final status is `status=success`.

* [x] **PH6_OBF_401** Transform summary includes obfuscation counters
- Description: Run CLI transform on a small project and validate expanded summary fields for obfuscation mapping and rewrite activity.
- Expected: Output contains `symbols_discovered`, `symbols_renamed`, `symbols_skipped_external`, `symbols_renamed_likely_local`, and `dynamic_name_rewrites`.

* [x] **PH6_OBF_402** Transform summary tracks likely-local dynamic rewrites
- Description: Run CLI transform on source that uses dynamic attribute access with likely-local object ownership.
- Expected: Output includes likely-local rename counters and `dynamic_name_rewrites=1`.
