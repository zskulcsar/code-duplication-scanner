* [x] **PH6_OBF_301** Global map stays consistent across multiple files
- Description: Analyze two modules with a shared class usage path and rewrite both using one rename map.
- Expected: Class and method identifiers are obfuscated consistently in declaration and cross-file usage sites.

* [x] **PH6_OBF_302** External attributes remain unchanged in cross-file pipeline
- Description: Rewrite a module with both project attributes and external module attribute usage.
- Expected: External attribute access remains unchanged while project-owned symbols follow rename rules.

* [x] **PH6_OBF_303** Module-qualified class usage is renamed for project classes
- Description: Rewrite a module that instantiates a project class through `import module` qualified access.
- Expected: The class segment in `module.ClassName(...)` is renamed to the mapped project class name.
