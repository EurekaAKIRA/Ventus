# platform-ui

## 模块定位
`platform-ui` 是平台后端能力的前端工作台，覆盖任务创建、需求解析、场景与 DSL 展示、执行监控、报告查看与产物管理。

## 本地开发
```bash
cd platform/platform-ui
npm install
npm run dev
```

## 构建
```bash
npm run build
```

## 前端文档入口（重要）
- **总入口（给前端）**：`docs/frontend_api_list.md` 的 **§1.1 前端参考文档索引**。
- 其余文档均从该总入口链过去即可。

## 相关文档（相对路径）
- `docs/frontend_api_list.md`
- `docs/ux_service_api_contract_draft.md`
- `platform/platform-ui/FRONTEND_DEVELOPMENT_GUIDE.md`
- `platform/platform-ui/FRONTEND_PAGE_PLAN.md`
- `docs/platform_requirements_status.md`
- `docs/platform_e2e_requirement.md`
- `docs/platform_quickstart.md`
- `platform/platform-ui/api-contract.ts`

## OpenAPI
后端启动后可访问：`http://127.0.0.1:8001/docs`
