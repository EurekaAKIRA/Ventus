import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outputDir = path.resolve(__dirname, "../../docs/thesis_figures");
const baseUrl = "http://127.0.0.1:5174";

const authPayload = {
  success: true,
  code: "OK",
  message: "ok",
  timestamp: new Date().toISOString(),
  data: {
    user: {
      id: "u-demo",
      username: "tester",
      display_name: "测试工程师",
      email: "tester@example.com",
      is_platform_admin: true,
      platform_role: "admin",
    },
    projects: [
      {
        id: "project-demo",
        name: "API 自动化测试平台",
        description: "毕业设计演示项目",
        is_default: true,
      },
    ],
  },
};

const pages = [
  { url: "/tasks/create", file: "图4-7_任务创建与需求提交页面.png" },
  { url: "/tasks/task_20260329_001?tab=scenario", file: "图4-8_测试场景预览页面.png" },
  { url: "/tasks/task_20260329_001?tab=dsl", file: "图4-9_DSL预览页面.png" },
  { url: "/tasks/task_20260329_001?tab=execution", file: "图4-10_执行跟踪页面.png" },
  { url: "/tasks/task_20260329_001?tab=report", file: "图4-11_测试报告页面.png" },
];

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 960 },
  deviceScaleFactor: 1.5,
});

await context.addInitScript(() => {
  window.localStorage.setItem("ventus_access_token", "demo-access-token");
  window.localStorage.setItem("ventus_refresh_token", "demo-refresh-token");
  window.localStorage.setItem("ventus_current_project_id", "project-demo");
});

await context.route("http://127.0.0.1:8001/api/auth/me", async (route) => {
  await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(authPayload) });
});

await context.route("http://127.0.0.1:8001/api/auth/refresh", async (route) => {
  await route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      ...authPayload,
      data: {
        access_token: "demo-access-token",
        refresh_token: "demo-refresh-token",
        user: authPayload.data.user,
        projects: authPayload.data.projects,
      },
    }),
  });
});

const page = await context.newPage();
for (const item of pages) {
  await page.goto(`${baseUrl}${item.url}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1600);
  const filePath = path.join(outputDir, item.file);
  await page.screenshot({ path: filePath, fullPage: false });
  console.log(filePath);
}

await browser.close();
