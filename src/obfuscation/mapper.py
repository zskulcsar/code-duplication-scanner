# Copyright 2026 Zsolt Kulcsar and Contributors. Licensed under the EUPL-1.2 or later
"""Build deterministic obfuscation symbol rename maps."""

import builtins
import keyword
import logging
from dataclasses import dataclass

from obfuscation.analyzer import ProjectIndex

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RenameMap:
    """Store generated symbol rename mapping and provenance hints.

    Args:
        mapping: Original symbol to obfuscated symbol mapping.
        likely_local_symbols: Symbols mapped with likely-local confidence.
    """

    mapping: dict[str, str]
    likely_local_symbols: frozenset[str]


def build_rename_map(index: ProjectIndex) -> RenameMap:
    """Build deterministic symbol map from project index.

    Args:
        index: Project symbol index.

    Returns:
        Deterministic rename map.
    """
    rename_targets = set(index.rename_candidates)
    rename_targets.update(index.project_attributes)
    rename_targets.difference_update(index.external_symbols)
    rename_targets = {name for name in rename_targets if _is_eligible(name)}

    blocked_names = set(rename_targets)
    blocked_names.update(index.external_symbols)
    blocked_names.update(keyword.kwlist)
    blocked_names.update(dir(builtins))

    mapping: dict[str, str] = {}
    generated_names: set[str] = set()
    for symbol in sorted(rename_targets):
        obfuscated = _next_symbol_name(
            blocked_names=blocked_names,
            generated_names=generated_names,
        )
        generated_names.add(obfuscated)
        mapping[symbol] = obfuscated

    likely_local_symbols = {
        symbol for symbol in index.likely_local_dynamic_attributes if symbol in mapping
    }

    if likely_local_symbols:
        logger.info(
            "Mapped likely-local symbols",
            extra={"count": len(likely_local_symbols)},
        )

    return RenameMap(
        mapping=mapping,
        likely_local_symbols=frozenset(likely_local_symbols),
    )


def _is_eligible(name: str) -> bool:
    """Check whether symbol is eligible for rename-map generation.

    Args:
        name: Symbol name.

    Returns:
        True when symbol should be mapped.
    """
    if not name.isidentifier():
        return False
    if name.startswith("__") and name.endswith("__"):
        return False
    return True


def _next_symbol_name(blocked_names: set[str], generated_names: set[str]) -> str:
    """Generate the next deterministic obfuscated symbol.

    Args:
        blocked_names: Names that cannot be used.
        generated_names: Already generated obfuscated names.

    Returns:
        Next available obfuscated name.
    """
    counter = 0
    while True:
        candidate = _alphabetic_name(counter)
        counter += 1
        if candidate in blocked_names:
            continue
        if candidate in generated_names:
            continue
        return candidate


def _alphabetic_name(counter: int) -> str:
    """Generate deterministic alphabetic identifier from integer counter.

    Args:
        counter: Zero-based integer index.

    Returns:
        Alphabetic identifier in base-26 lowercase.
    """
    alphabet = "abcdefghijklmnopqrstuvwxyz"
    index = counter
    chars: list[str] = []
    while True:
        chars.append(alphabet[index % 26])
        index = index // 26 - 1
        if index < 0:
            break
    return "".join(reversed(chars))
