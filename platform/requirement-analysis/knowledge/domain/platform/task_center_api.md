# Task Center API Knowledge

## Core Platform Flow
- `POST /api/tasks` creates a task and returns a task identifier used by later orchestration endpoints.
- `GET /api/tasks/{task_id}` reads task status and artifacts.
- `POST /api/tasks/{task_id}/execute` runs or resumes executable scenarios derived from the parsed requirement.

## Practical Notes
- Platform task documents are different from external API product documents and should be indexed only when the source actually discusses task-center APIs.
- Task-center contract knowledge should not dominate retrieval for unrelated external APIs such as Restful Booker or API Challenges.
