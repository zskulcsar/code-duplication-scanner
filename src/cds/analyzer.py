"""Analyzer interfaces and DTOs for source extraction."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol


SymbolKind = Literal["file", "class", "function", "method"]


@dataclass(frozen=True)
class ExtractedSymbol:
    """Represent one extracted source symbol.

    Attributes:
        kind: Symbol category.
        file_path: Project-relative source file path.
        signature: Exact declaration text; ``None`` for file-level records.
        start_line: Raw start line in original file (1-based).
        end_line: Raw end line in original file (1-based).
        raw_code: Exact raw code block for the symbol.
    """

    kind: SymbolKind
    file_path: str
    signature: str | None
    start_line: int
    end_line: int
    raw_code: str


@dataclass(frozen=True)
class AnalyzerError:
    """Represent an analyzer error for one file."""

    file_path: str
    message: str


class Analyzer(Protocol):
    """Language-agnostic source analyzer contract."""

    def analyze(
        self, root_path: Path
    ) -> tuple[list[ExtractedSymbol], list[AnalyzerError]]:
        """Analyze a project root and return extracted symbols and errors."""
