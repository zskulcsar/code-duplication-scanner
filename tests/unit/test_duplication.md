* [x] **PH4_DUP_001** Duplication checker groups exact md5 matches for function and method records
- Description: Validate that exact matching by `md5sum` includes only `function` and `method` records and excludes other kinds from duplication groups.
- Expected: Exactly one exact group is created with member IDs from function/method records only.

* [x] **PH4_DUP_002** Duplication checker reports fuzzy group score metrics and md5 overlap
- Description: Validate fuzzy grouping by Levenshtein ratio includes per-member `best_ratio` and `avg_ratio` and tracks md5 overlap pair counts.
- Expected: One fuzzy group is emitted with pair count, md5 overlap count, and all member score metrics above threshold.

* [x] **PH4_DUP_003** Duplication checker validates threshold bounds
- Description: Validate that checker initialization fails when intent threshold is outside the valid `[0.0, 1.0]` range.
- Expected: A `ValueError` is raised for out-of-range threshold values.
