import type {
  TaskListItem,
  TaskDetailPayload,
  ParsedRequirement,
  ScenarioModel,
  TestCaseDSL,
  ExecutionResult,
  ValidationReport,
  AnalysisReport,
  TaskContext,
  RetrievedChunk,
} from "../types";
import {
  mockTaskList,
  mockTaskDetail,
  mockParsedRequirement,
  mockRetrievedContext,
  mockScenarios,
  mockTestCaseDSL,
  mockExecutionResult,
  mockValidationReport,
  mockAnalysisReport,
} from "../mocks";

const delay = (ms = 400) => new Promise((r) => setTimeout(r, ms));

export async function fetchTaskList(_params?: {
  status?: string;
  keyword?: string;
  page?: number;
  page_size?: number;
}): Promise<{ items: TaskListItem[]; total: number }> {
  await delay();
  let items = [...mockTaskList];
  if (_params?.status) {
    items = items.filter((t) => t.status === _params.status);
  }
  if (_params?.keyword) {
    const kw = _params.keyword.toLowerCase();
    items = items.filter(
      (t) =>
        t.task_name.toLowerCase().includes(kw) ||
        t.task_id.toLowerCase().includes(kw),
    );
  }
  return { items, total: items.length };
}

export async function fetchTaskDetail(
  _taskId: string,
): Promise<TaskDetailPayload> {
  await delay();
  return { ...mockTaskDetail };
}

export async function createTask(payload: {
  task_name: string;
  source_type: string;
  requirement_text?: string;
  source_path?: string;
  target_system?: string;
  environment?: string;
}): Promise<TaskContext> {
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
  };
}

export async function deleteTask(_taskId: string): Promise<void> {
  await delay(300);
}

export async function fetchParsedRequirement(
  _taskId: string,
): Promise<ParsedRequirement> {
  await delay();
  return { ...mockParsedRequirement };
}

export async function fetchRetrievedContext(
  _taskId: string,
): Promise<RetrievedChunk[]> {
  await delay();
  return [...mockRetrievedContext];
}

export async function fetchScenarios(
  _taskId: string,
): Promise<ScenarioModel[]> {
  await delay();
  return [...mockScenarios];
}

export async function fetchDsl(_taskId: string): Promise<TestCaseDSL> {
  await delay();
  return { ...mockTestCaseDSL };
}

export async function fetchFeatureText(_taskId: string): Promise<string> {
  await delay();
  return mockTaskDetail.feature_text ?? "";
}

export async function startExecution(
  _taskId: string,
  _payload?: { execution_mode?: string; environment?: string },
): Promise<void> {
  await delay(500);
}

export async function fetchExecution(
  _taskId: string,
): Promise<ExecutionResult> {
  await delay();
  return { ...mockExecutionResult };
}

export async function fetchValidationReport(
  _taskId: string,
): Promise<ValidationReport> {
  await delay();
  return { ...mockValidationReport };
}

export async function fetchAnalysisReport(
  _taskId: string,
): Promise<AnalysisReport> {
  await delay();
  return { ...mockAnalysisReport };
}
