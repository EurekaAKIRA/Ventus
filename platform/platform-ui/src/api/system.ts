import type { AuditLogListPayload, EnvironmentPayload, PreflightCheckPayload } from "../types";
import { requestApi } from "./client";

export async function fetchEnvironments(projectId?: string): Promise<EnvironmentPayload[]> {
  const qp = new URLSearchParams();
  if (projectId) {
    qp.set("project_id", projectId);
  }
  const suffix = qp.toString() ? `?${qp.toString()}` : "";
  return await requestApi<EnvironmentPayload[]>(`/api/environments${suffix}`);
}

export async function saveEnvironment(payload: EnvironmentPayload): Promise<EnvironmentPayload> {
  return await requestApi<EnvironmentPayload>("/api/environments", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateEnvironment(name: string, payload: EnvironmentPayload): Promise<EnvironmentPayload> {
  return await requestApi<EnvironmentPayload>(`/api/environments/${encodeURIComponent(name)}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function probeEnvironment(payload: EnvironmentPayload): Promise<PreflightCheckPayload & { environment_name?: string; project_id?: string }> {
  return await requestApi<PreflightCheckPayload & { environment_name?: string; project_id?: string }>("/api/environments/probe", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function deleteEnvironment(name: string, projectId?: string): Promise<{ name: string; deleted: boolean }> {
  const qp = new URLSearchParams();
  if (projectId) {
    qp.set("project_id", projectId);
  }
  const suffix = qp.toString() ? `?${qp.toString()}` : "";
  return await requestApi<{ name: string; deleted: boolean }>(`/api/environments/${encodeURIComponent(name)}${suffix}`, {
    method: "DELETE",
  });
}

export async function fetchAuditLogs(params?: {
  action?: string;
  resource_type?: string;
  keyword?: string;
  actor?: string;
  user_id?: string;
  start_time?: string;
  end_time?: string;
  page?: number;
  page_size?: number;
}): Promise<AuditLogListPayload> {
  const qp = new URLSearchParams();
  const action = String(params?.action ?? "").trim();
  const resourceType = String(params?.resource_type ?? "").trim();
  const keyword = String(params?.keyword ?? "").trim();
  const actor = String(params?.actor ?? "").trim();
  const userId = String(params?.user_id ?? "").trim();
  const startTime = String(params?.start_time ?? "").trim();
  const endTime = String(params?.end_time ?? "").trim();
  if (action) {
    qp.set("action", action);
  }
  if (resourceType) {
    qp.set("resource_type", resourceType);
  }
  if (keyword) {
    qp.set("keyword", keyword);
  }
  if (actor) {
    qp.set("actor", actor);
  }
  if (userId) {
    qp.set("user_id", userId);
  }
  if (startTime) {
    qp.set("start_time", startTime);
  }
  if (endTime) {
    qp.set("end_time", endTime);
  }
  if (typeof params?.page === "number") {
    qp.set("page", String(params.page));
  }
  if (typeof params?.page_size === "number") {
    qp.set("page_size", String(params.page_size));
  }
  const suffix = qp.toString() ? `?${qp.toString()}` : "";
  return await requestApi<AuditLogListPayload>(`/api/audit/logs${suffix}`);
}
