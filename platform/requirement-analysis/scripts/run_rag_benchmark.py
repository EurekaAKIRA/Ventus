from __future__ import annotations

import json
import sys
from pathlib import Path


def _extend_path() -> None:
    root = Path(__file__).resolve().parents[3]
    additions = [
        root / "platform" / "shared" / "src",
        root / "platform" / "requirement-analysis" / "src",
    ]
    for item in additions:
        path = str(item)
        if path not in sys.path:
            sys.path.insert(0, path)


def main() -> int:
    _extend_path()
    from requirement_analysis.rag_benchmark import export_rag_benchmark_reports, run_rag_benchmark

    result = run_rag_benchmark()
    output_dir = Path(__file__).resolve().parents[1] / "benchmark_results"
    exported = export_rag_benchmark_reports(result, output_dir=output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("")
    print(json.dumps({"exported_reports": exported}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
