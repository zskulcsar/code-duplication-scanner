* [x] **PH6_OBF_001** Analyzer indexes declarations and external imports
- Description: Build an index for one module containing classes, functions, locals, and external imports and verify expected candidate and external symbol sets.
- Expected: Rename candidates include in-project symbols, dunder names are excluded, class attributes are tracked, and external imports are classified as external.

* [x] **PH6_OBF_002** Analyzer keeps in-project import symbols local
- Description: Analyze two modules where one imports a class from the other and verify classification.
- Expected: Imported in-project symbols are eligible for renaming and are not marked external.

* [x] **PH6_OBF_003** Analyzer flags likely-local dynamic attribute usage
- Description: Analyze a module with project-declared attribute and unresolved dynamic getattr usage.
- Expected: The declared attribute is tracked and unresolved dynamic access is recorded as likely-local.

* [x] **PH6_OBF_004** Analyzer treats `src` layout package imports as local
- Description: Analyze `src/`-layout package files where one file imports a class from another through package-qualified import.
- Expected: Imported project symbols remain local rename candidates and are not marked as external.

* [x] **PH6_OBF_005** Analyzer tracks class field names as project attributes
- Description: Analyze a dataclass-style class with class-body field declarations.
- Expected: Field names are included as project attributes so attribute callsites can be rewritten consistently.
