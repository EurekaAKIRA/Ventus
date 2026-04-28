import type {
  InterfaceAssetDebugPayload,
  InterfaceAssetImportPayload,
  InterfaceAssetListPayload,
  InterfaceAssetOpenApiImportPayload,
  InterfaceAssetPayload,
} from "../types";
import { requestApi } from "./client";

export type SaveInterfaceAssetPayload = {
  project_id: string;
  method: string;
  path: string;
  name?: string;
  description?: string;
  source?: string;
  status?: string;
  version?: string;
  tags?: string[];
  request_example?: unknown;
  response_example?: unknown;
  schema?: unknown;
};

export async function fetchInterfaceAssets(params: {
  project_id: string;
  method?: string;
  status?: string;
  keyword?: string;
  page?: number;
  page_size?: number;
}): Promise<InterfaceAssetListPayload> {
  const qp = new URLSearchParams();
  qp.set("project_id", params.project_id);
  if (params.method) qp.set("method", params.method);
  if (params.status) qp.set("status", params.status);
  if (params.keyword) qp.set("keyword", params.keyword);
  qp.set("page", String(params.page ?? 1));
  qp.set("page_size", String(params.page_size ?? 50));
  return await requestApi<InterfaceAssetListPayload>(`/api/interface-assets?${qp.toString()}`);
}

export async function saveInterfaceAsset(payload: SaveInterfaceAssetPayload): Promise<InterfaceAssetPayload> {
  return await requestApi<InterfaceAssetPayload>("/api/interface-assets", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateInterfaceAsset(
  assetId: string,
  payload: Partial<Omit<SaveInterfaceAssetPayload, "project_id" | "method" | "path">>,
): Promise<InterfaceAssetPayload> {
  return await requestApi<InterfaceAssetPayload>(`/api/interface-assets/${encodeURIComponent(assetId)}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function deleteInterfaceAsset(assetId: string): Promise<{ id: string; deleted: boolean }> {
  return await requestApi<{ id: string; deleted: boolean }>(`/api/interface-assets/${encodeURIComponent(assetId)}`, {
    method: "DELETE",
  });
}

export async function importInterfaceAssetsFromTask(taskId: string, projectId?: string): Promise<InterfaceAssetImportPayload> {
  return await requestApi<InterfaceAssetImportPayload>(`/api/tasks/${encodeURIComponent(taskId)}/interface-assets/import`, {
    method: "POST",
    body: JSON.stringify({ project_id: projectId }),
  });
}

export async function importInterfaceAssetsFromOpenApi(payload: {
  project_id: string;
  content: string;
  source_name?: string;
  version?: string;
  overwrite_examples?: boolean;
}): Promise<InterfaceAssetOpenApiImportPayload> {
  return await requestApi<InterfaceAssetOpenApiImportPayload>("/api/interface-assets/import/openapi", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function debugInterfaceAsset(
  assetId: string,
  payload: {
    project_id?: string;
    environment?: string;
    base_url?: string;
    headers?: Record<string, string>;
    params?: Record<string, unknown>;
    json_body?: unknown;
    raw_body?: string;
    timeout?: number;
  },
): Promise<InterfaceAssetDebugPayload> {
  return await requestApi<InterfaceAssetDebugPayload>(`/api/interface-assets/${encodeURIComponent(assetId)}/debug`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
