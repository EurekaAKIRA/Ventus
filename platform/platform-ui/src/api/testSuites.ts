import type { TestSuiteAssetExecutionPayload, TestSuiteAssetListPayload, TestSuiteAssetPayload } from "../types";
import { requestApi } from "./client";

export type SaveTestSuiteAssetPayload = {
  project_id: string;
  name: string;
  description?: string;
  status?: string;
  source?: string;
  case_ids?: string[];
  tags?: string[];
};

export async function fetchTestSuiteAssets(params: {
  project_id: string;
  status?: string;
  keyword?: string;
  page?: number;
  page_size?: number;
}): Promise<TestSuiteAssetListPayload> {
  const qp = new URLSearchParams();
  qp.set("project_id", params.project_id);
  if (params.status) qp.set("status", params.status);
  if (params.keyword) qp.set("keyword", params.keyword);
  qp.set("page", String(params.page ?? 1));
  qp.set("page_size", String(params.page_size ?? 50));
  return await requestApi<TestSuiteAssetListPayload>(`/api/test-suite-assets?${qp.toString()}`);
}

export async function saveTestSuiteAsset(payload: SaveTestSuiteAssetPayload): Promise<TestSuiteAssetPayload> {
  return await requestApi<TestSuiteAssetPayload>("/api/test-suite-assets", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateTestSuiteAsset(
  suiteId: string,
  payload: Partial<Omit<SaveTestSuiteAssetPayload, "project_id">>,
): Promise<TestSuiteAssetPayload> {
  return await requestApi<TestSuiteAssetPayload>(`/api/test-suite-assets/${encodeURIComponent(suiteId)}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function deleteTestSuiteAsset(suiteId: string): Promise<{ id: string; deleted: boolean }> {
  return await requestApi<{ id: string; deleted: boolean }>(`/api/test-suite-assets/${encodeURIComponent(suiteId)}`, {
    method: "DELETE",
  });
}

export async function executeTestSuiteAsset(
  suiteId: string,
  payload: {
    execution_mode?: string;
    environment?: string;
    base_url?: string;
    stop_on_failure?: boolean;
  },
): Promise<TestSuiteAssetExecutionPayload> {
  return await requestApi<TestSuiteAssetExecutionPayload>(`/api/test-suite-assets/${encodeURIComponent(suiteId)}/execute`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
