* [x] **PH3_PERS_001** SQLite persistence stores one run with all records
- Description: Validate that persistence creates schema, inserts one run row, and inserts all provided records with the expected run linkage.
- Expected: Returned run ID is positive, counts match inserted records, and database tables contain the expected run and record rows.

* [x] **PH3_PERS_002** SQLite persistence marks run status completed_with_errors when failures exist
- Description: Validate run status derivation when at least one analyzer error or failed intent is present in the persisted input.
- Expected: Persist result contains `completed_with_errors`, with accurate failed-intent and analyzer-error counters.

* [x] **PH3_PERS_003** SQLite persistence rolls back transaction on record insert failure
- Description: Validate that when record insertion fails after run insertion starts, the transaction is rolled back and no partial run row remains.
- Expected: Persistence raises `PersistenceError` and the `runs` table remains empty after the failed operation.
