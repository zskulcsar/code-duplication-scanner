"""Code normalization helpers for hashing and intent generation input."""

import io
import logging
import tokenize

logger = logging.getLogger(__name__)


def normalize_code(raw_code: str) -> str:
    """Normalize code by removing comments and docstrings.

    Args:
        raw_code: Raw code block as extracted from source.

    Returns:
        Normalized code text preserving code-bearing lines.
    """
    lines = raw_code.splitlines()
    lines = _strip_comment_only_lines(lines)
    lines = _strip_docstring_blocks(lines)
    return "\n".join(line for line in lines if line.strip())


def _strip_comment_only_lines(lines: list[str]) -> list[str]:
    """Remove lines that contain only comments."""
    return [line for line in lines if not line.lstrip().startswith("#")]


def _strip_docstring_blocks(lines: list[str]) -> list[str]:
    """Remove probable docstring blocks via token analysis.

    A standalone string token (``STRING`` followed by ``NEWLINE``) is treated
    as a docstring-like block and removed.
    """
    source = "\n".join(lines)
    if not source.strip():
        return []

    remove_lines: set[int] = set()
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except tokenize.TokenError as exc:
        logger.warning(
            "Tokenization failed while stripping docstrings; returning comment-stripped lines",
            extra={"error": str(exc)},
        )
        return lines
    for index, token in enumerate(tokens):
        if token.type != tokenize.STRING:
            continue
        prev_type = tokens[index - 1].type if index > 0 else None
        next_type = tokens[index + 1].type if index + 1 < len(tokens) else None
        if prev_type in {tokenize.INDENT, tokenize.NEWLINE, tokenize.DEDENT, None} and (
            next_type == tokenize.NEWLINE
        ):
            start_row = token.start[0]
            end_row = token.end[0]
            for line_no in range(start_row, end_row + 1):
                remove_lines.add(line_no)

    return [
        line
        for line_no, line in enumerate(lines, start=1)
        if line_no not in remove_lines
    ]
