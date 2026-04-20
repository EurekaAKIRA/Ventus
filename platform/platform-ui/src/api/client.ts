const API_BASE_URL =
  (import.meta.env.VITE_PLATFORM_API_BASE as string | undefined)?.trim() || "http://127.0.0.1:8001";

type ApiEnvelope<T> = {
  success: boolean;
  code: string;
  message: string;
  data: T;
  timestamp: string;
};

const ACCESS_TOKEN_KEY = "ventus_access_token";
const REFRESH_TOKEN_KEY = "ventus_refresh_token";
const CURRENT_PROJECT_ID_KEY = "ventus_current_project_id";
export const AUTH_REFRESHED_EVENT = "ventus:auth-refreshed";
export const AUTH_EXPIRED_EVENT = "ventus:auth-expired";

type RefreshPayload = {
  access_token?: string;
  refresh_token?: string;
};

let refreshInFlight: Promise<string | null> | null = null;

export function getApiBaseUrl(): string {
  return API_BASE_URL;
}

export function getStoredAccessToken(): string {
  return window.localStorage.getItem(ACCESS_TOKEN_KEY) ?? "";
}

export function setStoredAccessToken(token: string): void {
  if (token.trim()) {
    window.localStorage.setItem(ACCESS_TOKEN_KEY, token.trim());
  } else {
    window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  }
}

export function clearStoredAccessToken(): void {
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
}

export function getStoredRefreshToken(): string {
  return window.localStorage.getItem(REFRESH_TOKEN_KEY) ?? "";
}

export function setStoredRefreshToken(token: string): void {
  if (token.trim()) {
    window.localStorage.setItem(REFRESH_TOKEN_KEY, token.trim());
  } else {
    window.localStorage.removeItem(REFRESH_TOKEN_KEY);
  }
}

export function clearStoredRefreshToken(): void {
  window.localStorage.removeItem(REFRESH_TOKEN_KEY);
}

export function getStoredCurrentProjectId(): string {
  return window.localStorage.getItem(CURRENT_PROJECT_ID_KEY) ?? "";
}

export function setStoredCurrentProjectId(projectId: string): void {
  if (projectId.trim()) {
    window.localStorage.setItem(CURRENT_PROJECT_ID_KEY, projectId.trim());
  } else {
    window.localStorage.removeItem(CURRENT_PROJECT_ID_KEY);
  }
}

export function clearStoredCurrentProjectId(): void {
  window.localStorage.removeItem(CURRENT_PROJECT_ID_KEY);
}

function dispatchBrowserEvent(name: string, detail?: unknown): void {
  if (typeof window === "undefined") {
    return;
  }
  window.dispatchEvent(new CustomEvent(name, { detail }));
}

function clearStoredAuthSession(): void {
  clearStoredAccessToken();
  clearStoredRefreshToken();
}

async function performTokenRefresh(): Promise<string | null> {
  const refreshToken = getStoredRefreshToken();
  if (!refreshToken) {
    clearStoredAuthSession();
    dispatchBrowserEvent(AUTH_EXPIRED_EVENT);
    return null;
  }
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const payload = (await response.json()) as ApiEnvelope<RefreshPayload>;
        const nextAccessToken = String(payload.data?.access_token ?? "").trim();
        const nextRefreshToken = String(payload.data?.refresh_token ?? "").trim() || refreshToken;
        if (!nextAccessToken) {
          throw new Error("missing refreshed access token");
        }
        setStoredAccessToken(nextAccessToken);
        setStoredRefreshToken(nextRefreshToken);
        dispatchBrowserEvent(AUTH_REFRESHED_EVENT, payload.data);
        return nextAccessToken;
      } catch {
        clearStoredAuthSession();
        dispatchBrowserEvent(AUTH_EXPIRED_EVENT);
        return null;
      } finally {
        refreshInFlight = null;
      }
    })();
  }
  return await refreshInFlight;
}

async function doRequest(path: string, init?: RequestInit, overrideAccessToken?: string): Promise<Response> {
  const method = String(init?.method ?? "GET").toUpperCase();
  const hasBody = init?.body !== undefined && init?.body !== null;
  const mergedHeaders = new Headers(init?.headers ?? {});
  if (hasBody && !mergedHeaders.has("Content-Type")) {
    mergedHeaders.set("Content-Type", "application/json");
  }
  const accessToken = overrideAccessToken ?? getStoredAccessToken();
  if (accessToken && !mergedHeaders.has("Authorization")) {
    mergedHeaders.set("Authorization", `Bearer ${accessToken}`);
  }
  return await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    method,
    headers: mergedHeaders,
  });
}

export async function requestApi<T>(path: string, init?: RequestInit): Promise<T> {
  const normalizedPath = path.trim();
  const shouldTryRefresh =
    normalizedPath !== "/api/auth/login" &&
    normalizedPath !== "/api/auth/register" &&
    normalizedPath !== "/api/auth/refresh" &&
    normalizedPath !== "/api/auth/logout";
  let response = await doRequest(normalizedPath, init);
  if (response.status === 401 && shouldTryRefresh) {
    const nextAccessToken = await performTokenRefresh();
    if (nextAccessToken) {
      response = await doRequest(normalizedPath, init, nextAccessToken);
    }
  }
  if (!response.ok) {
    let detail = "";
    try {
      const errorPayload = (await response.json()) as Partial<ApiEnvelope<unknown>>;
      detail = String(errorPayload.message ?? "");
    } catch {
      detail = "";
    }
    throw new Error(detail ? `HTTP ${response.status}: ${detail}` : `HTTP ${response.status}`);
  }
  const payload = (await response.json()) as ApiEnvelope<T>;
  return payload.data;
}
