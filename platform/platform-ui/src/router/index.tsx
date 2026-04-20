import { Suspense, lazy, type ReactNode } from "react";
import { Spin } from "antd";
import { createBrowserRouter, Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const AppLayout = lazy(() => import("../AppLayout"));
const Dashboard = lazy(() => import("../pages/Dashboard"));
const Login = lazy(() => import("../pages/Login"));
const TaskList = lazy(() => import("../pages/TaskList"));
const TaskCreate = lazy(() => import("../pages/TaskCreate"));
const TaskDetail = lazy(() => import("../pages/TaskDetail"));
const TaskHistory = lazy(() => import("../pages/TaskHistory"));
const UserCenter = lazy(() => import("../pages/UserCenter"));
const EnvironmentCenter = lazy(() => import("../pages/EnvironmentCenter"));
const AuditCenter = lazy(() => import("../pages/AuditCenter"));

function withSuspense(element: ReactNode) {
  return (
    <Suspense
      fallback={
        <div style={{ minHeight: 280, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Spin size="large" tip="页面加载中..." />
        </div>
      }
    >
      {element}
    </Suspense>
  );
}

function RouteLoading() {
  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <Spin size="large" tip="正在校验登录态..." />
    </div>
  );
}

function RequireAuth() {
  const { ready, isAuthenticated } = useAuth();
  const location = useLocation();
  if (!ready) {
    return <RouteLoading />;
  }
  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return <Outlet />;
}

function GuestOnly() {
  const { ready, isAuthenticated } = useAuth();
  if (!ready) {
    return <RouteLoading />;
  }
  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }
  return <Outlet />;
}

const router = createBrowserRouter([
  {
    element: <GuestOnly />,
    children: [
      {
        path: "/login",
        element: withSuspense(<Login />),
      },
    ],
  },
  {
    element: <RequireAuth />,
    children: [
      {
        path: "/",
        element: withSuspense(<AppLayout />),
        children: [
          { index: true, element: <Navigate to="/dashboard" replace /> },
          { path: "dashboard", element: withSuspense(<Dashboard />) },
          { path: "tasks", element: withSuspense(<TaskList />) },
          { path: "tasks/history", element: withSuspense(<TaskHistory />) },
          { path: "tasks/create", element: withSuspense(<TaskCreate />) },
          { path: "tasks/:taskId", element: withSuspense(<TaskDetail />) },
          { path: "environments", element: withSuspense(<EnvironmentCenter />) },
          { path: "audit", element: withSuspense(<AuditCenter />) },
          { path: "users/me", element: withSuspense(<UserCenter />) },
        ],
      },
    ],
  },
  {
    path: "*",
    element: <Navigate to="/login" replace />,
  },
]);

export default router;
