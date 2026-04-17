# Assertion Guardrails

## Output Quality
- Assertions should prefer explicit expected effects over guesses derived only from path placeholders or endpoint names.
- Placeholder variables in paths such as `{id}` or `{guid}` are not by themselves evidence that a response body contains the same fields.
- For list and filter APIs, structural assertions are often safer than assuming fixed business values or record counts.

## Review Hints
- If the document only states status semantics, keep assertions focused on status code and coarse response structure.
- If a response is non-JSON or body shape is unclear, avoid forcing field-level JSON assertions.
