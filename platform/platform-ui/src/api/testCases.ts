import type { TestCaseAssetExecutionPayload, TestCaseAssetImportPayload, TestCaseAssetListPayload, TestCaseAssetPayload } from "../types";
import { requestApi } from "./client";

export type SaveTestCaseAssetPayload = {
  project_id: string;
  case_key?: string;
  name: string;
  description?: string;
  priority?: string;
  status?: string;
  source?: string;
  tags?: string[];
  dsl_scenario?: unknown;
  assertions?: unknown[];
};

export async function fetchTestCaseAssets(params: {
  project_id: string;
  status?: string;
  keyword?: string;
  page?: number;
  page_size?: number;
}): Promise<TestCaseAssetListPayload> {
  const qp = new URLSearchParams();
  qp.set("project_id", params.project_id);
  if (params.status) qp.set("status", params.status);
  if (params.keyword) qp.set("keyword", params.keyword);
  qp.set("page", String(params.page ?? 1));
  qp.set("page_size", String(params.page_size ?? 50));
  return await requestApi<TestCaseAssetListPayload>(`/api/test-case-assets?${qp.toString()}`);
}

export async function saveTestCaseAsset(payload: SaveTestCaseAssetPayload): Promise<TestCaseAssetPayload> {
  return await requestApi<TestCaseAssetPayload>("/api/test-case-assets", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateTestCaseAsset(
  caseId: string,
  payload: Partial<Omit<SaveTestCaseAssetPayload, "project_id" | "case_key">>,
): Promise<TestCaseAssetPayload> {
  return await requestApi<TestCaseAssetPayload>(`/api/test-case-assets/${encodeURIComponent(caseId)}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function deleteTestCaseAsset(caseId: string): Promise<{ id: string; deleted: boolean }> {
  return await requestApi<{ id: string; deleted: boolean }>(`/api/test-case-assets/${encodeURIComponent(caseId)}`, {
    method: "DELETE",
  });
}

export async function importTestCaseAssetsFromTask(taskId: string, projectId?: string): Promise<TestCaseAssetImportPayload> {
  return await requestApi<TestCaseAssetImportPayload>(`/api/tasks/${encodeURIComponent(taskId)}/test-case-assets/import`, {
    method: "POST",
    body: JSON.stringify({ project_id: projectId }),
  });
}

export async function executeTestCaseAsset(
  caseId: string,
  payload: {
    execution_mode?: string;
    environment?: string;
    base_url?: string;
  },
): Promise<TestCaseAssetExecutionPayload> {
  return await requestApi<TestCaseAssetExecutionPayload>(`/api/test-case-assets/${encodeURIComponent(caseId)}/execute`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
