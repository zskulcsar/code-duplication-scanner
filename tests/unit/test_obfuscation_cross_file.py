# Copyright 2026 Zsolt Kulcsar and Contributors. Licensed under the EUPL-1.2 or later
"""Cross-file obfuscation tests for global mapping consistency."""

from pathlib import Path

from obfuscation import analyze_project, build_rename_map, rewrite_source


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_ph6_obf_301_cross_file_global_map_is_consistent(tmp_path: Path) -> None:
    project_root = tmp_path / "proj"
    first = project_root / "module_a.py"
    second = project_root / "module_b.py"
    _write_file(
        first, "class Greeter:\n    def hello(self, name):\n        return name\n"
    )
    _write_file(
        second,
        "from module_a import Greeter\n\n"
        "def run(value):\n"
        "    g = Greeter()\n"
        "    return g.hello(value)\n",
    )

    files = [first, second]
    index = analyze_project(project_root=project_root, files=files)
    rename_map = build_rename_map(index=index)

    transformed_first = rewrite_source(
        source=first.read_text(encoding="utf-8"),
        rename_map=rename_map,
        index=index,
    ).transformed_source
    transformed_second = rewrite_source(
        source=second.read_text(encoding="utf-8"),
        rename_map=rename_map,
        index=index,
    ).transformed_source

    class_name = rename_map.mapping["Greeter"]
    method_name = rename_map.mapping["hello"]
    assert f"class {class_name}" in transformed_first
    assert f"from module_a import {class_name}" in transformed_second
    assert f".{method_name}(" in transformed_second


def test_ph6_obf_302_cross_file_external_attribute_remains_unchanged(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "proj"
    source = project_root / "module_a.py"
    _write_file(
        source,
        "import os\n\n"
        "class Box:\n"
        "    def __init__(self):\n"
        "        self.path = 'x'\n\n"
        "def read():\n"
        "    return os.path\n",
    )

    index = analyze_project(project_root=project_root, files=[source])
    rename_map = build_rename_map(index=index)
    transformed = rewrite_source(
        source=source.read_text(encoding="utf-8"),
        rename_map=rename_map,
        index=index,
    ).transformed_source

    assert "import os as " in transformed
    assert ".path" in transformed


def test_ph6_obf_303_cross_file_module_qualified_class_name_is_renamed(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "proj"
    source_a = project_root / "module_a.py"
    source_b = project_root / "module_b.py"
    _write_file(source_a, "class Greeter:\n    pass\n")
    _write_file(
        source_b,
        "import module_a\n\ndef run():\n    return module_a.Greeter()\n",
    )

    files = [source_a, source_b]
    index = analyze_project(project_root=project_root, files=files)
    rename_map = build_rename_map(index=index)
    transformed = rewrite_source(
        source=source_b.read_text(encoding="utf-8"),
        rename_map=rename_map,
        index=index,
    ).transformed_source

    class_name = rename_map.mapping["Greeter"]
    assert "import module_a as " in transformed
    assert f".{class_name}()" in transformed
