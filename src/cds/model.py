# Copyright 2026 Zsolt Kulcsar and Contributors. Licensed under the EUPL-1.2 or later
"""Domain models for analysis artifacts."""

from dataclasses import dataclass

from cds.analyzer import SymbolKind


@dataclass(frozen=True)
class Record:
    """Represent one normalized source record.

    Attributes:
        kind: Symbol kind for this record.
        file_path: Project-relative source file path.
        signature: Exact declaration text; ``None`` for file-level records.
        start_line: Raw start line in source (1-based).
        end_line: Raw end line in source (1-based).
        raw_code: Exact extracted source block.
        normalized_code: Bare code after comment/docstring stripping.
        md5sum: MD5 hash of ``normalized_code``.
        intent: Intent description. Set to ``None`` until enrichment succeeds.
        intent_status: Enrichment status (`skipped`, `success`, `failed`).
        intent_error: Error detail for failed enrichments.
    """

    kind: SymbolKind
    file_path: str
    signature: str | None
    start_line: int
    end_line: int
    raw_code: str
    normalized_code: str
    md5sum: str
    intent: str | None
    intent_status: str = "skipped"
    intent_error: str | None = None
