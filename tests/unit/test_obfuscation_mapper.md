* [x] **PH6_OBF_101** Mapper output is deterministic
- Description: Build rename maps multiple times from the same index and compare outputs.
- Expected: Mapping keys and generated obfuscated names are identical across runs.

* [x] **PH6_OBF_102** Mapper excludes external and dunder symbols
- Description: Build a map from candidates containing external and dunder symbols.
- Expected: External and dunder names are not present in the output mapping.

* [x] **PH6_OBF_103** Mapper tags likely-local symbols
- Description: Build a map from an index with likely-local dynamic attribute names.
- Expected: Likely-local symbols are mapped and reported in the likely-local symbol set.
