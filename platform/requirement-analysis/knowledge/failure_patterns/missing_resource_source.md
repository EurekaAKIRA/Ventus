# Missing Resource Source Pattern

## Symptom
- A generated scenario contains `GET /resource/{id}`, `PUT /resource/{id}`, `PATCH /resource/{id}`, or `DELETE /resource/{id}` but no prior step explains where the live resource id comes from.

## Risk
- Execution often fails with `404`, `401`, empty assertions, or pseudo-failures that are caused by setup gaps rather than the target API.

## Mitigation
- Merge the operation back into a dependency-chain scenario.
- Save the resource id explicitly after `create` or `list/detail`.
- Only keep standalone resource-modification scenarios when the document explicitly declares a preset resource.
