# Dependency Lifecycle Rules

## Core Constraint
- Treat resource lifecycle as a first-class scenario constraint.
- `detail`, `update`, `patch`, and `delete` operations should not run as standalone scenarios when the resource source is missing.
- A live resource may come from same-scenario `create`, same-resource `list/detail` with saved id, or an explicitly declared preset resource.

## Scenario Planning
- If a placeholder path such as `/resource/{id}` appears, prefer chaining it with the step that creates or discovers the id.
- When multiple operations share one resource, favor one lifecycle scenario over several isolated scenarios with duplicated setup.
- A scenario that consumes a saved id should make that dependency explicit through `save_context` or a clear resource-source note.
