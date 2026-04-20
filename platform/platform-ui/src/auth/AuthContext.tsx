import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { PropsWithChildren } from "react";
import { message } from "antd";
import type { AuthLoginPayload, ProjectSummary, UserProfile } from "../types";
import {
  AUTH_EXPIRED_EVENT,
  AUTH_REFRESHED_EVENT,
  clearStoredAccessToken,
  clearStoredCurrentProjectId,
  clearStoredRefreshToken,
  getStoredAccessToken,
  getStoredCurrentProjectId,
  getStoredRefreshToken,
  setStoredAccessToken,
  setStoredCurrentProjectId,
  setStoredRefreshToken,
} from "../api/client";
import { fetchAuthMe, loginUser, logoutUser, registerUser, createProject as createProjectApi } from "../api/auth";

type AuthContextValue = {
  ready: boolean;
  isAuthenticated: boolean;
  user: UserProfile | null;
  projects: ProjectSummary[];
  currentProjectId: string;
  setCurrentProjectId: (projectId: string) => void;
  login: (payload: { username: string; password: string }) => Promise<void>;
  register: (payload: { username: string; password: string; email?: string; display_name?: string }) => Promise<void>;
  logout: () => Promise<void>;
  reloadProfile: () => Promise<void>;
  createProject: (payload: { name: string; description?: string }) => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function normalizeProjectSelection(projects: ProjectSummary[], preferredProjectId: string): string {
  if (preferredProjectId && projects.some((item) => item.id === preferredProjectId)) {
    return preferredProjectId;
  }
  return projects[0]?.id ?? "";
}

export function AuthProvider({ children }: PropsWithChildren) {
  const [ready, setReady] = useState(false);
  const [user, setUser] = useState<UserProfile | null>(null);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [currentProjectId, setCurrentProjectIdState] = useState(getStoredCurrentProjectId());

  const applyAuthPayload = (payload: AuthLoginPayload) => {
    setStoredAccessToken(payload.access_token);
    setStoredRefreshToken(payload.refresh_token ?? getStoredRefreshToken());
    const nextProjects = payload.projects ?? [];
    setUser(payload.user ?? null);
    setProjects(nextProjects);
    const nextProjectId = normalizeProjectSelection(nextProjects, getStoredCurrentProjectId() || currentProjectId);
    setCurrentProjectIdState(nextProjectId);
    setStoredCurrentProjectId(nextProjectId);
  };

  const clearAuthState = () => {
    clearStoredAccessToken();
    clearStoredRefreshToken();
    clearStoredCurrentProjectId();
    setUser(null);
    setProjects([]);
    setCurrentProjectIdState("");
  };

  const reloadProfile = async () => {
    const token = getStoredAccessToken();
    if (!token) {
      clearAuthState();
      return;
    }
    try {
      const payload = await fetchAuthMe();
      setUser(payload.user ?? null);
      const nextProjects = payload.projects ?? [];
      setProjects(nextProjects);
      const nextProjectId = normalizeProjectSelection(nextProjects, getStoredCurrentProjectId());
      setCurrentProjectIdState(nextProjectId);
      setStoredCurrentProjectId(nextProjectId);
    } catch {
      clearAuthState();
    }
  };

  useEffect(() => {
    void (async () => {
      await reloadProfile();
      setReady(true);
    })();
  }, []);

  useEffect(() => {
    const handleAuthExpired = () => {
      clearAuthState();
    };
    const handleAuthRefreshed = () => {
      void reloadProfile();
    };
    window.addEventListener(AUTH_EXPIRED_EVENT, handleAuthExpired);
    window.addEventListener(AUTH_REFRESHED_EVENT, handleAuthRefreshed);
    return () => {
      window.removeEventListener(AUTH_EXPIRED_EVENT, handleAuthExpired);
      window.removeEventListener(AUTH_REFRESHED_EVENT, handleAuthRefreshed);
    };
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      ready,
      isAuthenticated: Boolean(user),
      user,
      projects,
      currentProjectId,
      setCurrentProjectId: (projectId: string) => {
        setCurrentProjectIdState(projectId);
        setStoredCurrentProjectId(projectId);
      },
      login: async (payload) => {
        const authPayload = await loginUser(payload);
        applyAuthPayload(authPayload);
      },
      register: async (payload) => {
        const registered = await registerUser(payload);
        if (registered.user?.username) {
          const authPayload = await loginUser({
            username: registered.user.username,
            password: payload.password,
          });
          applyAuthPayload(authPayload);
        }
      },
      logout: async () => {
        try {
          if (getStoredAccessToken()) {
            await logoutUser();
          }
        } catch {
          message.warning("服务端退出失败，已清理本地登录态");
        } finally {
          clearAuthState();
        }
      },
      reloadProfile,
      createProject: async (payload) => {
        const created = await createProjectApi(payload);
        const nextProjects = [created, ...projects.filter((item) => item.id !== created.id)];
        setProjects(nextProjects);
        setCurrentProjectIdState(created.id);
        setStoredCurrentProjectId(created.id);
      },
    }),
    [ready, user, projects, currentProjectId],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
