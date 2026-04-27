import type { DefectListPayload, DefectPayload } from "../types";
import { getStoredCurrentProjectId, requestApi } from "./client";

function resolveProjectId(projectId?: string) {
  return String(projectId ?? getStoredCurrentProjectId()).trim();
}

export async function fetchDefects(params: {
  project_id?: string;
  status?: string;
  severity?: string;
  keyword?: string;
  task_id?: string;
  assignee_user_id?: string;
  page?: number;
  page_size?: number;
}): Promise<DefectListPayload> {
  const projectId = resolveProjectId(params.project_id);
  if (!projectId) {
    throw new Error("请选择项目后再查看缺陷");
  }
  const qp = new URLSearchParams();
  qp.set("project_id", projectId);
  if (params.status) qp.set("status", params.status);
  if (params.severity) qp.set("severity", params.severity);
  if (params.keyword) qp.set("keyword", params.keyword);
  if (params.task_id) qp.set("task_id", params.task_id);
  if (params.assignee_user_id) qp.set("assignee_user_id", params.assignee_user_id);
  qp.set("page", String(params.page ?? 1));
  qp.set("page_size", String(params.page_size ?? 20));
  return await requestApi<DefectListPayload>(`/api/defects?${qp.toString()}`);
}

export async function createDefect(payload: {
  project_id?: string;
  task_id?: string;
  title: string;
  description?: string;
  severity?: string;
  status?: string;
  source?: string;
  assignee_user_id?: string;
  reproduction_steps?: string;
  expected_result?: string;
  actual_result?: string;
}): Promise<DefectPayload> {
  const projectId = resolveProjectId(payload.project_id);
  if (!projectId) {
    throw new Error("请选择项目后再创建缺陷");
  }
  return await requestApi<DefectPayload>("/api/defects", {
    method: "POST",
    body: JSON.stringify({
      ...payload,
      project_id: projectId,
    }),
  });
}

export async function updateDefect(
  defectId: string,
  payload: {
    task_id?: string | null;
    clear_task?: boolean;
    title?: string;
    description?: string;
    severity?: string;
    status?: string;
    source?: string;
    assignee_user_id?: string | null;
    clear_assignee?: boolean;
    reproduction_steps?: string;
    expected_result?: string;
    actual_result?: string;
  },
): Promise<DefectPayload> {
  return await requestApi<DefectPayload>(`/api/defects/${defectId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function fetchDefect(defectId: string): Promise<DefectPayload> {
  return await requestApi<DefectPayload>(`/api/defects/${defectId}`);
}
