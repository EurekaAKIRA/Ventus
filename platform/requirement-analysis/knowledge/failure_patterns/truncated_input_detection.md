# Truncated Input Pattern

## Symptom
- Only the opening sections of a requirement document are present, while interface lists, scenarios, or examples disappear unexpectedly.

## Parser Impact
- Rule extraction can only parse the visible part of the input and may return a small subset of endpoints even when the original full document covered much more.
- RAG cannot recover missing sections that never entered the system.

## Mitigation
- Flag incomplete markdown, unterminated JSON blocks, abrupt file endings, or suspiciously short specs for manual review.
- When parser output is much smaller than the declared coverage scope, suspect input truncation before blaming retrieval alone.
