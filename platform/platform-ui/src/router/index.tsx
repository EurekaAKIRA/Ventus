import { createBrowserRouter, Navigate } from "react-router-dom";
import AppLayout from "../AppLayout";
import Dashboard from "../pages/Dashboard";
import TaskList from "../pages/TaskList";
import TaskCreate from "../pages/TaskCreate";
import TaskDetail from "../pages/TaskDetail";

const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: "dashboard", element: <Dashboard /> },
      { path: "tasks", element: <TaskList /> },
      { path: "tasks/create", element: <TaskCreate /> },
      { path: "tasks/:taskId", element: <TaskDetail /> },
    ],
  },
]);

export default router;
