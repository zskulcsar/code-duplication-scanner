def analyze_project(project_root: Path, files: list[Path]) -> ProjectIndex:
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