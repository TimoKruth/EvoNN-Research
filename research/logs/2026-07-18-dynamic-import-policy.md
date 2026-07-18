---
document_kind: research_log
status: completed
authoritative: false
subject: dynamic_import_boundary_enforcement
superseded_by: strict_primitive_prohibition
---

# Dynamic-import boundary policy negative result

The path-sensitive, interprocedural dynamic-import analyzer developed during Gate B0.4 was abandoned after repeated adversarial review. Tracking aliases, branches, exception prefixes, loops, function invocation state, globals, nonlocals, pattern matching, annotations, and reflection still could not soundly guarantee that every Python dynamic-loading path was modeled.

The permanent replacement is a strict primitive prohibition over production package sources and shipped Python scripts. Production code may not acquire the general `importlib.import_module`, `runpy.run_module`, or `builtins.__import__` providers; directly call `__import__`, `exec`, or `eval`; or use explicit reflection naming those primitives. Safe specific imports such as `importlib.metadata` remain allowed.

This strict primitive prohibition supersedes the abandoned analyzer. Any future dynamic-loading exception requires an explicit reviewed policy update, a narrow exact allowlist, and written justification. This research log records negative evidence only and is not an execution plan or authority source.
