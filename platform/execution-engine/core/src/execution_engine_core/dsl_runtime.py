"""Unified DSL runtime for execution-engine."""

from __future__ import annotations


def run_dsl(test_case_dsl: dict, execution_mode: str | None = None) -> dict:
    """Dispatch DSL payloads to the appropriate executor."""
    mode = execution_mode or test_case_dsl.get("execution_mode", "api")

    if mode == "api":
        from api_runner import execute_test_case_dsl

        return execute_test_case_dsl(test_case_dsl)

    if mode == "web-ui":
        return {
            "task_id": test_case_dsl.get("task_id", "unknown_task"),
            "executor": "lavague-adapter",
            "status": "not_implemented",
            "scenario_results": [],
            "metrics": {},
            "logs": [{"level": "warning", "message": "web-ui executor is not connected yet"}],
        }

    if mode == "cloud-load":
        from cloud_load_runner import execute_load_test_case_dsl

        return execute_load_test_case_dsl(test_case_dsl)

    return {
        "task_id": test_case_dsl.get("task_id", "unknown_task"),
        "executor": "unknown",
        "status": "failed",
        "scenario_results": [],
        "metrics": {},
        "logs": [{"level": "error", "message": f"Unsupported execution mode: {mode}"}],
    }
