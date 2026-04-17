# Placeholder Field Pollution Pattern

## Symptom
- Path placeholders such as `{id}` or `{guid}` are mistakenly converted into response assertions like `json.id exists` even though the document never states that the response body includes those fields.

## Why It Happens
- Endpoint extraction sees the placeholder in the route and downstream logic overgeneralizes from the path shape.

## Mitigation
- Treat placeholder tokens as routing hints first, not response-field evidence.
- Prefer assertions that come from explicit response examples, saved context, or documented result semantics.
