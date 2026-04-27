import type {
  AnalysisReport,
  AnalysisProgressPayload,
  ExecutionExplanationPayload,
  ExecutionHistoryItem,
  ExecutionResult,
  HistoryTaskItem,
  ParsedRequirement,
  PreflightCheckPayload,
  RegressionDiffPayload,
  RetrievedChunk,
  ScenarioModel,
  TaskArtifactContent,
  TaskArtifactItem,
  TaskContext,
  TaskDashboardPayload,
  TaskDetailPayload,
  TaskDraftAgentPayload,
  TaskListItem,
  TestCaseDSL,
  ValidationReport,
} from "../types";
import {
  mockAnalysisReport,
  mockArtifactContentByType,
  mockArtifacts,
  mockExecutionResult,
  mockHistoryTaskList,
  mockParseMetadata,
  mockParsedRequirement,
  mockRetrievedContext,
  mockScenarios,
  mockTaskDetail,
  mockTaskList,
  mockTestCaseDSL,
  mockValidationReport,
} from "../mocks";
import { getStoredCurrentProjectId, requestApi } from "./client";

const delay = (ms = 400) => new Promise((r) => setTimeout(r, ms));

/** Matches `platform/shared/config/runtime_config.json` → `requirement_analysis.defaults.rag_enabled`. */
export const DEFAULT_REQUIREMENT_RAG_ENABLED = false;
const USE_MOCK_API = String(import.meta.env.VITE_USE_MOCK_API ?? "").toLowerCase() === "true";
const HISTORY_PAGE_SIZE_MAX = 200;
let regressionDiffApiAvailable: boolean | null = null;

function taskApiPath(taskId: string): string {
  return `/api/tasks/${encodeURIComponent(taskId)}`;
}

function taskArtifactApiPath(taskId: string, artifactType: string): string {
  return `${taskApiPath(taskId)}/artifacts/${encodeURIComponent(artifactType)}`;
}

function normalizeStatus(status: string): string {
  return status === "scenario_generated" ? "generated" : status;
}

function normalizeTaskItem(input: Partial<TaskListItem> & Record<string, unknown>): TaskListItem {
  const rawStatus = String(input.status ?? "received");
  const normalizedStatus = normalizeStatus(rawStatus);
  return {
    task_id: String(input.task_id ?? ""),
    task_name: String(input.task_name ?? ""),
    source_type: String(input.source_type ?? "text"),
    source_path: (input.source_path as string | null | undefined) ?? null,
    created_at: String(input.created_at ?? new Date().toISOString()),
    language: String(input.language ?? "zh-CN"),
    status: normalizedStatus,
    notes: Array.isArray(input.notes) ? (input.notes as string[]) : [],
    project_id: typeof input.project_id === "string" ? input.project_id : undefined,
    created_by: typeof input.created_by === "string" ? input.created_by : undefined,
  };
}

function toArtifactLabel(artifactType: string): string {
  const mapping: Record<string, string> = {
    raw: "原始需求文本",
    "parse-metadata": "解析元数据",
    "parsed-requirement": "结构化需求",
    "retrieved-context": "检索上下文",
    scenarios: "测试场景",
    dsl: "DSL 文件",
    feature: "Feature 文件",
    "validation-report": "校验报告",
    "analysis-report": "分析报告",
  };
  return mapping[artifactType] ?? artifactType;
}

function appendProjectId(qp: URLSearchParams, projectId?: string) {
  const resolved = String(projectId ?? getStoredCurrentProjectId()).trim();
  if (resolved) {
    qp.set("project_id", resolved);
  }
}

export async function fetchTaskList(_params?: {
  status?: string;
  keyword?: string;
  page?: number;
  page_size?: number;
  project_id?: string;
}): Promise<{ items: TaskListItem[]; total: number }> {
  const requestedStatus = _params?.status?.trim() ?? "";
  const useClientSideRunningFilter = requestedStatus === "running";

  if (USE_MOCK_API) {
    await delay();
    let items = [...mockTaskList];
    if (requestedStatus) {
      items = items.filter((t) => normalizeStatus(String(t.status ?? "")) === requestedStatus);
    }
    if (_params?.keyword) {
      const kw = _params.keyword.toLowerCase();
      items = items.filter((t) => t.task_name.toLowerCase().includes(kw) || t.task_id.toLowerCase().includes(kw));
    }
    return { items, total: items.length };
  }
  try {
    const qp = new URLSearchParams();
    const status = useClientSideRunningFilter ? "" : requestedStatus;
    const keyword = _params?.keyword?.trim();
    const page = _params?.page ?? 1;
    const pageSize = _params?.page_size ?? 20;
    if (status) qp.set("status", status);
    if (keyword) qp.set("keyword", keyword);
    appendProjectId(qp, _params?.project_id);
    qp.set("page", String(page));
    qp.set("page_size", String(pageSize));

    const payload = await requestApi<{ items: Array<Record<string, unknown>>; total: number }>(`/api/tasks?${qp.toString()}`);
    let items = payload.items.map((item) => normalizeTaskItem(item));
    if (useClientSideRunningFilter) {
      items = items.filter((item) => normalizeStatus(item.status) === "running");
    }
    return {
      items,
      total: useClientSideRunningFilter ? items.length : payload.total,
    };
  } catch (error) {
    throw new Error(`获取任务列表失败: ${(error as Error).message}`);
  }
}

export async function fetchTaskDetail(taskId: string, options?: { detailLevel?: "full" | "summary" }): Promise<TaskDetailPayload> {
  if (USE_MOCK_API) {
    await delay();
    return { ...mockTaskDetail };
  }
  try {
    const level = options?.detailLevel ?? "full";
    const qs = level === "summary" ? "?detail_level=summary" : "";
    return await requestApi<TaskDetailPayload>(`${taskApiPath(taskId)}${qs}`);
  } catch (error) {
    throw new Error(`获取任务详情失败: ${(error as Error).message}`);
  }
}

export async function createTask(payload: {
  task_name: string;
  source_type: string;
  requirement_text?: string;
  source_path?: string;
  target_system?: string;
  environment?: string;
  rag_enabled?: boolean;
  project_id?: string;
}): Promise<TaskContext & { project_id?: string; created_by?: string }> {
  if (USE_MOCK_API) {
    await delay(600);
    return {
      task_id: `task_${Date.now()}`,
      task_name: payload.task_name,
      source_type: payload.source_type,
      source_path: payload.source_path ?? null,
      created_at: new Date().toISOString(),
      language: "zh-CN",
      status: "received",
      notes: [],
      project_id: payload.project_id,
    };
  }
  try {
    const data = await requestApi<{
      task_id: string;
      task_context: TaskContext;
      project_id?: string;
      created_by?: string;
    }>("/api/tasks", {
      method: "POST",
      body: JSON.stringify({
        ...payload,
        project_id: payload.project_id ?? (getStoredCurrentProjectId() || undefined),
      }),
    });
    return {
      ...data.task_context,
      project_id: data.project_id,
      created_by: data.created_by,
    };
  } catch (error) {
    throw new Error(`创建任务失败: ${(error as Error).message}`);
  }
}

export async function fetchTaskDraftAgent(payload: {
  task_name?: string;
  requirement_text?: string;
  source_path?: string;
  target_system?: string;
  environment?: string;
  project_id?: string;
}): Promise<TaskDraftAgentPayload> {
  if (USE_MOCK_API) {
    await delay(240);
    return {
      reply: "已根据当前输入生成建议。",
      summary: {
        ready_score: 2,
        max_score: 4,
        requirement_chars: String(payload.requirement_text ?? "").length,
        ready_to_create: true,
        ready_to_execute: Boolean(payload.environment),
        highlight_count: 2,
        risk_count: 0,
        confidence_score: 74,
        confidence_level: "medium",
      },
      suggested_task_name: payload.task_name || "示例任务",
      detected_base_url: payload.target_system || "",
      selected_environment: payload.environment || null,
      recommended_environment: payload.environment || null,
      environment_candidates: payload.environment
        ? [
            {
              name: payload.environment,
              match_type: "selected_environment",
            },
          ]
        : [],
      checks: [
        {
          key: "requirement_text",
          status: String(payload.requirement_text ?? "").trim() ? "ready" : "attention",
          message: String(payload.requirement_text ?? "").trim() ? "需求描述已提供" : "请补充需求描述",
        },
      ],
      form_patch: {},
      signals: [
        {
          key: "document_shape",
          label: "文档形态",
          value: "半结构化",
          tone: "default",
        },
        {
          key: "endpoint_count",
          label: "接口识别",
          value: payload.target_system ? "1 个接口 / 1 种方法" : "未识别到接口标识",
          tone: payload.target_system ? "success" : "warning",
        },
      ],
      recognized_endpoints: payload.target_system ? ["GET /demo/resource"] : [],
      scenario_outlook: {
        estimated_scenario_count: payload.target_system ? 1 : 0,
        endpoint_count: payload.target_system ? 1 : 0,
        resource_group_count: payload.target_system ? 1 : 0,
        write_endpoint_count: 0,
        read_only_endpoint_count: payload.target_system ? 1 : 0,
        lifecycle_chain_count: 0,
        standalone_endpoint_count: payload.target_system ? 1 : 0,
        uncovered_live_resource_endpoints: [],
        scenario_shape: payload.target_system ? "单接口/松散型" : "待补充",
      },
      resource_groups: payload.target_system
        ? [
            {
              resource_key: "resource",
              methods: ["GET"],
              endpoints: ["GET /demo/resource"],
              status: "read_only",
              has_create: false,
              has_context_flow: false,
              has_live_resource: false,
              has_list_source: true,
              estimated_scenarios: 1,
            },
          ]
        : [],
      highlights: ["已生成基础草案", "可继续回填任务名称和目标系统"],
      risks: [],
      document_fixes: ["为关键步骤补充 `**Request:**` 和 `**Expected:**`，便于后续自动场景生成"],
      document_actions: [
        {
          key: "request_expected_template",
          title: "插入步骤模板",
          mode: "append",
          reason: "补齐 Request / Expected 结构锚点",
          content: "\n## Scenario: 示例场景\n**Request:** `GET /resource`\n**Expected:** 返回 200\n",
        },
      ],
      document_preview: {
        content: `${String(payload.requirement_text ?? "").trim()}\n\n## Scenario: 示例场景\n**Request:** \`GET /resource\`\n**Expected:** 返回 200`.trim(),
        summary: "已整合步骤模板",
        action_count: 1,
        applied_action_keys: ["request_expected_template"],
      },
      knowledge_hits: [
        {
          title: "API Requirement Spec v1",
          source_file: "standards/api_requirement_spec_v1.md",
          doc_type: "standard",
          score: 4.2,
          query_match_count: 2,
          excerpt: "建议文档统一使用 Request / Expected / save_context 等结构锚点，减少后续解析歧义。",
        },
      ],
      knowledge_summary: "已从知识库匹配到 1 条参考片段",
      rag_support: {
        knowledge_applied: true,
        knowledge_chunk_count: 3,
        retrieved_hit_count: 1,
        query_count: 2,
        query_variants_preview: ["POST /auth/login", "Base URL: https://api.example.com"],
        source_file_count: 1,
        source_file_diversity: 1,
        doc_type_count: 1,
      },
      follow_up_questions: [
        {
          key: "request_structure",
          field: "requirement_text",
          priority: "medium",
          question: "能否把关键步骤改写成 `**Request:**` 结构？",
          reason: "这样更利于场景边界识别",
          action_kind: "apply_document_action",
          action_label: "插入模板",
          document_action_key: "request_expected_template",
          answer_mode: "append_requirement",
          answer_placeholder: "例如：先创建订单，再查询详情",
          answer_template: "\n**补充说明:**\n- {answer}\n",
        },
      ],
      warnings: [],
      next_actions: [],
      suggestions: [],
      capabilities: {
        backend_ready: true,
        mcp_direct_supported: false,
        requires_backend_proxy: true,
        auto_analysis_supported: true,
        diagnostics_supported: true,
        document_actions_supported: true,
        knowledge_rag_supported: true,
      },
    };
  }
  try {
    return await requestApi<TaskDraftAgentPayload>("/api/tasks/agent/draft", {
      method: "POST",
      body: JSON.stringify({
        ...payload,
        project_id: payload.project_id ?? (getStoredCurrentProjectId() || undefined),
      }),
    });
  } catch (error) {
    throw new Error(`获取 Agent 建议失败: ${(error as Error).message}`);
  }
}

export async function deleteTask(taskId: string): Promise<void> {
  if (USE_MOCK_API) {
    await delay(300);
    return;
  }
  try {
    await requestApi(taskApiPath(taskId), { method: "DELETE" });
  } catch (error) {
    throw new Error(`删除任务失败: ${(error as Error).message}`);
  }
}

export async function fetchParsedRequirement(taskId: string): Promise<ParsedRequirement> {
  if (USE_MOCK_API) {
    await delay();
    return { ...mockParsedRequirement };
  }
  try {
    return await requestApi<ParsedRequirement>(`${taskApiPath(taskId)}/parsed-requirement`);
  } catch (error) {
    throw new Error(`获取结构化需求失败: ${(error as Error).message}`);
  }
}

export async function fetchRetrievedContext(taskId: string): Promise<RetrievedChunk[]> {
  if (USE_MOCK_API) {
    await delay();
    return [...mockRetrievedContext];
  }
  try {
    return await requestApi<RetrievedChunk[]>(`${taskApiPath(taskId)}/retrieved-context`);
  } catch (error) {
    throw new Error(`获取检索上下文失败: ${(error as Error).message}`);
  }
}

export async function refreshTaskParse(
  taskId: string,
  payload?: {
    use_llm?: boolean;
    rag_enabled?: boolean;
    retrieval_top_k?: number;
    rerank_enabled?: boolean;
  },
): Promise<{ parsed_requirement: ParsedRequirement; parse_metadata: TaskDetailPayload["parse_metadata"] }> {
  if (USE_MOCK_API) {
    await delay();
    return {
      parsed_requirement: { ...mockParsedRequirement },
      parse_metadata: { ...mockParseMetadata },
    };
  }
  try {
    return await requestApi<{ parsed_requirement: ParsedRequirement; parse_metadata: TaskDetailPayload["parse_metadata"] }>(
      `${taskApiPath(taskId)}/parse`,
      {
        method: "POST",
        body: JSON.stringify(payload ?? {}),
      },
    );
  } catch (error) {
    throw new Error(`刷新解析失败: ${(error as Error).message}`);
  }
}

export async function startTaskAnalysis(taskId: string): Promise<AnalysisProgressPayload> {
  if (USE_MOCK_API) {
    await delay(400);
    return {
      task_id: taskId,
      kind: "analysis",
      stage: "requirement_parsed",
      percent: 45,
      status: "running",
      message: "需求解析完成，开始生成测试场景",
      updated_at: new Date().toISOString(),
      detail: {
        chunk_count: 2,
      },
    };
  }
  try {
    return await requestApi<AnalysisProgressPayload>(`${taskApiPath(taskId)}/analysis/start`, {
      method: "POST",
    });
  } catch (error) {
    throw new Error(`启动解析失败: ${(error as Error).message}`);
  }
}

export async function fetchTaskAnalysisProgress(taskId: string): Promise<AnalysisProgressPayload> {
  if (USE_MOCK_API) {
    await delay(300);
    return {
      task_id: taskId,
      kind: "analysis",
      stage: "ready",
      percent: 100,
      status: "completed",
      message: "任务解析完成，可进入详情页查看",
      updated_at: new Date().toISOString(),
      detail: {
        scenario_count: mockScenarios.length,
      },
    };
  }
  try {
    return await requestApi<AnalysisProgressPayload>(`${taskApiPath(taskId)}/analysis/progress`);
  } catch (error) {
    throw new Error(`获取解析进度失败: ${(error as Error).message}`);
  }
}

export async function fetchScenarios(taskId: string): Promise<ScenarioModel[]> {
  if (USE_MOCK_API) {
    await delay();
    return [...mockScenarios];
  }
  try {
    return await requestApi<ScenarioModel[]>(`${taskApiPath(taskId)}/scenarios`);
  } catch (error) {
    throw new Error(`获取场景失败: ${(error as Error).message}`);
  }
}

export async function fetchDsl(taskId: string): Promise<TestCaseDSL> {
  if (USE_MOCK_API) {
    await delay();
    return { ...mockTestCaseDSL };
  }
  try {
    return await requestApi<TestCaseDSL>(`${taskApiPath(taskId)}/dsl`);
  } catch (error) {
    throw new Error(`获取 DSL 失败: ${(error as Error).message}`);
  }
}

export async function fetchFeatureText(taskId: string): Promise<string> {
  if (USE_MOCK_API) {
    await delay();
    return mockTaskDetail.feature_text ?? "";
  }
  try {
    const payload = await requestApi<{ feature_text?: string }>(`${taskApiPath(taskId)}/feature`);
    return payload.feature_text ?? "";
  } catch (error) {
    throw new Error(`获取 Feature 失败: ${(error as Error).message}`);
  }
}

export async function startExecution(
  taskId: string,
  payload?: { execution_mode?: string; environment?: string; async_mode?: boolean },
): Promise<void> {
  if (USE_MOCK_API) {
    await delay(500);
    return;
  }
  try {
    await requestApi(`${taskApiPath(taskId)}/execute`, {
      method: "POST",
      body: JSON.stringify(payload ?? { execution_mode: "api", async_mode: true }),
    });
  } catch (error) {
    throw new Error(`启动执行失败: ${(error as Error).message}`);
  }
}

export async function stopExecution(taskId: string): Promise<void> {
  if (USE_MOCK_API) {
    await delay(300);
    return;
  }
  try {
    await requestApi(`${taskApiPath(taskId)}/execution/stop`, {
      method: "POST",
      body: JSON.stringify({}),
    });
  } catch (error) {
    throw new Error(`停止执行失败: ${(error as Error).message}`);
  }
}

export async function fetchExecution(taskId: string): Promise<ExecutionResult> {
  if (USE_MOCK_API) {
    await delay();
    const statuses = ["running", "running", "passed"];
    const status = statuses[Math.floor(Math.random() * statuses.length)];
    return {
      ...mockExecutionResult,
      status,
      logs: [
        ...mockExecutionResult.logs,
        {
          time: new Date().toISOString(),
          level: "INFO",
          message: status === "running" ? "任务仍在执行中..." : "任务执行完成",
        },
      ],
    };
  }
  try {
    return await requestApi<ExecutionResult>(`${taskApiPath(taskId)}/execution`);
  } catch (error) {
    throw new Error(`获取执行结果失败: ${(error as Error).message}`);
  }
}

export async function fetchValidationReport(taskId: string): Promise<ValidationReport> {
  if (USE_MOCK_API) {
    await delay();
    return { ...mockValidationReport };
  }
  try {
    return await requestApi<ValidationReport>(`${taskApiPath(taskId)}/validation-report`);
  } catch (error) {
    throw new Error(`获取校验报告失败: ${(error as Error).message}`);
  }
}

export async function fetchAnalysisReport(taskId: string): Promise<AnalysisReport> {
  if (USE_MOCK_API) {
    await delay();
    return { ...mockAnalysisReport };
  }
  try {
    return await requestApi<AnalysisReport>(`${taskApiPath(taskId)}/analysis-report`);
  } catch (error) {
    throw new Error(`获取分析报告失败: ${(error as Error).message}`);
  }
}

export async function fetchTaskArtifacts(taskId: string, options?: { shallow?: boolean }): Promise<TaskArtifactItem[]> {
  if (USE_MOCK_API) {
    await delay();
    return [...mockArtifacts];
  }
  try {
    const shallow = options?.shallow === true;
    const path = shallow ? `${taskApiPath(taskId)}/artifacts?shallow=true` : `${taskApiPath(taskId)}/artifacts`;
    const payload = await requestApi<{ task_id: string; artifacts: Array<{ type: string; content?: unknown }> }>(path);
    return payload.artifacts.map((item) => ({
      type: item.type,
      label: toArtifactLabel(item.type),
      updated_at: new Date().toISOString(),
    }));
  } catch (error) {
    throw new Error(`获取产物列表失败: ${(error as Error).message}`);
  }
}

export async function fetchTaskArtifactContent(taskId: string, artifactType: string): Promise<TaskArtifactContent> {
  if (USE_MOCK_API) {
    await delay();
    return mockArtifactContentByType[artifactType] ?? { type: artifactType, content: "暂无该类型产物内容" };
  }
  try {
    const payload = await requestApi<{ task_id: string; type: string; content: unknown }>(
      taskArtifactApiPath(taskId, artifactType),
    );
    return {
      type: payload.type ?? artifactType,
      content: payload.content,
    };
  } catch (error) {
    throw new Error(`获取产物内容失败: ${(error as Error).message}`);
  }
}

export async function fetchHistoryTasks(_params?: {
  status?: string;
  keyword?: string;
  environment?: string;
  project_id?: string;
  start_time?: string;
  end_time?: string;
  page?: number;
  page_size?: number;
}): Promise<{ items: HistoryTaskItem[]; total: number }> {
  if (USE_MOCK_API) {
    await delay();
    let items = [...mockHistoryTaskList];
    if (_params?.status) {
      items = items.filter((t) => t.status === _params.status);
    }
    if (_params?.keyword) {
      const kw = _params.keyword.toLowerCase();
      items = items.filter((t) => t.task_name.toLowerCase().includes(kw) || t.task_id.toLowerCase().includes(kw));
    }
    return { items, total: items.length };
  }
  try {
    const qp = new URLSearchParams();
    const status = _params?.status?.trim();
    const keyword = _params?.keyword?.trim();
    const environment = _params?.environment?.trim();
    const startTime = _params?.start_time?.trim();
    const endTime = _params?.end_time?.trim();
    const page = _params?.page ?? 1;
    const pageSize = Math.min(_params?.page_size ?? 100, HISTORY_PAGE_SIZE_MAX);
    if (status) qp.set("status", status);
    if (keyword) qp.set("keyword", keyword);
    if (environment) qp.set("environment", environment);
    appendProjectId(qp, _params?.project_id);
    if (startTime) qp.set("start_time", startTime);
    if (endTime) qp.set("end_time", endTime);
    qp.set("page", String(page));
    qp.set("page_size", String(pageSize));

    const payload = await requestApi<{ items: Array<Record<string, unknown>>; total: number }>(
      `/api/history/tasks?${qp.toString()}`,
    );
    const items = payload.items.map((item) => ({
      ...normalizeTaskItem(item),
      finished_at: typeof item.finished_at === "string" ? item.finished_at : undefined,
    }));
    return { items, total: payload.total };
  } catch (error) {
    throw new Error(`获取历史任务失败: ${(error as Error).message}`);
  }
}

export async function fetchExecutionHistory(_params?: {
  task_id?: string;
  status?: string;
  keyword?: string;
  environment?: string;
  project_id?: string;
  start_time?: string;
  end_time?: string;
  page?: number;
  page_size?: number;
}): Promise<{ items: ExecutionHistoryItem[]; total: number }> {
  if (USE_MOCK_API) {
    await delay();
    const items: ExecutionHistoryItem[] = [...mockHistoryTaskList].map((task, index) => ({
      task_id: task.task_id,
      task_name: task.task_name,
      environment: "test",
      execution_mode: "api",
      status: task.status,
      executor: "api-runner",
      executed_at: task.finished_at ?? task.created_at,
      metrics: {
        step_count: 20 + (index % 8),
        failed_step_count: task.status === "failed" ? (index % 3) + 1 : 0,
        avg_elapsed_ms: 800 + index * 120,
      },
      analysis_summary: {
        success_rate: task.status === "passed" ? 100 : task.status === "failed" ? 75 : 90,
        failed_steps: task.status === "failed" ? (index % 3) + 1 : 0,
        avg_elapsed_ms: 800 + index * 120,
      },
    }));
    return { items, total: items.length };
  }
  try {
    const qp = new URLSearchParams();
    const taskId = _params?.task_id?.trim();
    const status = _params?.status?.trim();
    const keyword = _params?.keyword?.trim();
    const environment = _params?.environment?.trim();
    const startTime = _params?.start_time?.trim();
    const endTime = _params?.end_time?.trim();
    const page = _params?.page ?? 1;
    const pageSize = Math.min(_params?.page_size ?? 100, HISTORY_PAGE_SIZE_MAX);
    if (taskId) qp.set("task_id", taskId);
    if (status) qp.set("status", status);
    if (keyword) qp.set("keyword", keyword);
    if (environment) qp.set("environment", environment);
    appendProjectId(qp, _params?.project_id);
    if (startTime) qp.set("start_time", startTime);
    if (endTime) qp.set("end_time", endTime);
    qp.set("page", String(page));
    qp.set("page_size", String(pageSize));

    const payload = await requestApi<{ items: Array<Record<string, unknown>>; total: number }>(
      `/api/history/executions?${qp.toString()}`,
    );
    const items: ExecutionHistoryItem[] = payload.items.map((item) => ({
      task_id: String(item.task_id ?? ""),
      task_name: String(item.task_name ?? ""),
      environment: String(item.environment ?? "default"),
      execution_mode: String(item.execution_mode ?? "api"),
      status: String(item.status ?? "unknown"),
      executor: String(item.executor ?? "api-runner"),
      executed_at: String(item.executed_at ?? ""),
      metrics: typeof item.metrics === "object" && item.metrics !== null ? (item.metrics as Record<string, unknown>) : {},
      analysis_summary:
        typeof item.analysis_summary === "object" && item.analysis_summary !== null
          ? (item.analysis_summary as ExecutionHistoryItem["analysis_summary"])
          : {},
    }));
    return { items, total: payload.total };
  } catch (error) {
    throw new Error(`获取执行历史失败: ${(error as Error).message}`);
  }
}

export async function fetchTaskDashboard(taskId: string): Promise<TaskDashboardPayload> {
  if (USE_MOCK_API) {
    await delay();
    return {
      task: mockTaskDetail.task_context,
      analysis_report: mockAnalysisReport,
      summary: mockAnalysisReport.summary,
      chart_data: mockAnalysisReport.chart_data,
      findings: mockAnalysisReport.findings,
      task_summary_text: "当前为 mock 单任务看板摘要。",
      failure_reasons: [],
    };
  }
  try {
    return await requestApi<TaskDashboardPayload>(`${taskApiPath(taskId)}/dashboard`);
  } catch (error) {
    throw new Error(`获取单任务看板失败: ${(error as Error).message}`);
  }
}

export async function fetchPreflightCheck(
  taskId: string,
  payload?: {
    environment?: string;
    checks?: string[];
    latency_threshold_ms?: number;
  },
): Promise<PreflightCheckPayload> {
  if (USE_MOCK_API) {
    await delay();
    return {
      task_id: taskId,
      overall_status: "passed",
      blocking: false,
      checks: [
        { name: "base_url_reachable", status: "passed", elapsed_ms: 42, message: "base_url reachable" },
        { name: "auth_config_valid", status: "warning", elapsed_ms: 2, message: "no explicit auth configured" },
      ],
      blocking_issues: [],
      suggestions: [],
    };
  }
  return await requestApi<PreflightCheckPayload>(`${taskApiPath(taskId)}/preflight-check`, {
    method: "POST",
    body: JSON.stringify(
      payload ?? {
        checks: ["base_url_reachable", "auth_config_valid", "core_endpoints_reachable", "latency_budget"],
        latency_threshold_ms: 1500,
      },
    ),
  });
}

export async function fetchExecutionExplanations(
  taskId: string,
  params?: { execution_id?: string; top_n?: number },
): Promise<ExecutionExplanationPayload> {
  if (USE_MOCK_API) {
    await delay();
    return {
      task_id: taskId,
      summary: { failed_scenarios: 1, failed_steps: 2 },
      top_reasons: ["field_mapping"],
      failure_groups: [
        {
          category: "field_mapping",
          count: 1,
          examples: ["json.id not found"],
          recommended_actions: ["调整 save_context 字段路径映射"],
        },
      ],
    };
  }
  const qp = new URLSearchParams();
  if (params?.execution_id) qp.set("execution_id", params.execution_id);
  if (typeof params?.top_n === "number") qp.set("top_n", String(params.top_n));
  const suffix = qp.toString() ? `?${qp.toString()}` : "";
  return await requestApi<ExecutionExplanationPayload>(`${taskApiPath(taskId)}/execution/explanations${suffix}`);
}

export async function fetchRegressionDiff(
  taskId: string,
  params?: { base_execution_id?: string; target_execution_id?: string },
): Promise<RegressionDiffPayload> {
  if (USE_MOCK_API) {
    await delay();
    return {
      task_id: taskId,
      verdict: "unchanged",
      metrics_diff: {},
      failure_type_diff: [],
    };
  }
  const buildFallbackDiff = async (): Promise<RegressionDiffPayload> => {
    const payload = await fetchExecutionHistory({
      task_id: taskId,
      page: 1,
      page_size: HISTORY_PAGE_SIZE_MAX,
    });
    const items = [...payload.items]
      .filter((item) => item.task_id === taskId)
      .sort((a, b) => new Date(a.executed_at).getTime() - new Date(b.executed_at).getTime());

    const latest = items[items.length - 1];
    const previous = items[items.length - 2];
    if (!latest || !previous) {
      return {
        task_id: taskId,
        verdict: "unchanged",
        metrics_diff: { note: "insufficient_history", compared_runs: items.length },
        failure_type_diff: [],
      };
    }

    const latestFailedSteps = Number(latest.analysis_summary?.failed_steps ?? latest.metrics?.failed_step_count ?? 0);
    const previousFailedSteps = Number(previous.analysis_summary?.failed_steps ?? previous.metrics?.failed_step_count ?? 0);
    const latestSuccessRate = Number(latest.analysis_summary?.success_rate ?? 0);
    const previousSuccessRate = Number(previous.analysis_summary?.success_rate ?? 0);
    const latestAvgMs = Number(latest.analysis_summary?.avg_elapsed_ms ?? latest.metrics?.avg_elapsed_ms ?? 0);
    const previousAvgMs = Number(previous.analysis_summary?.avg_elapsed_ms ?? previous.metrics?.avg_elapsed_ms ?? 0);

    const failedStepsDelta = latestFailedSteps - previousFailedSteps;
    const successRateDelta = latestSuccessRate - previousSuccessRate;
    const avgElapsedDelta = latestAvgMs - previousAvgMs;

    let verdict: RegressionDiffPayload["verdict"] = "unchanged";
    if (failedStepsDelta > 0 || successRateDelta < 0) {
      verdict = "regressed";
    } else if (failedStepsDelta < 0 || successRateDelta > 0) {
      verdict = "improved";
    }

    return {
      task_id: taskId,
      verdict,
      metrics_diff: {
        base_executed_at: previous.executed_at,
        target_executed_at: latest.executed_at,
        failed_steps_delta: failedStepsDelta,
        success_rate_delta: Number(successRateDelta.toFixed(2)),
        avg_elapsed_ms_delta: Number(avgElapsedDelta.toFixed(2)),
      },
      failure_type_diff: [
        {
          category: "failed_steps",
          base: previousFailedSteps,
          target: latestFailedSteps,
          delta: failedStepsDelta,
        },
      ],
    };
  };

  if (regressionDiffApiAvailable === false) {
    return await buildFallbackDiff();
  }

  const qp = new URLSearchParams();
  if (params?.base_execution_id) qp.set("base_execution_id", params.base_execution_id);
  if (params?.target_execution_id) qp.set("target_execution_id", params.target_execution_id);
  const suffix = qp.toString() ? `?${qp.toString()}` : "";

  try {
    const payload = await requestApi<RegressionDiffPayload>(`${taskApiPath(taskId)}/regression-diff${suffix}`);
    regressionDiffApiAvailable = true;
    return payload;
  } catch (error) {
    const message = (error as Error).message || "";
    if (message.includes("HTTP 409")) {
      regressionDiffApiAvailable = true;
      return {
        task_id: taskId,
        verdict: "unchanged",
        metrics_diff: { note: "not_ready" },
        failure_type_diff: [],
      };
    }
    if (message.includes("HTTP 404")) {
      regressionDiffApiAvailable = false;
      return await buildFallbackDiff();
    }
    throw error;
  }
}
