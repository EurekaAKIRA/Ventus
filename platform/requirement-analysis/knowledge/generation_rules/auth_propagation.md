# Auth Propagation Rules

## Token And Header Flow
- If a document declares an auth endpoint, downstream protected interfaces should inherit that dependency even when the document does not repeat it for every step.
- Common auth carriers include `Authorization`, `Cookie`, `X-AUTH-TOKEN`, and `X-CHALLENGER`.
- A protected endpoint should not be planned as an isolated scenario unless the token source or preset credential source is explicit.

## Context Usage
- Values returned by auth endpoints should be saved as reusable context keys when later requests depend on them.
- Header or cookie injection rules belong to global constraints, but scenario generation should still bind them to the consuming requests.
