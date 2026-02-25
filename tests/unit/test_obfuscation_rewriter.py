# Copyright 2026 Zsolt Kulcsar and Contributors. Licensed under the EUPL-1.2 or later
"""Unit tests for obfuscation source rewriter."""

import ast

from obfuscation import ProjectIndex, RenameMap, rewrite_source


def test_ph6_obf_201_rewriter_renames_project_symbols_and_keeps_external_calls() -> (
    None
):
    source = (
        "import os\n"
        "\n"
        "class Greeter:\n"
        "    def hello(self, name):\n"
        "        return name\n"
        "\n"
        "def run(value):\n"
        "    local = value\n"
        "    return Greeter().hello(local) + os.getcwd()\n"
    )
    rename_map = RenameMap(
        mapping={
            "Greeter": "a",
            "hello": "b",
            "run": "c",
            "value": "d",
            "local": "e",
            "name": "f",
        },
        likely_local_symbols=frozenset(),
    )
    index = ProjectIndex(
        rename_candidates=frozenset(rename_map.mapping.keys()),
        external_symbols=frozenset({"os"}),
        project_class_names=frozenset({"Greeter"}),
        project_attributes=frozenset({"hello"}),
        likely_local_dynamic_attributes=frozenset(),
    )

    result = rewrite_source(source=source, rename_map=rename_map, index=index)

    assert "class a:" in result.transformed_source
    assert "def c(d):" in result.transformed_source
    assert "import os as " in result.transformed_source
    assert ".getcwd()" in result.transformed_source
    assert result.symbols_renamed > 0


def test_ph6_obf_202_rewriter_keeps_plain_string_text_unchanged() -> None:
    source = 'text = "keep me"\nname = "x"\n'
    rename_map = RenameMap(mapping={"name": "n"}, likely_local_symbols=frozenset())
    index = ProjectIndex(
        rename_candidates=frozenset({"name"}),
        external_symbols=frozenset(),
        project_class_names=frozenset(),
        project_attributes=frozenset(),
        likely_local_dynamic_attributes=frozenset(),
    )

    result = rewrite_source(source=source, rename_map=rename_map, index=index)

    module = ast.parse(result.transformed_source)
    string_values = {
        node.value
        for node in ast.walk(module)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert "keep me" in string_values


def test_ph6_obf_203_rewriter_updates_fstring_expressions_only() -> None:
    source = 'user = "alice"\ntext = f"hello {user}"\n'
    rename_map = RenameMap(mapping={"user": "a"}, likely_local_symbols=frozenset())
    index = ProjectIndex(
        rename_candidates=frozenset({"user"}),
        external_symbols=frozenset(),
        project_class_names=frozenset(),
        project_attributes=frozenset(),
        likely_local_dynamic_attributes=frozenset(),
    )

    result = rewrite_source(source=source, rename_map=rename_map, index=index)

    assert "hello {a}" in result.transformed_source


def test_ph6_obf_204_rewriter_never_renames_dunder_methods() -> None:
    source = "class Box:\n    def __init__(self):\n        self.value = 1\n"
    rename_map = RenameMap(
        mapping={"Box": "a", "__init__": "b", "value": "c"},
        likely_local_symbols=frozenset(),
    )
    index = ProjectIndex(
        rename_candidates=frozenset({"Box", "value"}),
        external_symbols=frozenset(),
        project_class_names=frozenset({"Box"}),
        project_attributes=frozenset({"value"}),
        likely_local_dynamic_attributes=frozenset(),
    )

    result = rewrite_source(source=source, rename_map=rename_map, index=index)

    assert "def __init__(self):" in result.transformed_source


def test_ph6_obf_205_rewriter_rewrites_dynamic_attr_name_for_likely_local_obj() -> None:
    source = (
        "class Box:\n"
        "    def __init__(self):\n"
        "        self.value = 1\n"
        "\n"
        "def read(obj):\n"
        '    return getattr(obj, "value")\n'
    )
    rename_map = RenameMap(
        mapping={"Box": "a", "read": "b", "obj": "c", "value": "d"},
        likely_local_symbols=frozenset({"value"}),
    )
    index = ProjectIndex(
        rename_candidates=frozenset(rename_map.mapping.keys()),
        external_symbols=frozenset(),
        project_class_names=frozenset({"Box"}),
        project_attributes=frozenset({"value"}),
        likely_local_dynamic_attributes=frozenset({"value"}),
    )

    result = rewrite_source(source=source, rename_map=rename_map, index=index)

    assert (
        "getattr(c, 'd')" in result.transformed_source
        or 'getattr(c, "d")' in result.transformed_source
    )
    assert result.dynamic_name_rewrites == 1
    assert result.likely_local_rewrites >= 1


def test_ph6_obf_206_rewriter_keeps_dynamic_attr_name_for_external_obj() -> None:
    source = 'import os\n\ndef read():\n    return getattr(os, "path")\n'
    rename_map = RenameMap(
        mapping={"read": "a", "path": "b"},
        likely_local_symbols=frozenset({"path"}),
    )
    index = ProjectIndex(
        rename_candidates=frozenset({"read", "path"}),
        external_symbols=frozenset({"os"}),
        project_class_names=frozenset(),
        project_attributes=frozenset({"path"}),
        likely_local_dynamic_attributes=frozenset({"path"}),
    )

    result = rewrite_source(source=source, rename_map=rename_map, index=index)

    module = ast.parse(result.transformed_source)
    calls = [
        node
        for node in ast.walk(module)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "getattr"
    ]
    assert len(calls) == 1
    assert len(calls[0].args) >= 2
    assert isinstance(calls[0].args[1], ast.Constant)
    assert calls[0].args[1].value == "path"


def test_ph6_obf_207_rewriter_output_is_parseable() -> None:
    source = "def run(value):\n    return value + 1\n"
    rename_map = RenameMap(
        mapping={"run": "a", "value": "b"}, likely_local_symbols=frozenset()
    )
    index = ProjectIndex(
        rename_candidates=frozenset({"run", "value"}),
        external_symbols=frozenset(),
        project_class_names=frozenset(),
        project_attributes=frozenset(),
        likely_local_dynamic_attributes=frozenset(),
    )

    result = rewrite_source(source=source, rename_map=rename_map, index=index)

    ast.parse(result.transformed_source)


def test_ph6_obf_208_rewriter_normalizes_imports_to_as_aliases() -> None:
    source = "import os\n\ndef run():\n    return os.getcwd()\n"
    rename_map = RenameMap(mapping={"run": "a"}, likely_local_symbols=frozenset())
    index = ProjectIndex(
        rename_candidates=frozenset({"run"}),
        external_symbols=frozenset({"os"}),
        project_class_names=frozenset(),
        project_attributes=frozenset(),
        likely_local_dynamic_attributes=frozenset(),
    )

    result = rewrite_source(source=source, rename_map=rename_map, index=index)

    assert "import os as " in result.transformed_source
    assert ".getcwd()" in result.transformed_source
    assert "os.getcwd()" not in result.transformed_source


def test_ph6_obf_209_rewriter_updates_arg_annotations_after_symbol_renames() -> None:
    source = (
        "import ast\n"
        "\n"
        "class _NodeContext:\n"
        "    pass\n"
        "\n"
        "def run(node: ast.stmt, ctx: _NodeContext | None = None) -> ast.AST:\n"
        "    return node\n"
    )
    rename_map = RenameMap(
        mapping={"_NodeContext": "a", "run": "b"},
        likely_local_symbols=frozenset(),
    )
    index = ProjectIndex(
        rename_candidates=frozenset({"_NodeContext", "run"}),
        external_symbols=frozenset({"ast"}),
        project_class_names=frozenset({"_NodeContext"}),
        project_attributes=frozenset(),
        likely_local_dynamic_attributes=frozenset(),
    )

    result = rewrite_source(source=source, rename_map=rename_map, index=index)

    assert "import ast as " in result.transformed_source
    assert "ctx: a | None" in result.transformed_source
    assert "->" in result.transformed_source
    assert "ast.stmt" not in result.transformed_source


def test_ph6_obf_210_rewriter_renames_keyword_args_for_local_calls() -> None:
    source = (
        "def run(argv):\n"
        "    return argv\n"
        "\n"
        "def main(args):\n"
        "    return run(argv=args)\n"
    )
    rename_map = RenameMap(
        mapping={"run": "a", "main": "b", "argv": "c", "args": "d"},
        likely_local_symbols=frozenset(),
    )
    index = ProjectIndex(
        rename_candidates=frozenset({"run", "main", "argv", "args"}),
        external_symbols=frozenset(),
        project_class_names=frozenset(),
        project_attributes=frozenset(),
        likely_local_dynamic_attributes=frozenset(),
    )

    result = rewrite_source(source=source, rename_map=rename_map, index=index)

    assert "def a(c):" in result.transformed_source
    assert "def b(d):" in result.transformed_source
    assert "a(c=d)" in result.transformed_source


def test_ph6_obf_211_rewriter_keeps_keyword_args_for_external_calls() -> None:
    source = (
        "import argparse\n\ndef main():\n    return argparse.ArgumentParser(prog='x')\n"
    )
    rename_map = RenameMap(
        mapping={"main": "a", "prog": "b"},
        likely_local_symbols=frozenset(),
    )
    index = ProjectIndex(
        rename_candidates=frozenset({"main", "prog"}),
        external_symbols=frozenset({"argparse"}),
        project_class_names=frozenset(),
        project_attributes=frozenset(),
        likely_local_dynamic_attributes=frozenset(),
    )

    result = rewrite_source(source=source, rename_map=rename_map, index=index)

    assert "import argparse as " in result.transformed_source
    assert "ArgumentParser(prog='x')" in result.transformed_source


def test_ph6_obf_212_rewriter_keeps_keyword_args_for_external_method_calls() -> None:
    source = (
        "import argparse\n"
        "\n"
        "def main():\n"
        "    parser = argparse.ArgumentParser()\n"
        "    return parser.add_argument('--path', required=False)\n"
    )
    rename_map = RenameMap(
        mapping={"main": "a", "parser": "b", "required": "c"},
        likely_local_symbols=frozenset(),
    )
    index = ProjectIndex(
        rename_candidates=frozenset({"main", "parser", "required"}),
        external_symbols=frozenset({"argparse"}),
        project_class_names=frozenset(),
        project_attributes=frozenset(),
        likely_local_dynamic_attributes=frozenset(),
    )

    result = rewrite_source(source=source, rename_map=rename_map, index=index)

    assert ".add_argument(" in result.transformed_source
    assert "required=False" in result.transformed_source


def test_ph6_obf_213_rewriter_renames_keyword_args_for_local_method_calls() -> None:
    source = (
        "class Store:\n"
        "    def load(self, run_id):\n"
        "        return run_id\n"
        "\n"
        "def main(db):\n"
        "    return db.load(run_id=1)\n"
    )
    rename_map = RenameMap(
        mapping={"Store": "a", "load": "b", "run_id": "c", "main": "d", "db": "e"},
        likely_local_symbols=frozenset(),
    )
    index = ProjectIndex(
        rename_candidates=frozenset({"Store", "load", "run_id", "main", "db"}),
        external_symbols=frozenset(),
        project_class_names=frozenset({"Store"}),
        project_attributes=frozenset({"load"}),
        likely_local_dynamic_attributes=frozenset(),
    )

    result = rewrite_source(source=source, rename_map=rename_map, index=index)

    assert "def b(self, c):" in result.transformed_source
    assert "return e.b(c=1)" in result.transformed_source


def test_ph6_obf_214_rewriter_renames_dataclass_field_attribute_usage() -> None:
    source = (
        "from dataclasses import dataclass\n"
        "\n"
        "@dataclass\n"
        "class Item:\n"
        "    kind: str\n"
        "\n"
        "def read(item):\n"
        "    return item.kind\n"
    )
    rename_map = RenameMap(
        mapping={"Item": "a", "kind": "b", "read": "c", "item": "d"},
        likely_local_symbols=frozenset(),
    )
    index = ProjectIndex(
        rename_candidates=frozenset({"Item", "kind", "read", "item"}),
        external_symbols=frozenset(),
        project_class_names=frozenset({"Item"}),
        project_attributes=frozenset({"kind"}),
        likely_local_dynamic_attributes=frozenset(),
    )

    result = rewrite_source(source=source, rename_map=rename_map, index=index)

    assert "class a:" in result.transformed_source
    assert "b: str" in result.transformed_source
    assert "return d.b" in result.transformed_source


def test_ph6_obf_215_rewriter_keeps_colliding_attrs_on_external_parse_result() -> None:
    source = (
        "import argparse\n"
        "\n"
        "class Config:\n"
        "    db_path: str\n"
        "\n"
        "def run():\n"
        "    parser = argparse.ArgumentParser()\n"
        "    args = parser.parse_args([])\n"
        "    return args.db_path\n"
    )
    rename_map = RenameMap(
        mapping={
            "Config": "a",
            "db_path": "b",
            "run": "c",
            "parser": "d",
            "args": "e",
        },
        likely_local_symbols=frozenset(),
    )
    index = ProjectIndex(
        rename_candidates=frozenset({"Config", "db_path", "run", "parser", "args"}),
        external_symbols=frozenset({"argparse"}),
        project_class_names=frozenset({"Config"}),
        project_attributes=frozenset({"db_path"}),
        likely_local_dynamic_attributes=frozenset(),
    )

    result = rewrite_source(source=source, rename_map=rename_map, index=index)

    assert ".parse_args(" in result.transformed_source
    assert ".db_path" in result.transformed_source


def test_ph6_obf_216_rewriter_keeps_namespace_param_attrs_from_annotation() -> None:
    source = (
        "import argparse\n"
        "\n"
        "class Config:\n"
        "    run_id: int\n"
        "\n"
        "def use(parsed: argparse.Namespace):\n"
        "    return parsed.run_id\n"
    )
    rename_map = RenameMap(
        mapping={"Config": "a", "run_id": "b", "use": "c", "parsed": "d"},
        likely_local_symbols=frozenset(),
    )
    index = ProjectIndex(
        rename_candidates=frozenset({"Config", "run_id", "use", "parsed"}),
        external_symbols=frozenset({"argparse"}),
        project_class_names=frozenset({"Config"}),
        project_attributes=frozenset({"run_id"}),
        likely_local_dynamic_attributes=frozenset(),
    )

    result = rewrite_source(source=source, rename_map=rename_map, index=index)

    assert "def c(d:" in result.transformed_source
    assert ".run_id" in result.transformed_source


def test_ph6_obf_217_rewriter_renames_method_call_after_local_factory_assignment() -> (
    None
):
    source = (
        "class Store:\n"
        "    def load_records_for_run(self, run_id):\n"
        "        return run_id\n"
        "\n"
        "def make_store():\n"
        "    return Store()\n"
        "\n"
        "def main(run_id):\n"
        "    store = make_store()\n"
        "    return store.load_records_for_run(run_id=run_id)\n"
    )
    rename_map = RenameMap(
        mapping={
            "Store": "a",
            "load_records_for_run": "b",
            "make_store": "c",
            "main": "d",
            "run_id": "e",
            "store": "f",
        },
        likely_local_symbols=frozenset(),
    )
    index = ProjectIndex(
        rename_candidates=frozenset(rename_map.mapping.keys()),
        external_symbols=frozenset(),
        project_class_names=frozenset({"Store"}),
        project_attributes=frozenset({"load_records_for_run"}),
        likely_local_dynamic_attributes=frozenset(),
    )

    result = rewrite_source(source=source, rename_map=rename_map, index=index)

    assert "def b(self, e):" in result.transformed_source
    assert "return f.b(e=e)" in result.transformed_source


def test_ph6_obf_218_rewriter_renames_attrs_in_list_comprehension_targets() -> None:
    source = (
        "class Row:\n"
        "    kind: str\n"
        "\n"
        "def collect(rows: list[Row]):\n"
        "    return [r.kind for r in rows if r.kind]\n"
    )
    rename_map = RenameMap(
        mapping={"Row": "a", "kind": "b", "collect": "c", "rows": "d", "r": "e"},
        likely_local_symbols=frozenset(),
    )
    index = ProjectIndex(
        rename_candidates=frozenset({"Row", "kind", "collect", "rows", "r"}),
        external_symbols=frozenset(),
        project_class_names=frozenset({"Row"}),
        project_attributes=frozenset({"kind"}),
        likely_local_dynamic_attributes=frozenset(),
    )

    result = rewrite_source(source=source, rename_map=rename_map, index=index)

    assert "def c(d: list[a]):" in result.transformed_source
    assert "[e.b for e in d if e.b]" in result.transformed_source


def test_ph6_obf_219_rewriter_renames_attrs_in_for_loop_targets() -> None:
    source = (
        "class Row:\n"
        "    kind: str\n"
        "\n"
        "def collect(rows: list[Row]):\n"
        "    values = []\n"
        "    for row in rows:\n"
        "        values.append(row.kind)\n"
        "    return values\n"
    )
    rename_map = RenameMap(
        mapping={
            "Row": "a",
            "kind": "b",
            "collect": "c",
            "rows": "d",
            "values": "e",
            "row": "f",
        },
        likely_local_symbols=frozenset(),
    )
    index = ProjectIndex(
        rename_candidates=frozenset(
            {"Row", "kind", "collect", "rows", "values", "row"}
        ),
        external_symbols=frozenset(),
        project_class_names=frozenset({"Row"}),
        project_attributes=frozenset({"kind"}),
        likely_local_dynamic_attributes=frozenset(),
    )

    result = rewrite_source(source=source, rename_map=rename_map, index=index)

    assert "for f in d:" in result.transformed_source
    assert "e.append(f.b)" in result.transformed_source


def test_ph6_obf_220_rewriter_keeps_builtin_keyword_names() -> None:
    source = "def main(items):\n    return sorted(items, key=lambda x: x)\n"
    rename_map = RenameMap(
        mapping={"main": "a", "items": "b", "key": "c", "x": "d"},
        likely_local_symbols=frozenset(),
    )
    index = ProjectIndex(
        rename_candidates=frozenset({"main", "items", "key", "x"}),
        external_symbols=frozenset(),
        project_class_names=frozenset(),
        project_attributes=frozenset(),
        likely_local_dynamic_attributes=frozenset(),
    )

    result = rewrite_source(source=source, rename_map=rename_map, index=index)

    assert "sorted(b, key=lambda d: d)" in result.transformed_source


def test_ph6_obf_221_rewriter_renames_lambda_param_attributes() -> None:
    source = (
        "class Row:\n"
        "    record_id: int\n"
        "\n"
        "def collect(rows: list[Row]):\n"
        "    return sorted(rows, key=lambda item: item.record_id)\n"
    )
    rename_map = RenameMap(
        mapping={
            "Row": "a",
            "record_id": "b",
            "collect": "c",
            "rows": "d",
            "item": "e",
        },
        likely_local_symbols=frozenset(),
    )
    index = ProjectIndex(
        rename_candidates=frozenset({"Row", "record_id", "collect", "rows", "item"}),
        external_symbols=frozenset(),
        project_class_names=frozenset({"Row"}),
        project_attributes=frozenset({"record_id"}),
        likely_local_dynamic_attributes=frozenset(),
    )

    result = rewrite_source(source=source, rename_map=rename_map, index=index)

    assert "def c(d: list[a]):" in result.transformed_source
    assert "sorted(d, key=lambda e: e.b)" in result.transformed_source


def test_ph6_obf_222_rewriter_tracks_sorted_result_ownership_for_loop_attrs() -> None:
    source = (
        "class Row:\n"
        "    md5sum: str\n"
        "\n"
        "def collect(rows: list[Row]):\n"
        "    ordered = sorted(rows, key=lambda row: row.md5sum)\n"
        "    return [item.md5sum for item in ordered]\n"
    )
    rename_map = RenameMap(
        mapping={
            "Row": "a",
            "md5sum": "b",
            "collect": "c",
            "rows": "d",
            "ordered": "e",
            "row": "f",
            "item": "g",
        },
        likely_local_symbols=frozenset(),
    )
    index = ProjectIndex(
        rename_candidates=frozenset(
            {"Row", "md5sum", "collect", "rows", "ordered", "row", "item"}
        ),
        external_symbols=frozenset(),
        project_class_names=frozenset({"Row"}),
        project_attributes=frozenset({"md5sum"}),
        likely_local_dynamic_attributes=frozenset(),
    )

    result = rewrite_source(source=source, rename_map=rename_map, index=index)

    assert "ordered" not in result.transformed_source
    assert "sorted(d, key=lambda f: f.b)" in result.transformed_source
    assert "[g.b for g in e]" in result.transformed_source


def test_ph6_obf_223_rewriter_tracks_enumerate_and_annotated_list_ownership() -> None:
    source = (
        "class Edge:\n"
        "    left_id: int\n"
        "\n"
        "def build(edges: list[Edge]):\n"
        "    tracked: list[Edge] = []\n"
        "    for idx, edge in enumerate(edges):\n"
        "        tracked.append(edge.left_id)\n"
        "    return tracked\n"
    )
    rename_map = RenameMap(
        mapping={
            "Edge": "a",
            "left_id": "b",
            "build": "c",
            "edges": "d",
            "tracked": "e",
            "idx": "f",
            "edge": "g",
        },
        likely_local_symbols=frozenset(),
    )
    index = ProjectIndex(
        rename_candidates=frozenset(
            {"Edge", "left_id", "build", "edges", "tracked", "idx", "edge"}
        ),
        external_symbols=frozenset(),
        project_class_names=frozenset({"Edge"}),
        project_attributes=frozenset({"left_id"}),
        likely_local_dynamic_attributes=frozenset(),
    )

    result = rewrite_source(source=source, rename_map=rename_map, index=index)

    assert "for f, g in enumerate(d):" in result.transformed_source
    assert "e.append(g.b)" in result.transformed_source


def test_ph6_obf_224_rewriter_tracks_slice_iterable_ownership() -> None:
    source = (
        "class Row:\n"
        "    md5sum: str\n"
        "\n"
        "def collect(rows: list[Row]):\n"
        "    out = []\n"
        "    for row in rows[1:]:\n"
        "        out.append(row.md5sum)\n"
        "    return out\n"
    )
    rename_map = RenameMap(
        mapping={
            "Row": "a",
            "md5sum": "b",
            "collect": "c",
            "rows": "d",
            "out": "e",
            "row": "f",
        },
        likely_local_symbols=frozenset(),
    )
    index = ProjectIndex(
        rename_candidates=frozenset({"Row", "md5sum", "collect", "rows", "out", "row"}),
        external_symbols=frozenset(),
        project_class_names=frozenset({"Row"}),
        project_attributes=frozenset({"md5sum"}),
        likely_local_dynamic_attributes=frozenset(),
    )

    result = rewrite_source(source=source, rename_map=rename_map, index=index)

    assert "for f in d[1:]" in result.transformed_source
    assert "e.append(f.b)" in result.transformed_source


def test_ph6_obf_225_rewriter_tracks_project_method_call_result_ownership() -> None:
    source = (
        "class Result:\n"
        "    exact_groups: list[str]\n"
        "\n"
        "class Checker:\n"
        "    def check(self) -> Result:\n"
        "        return Result()\n"
        "\n"
        "def run():\n"
        "    checker = Checker()\n"
        "    result = checker.check()\n"
        "    return result.exact_groups\n"
    )
    rename_map = RenameMap(
        mapping={
            "Result": "a",
            "exact_groups": "b",
            "Checker": "c",
            "check": "d",
            "run": "e",
            "checker": "f",
            "result": "g",
        },
        likely_local_symbols=frozenset(),
    )
    index = ProjectIndex(
        rename_candidates=frozenset(
            {"Result", "exact_groups", "Checker", "check", "run", "checker", "result"}
        ),
        external_symbols=frozenset(),
        project_class_names=frozenset({"Result", "Checker"}),
        project_attributes=frozenset({"exact_groups", "check"}),
        likely_local_dynamic_attributes=frozenset(),
    )

    result = rewrite_source(source=source, rename_map=rename_map, index=index)

    assert "g = f.d()" in result.transformed_source
    assert "return g.b" in result.transformed_source


def test_ph6_obf_226_rewriter_tracks_iterable_ownership_from_project_attributes() -> (
    None
):
    source = (
        "class Member:\n"
        "    group_id: int\n"
        "\n"
        "class Group:\n"
        "    members: list[Member]\n"
        "\n"
        "def run(groups: list[Group]):\n"
        "    for group in groups:\n"
        "        for member in group.members:\n"
        "            print(member.group_id)\n"
    )
    rename_map = RenameMap(
        mapping={
            "Member": "a",
            "group_id": "b",
            "Group": "c",
            "members": "d",
            "run": "e",
            "groups": "f",
            "group": "g",
            "member": "h",
        },
        likely_local_symbols=frozenset(),
    )
    index = ProjectIndex(
        rename_candidates=frozenset(
            {
                "Member",
                "group_id",
                "Group",
                "members",
                "run",
                "groups",
                "group",
                "member",
            }
        ),
        external_symbols=frozenset(),
        project_class_names=frozenset({"Member", "Group"}),
        project_attributes=frozenset({"group_id", "members"}),
        likely_local_dynamic_attributes=frozenset(),
    )

    result = rewrite_source(source=source, rename_map=rename_map, index=index)

    assert "for g in f:" in result.transformed_source
    assert "for h in g.d:" in result.transformed_source
    assert "print(h.b)" in result.transformed_source
