# API Challenges Domain Knowledge

## Domain Facts
- `POST /challenger` initializes a challenger session and provides `X-CHALLENGER` for later requests.
- `POST /secret/token` provides a protected token that may be required before accessing secret endpoints such as `GET /secret/note`.
- Todo endpoints commonly combine collection operations on `/todos` with resource operations on `/todos/{id}` and filtered queries.

## Scenario Hints
- Session initialization should generally precede detail or protected endpoints that rely on the challenger guid.
- If the document mentions `/challenger/{guid}` or `/challenger/database/{guid}`, those routes should be treated as resource-dependent flows rather than isolated read-only checks.
