# Copyright 2026 Zsolt Kulcsar and Contributors. Licensed under the EUPL-1.2 or later
"""Model building from extracted analyzer symbols."""

import hashlib
import logging

from cds.analyzer import ExtractedSymbol
from cds.model import Record
from cds.normalizer import normalize_code

logger = logging.getLogger(__name__)


class ModelBuilder:
    """Build normalized records from extracted symbols."""

    def build(self, symbols: list[ExtractedSymbol]) -> list[Record]:
        """Build records from analyzer symbols.

        Args:
            symbols: Extracted source symbols.

        Returns:
            Normalized records with MD5 hashes and ``intent=None``.
        """
        records: list[Record] = []
        for symbol in symbols:
            normalized_code = normalize_code(symbol.raw_code)
            if not normalized_code:
                logger.warning(
                    "Normalized code is empty; MD5 is computed from empty content",
                    extra={"file_path": symbol.file_path, "kind": symbol.kind},
                )
            md5sum = hashlib.md5(normalized_code.encode("utf-8")).hexdigest()  # noqa: S324
            records.append(
                Record(
                    kind=symbol.kind,
                    file_path=symbol.file_path,
                    signature=symbol.signature,
                    start_line=symbol.start_line,
                    end_line=symbol.end_line,
                    raw_code=symbol.raw_code,
                    normalized_code=normalized_code,
                    md5sum=md5sum,
                    intent=None,
                )
            )
        return records
