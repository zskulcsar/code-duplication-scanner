# Copyright 2026 Zsolt Kulcsar and Contributors. Licensed under the EUPL-1.2 or later
"""Unit tests for obfuscation rename map generation."""

from obfuscation import ProjectIndex, build_rename_map


def test_ph6_obf_101_mapper_builds_stable_mapping() -> None:
    index = ProjectIndex(
        rename_candidates=frozenset({"Alpha", "beta", "gamma"}),
        external_symbols=frozenset(),
        project_class_names=frozenset(),
        project_attributes=frozenset({"field"}),
        likely_local_dynamic_attributes=frozenset(),
    )

    first = build_rename_map(index=index)
    second = build_rename_map(index=index)

    assert first.mapping == second.mapping
    assert set(first.mapping.keys()) == {"Alpha", "beta", "gamma", "field"}


def test_ph6_obf_102_mapper_excludes_external_and_dunder() -> None:
    index = ProjectIndex(
        rename_candidates=frozenset({"run", "__init__", "path"}),
        external_symbols=frozenset({"path"}),
        project_class_names=frozenset(),
        project_attributes=frozenset(),
        likely_local_dynamic_attributes=frozenset(),
    )

    rename_map = build_rename_map(index=index)

    assert "path" not in rename_map.mapping
    assert "__init__" not in rename_map.mapping
    assert "run" in rename_map.mapping


def test_ph6_obf_103_mapper_marks_likely_local_symbols() -> None:
    index = ProjectIndex(
        rename_candidates=frozenset({"worker"}),
        external_symbols=frozenset(),
        project_class_names=frozenset(),
        project_attributes=frozenset({"value"}),
        likely_local_dynamic_attributes=frozenset({"value"}),
    )

    rename_map = build_rename_map(index=index)

    assert "value" in rename_map.mapping
    assert "value" in rename_map.likely_local_symbols
