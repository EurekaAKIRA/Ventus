import type { AuthLoginPayload, AuthMePayload, AuthRegisterPayload, CreateProjectPayload, ProjectMemberPayload, ProjectSummary, UserProfile } from "../types";
import { requestApi } from "./client";

export async function registerUser(payload: {
  username: string;
  password: string;
  email?: string;
  display_name?: string;
}): Promise<AuthRegisterPayload> {
  return await requestApi<AuthRegisterPayload>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function loginUser(payload: {
  username: string;
  password: string;
  client_type?: string;
}): Promise<AuthLoginPayload> {
  return await requestApi<AuthLoginPayload>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function refreshAuthToken(refreshToken: string): Promise<AuthLoginPayload> {
  return await requestApi<AuthLoginPayload>("/api/auth/refresh", {
    method: "POST",
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
}

export async function logoutUser(): Promise<{ logged_out: boolean }> {
  return await requestApi<{ logged_out: boolean }>("/api/auth/logout", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function fetchAuthMe(): Promise<AuthMePayload> {
  return await requestApi<AuthMePayload>("/api/auth/me");
}

export async function updateMyProfile(payload: {
  display_name?: string;
  email?: string;
  avatar_url?: string;
}): Promise<UserProfile> {
  return await requestApi<UserProfile>("/api/users/me", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function uploadMyAvatar(file: File): Promise<UserProfile> {
  return await requestApi<UserProfile>("/api/users/me/avatar", {
    method: "POST",
    headers: {
      "Content-Type": file.type || "application/octet-stream",
    },
    body: file,
  });
}

export async function searchUsers(params?: { keyword?: string; limit?: number }): Promise<UserProfile[]> {
  const qp = new URLSearchParams();
  const keyword = String(params?.keyword ?? "").trim();
  if (keyword) {
    qp.set("keyword", keyword);
  }
  if (typeof params?.limit === "number") {
    qp.set("limit", String(params.limit));
  }
  const suffix = qp.toString() ? `?${qp.toString()}` : "";
  return await requestApi<UserProfile[]>(`/api/users${suffix}`);
}

export async function fetchProjects(): Promise<ProjectSummary[]> {
  return await requestApi<ProjectSummary[]>("/api/projects");
}

export async function createProject(payload: {
  name: string;
  description?: string;
}): Promise<CreateProjectPayload> {
  return await requestApi<CreateProjectPayload>("/api/projects", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchProject(projectId: string): Promise<{ project: ProjectSummary; members: ProjectMemberPayload[] }> {
  return await requestApi<{ project: ProjectSummary; members: ProjectMemberPayload[] }>(`/api/projects/${projectId}`);
}

export async function addProjectMember(
  projectId: string,
  payload: { username: string; role: string },
): Promise<ProjectMemberPayload> {
  return await requestApi<ProjectMemberPayload>(`/api/projects/${projectId}/members`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
