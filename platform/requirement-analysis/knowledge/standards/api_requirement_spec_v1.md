# API Requirement Spec v1

## Minimal Structure
- API requirement documents should keep global information outside executable steps.
- Recommended order: document objective, environment info, auth/global constraints, resource dependency notes, scenario list, expected effects.
- Explicit anchors such as `**涉及接口:**`, `**关键依赖:**`, `**资源来源:**`, `**save_context:**`, and `**uses_context:**` help downstream parsing stay stable.

## Parsing Guidance
- Interface identifiers should use the format `` `METHOD /path` `` instead of free-form natural language alone.
- Scenario titles should be explicit and should describe a testable goal rather than background commentary.
- Global explanatory text should not be treated as executable action steps.
