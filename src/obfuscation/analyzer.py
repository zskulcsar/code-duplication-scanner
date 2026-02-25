# Copyright 2026 Zsolt Kulcsar and Contributors. Licensed under the EUPL-1.2 or later
"""Analyze Python sources to build project obfuscation symbol index."""

import ast
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_DYNAMIC_CALL_NAMES: set[str] = {"getattr", "setattr", "hasattr"}


@dataclass(frozen=True)
class ProjectIndex:
    """Represent indexed symbols and ownership hints for obfuscation.

    Args:
        rename_candidates: Symbols eligible for renaming.
        external_symbols: Names imported from modules outside the project.
        project_class_names: Class names declared in project source files.
        project_attributes: Attribute names declared in project classes.
        likely_local_dynamic_attributes: Dynamic attribute names considered likely-local.
    """

    rename_candidates: frozenset[str]
    external_symbols: frozenset[str]
    project_class_names: frozenset[str]
    project_attributes: frozenset[str]
    likely_local_dynamic_attributes: frozenset[str]


class _SymbolCollector(ast.NodeVisitor):
    """Collect candidate and ownership symbols from one AST module."""

    def __init__(self, local_root_modules: set[str]) -> None:
        """Initialize collector state.

        Args:
            local_root_modules: Known top-level module names in the project.
        """
        self._local_root_modules = local_root_modules
        self.rename_candidates: set[str] = set()
        self.external_symbols: set[str] = set()
        self.project_class_names: set[str] = set()
        self.project_attributes: set[str] = set()
        self.likely_local_dynamic_attributes: set[str] = set()
        self._in_class: bool = False

    def visit_Import(self, node: ast.Import) -> None:
        """Visit import statement.

        Args:
            node: Import node.
        """
        for alias in node.names:
            exposed_name = alias.asname or alias.name.split(".")[0]
            root_name = alias.name.split(".")[0]
            if root_name not in self._local_root_modules:
                self.external_symbols.add(exposed_name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Visit from-import statement.

        Args:
            node: ImportFrom node.
        """
        if node.module is None:
            self.generic_visit(node)
            return
        root_name = node.module.split(".")[0]
        is_local = root_name in self._local_root_modules
        for alias in node.names:
            if alias.name == "*":
                continue
            exposed_name = alias.asname or alias.name
            if not is_local:
                self.external_symbols.add(exposed_name)
            else:
                self._add_candidate(exposed_name)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class definition.

        Args:
            node: ClassDef node.
        """
        self.project_class_names.add(node.name)
        self._add_candidate(node.name)
        previous_in_class = self._in_class
        self._in_class = True
        self.generic_visit(node)
        self._in_class = previous_in_class

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definition.

        Args:
            node: FunctionDef node.
        """
        self._add_candidate(node.name)
        if self._in_class and not _is_dunder(node.name):
            self.project_attributes.add(node.name)
        self._collect_arguments(node.args)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definition.

        Args:
            node: AsyncFunctionDef node.
        """
        self._add_candidate(node.name)
        if self._in_class and not _is_dunder(node.name):
            self.project_attributes.add(node.name)
        self._collect_arguments(node.args)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        """Visit name node.

        Args:
            node: Name node.
        """
        if isinstance(node.ctx, ast.Store):
            self._add_candidate(node.id)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        """Visit assignment node.

        Args:
            node: Assign node.
        """
        for target in node.targets:
            self._collect_attribute_target(target)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """Visit annotated assignment node.

        Args:
            node: AnnAssign node.
        """
        self._collect_attribute_target(node.target)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Visit call node to capture dynamic-attribute patterns.

        Args:
            node: Call node.
        """
        call_name = _resolve_call_name(node.func)
        if call_name in _DYNAMIC_CALL_NAMES and len(node.args) >= 2:
            object_arg = node.args[0]
            name_arg = node.args[1]
            if isinstance(name_arg, ast.Constant) and isinstance(name_arg.value, str):
                attr_name = name_arg.value
                if attr_name in self.project_attributes and isinstance(
                    object_arg, ast.Name
                ):
                    if (
                        object_arg.id != "self"
                        and object_arg.id not in self.external_symbols
                    ):
                        self.likely_local_dynamic_attributes.add(attr_name)
        self.generic_visit(node)

    def _collect_arguments(self, node: ast.arguments) -> None:
        """Collect rename candidates from function arguments.

        Args:
            node: Function arguments node.
        """
        for arg in list(node.posonlyargs) + list(node.args) + list(node.kwonlyargs):
            self._add_candidate(arg.arg)
        if node.vararg is not None:
            self._add_candidate(node.vararg.arg)
        if node.kwarg is not None:
            self._add_candidate(node.kwarg.arg)

    def _collect_attribute_target(self, target: ast.expr) -> None:
        """Collect project attribute declarations from assignment targets.

        Args:
            target: Assignment target expression.
        """
        if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
            if target.value.id == "self" and not _is_dunder(target.attr):
                self.project_attributes.add(target.attr)
        if isinstance(target, ast.Name):
            if self._in_class and not _is_dunder(target.id):
                self.project_attributes.add(target.id)
            self._add_candidate(target.id)

    def _add_candidate(self, name: str) -> None:
        """Add rename candidate when allowed.

        Args:
            name: Symbol name to add.
        """
        if not _is_renameable(name):
            return
        self.rename_candidates.add(name)


def analyze_project(project_root: Path, files: list[Path]) -> ProjectIndex:
    """Analyze project files and build an obfuscation symbol index.

    Args:
        project_root: Root path of analyzed project.
        files: Python files to parse.

    Returns:
        Project symbol index for rename planning.
    """
    local_root_modules = _project_local_root_modules(
        project_root=project_root, files=files
    )
    rename_candidates: set[str] = set()
    external_symbols: set[str] = set()
    project_class_names: set[str] = set()
    project_attributes: set[str] = set()
    likely_local_dynamic_attributes: set[str] = set()

    for source_file in sorted(files):
        try:
            source = source_file.read_text(encoding="utf-8")
            module = ast.parse(source)
        except (OSError, UnicodeDecodeError, SyntaxError) as exc:
            logger.warning(
                "Skipping file during analysis due to parse/read failure",
                extra={"path": str(source_file), "error": str(exc)},
            )
            continue

        collector = _SymbolCollector(local_root_modules=local_root_modules)
        collector.visit(module)
        rename_candidates.update(collector.rename_candidates)
        external_symbols.update(collector.external_symbols)
        project_class_names.update(collector.project_class_names)
        project_attributes.update(collector.project_attributes)
        likely_local_dynamic_attributes.update(
            collector.likely_local_dynamic_attributes
        )

    rename_candidates.difference_update(external_symbols)

    return ProjectIndex(
        rename_candidates=frozenset(rename_candidates),
        external_symbols=frozenset(external_symbols),
        project_class_names=frozenset(project_class_names),
        project_attributes=frozenset(project_attributes),
        likely_local_dynamic_attributes=frozenset(likely_local_dynamic_attributes),
    )


def _project_local_root_modules(project_root: Path, files: list[Path]) -> set[str]:
    """Build top-level module names for project-owned files.

    Args:
        project_root: Project root directory.
        files: Python file paths.

    Returns:
        Set of top-level module names.
    """
    root_modules: set[str] = set()
    for file_path in files:
        try:
            relative = file_path.resolve().relative_to(project_root.resolve())
        except ValueError:
            relative = file_path
        module_parts = list(relative.with_suffix("").parts)
        if module_parts and module_parts[-1] == "__init__":
            module_parts = module_parts[:-1]
        if not module_parts:
            continue
        root_modules.add(module_parts[0])
        if module_parts[0] in {"src", "tests"} and len(module_parts) >= 2:
            root_modules.add(module_parts[1])
    return root_modules


def _is_dunder(name: str) -> bool:
    """Check whether symbol is a dunder name.

    Args:
        name: Symbol name.

    Returns:
        True when name is dunder.
    """
    return name.startswith("__") and name.endswith("__")


def _is_renameable(name: str) -> bool:
    """Check whether symbol can be renamed.

    Args:
        name: Symbol name.

    Returns:
        True when symbol is eligible.
    """
    if not name.isidentifier():
        return False
    if _is_dunder(name):
        return False
    return True


def _resolve_call_name(node: ast.expr) -> str | None:
    """Resolve function name for simple call expressions.

    Args:
        node: Call function expression.

    Returns:
        Resolved function name when direct name is used.
    """
    if isinstance(node, ast.Name):
        return node.id
    return None
