"""Repository resilience test for empty and corrupted task-center stores."""

from __future__ import annotations

import tempfile
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_task_repository():
    root = Path(__file__).resolve().parents[3]
    module_path = root / "platform" / "task-center" / "src" / "task_center" / "repository.py"
    spec = spec_from_file_location("task_center_repository", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load repository module from {module_path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.TaskRepository


def main() -> int:
    TaskRepository = _load_task_repository()

    with tempfile.TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir) / "tasks.json"
        repo_path.write_text("", encoding="utf-8")

        repository = TaskRepository(str(repo_path))
        assert repository.load_tasks() == []

        repo_path.write_text("{", encoding="utf-8")
        assert repository.load_tasks() == []
        assert list(Path(temp_dir).glob("tasks.json.corrupt.*"))

        repository.save_tasks([{"task_id": "task-1", "task_name": "demo"}])
        payload = repository.load_tasks()
        assert payload[0]["task_id"] == "task-1"

    print("repository resilience test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
