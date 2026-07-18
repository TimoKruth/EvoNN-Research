---
document_kind: research_log
status: completed
authoritative: false
subject: dynamic_import_boundary_enforcement
superseded_by: strict_primitive_prohibition
---

# Dynamic-import boundary policy negative result

The path-sensitive, interprocedural dynamic-import analyzer developed during Gate B0.4 was abandoned after repeated adversarial review. Tracking aliases, branches, exception prefixes, loops, function invocation state, globals, nonlocals, pattern matching, annotations, and reflection still could not soundly guarantee that every Python dynamic-loading path was modeled.

The permanent replacement is a strict primitive prohibition over every production package `src/**/*.py` file and every shipped `scripts/**/*.py` file. Tests are outside production scope. The policy is intentionally syntax-only and spelling-based: it does not infer runtime values, follow aliases, execute target code, or attempt a partial Python interpreter. A reserved spelling is rejected when it appears in a prohibited acquisition shape even if a particular runtime path might be harmless.

## Reserved names and attributes

The canonical reserved set covers these categories:

- dynamic providers and execution: `importlib`, `import_module`, `runpy`, `run_module`, `builtins`, `__import__`, `exec`, and `eval`;
- builtin reflection: `getattr`, `hasattr`, `setattr`, and `delattr`;
- namespace access: `globals`, `locals`, and `vars`, plus `__builtins__`, `__dict__`, `__class__`, and `__getattribute__`;
- loader paths: `__loader__`, `__spec__`, `exec_module`, and `load_module`;
- operator helpers: `attrgetter`, `itemgetter`, `methodcaller`, and `getitem`;
- metadata plugin surfaces: `entry_points` and `EntryPoint`.

General imports of `importlib`, `runpy`, or `builtins`; provider star imports; direct/bare reserved-name loads; reserved attribute or subscript acquisition; and imports of reserved names from arbitrary modules fail closed. Python `eval`, `exec`, and `__import__` remain banned as names, imports, attributes, reflected strings, and mapping/subscript acquisitions.

## Reflection, namespace, and mapping rules

Direct `getattr`, `hasattr`, `setattr`, and `delattr` calls are accepted only when their attribute-name argument is a literal safe string outside the reserved set. Missing, computed, formatted, parameter-derived, or reserved literal names fail closed. Acquiring any reflection helper as a value remains prohibited.

Literal-string subscripts naming reserved primitives are rejected. Mapping `get`, `__getitem__`, `setdefault`, and `pop` calls are accepted only in the validated positional forms with a literal safe string key; keyword keys, nonliteral keys, unsupported arity, and unresolved starred arguments fail closed. Namespace constructors and paths such as `globals`, `locals`, `vars`, `__builtins__`, `__dict__`, `__class__`, and `__getattribute__` do not provide an escape from those rules.

`operator.attrgetter`, `operator.itemgetter`, `operator.methodcaller`, and `operator.getitem` are prohibited acquisition surfaces, including direct imports, aliases, star imports, attributes, and reserved literal targets.

## Narrow `importlib.metadata` surface

Exact `import importlib.metadata` is allowed only as the syntactic prefix of approved direct attributes. Exact direct imports of `version` and `PackageNotFoundError` are allowed. Module alias/acquisition forms, other `importlib` submodules, `entry_points`, `EntryPoint`, plugin `.load()`, and loader/spec paths remain prohibited. A benign `importlib.metadata` prefix never masks a reserved outer attribute.

## Reviewed external API call allowance

Some external libraries use a reserved spelling for a non-dynamic API. The policy handles this through the canonical `ALLOWED_EXTERNAL_MODULE_ATTRIBUTE_CALLS` set rather than path- or callsite-specific exceptions. Its initial reviewed entry is `("mlx.core", "eval")`.

An allowed external attribute is accepted only when it is the function of a call and its receiver is established by an exact static import of the configured module in the same file. Supported MLX forms include `import mlx.core as mx`, `from mlx import core as mx`, `from mlx import core`, and unaliased `import mlx.core`. Multiple legitimate `mx.eval(...)` calls are allowed. Attribute acquisition as a value, indirect aliases, neighboring/fake modules, `from mlx.core import eval`, and Python `eval` remain banned. Any alias rebinding or shadowing anywhere in the file disables the allowance for that alias.

The canonical set is deliberately small and data-driven so a later collision such as another external library's non-dynamic method can be considered without adding a bespoke AST-node or per-callsite exception.

## Future reviewed-exception process

This strict primitive prohibition supersedes the abandoned analyzer. Any new external API allowance or dynamic-loading exception requires all of the following in one reviewed policy change:

1. a written justification distinguishing the external API from Python loading/execution;
2. a canonical module-and-attribute entry or narrower reviewed mechanism;
3. RED tests for legitimate calls and adversarial fake, alias, rebinding, acquisition, and Python-primitive cases;
4. GREEN policy, full-suite, and cross-host verification evidence;
5. an update to this non-authoritative research log and any affected governance evidence.

No exception may be introduced solely by file path, function name, AST-node count, or an unreviewed local workaround. This research log records negative and policy-design evidence only; it is not an execution plan or authority source.
