# Copyright 2026 Zsolt Kulcsar and Contributors. Licensed under the EUPL-1.2 or later
import pytest

from cds.duplication import DuplicationChecker, PersistedRecord


def test_ph4_dup_001_checker_groups_exact_md5_for_function_and_method_only() -> None:
    checker = DuplicationChecker(intent_threshold=0.85)
    records = [
        PersistedRecord(
            record_id=1,
            kind="function",
            file_path="a.py",
            signature="def a() -> int:",
            start_line=1,
            end_line=2,
            md5sum="same",
            normalized_code="def a() -> int:\n    return 1",
            intent="return one",
        ),
        PersistedRecord(
            record_id=2,
            kind="method",
            file_path="b.py",
            signature="def b(self) -> int:",
            start_line=1,
            end_line=2,
            md5sum="same",
            normalized_code="def b(self) -> int:\n    return 1",
            intent="return one",
        ),
        PersistedRecord(
            record_id=3,
            kind="class",
            file_path="c.py",
            signature="class C:",
            start_line=1,
            end_line=10,
            md5sum="same",
            normalized_code="class C:\n    pass",
            intent="container",
        ),
    ]

    result = checker.check(records=records)

    assert len(result.exact_groups) == 1
    assert len(result.exact_groups[0].members) == 2
    member_ids = {member.record_id for member in result.exact_groups[0].members}
    assert member_ids == {1, 2}


def test_ph4_dup_002_checker_builds_fuzzy_group_with_best_and_avg_scores() -> None:
    checker = DuplicationChecker(intent_threshold=0.8)
    records = [
        PersistedRecord(
            record_id=10,
            kind="function",
            file_path="x.py",
            signature="def parse_file() -> dict:",
            start_line=1,
            end_line=3,
            md5sum="m1",
            normalized_code="def parse_file() -> dict:\n    return {}",
            intent="parse file content into json object",
        ),
        PersistedRecord(
            record_id=11,
            kind="method",
            file_path="y.py",
            signature="def parse(self) -> dict:",
            start_line=1,
            end_line=3,
            md5sum="m1",
            normalized_code="def parse(self) -> dict:\n    return {}",
            intent="parse file contents into json object",
        ),
    ]

    result = checker.check(records=records)

    assert len(result.fuzzy_groups) == 1
    group = result.fuzzy_groups[0]
    assert group.pair_count == 1
    assert group.md5_overlap_pairs == 1
    assert all(member.best_ratio >= 0.8 for member in group.members)
    assert all(member.avg_ratio >= 0.8 for member in group.members)


def test_ph4_dup_003_checker_rejects_out_of_range_threshold() -> None:
    with pytest.raises(ValueError):
        DuplicationChecker(intent_threshold=1.2)


def test_ph4_dup_004_checker_builds_normalized_code_fuzzy_groups() -> None:
    checker = DuplicationChecker(intent_threshold=0.8)
    records = [
        PersistedRecord(
            record_id=20,
            kind="function",
            file_path="a.py",
            signature="def parse_a() -> dict:",
            start_line=1,
            end_line=3,
            md5sum="m1",
            normalized_code="def parse_a() -> dict:\n    return {'k': 1}",
            intent="unrelated intent alpha",
        ),
        PersistedRecord(
            record_id=21,
            kind="method",
            file_path="b.py",
            signature="def parse_b(self) -> dict:",
            start_line=1,
            end_line=3,
            md5sum="m2",
            normalized_code="def parse_b(self) -> dict:\n    return {'k': 1}",
            intent="totally different intent beta",
        ),
    ]

    result = checker.check(records=records)

    assert result.fuzzy_groups == []
    assert len(result.normalized_code_fuzzy_groups) == 1
    group = result.normalized_code_fuzzy_groups[0]
    assert group.match_type == "normalized_code_fuzzy"
    assert group.pair_count == 1
    assert all(member.best_ratio >= 0.8 for member in group.members)
