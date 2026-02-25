* [x] **PH6_OBF_201** Rewriter renames project symbols and leaves external calls unchanged
- Description: Rewrite source containing local symbols and external module calls with a predefined map.
- Expected: In-project definitions/references are renamed while external module usage remains unchanged.

* [x] **PH6_OBF_202** Rewriter preserves plain string literal text
- Description: Rewrite source containing normal string literals and a renamed identifier.
- Expected: Plain string literal text remains unchanged in the transformed source.

* [x] **PH6_OBF_203** Rewriter updates only f-string expressions
- Description: Rewrite source with f-string interpolation and a renamed symbol used in the expression.
- Expected: Static f-string text stays unchanged and expression identifiers are renamed.

* [x] **PH6_OBF_204** Rewriter never renames dunder methods
- Description: Rewrite class source with a dunder method while map includes a dunder entry.
- Expected: Dunder method names remain unchanged in transformed code.

* [x] **PH6_OBF_205** Rewriter updates dynamic attribute names for likely-local objects
- Description: Rewrite source using getattr with a likely-local object and attribute name.
- Expected: Dynamic attribute string argument is rewritten, and rewrite counters are updated.

* [x] **PH6_OBF_206** Rewriter keeps dynamic attribute names for external objects
- Description: Rewrite source using getattr against an external module object.
- Expected: Dynamic attribute string argument remains unchanged.

* [x] **PH6_OBF_207** Rewriter output remains parseable
- Description: Rewrite a simple function and parse the transformed source.
- Expected: Transformed output parses without syntax errors.

* [x] **PH6_OBF_208** Rewriter normalizes plain imports to alias form
- Description: Rewrite a module with a simple import and verify alias-form import rewriting and reference updates.
- Expected: `import x` is rewritten to `import x as <alias>` and symbol usages switch to the alias.

* [x] **PH6_OBF_209** Rewriter updates argument annotations after renaming
- Description: Rewrite a function with argument annotations that reference aliased imports and renamed project classes.
- Expected: Annotation references are updated consistently so renamed imports and class names are used in function signatures.

* [x] **PH6_OBF_210** Rewriter renames keyword arguments for local calls
- Description: Rewrite local function definitions and callsites where arguments are passed with named keywords.
- Expected: Renamed local callsites use renamed keyword names matching renamed parameter names.

* [x] **PH6_OBF_211** Rewriter keeps keyword arguments for external calls
- Description: Rewrite code calling external APIs with named keyword arguments.
- Expected: External call keyword names remain unchanged while import aliasing is still applied.

* [x] **PH6_OBF_212** Rewriter keeps keyword arguments for external method calls
- Description: Rewrite code calling external object methods with named keyword arguments on locally stored instances.
- Expected: Keyword names for external API methods remain unchanged even when receiver variables are renamed.

* [x] **PH6_OBF_213** Rewriter renames keyword arguments for local method calls
- Description: Rewrite project-local instance method calls that use named arguments after method and parameter renaming.
- Expected: Named call arguments are rewritten to the renamed parameter names for local method calls.

* [x] **PH6_OBF_214** Rewriter renames dataclass field attribute usage
- Description: Rewrite dataclass-style field declarations and instance attribute reads in project code.
- Expected: Renamed field declarations and corresponding instance attribute access stay consistent.

* [x] **PH6_OBF_215** Rewriter keeps colliding attrs on external parse results
- Description: Rewrite code that accesses external parser namespace attributes colliding with project field names.
- Expected: Attributes on externally produced objects (for example `parse_args()` results) are not renamed by project-field collisions.

* [x] **PH6_OBF_216** Rewriter keeps annotated namespace parameter attributes unchanged
- Description: Rewrite a function that accesses a field on a parameter annotated as `argparse.Namespace` while the same field name exists in project class fields.
- Expected: Parameter name can be renamed, but accessed namespace attribute names remain unchanged to preserve external object semantics.

* [x] **PH6_OBF_217** Rewriter renames method calls on values returned from local factories
- Description: Rewrite code where a local helper function returns a project object and method calls are made through a variable assigned from that helper.
- Expected: Method name and named arguments are rewritten consistently after assignment from local helper calls.

* [x] **PH6_OBF_218** Rewriter renames attributes in list-comprehension targets
- Description: Rewrite code where a list comprehension iterates project-typed records and accesses project attributes on the comprehension variable.
- Expected: Comprehension target variable attribute accesses are renamed consistently with project field mappings.

* [x] **PH6_OBF_219** Rewriter renames attributes in for-loop targets
- Description: Rewrite code where a for-loop iterates project-typed records and accesses project attributes on the loop variable.
- Expected: Loop target variable attribute accesses are renamed consistently with project field mappings.

* [x] **PH6_OBF_220** Rewriter keeps builtin call keyword names unchanged
- Description: Rewrite code that calls builtin functions (for example `sorted`) using named keyword arguments while similarly named project symbols exist.
- Expected: Builtin keyword argument names are preserved and only local identifiers are renamed.

* [x] **PH6_OBF_221** Rewriter renames lambda-parameter attribute access for project objects
- Description: Rewrite code that sorts project records with a lambda key function that reads a project attribute from the lambda parameter.
- Expected: Lambda parameter names and project attribute accesses are renamed consistently.

* [x] **PH6_OBF_222** Rewriter propagates ownership through `sorted(...)` results
- Description: Rewrite code where a project-typed list is passed through `sorted(...)`, then consumed by comprehensions and attribute access.
- Expected: Ownership is preserved across the sorted result so project attribute access remains consistently renamed.

* [x] **PH6_OBF_223** Rewriter propagates ownership through `enumerate(...)` and annotated list declarations
- Description: Rewrite code where enumerate loop targets and annotated list variables carry project-owned records used in attribute access.
- Expected: Loop target and appended attribute access names are renamed consistently with project field mappings.

* [x] **PH6_OBF_224** Rewriter propagates ownership through slice-based iterable loops
- Description: Rewrite code where a loop iterates over a sliced project-owned iterable (for example `rows[1:]`) and accesses project attributes on the loop target.
- Expected: Slice-derived loop targets preserve project ownership and attribute accesses are renamed consistently.

* [x] **PH6_OBF_225** Rewriter propagates ownership from project method-call results
- Description: Rewrite code where a project object method returns another project object whose attributes are accessed via an intermediate variable.
- Expected: Method-call result variables preserve project ownership so downstream project attribute accesses are renamed consistently.

* [x] **PH6_OBF_226** Rewriter propagates iterable ownership from project attribute containers
- Description: Rewrite code with nested loops where the inner iterable is a project-owned attribute container (for example `group.members`).
- Expected: Inner loop targets inherit project ownership and project attribute accesses are renamed consistently.
