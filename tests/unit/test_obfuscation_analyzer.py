# Copyright 2026 Zsolt Kulcsar and Contributors. Licensed under the EUPL-1.2 or later
"""Unit tests for obfuscation analyzer behavior."""

from pathlib import Path

from obfuscation import analyze_project


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_ph6_obf_001_analyzer_indexes_symbols_and_externals(tmp_path: Path) -> None:
    project_root = tmp_path / "proj"
    source = project_root / "module_a.py"
    _write_file(
        source,
        """
import os
from math import sqrt

class Greeter:
    def __init__(self, name):
        self.name = name

    def say(self, msg):
        local_text = msg
        return f"hello {self.name} {local_text}"


def helper(value):
    total = value + 1
    return total
""".strip()
        + "\n",
    )

    index = analyze_project(project_root=project_root, files=[source])

    assert "Greeter" in index.rename_candidates
    assert "say" in index.rename_candidates
    assert "helper" in index.rename_candidates
    assert "value" in index.rename_candidates
    assert "local_text" in index.rename_candidates
    assert "name" in index.project_attributes
    assert "__init__" not in index.rename_candidates
    assert "os" in index.external_symbols
    assert "sqrt" in index.external_symbols


def test_ph6_obf_002_analyzer_treats_in_project_import_as_local(tmp_path: Path) -> None:
    project_root = tmp_path / "proj"
    source_a = project_root / "module_a.py"
    source_b = project_root / "module_b.py"
    _write_file(source_b, "class LocalType:\n    pass\n")
    _write_file(source_a, "from module_b import LocalType\nvalue = LocalType()\n")

    index = analyze_project(project_root=project_root, files=[source_a, source_b])

    assert "LocalType" in index.rename_candidates
    assert "LocalType" not in index.external_symbols


def test_ph6_obf_003_analyzer_marks_likely_local_dynamic_attribute(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "proj"
    source = project_root / "module_a.py"
    _write_file(
        source,
        """
class Box:
    def __init__(self):
        self.value = 1


def read_dynamic(obj):
    return getattr(obj, "value")
""".strip()
        + "\n",
    )

    index = analyze_project(project_root=project_root, files=[source])

    assert "value" in index.project_attributes
    assert "value" in index.likely_local_dynamic_attributes


def test_ph6_obf_004_analyzer_treats_src_layout_imports_as_local(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "proj"
    source_a = project_root / "src" / "obfuscation" / "analyzer.py"
    source_b = project_root / "src" / "obfuscation" / "__init__.py"
    _write_file(source_a, "class ProjectIndex:\n    pass\n")
    _write_file(
        source_b,
        "from obfuscation.analyzer import ProjectIndex\n__all__ = ['ProjectIndex']\n",
    )

    index = analyze_project(project_root=project_root, files=[source_a, source_b])

    assert "ProjectIndex" in index.rename_candidates
    assert "ProjectIndex" not in index.external_symbols


def test_ph6_obf_005_analyzer_tracks_class_field_names_as_project_attributes(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "proj"
    source = project_root / "model.py"
    _write_file(
        source,
        "from dataclasses import dataclass\n\n@dataclass\nclass Item:\n    kind: str\n",
    )

    index = analyze_project(project_root=project_root, files=[source])

    assert "kind" in index.rename_candidates
    assert "kind" in index.project_attributes
