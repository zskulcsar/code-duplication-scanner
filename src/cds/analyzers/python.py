# Copyright 2026 Zsolt Kulcsar and Contributors. Licensed under the EUPL-1.2 or later
"""Python source analyzer implementation."""

import ast
import logging
from dataclasses import dataclass
from pathlib import Path

from cds.analyzer import AnalyzerError, ExtractedSymbol, SymbolKind

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _NodeContext:
    scope: str


class PythonAnalyzer:
    """Analyze Python files and extract source symbols."""

    def analyze(
        self, root_path: Path
    ) -> tuple[list[ExtractedSymbol], list[AnalyzerError]]:
        """Analyze Python files beneath the provided root path.

        Args:
            root_path: Root directory to analyze.

        Returns:
            A tuple of extracted symbols and recoverable analyzer errors.
        """
        symbols: list[ExtractedSymbol] = []
        errors: list[AnalyzerError] = []

        for file_path in sorted(root_path.rglob("*.py")):
            try:
                source = file_path.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(file_path))
            except (OSError, UnicodeDecodeError, SyntaxError, ValueError) as exc:
                relative_path = str(file_path.relative_to(root_path))
                logger.warning(
                    f"Skipping file due to parse/read failure (file_path={relative_path} error={exc})",
                )
                errors.append(AnalyzerError(file_path=relative_path, message=str(exc)))
                continue

            lines = source.splitlines()
            symbols.append(
                self._build_file_symbol(root_path, file_path, source, len(lines))
            )
            symbols.extend(
                self._extract_node_symbols(root_path, file_path, lines, tree.body)
            )

        return symbols, errors

    def _build_file_symbol(
        self, root_path: Path, file_path: Path, source: str, line_count: int
    ) -> ExtractedSymbol:
        return ExtractedSymbol(
            kind="file",
            file_path=str(file_path.relative_to(root_path)),
            signature=None,
            start_line=1,
            end_line=max(1, line_count),
            raw_code=source,
        )

    def _extract_node_symbols(
        self,
        root_path: Path,
        file_path: Path,
        lines: list[str],
        body: list[ast.stmt],
        context: _NodeContext | None = None,
    ) -> list[ExtractedSymbol]:
        context = context or _NodeContext(scope="module")
        symbols: list[ExtractedSymbol] = []
        for node in body:
            if isinstance(node, ast.ClassDef):
                symbols.append(
                    self._create_symbol(
                        kind="class",
                        root_path=root_path,
                        file_path=file_path,
                        lines=lines,
                        node=node,
                    )
                )
                symbols.extend(
                    self._extract_node_symbols(
                        root_path=root_path,
                        file_path=file_path,
                        lines=lines,
                        body=node.body,
                        context=_NodeContext(scope="class"),
                    )
                )
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                kind: SymbolKind = "method" if context.scope == "class" else "function"
                symbols.append(
                    self._create_symbol(
                        kind=kind,
                        root_path=root_path,
                        file_path=file_path,
                        lines=lines,
                        node=node,
                    )
                )
                symbols.extend(
                    self._extract_node_symbols(
                        root_path=root_path,
                        file_path=file_path,
                        lines=lines,
                        body=node.body,
                        context=_NodeContext(scope="function"),
                    )
                )
        return symbols

    def _create_symbol(
        self,
        kind: SymbolKind,
        root_path: Path,
        file_path: Path,
        lines: list[str],
        node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> ExtractedSymbol:
        start_line = int(node.lineno)
        end_line = int(getattr(node, "end_lineno", node.lineno))
        signature_end_line = self._determine_signature_end_line(
            node=node, start_line=start_line
        )
        signature = self._slice_lines(
            lines=lines,
            start_line=start_line,
            end_line=signature_end_line,
        )
        raw_code = self._slice_lines(
            lines=lines, start_line=start_line, end_line=end_line
        )
        return ExtractedSymbol(
            kind=kind,
            file_path=str(file_path.relative_to(root_path)),
            signature=signature,
            start_line=start_line,
            end_line=end_line,
            raw_code=raw_code,
        )

    def _determine_signature_end_line(
        self,
        node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
        start_line: int,
    ) -> int:
        if not node.body:
            return start_line
        candidate = int(getattr(node.body[0], "lineno", start_line)) - 1
        if candidate < start_line:
            return start_line
        return candidate

    def _slice_lines(self, lines: list[str], start_line: int, end_line: int) -> str:
        return "\n".join(lines[start_line - 1 : end_line])
