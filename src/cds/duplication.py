# Copyright 2026 Zsolt Kulcsar and Contributors. Licensed under the EUPL-1.2 or later
"""Duplication detection models and matching service."""

import logging
from dataclasses import dataclass
from typing import Callable, Literal

import Levenshtein

from cds.analyzer import SymbolKind

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PersistedRecord:
    """Represent one persisted record loaded from SQLite.

    Attributes:
        record_id: Record primary key.
        kind: Symbol kind.
        file_path: Source file path.
        signature: Symbol signature.
        start_line: Start line in source.
        end_line: End line in source.
        md5sum: Normalized code checksum.
        normalized_code: Normalized source code used for MD5 and fuzzy checks.
        intent: Generated intent text.
    """

    record_id: int
    kind: SymbolKind
    file_path: str
    signature: str | None
    start_line: int
    end_line: int
    md5sum: str
    normalized_code: str
    intent: str | None


@dataclass(frozen=True)
class DuplicationMember:
    """Represent one member row in a duplication group."""

    group_id: int
    record_id: int
    kind: SymbolKind
    file_path: str
    signature: str | None
    normalized_code: str
    intent: str | None
    start_line: int
    end_line: int
    best_ratio: float
    avg_ratio: float
    md5_overlap: bool


@dataclass(frozen=True)
class DuplicationGroup:
    """Represent one duplication group."""

    group_id: int
    members: list[DuplicationMember]
    pair_count: int
    md5_overlap_pairs: int
    match_type: Literal["exact", "fuzzy", "normalized_code_fuzzy"]


@dataclass(frozen=True)
class DuplicationResult:
    """Represent duplication findings for one run."""

    exact_groups: list[DuplicationGroup]
    fuzzy_groups: list[DuplicationGroup]
    normalized_code_fuzzy_groups: list[DuplicationGroup]


@dataclass(frozen=True)
class _PairEdge:
    """Represent one pair match edge in fuzzy graph."""

    left_id: int
    right_id: int
    ratio: float
    md5_match: bool


class DuplicationChecker:
    """Find duplication groups using exact and fuzzy matching."""

    def __init__(self, intent_threshold: float) -> None:
        """Initialize checker with fuzzy threshold.

        Args:
            intent_threshold: Inclusive intent similarity threshold in [0.0, 1.0].

        Raises:
            ValueError: If threshold is outside [0.0, 1.0].
        """
        if intent_threshold < 0.0 or intent_threshold > 1.0:
            raise ValueError("intent_threshold must be between 0.0 and 1.0.")
        self._intent_threshold = intent_threshold

    def check(self, records: list[PersistedRecord]) -> DuplicationResult:
        """Compute exact and fuzzy duplication groups.

        Args:
            records: Candidate records loaded for a run.

        Returns:
            Duplication results with exact, fuzzy-intent, and fuzzy-code groups.
        """
        eligible = [r for r in records if r.kind in {"function", "method"}]
        exact_groups = self._build_exact_groups(records=eligible)
        fuzzy_groups = self._build_fuzzy_groups_by_text(
            records=eligible,
            text_getter=lambda record: record.intent or "",
            match_type="fuzzy",
        )
        normalized_code_fuzzy_groups = self._build_fuzzy_groups_by_text(
            records=eligible,
            text_getter=lambda record: record.normalized_code,
            match_type="normalized_code_fuzzy",
        )
        return DuplicationResult(
            exact_groups=exact_groups,
            fuzzy_groups=fuzzy_groups,
            normalized_code_fuzzy_groups=normalized_code_fuzzy_groups,
        )

    def _build_exact_groups(
        self, records: list[PersistedRecord]
    ) -> list[DuplicationGroup]:
        """Build exact duplication groups by md5 checksum."""
        by_md5: dict[str, list[PersistedRecord]] = {}
        for record in records:
            by_md5.setdefault(record.md5sum, []).append(record)

        groups: list[DuplicationGroup] = []
        group_id = 1
        for md5sum in sorted(by_md5):
            members = sorted(by_md5[md5sum], key=lambda r: r.record_id)
            if len(members) < 2:
                continue
            pair_count = len(members) * (len(members) - 1) // 2
            group_members = [
                DuplicationMember(
                    group_id=group_id,
                    record_id=record.record_id,
                    kind=record.kind,
                    file_path=record.file_path,
                    signature=record.signature,
                    normalized_code=record.normalized_code,
                    intent=record.intent,
                    start_line=record.start_line,
                    end_line=record.end_line,
                    best_ratio=1.0,
                    avg_ratio=1.0,
                    md5_overlap=True,
                )
                for record in members
            ]
            groups.append(
                DuplicationGroup(
                    group_id=group_id,
                    members=group_members,
                    pair_count=pair_count,
                    md5_overlap_pairs=pair_count,
                    match_type="exact",
                )
            )
            group_id += 1
        return groups

    def _build_fuzzy_groups_by_text(
        self,
        records: list[PersistedRecord],
        text_getter: Callable[[PersistedRecord], str],
        match_type: Literal["fuzzy", "normalized_code_fuzzy"],
    ) -> list[DuplicationGroup]:
        """Build fuzzy duplication groups by text similarity."""
        edges: list[_PairEdge] = []
        neighbors: dict[int, set[int]] = {record.record_id: set() for record in records}
        by_id = {record.record_id: record for record in records}

        sorted_records = sorted(records, key=lambda r: r.record_id)
        for index, left in enumerate(sorted_records):
            left_text = text_getter(left)
            for right in sorted_records[index + 1 :]:
                right_text = text_getter(right)
                ratio = float(Levenshtein.ratio(left_text, right_text))
                if ratio < self._intent_threshold:
                    continue
                md5_match = left.md5sum == right.md5sum
                edges.append(
                    _PairEdge(
                        left_id=left.record_id,
                        right_id=right.record_id,
                        ratio=ratio,
                        md5_match=md5_match,
                    )
                )
                neighbors[left.record_id].add(right.record_id)
                neighbors[right.record_id].add(left.record_id)

        components: list[list[int]] = []
        visited: set[int] = set()
        for record in sorted_records:
            root = record.record_id
            if root in visited or not neighbors[root]:
                continue
            stack = [root]
            component: list[int] = []
            visited.add(root)
            while stack:
                current = stack.pop()
                component.append(current)
                for linked in neighbors[current]:
                    if linked in visited:
                        continue
                    visited.add(linked)
                    stack.append(linked)
            if len(component) >= 2:
                components.append(sorted(component))

        groups: list[DuplicationGroup] = []
        group_id = 1
        for component in components:
            component_set = set(component)
            component_edges = [
                edge
                for edge in edges
                if edge.left_id in component_set and edge.right_id in component_set
            ]
            if not component_edges:
                continue
            members: list[DuplicationMember] = []
            for record_id in component:
                record = by_id[record_id]
                linked_edges = [
                    edge
                    for edge in component_edges
                    if edge.left_id == record_id or edge.right_id == record_id
                ]
                ratios = [edge.ratio for edge in linked_edges]
                best_ratio = max(ratios)
                avg_ratio = sum(ratios) / len(ratios)
                md5_overlap = any(edge.md5_match for edge in linked_edges)
                members.append(
                    DuplicationMember(
                        group_id=group_id,
                        record_id=record.record_id,
                        kind=record.kind,
                        file_path=record.file_path,
                        signature=record.signature,
                        normalized_code=record.normalized_code,
                        intent=record.intent,
                        start_line=record.start_line,
                        end_line=record.end_line,
                        best_ratio=best_ratio,
                        avg_ratio=avg_ratio,
                        md5_overlap=md5_overlap,
                    )
                )
            groups.append(
                DuplicationGroup(
                    group_id=group_id,
                    members=members,
                    pair_count=len(component_edges),
                    md5_overlap_pairs=sum(
                        1 for edge in component_edges if edge.md5_match
                    ),
                    match_type=match_type,
                )
            )
            group_id += 1
        return groups
