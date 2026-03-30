# examples 说明

本目录用于放置 `analysis-module` 的最小输入示例，便于直接验证独立运行能力。

当前建议从以下命令开始：

```powershell
python analysis-module/run_analysis.py --task-name user_center_demo --input-file analysis-module/examples/sample_requirement.md
```

运行后可在 `analysis-module/artifacts/` 下查看：

- `parsed/cleaned_document.json`
- `parsed/parsed_requirement.json`
- `retrieval/retrieved_chunks.json`
- `scenarios/scenario_bundle.json`
- `validation/validation_report.json`
- `generated.feature`
