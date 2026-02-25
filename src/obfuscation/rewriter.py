# Copyright 2026 Zsolt Kulcsar and Contributors. Licensed under the EUPL-1.2 or later
"""Rewrite Python source code using obfuscation rename maps."""

import ast
import builtins
import keyword
import logging
from dataclasses import dataclass

from obfuscation.analyzer import ProjectIndex
from obfuscation.mapper import RenameMap

logger = logging.getLogger(__name__)

_DYNAMIC_CALL_NAMES: set[str] = {"getattr", "setattr", "hasattr"}


@dataclass(frozen=True)
class RewriteResult:
    """Store transformed source and rewrite counters.

    Args:
        transformed_source: Rewritten Python source code.
        symbols_renamed: Count of symbol replacements applied.
        likely_local_rewrites: Count of likely-local replacements.
        dynamic_name_rewrites: Count of dynamic attribute string rewrites.
    """

    transformed_source: str
    symbols_renamed: int
    likely_local_rewrites: int
    dynamic_name_rewrites: int


class RewriteError(RuntimeError):
    """Represent rewrite-phase failure."""


class _Renamer(ast.NodeTransformer):
    """Apply rename rules to AST nodes."""

    def __init__(self, rename_map: RenameMap, index: ProjectIndex) -> None:
        """Initialize transformer state.

        Args:
            rename_map: Generated rename map.
            index: Project index metadata.
        """
        self._rename_map = rename_map.mapping
        self._reverse_rename_map: dict[str, str] = {
            value: key for key, value in rename_map.mapping.items()
        }
        self._project_class_names = set(index.project_class_names)
        self._project_attributes = set(index.project_attributes)
        self._mapped_project_class_names = {
            rename_map.mapping.get(name, name) for name in self._project_class_names
        }
        self._mapped_project_attributes = {
            rename_map.mapping.get(name, name) for name in self._project_attributes
        }
        self._external_symbols = set(index.external_symbols)
        self._likely_local_symbols = set(rename_map.likely_local_symbols)
        self._import_aliases: dict[str, str] = {}
        self._external_aliases: set[str] = set()
        self._alias_counter: int = 0
        self._blocked_alias_names: set[str] = set(index.rename_candidates)
        self._blocked_alias_names.update(rename_map.mapping.keys())
        self._blocked_alias_names.update(rename_map.mapping.values())
        self._blocked_alias_names.update(index.external_symbols)
        self._blocked_alias_names.update(keyword.kwlist)
        self._blocked_alias_names.update(dir(builtins))
        self._name_ownership_scopes: list[dict[str, str]] = [{}]
        self.symbols_renamed: int = 0
        self.likely_local_rewrites: int = 0
        self.dynamic_name_rewrites: int = 0

    def visit_Name(self, node: ast.Name) -> ast.AST:
        """Rename identifier names.

        Args:
            node: Name node.

        Returns:
            Updated node.
        """
        replacement = self._mapped_name(node.id)
        if node.id in self._import_aliases:
            replacement = self._import_aliases[node.id]
        if replacement is None:
            return node
        if node.id in self._external_symbols and node.id not in self._import_aliases:
            return node
        if replacement != node.id:
            self.symbols_renamed += 1
            return ast.copy_location(ast.Name(id=replacement, ctx=node.ctx), node)
        return node

    def visit_Import(self, node: ast.Import) -> ast.AST:
        """Normalize plain imports to alias form and track alias rewrites.

        Args:
            node: Import node.

        Returns:
            Updated import node.
        """
        updated_aliases: list[ast.alias] = []
        changed = False
        for alias in node.names:
            if alias.asname is not None:
                updated_aliases.append(alias)
                continue
            if "." in alias.name:
                updated_aliases.append(alias)
                continue
            exposed_name = alias.name
            replacement = self._import_aliases.get(exposed_name)
            if replacement is None:
                replacement = self._next_alias_name()
                self._import_aliases[exposed_name] = replacement
            if exposed_name in self._external_symbols:
                self._external_aliases.add(replacement)
            updated_aliases.append(
                ast.alias(name=alias.name, asname=replacement),
            )
            changed = True
            self.symbols_renamed += 1
        if not changed:
            return node
        return ast.copy_location(ast.Import(names=updated_aliases), node)

    def visit_alias(self, node: ast.alias) -> ast.AST:
        """Rename import aliases for in-project symbol imports.

        Args:
            node: Import alias node.

        Returns:
            Updated node.
        """
        if "." in node.name:
            return node
        replacement = self._mapped_name(node.name)
        if replacement is None or replacement == node.name:
            return node
        self.symbols_renamed += 1
        return ast.copy_location(
            ast.alias(name=replacement, asname=node.asname),
            node,
        )

    def visit_arg(self, node: ast.arg) -> ast.AST:
        """Rename function argument name.

        Args:
            node: Argument node.

        Returns:
            Updated node.
        """
        updated = self.generic_visit(node)
        if not isinstance(updated, ast.arg):
            return updated
        replacement = self._mapped_name(updated.arg)
        if replacement is None or replacement == updated.arg:
            return updated
        self.symbols_renamed += 1
        return ast.copy_location(
            ast.arg(
                arg=replacement,
                annotation=updated.annotation,
                type_comment=updated.type_comment,
            ),
            updated,
        )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        """Rename function definitions.

        Args:
            node: Function node.

        Returns:
            Updated node.
        """
        self._push_scope()
        self._seed_arg_ownership(node.args)
        updated = self.generic_visit(node)
        self._pop_scope()
        if not isinstance(updated, ast.FunctionDef):
            return updated
        replacement = self._mapped_name(updated.name)
        if replacement is None or replacement == updated.name:
            return updated
        self.symbols_renamed += 1
        return ast.copy_location(
            updated.__class__(
                name=replacement,
                args=updated.args,
                body=updated.body,
                decorator_list=updated.decorator_list,
                returns=updated.returns,
                type_comment=updated.type_comment,
            ),
            updated,
        )

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        """Rename async function definitions.

        Args:
            node: Async function node.

        Returns:
            Updated node.
        """
        self._push_scope()
        self._seed_arg_ownership(node.args)
        updated = self.generic_visit(node)
        self._pop_scope()
        if not isinstance(updated, ast.AsyncFunctionDef):
            return updated
        replacement = self._mapped_name(updated.name)
        if replacement is None or replacement == updated.name:
            return updated
        self.symbols_renamed += 1
        return ast.copy_location(
            updated.__class__(
                name=replacement,
                args=updated.args,
                body=updated.body,
                decorator_list=updated.decorator_list,
                returns=updated.returns,
                type_comment=updated.type_comment,
            ),
            updated,
        )

    def visit_Lambda(self, node: ast.Lambda) -> ast.AST:
        """Track lambda argument ownership within lambda scope.

        Args:
            node: Lambda node.

        Returns:
            Updated node.
        """
        self._push_scope()
        self._seed_arg_ownership(node.args)
        updated = self.generic_visit(node)
        self._pop_scope()
        return updated

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        """Rename class definitions.

        Args:
            node: Class node.

        Returns:
            Updated node.
        """
        self._push_scope()
        updated = self.generic_visit(node)
        self._pop_scope()
        if not isinstance(updated, ast.ClassDef):
            return updated
        replacement = self._mapped_name(updated.name)
        if replacement is None or replacement == updated.name:
            return updated
        self.symbols_renamed += 1
        return ast.copy_location(
            updated.__class__(
                name=replacement,
                bases=updated.bases,
                keywords=updated.keywords,
                body=updated.body,
                decorator_list=updated.decorator_list,
            ),
            updated,
        )

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        """Rename attribute access names.

        Args:
            node: Attribute node.

        Returns:
            Updated node.
        """
        updated = self.generic_visit(node)
        if not isinstance(updated, ast.Attribute):
            return updated
        is_project_attribute = updated.attr in self._project_attributes
        is_project_class_name = updated.attr in self._project_class_names
        if not is_project_attribute and not is_project_class_name:
            return updated
        replacement = self._mapped_name(updated.attr)
        if replacement is None or replacement == updated.attr:
            return updated

        ownership = self._attribute_ownership(updated.value)
        if ownership == "external":
            return updated
        if ownership == "likely_local":
            self.likely_local_rewrites += 1

        self.symbols_renamed += 1
        return ast.copy_location(
            ast.Attribute(value=updated.value, attr=replacement, ctx=updated.ctx),
            updated,
        )

    def visit_Call(self, node: ast.Call) -> ast.AST:
        """Rename supported dynamic attribute string arguments.

        Args:
            node: Call node.

        Returns:
            Updated node.
        """
        updated = self.generic_visit(node)
        if not isinstance(updated, ast.Call):
            return updated
        should_rename_keywords = self._should_rename_call_keywords(updated.func)

        renamed_keywords = list(updated.keywords)
        keyword_changed = False
        if should_rename_keywords:
            for index, keyword_arg in enumerate(renamed_keywords):
                if keyword_arg.arg is None:
                    continue
                keyword_replacement = self._mapped_name(keyword_arg.arg)
                if (
                    keyword_replacement is None
                    or keyword_replacement == keyword_arg.arg
                ):
                    continue
                renamed_keywords[index] = ast.keyword(
                    arg=keyword_replacement,
                    value=keyword_arg.value,
                )
                self.symbols_renamed += 1
                keyword_changed = True
            if keyword_changed:
                self.likely_local_rewrites += 1
        if keyword_changed:
            updated = ast.copy_location(
                ast.Call(
                    func=updated.func,
                    args=updated.args,
                    keywords=renamed_keywords,
                ),
                updated,
            )

        call_name = _call_name(updated.func)
        if call_name not in _DYNAMIC_CALL_NAMES or len(updated.args) < 2:
            return updated

        object_arg = updated.args[0]
        name_arg = updated.args[1]
        if not isinstance(name_arg, ast.Constant) or not isinstance(
            name_arg.value, str
        ):
            return updated

        attr_name = name_arg.value
        if attr_name not in self._project_attributes:
            return updated

        replacement = self._mapped_name(attr_name)
        if replacement is None or replacement == attr_name:
            return updated

        ownership = self._attribute_ownership(object_arg)
        if ownership == "external":
            return updated
        if ownership == "likely_local":
            self.likely_local_rewrites += 1

        replaced_name_arg = ast.Constant(value=replacement)
        new_args = list(updated.args)
        new_args[1] = replaced_name_arg
        self.dynamic_name_rewrites += 1
        self.symbols_renamed += 1
        return ast.copy_location(
            ast.Call(
                func=updated.func,
                args=new_args,
                keywords=updated.keywords,
            ),
            updated,
        )

    def visit_Assign(self, node: ast.Assign) -> ast.AST:
        """Track ownership for assigned names.

        Args:
            node: Assign node.

        Returns:
            Updated node.
        """
        updated = self.generic_visit(node)
        if not isinstance(updated, ast.Assign):
            return updated
        ownership = self._infer_value_ownership(updated.value)
        if ownership is None:
            return updated
        for target in updated.targets:
            if isinstance(target, ast.Name):
                self._record_name_ownership_variants(target.id, ownership)
        return updated

    def visit_For(self, node: ast.For) -> ast.AST:
        """Track ownership for loop targets from iterable ownership.

        Args:
            node: For-loop node.

        Returns:
            Updated node.
        """
        ownership = self._infer_iter_ownership(node.iter)
        if ownership is not None:
            self._assign_target_ownership(node.target, ownership)
        return self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> ast.AST:
        """Track ownership for async loop targets from iterable ownership.

        Args:
            node: Async for-loop node.

        Returns:
            Updated node.
        """
        ownership = self._infer_iter_ownership(node.iter)
        if ownership is not None:
            self._assign_target_ownership(node.target, ownership)
        return self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> ast.AST:
        """Track ownership for comprehension targets from iterable ownership.

        Args:
            node: Comprehension clause node.

        Returns:
            Updated node.
        """
        ownership = self._infer_iter_ownership(node.iter)
        if ownership is not None:
            self._assign_target_ownership(node.target, ownership)
        return self.generic_visit(node)

    def visit_ListComp(self, node: ast.ListComp) -> ast.AST:
        """Seed ownership for list comprehension targets before visiting element.

        Args:
            node: List comprehension node.

        Returns:
            Updated node.
        """
        self._seed_comprehension_target_ownership(node.generators)
        return self.generic_visit(node)

    def visit_SetComp(self, node: ast.SetComp) -> ast.AST:
        """Seed ownership for set comprehension targets before visiting element.

        Args:
            node: Set comprehension node.

        Returns:
            Updated node.
        """
        self._seed_comprehension_target_ownership(node.generators)
        return self.generic_visit(node)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> ast.AST:
        """Seed ownership for generator expression targets before visiting element.

        Args:
            node: Generator expression node.

        Returns:
            Updated node.
        """
        self._seed_comprehension_target_ownership(node.generators)
        return self.generic_visit(node)

    def visit_DictComp(self, node: ast.DictComp) -> ast.AST:
        """Seed ownership for dict comprehension targets before visiting key/value.

        Args:
            node: Dict comprehension node.

        Returns:
            Updated node.
        """
        self._seed_comprehension_target_ownership(node.generators)
        return self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> ast.AST:
        """Track ownership for annotated assignments.

        Args:
            node: AnnAssign node.

        Returns:
            Updated node.
        """
        updated = self.generic_visit(node)
        if not isinstance(updated, ast.AnnAssign):
            return updated
        ownership: str | None = None
        if updated.value is not None:
            ownership = self._infer_value_ownership(updated.value)
        if ownership is None:
            ownership = self._annotation_ownership(updated.annotation)
        if ownership is None:
            return updated
        if isinstance(updated.target, ast.Name):
            self._record_name_ownership_variants(updated.target.id, ownership)
        return updated

    def _mapped_name(self, name: str) -> str | None:
        """Resolve mapped name when eligible.

        Args:
            name: Original symbol name.

        Returns:
            Mapped name when available, else None.
        """
        if name.startswith("__") and name.endswith("__"):
            return None
        return self._rename_map.get(name)

    def _attribute_ownership(self, value: ast.expr) -> str:
        """Classify ownership of attribute base object.

        Args:
            value: Attribute value expression.

        Returns:
            Ownership label: `project`, `external`, or `likely_local`.
        """
        if isinstance(value, ast.Name):
            tracked = self._get_name_ownership(value.id)
            if tracked is not None:
                return tracked
            if value.id in self._likely_local_symbols:
                return "likely_local"
            if value.id in self._external_symbols:
                return "external"
            if value.id in self._external_aliases:
                return "external"
            if value.id in self._import_aliases.values():
                return "project"
            if value.id == "self":
                return "project"
            return "external"
        return "likely_local"

    def _next_alias_name(self) -> str:
        """Generate deterministic alias name for rewritten imports.

        Returns:
            Next available alias identifier.
        """
        while True:
            alias = _alphabetic_name(self._alias_counter)
            self._alias_counter += 1
            if alias in self._blocked_alias_names:
                continue
            if alias in self._import_aliases.values():
                continue
            return alias

    def _should_rename_call_keywords(self, func: ast.expr) -> bool:
        """Determine whether call keywords should be renamed.

        Args:
            func: Call function expression.

        Returns:
            True when call target is project-local enough for keyword renames.
        """
        if isinstance(func, ast.Name):
            if func.id in self._external_symbols or func.id in self._external_aliases:
                return False
            if (
                func.id in self._project_class_names
                or func.id in self._mapped_project_class_names
            ):
                return True
            return func.id in self._rename_map or func.id in self._rename_map.values()
        if isinstance(func, ast.Attribute):
            return (
                func.attr in self._project_attributes
                or func.attr in self._mapped_project_attributes
                or func.attr in self._project_class_names
                or func.attr in self._mapped_project_class_names
            )
        return False

    def _push_scope(self) -> None:
        """Push a new name-ownership scope."""
        self._name_ownership_scopes.append({})

    def _pop_scope(self) -> None:
        """Pop the current name-ownership scope."""
        if len(self._name_ownership_scopes) > 1:
            self._name_ownership_scopes.pop()

    def _set_name_ownership(self, name: str, ownership: str) -> None:
        """Record ownership for a name in current scope.

        Args:
            name: Variable name.
            ownership: Ownership label.
        """
        self._name_ownership_scopes[-1][name] = ownership

    def _get_name_ownership(self, name: str) -> str | None:
        """Resolve ownership from current scope stack.

        Args:
            name: Variable name.

        Returns:
            Ownership when known.
        """
        for scope in reversed(self._name_ownership_scopes):
            if name in scope:
                return scope[name]
        return None

    def _infer_value_ownership(self, value: ast.expr) -> str | None:
        """Infer ownership from assigned expression.

        Args:
            value: Assigned expression.

        Returns:
            Ownership label when inferable.
        """
        if isinstance(value, ast.Name):
            tracked = self._get_name_ownership(value.id)
            if tracked is not None:
                return tracked
            if value.id in self._likely_local_symbols:
                return "likely_local"
            return None
        if not isinstance(value, ast.Call):
            return None
        func = value.func
        if isinstance(func, ast.Name):
            if func.id in self._external_symbols or func.id in self._external_aliases:
                return "external"
            if func.id == "enumerate":
                if value.args:
                    return self._infer_iter_ownership(value.args[0])
                return None
            if func.id in {"sorted", "list", "tuple", "set", "reversed"}:
                if value.args:
                    return self._infer_iter_ownership(value.args[0])
                return None
            if (
                func.id in self._project_class_names
                or func.id in self._mapped_project_class_names
            ):
                return "project"
            if func.id in self._rename_map or func.id in self._rename_map.values():
                return "likely_local"
            return None
        if isinstance(func, ast.Attribute):
            owner = self._attribute_ownership(func.value)
            if owner == "external":
                return "external"
            if (
                func.attr in self._project_class_names
                or func.attr in self._mapped_project_class_names
            ):
                return "project"
            if owner in {"project", "likely_local"} and (
                func.attr in self._project_attributes
                or func.attr in self._mapped_project_attributes
            ):
                return "likely_local"
            return None
        return None

    def _infer_iter_ownership(self, iterable: ast.expr) -> str | None:
        """Infer ownership for iterable expressions used by loops/comprehensions.

        Args:
            iterable: Iterable expression.

        Returns:
            Ownership label when inferable.
        """
        if isinstance(iterable, ast.Name):
            return self._get_name_ownership(iterable.id)
        if isinstance(iterable, ast.Call):
            return self._infer_value_ownership(iterable)
        if isinstance(iterable, ast.Subscript):
            return self._infer_iter_ownership(iterable.value)
        if isinstance(iterable, ast.Attribute):
            owner = self._attribute_ownership(iterable.value)
            if owner == "external":
                return "external"
            if (
                iterable.attr in self._project_attributes
                or iterable.attr in self._mapped_project_attributes
                or iterable.attr in self._project_class_names
                or iterable.attr in self._mapped_project_class_names
            ):
                return "likely_local"
            return owner
        return None

    def _assign_target_ownership(self, target: ast.expr, ownership: str) -> None:
        """Assign ownership recursively for loop/comprehension targets.

        Args:
            target: Assignment target expression.
            ownership: Ownership label.
        """
        if isinstance(target, ast.Name):
            self._record_name_ownership_variants(target.id, ownership)
            return
        if isinstance(target, (ast.Tuple, ast.List)):
            for element in target.elts:
                self._assign_target_ownership(element, ownership)

    def _seed_comprehension_target_ownership(
        self, generators: list[ast.comprehension]
    ) -> None:
        """Seed target ownership for comprehension generators in order.

        Args:
            generators: Comprehension generators.
        """
        for generator in generators:
            ownership = self._infer_iter_ownership(generator.iter)
            if ownership is None:
                continue
            self._assign_target_ownership(generator.target, ownership)

    def _seed_arg_ownership(self, args: ast.arguments) -> None:
        """Seed ownership for function parameters in current scope.

        Args:
            args: Function argument container.
        """
        for argument in self._iter_all_args(args):
            if argument.arg == "self":
                self._record_arg_ownership(argument.arg, "project")
                continue
            if argument.arg == "cls":
                self._record_arg_ownership(argument.arg, "project")
                continue
            if argument.annotation is None:
                self._record_arg_ownership(argument.arg, "likely_local")
                continue
            annotation_ownership = self._annotation_ownership(argument.annotation)
            if annotation_ownership is None:
                continue
            self._record_arg_ownership(argument.arg, annotation_ownership)

    def _record_arg_ownership(self, arg_name: str, ownership: str) -> None:
        """Record ownership for original and mapped argument names.

        Args:
            arg_name: Original argument name.
            ownership: Ownership label.
        """
        self._record_name_ownership_variants(arg_name, ownership)

    def _record_name_ownership_variants(self, name: str, ownership: str) -> None:
        """Record ownership across known name variants.

        Args:
            name: Name to record.
            ownership: Ownership label.
        """
        self._set_name_ownership(name, ownership)
        mapped_name = self._mapped_name(name)
        if mapped_name is not None:
            self._set_name_ownership(mapped_name, ownership)
        original_name = self._reverse_rename_map.get(name)
        if original_name is not None:
            self._set_name_ownership(original_name, ownership)

    def _annotation_ownership(self, annotation: ast.expr) -> str | None:
        """Infer ownership based on a type annotation node.

        Args:
            annotation: Annotation expression.

        Returns:
            Ownership label when inferable.
        """
        names: set[str] = {
            node.id for node in ast.walk(annotation) if isinstance(node, ast.Name)
        }
        if names & self._project_class_names:
            return "project"
        if names & self._mapped_project_class_names:
            return "project"
        if names:
            return "external"
        return None

    def _iter_all_args(self, args: ast.arguments) -> list[ast.arg]:
        """Flatten all argument slots in declaration order.

        Args:
            args: Function argument container.

        Returns:
            Collected argument nodes.
        """
        collected = list(args.posonlyargs)
        collected.extend(args.args)
        if args.vararg is not None:
            collected.append(args.vararg)
        collected.extend(args.kwonlyargs)
        if args.kwarg is not None:
            collected.append(args.kwarg)
        return collected


def rewrite_source(
    source: str, rename_map: RenameMap, index: ProjectIndex
) -> RewriteResult:
    """Rewrite one source file according to obfuscation rules.

    Args:
        source: Original Python source code.
        rename_map: Symbol rename mapping.
        index: Project index metadata.

    Returns:
        Rewritten source and counters.

    Raises:
        RewriteError: If source cannot be parsed or unparsed.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        logger.warning("Rewrite skipped due to parse error", extra={"error": str(exc)})
        raise RewriteError(str(exc)) from exc

    renamer = _Renamer(rename_map=rename_map, index=index)
    new_tree = renamer.visit(tree)
    ast.fix_missing_locations(new_tree)

    try:
        transformed_source = ast.unparse(new_tree)
    except ValueError as exc:
        logger.warning("Rewrite failed during unparse", extra={"error": str(exc)})
        raise RewriteError(str(exc)) from exc

    return RewriteResult(
        transformed_source=f"{transformed_source}\n",
        symbols_renamed=renamer.symbols_renamed,
        likely_local_rewrites=renamer.likely_local_rewrites,
        dynamic_name_rewrites=renamer.dynamic_name_rewrites,
    )


def _call_name(node: ast.expr) -> str | None:
    """Resolve simple call function names.

    Args:
        node: Function expression.

    Returns:
        Function name when directly callable by name.
    """
    if isinstance(node, ast.Name):
        return node.id
    return None


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
