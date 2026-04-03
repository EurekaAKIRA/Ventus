import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const API_BASE = (process.env.PLATFORM_API_BASE || "http://127.0.0.1:8001").replace(/\/+$/, "");
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REQUIREMENT_PATH = path.resolve(__dirname, "../../docs/platform_e2e_requirement.md");

async function request(path, init = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers || {}),
    },
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} ${path}`);
  }
  const payload = await response.json();
  if (!payload || payload.success !== true) {
    throw new Error(`API envelope invalid: ${path}`);
  }
  return payload.data;
}

async function main() {
  console.log(`[smoke] using api base: ${API_BASE}`);
  const requirementText = fs.readFileSync(REQUIREMENT_PATH, "utf-8");

  const created = await request("/api/tasks", {
    method: "POST",
    body: JSON.stringify({
      task_name: `ui_smoke_${Date.now()}`,
      source_type: "text",
      requirement_text: requirementText,
      target_system: API_BASE,
      environment: "test",
    }),
  });
  const taskId = created.task_id;
  if (!taskId) throw new Error("missing task_id");
  console.log(`[smoke] task created: ${taskId}`);

  try {
    const parsed = await request(`/api/tasks/${taskId}/parse`, {
      method: "POST",
      body: JSON.stringify({
        use_llm: false,
        rag_enabled: true,
        retrieval_top_k: 3,
        rerank_enabled: false,
      }),
    });
    if (!parsed.parse_metadata) throw new Error("missing parse_metadata");
    console.log("[smoke] parse ok");

    await request(`/api/tasks/${taskId}`);
    await request(`/api/tasks/${taskId}/scenarios`);
    await request(`/api/tasks/${taskId}/dsl`);
    await request(`/api/tasks/${taskId}/feature`);
    await request(`/api/tasks/${taskId}/validation-report`);
    await request(`/api/tasks/${taskId}/analysis-report`);
    await request(`/api/tasks/${taskId}/artifacts`);
    await request(`/api/tasks/${taskId}/execution`);
    console.log("[smoke] query endpoints ok");

    await request(`/api/tasks/${taskId}/execute`, {
      method: "POST",
      body: JSON.stringify({ execution_mode: "api", environment: "test" }),
    });
    for (let i = 0; i < 30; i += 1) {
      const execution = await request(`/api/tasks/${taskId}/execution`);
      if (["passed", "failed", "stopped"].includes(execution.status)) {
        if (execution.status !== "passed") {
          console.warn(`[smoke] execution finished with status=${execution.status}`);
        }
        break;
      }
      await new Promise((resolve) => setTimeout(resolve, 1000));
      if (i === 29) {
        throw new Error("execution polling timed out");
      }
    }
    console.log("[smoke] execute path ok");
  } finally {
    await request(`/api/tasks/${taskId}`, { method: "DELETE" });
    console.log("[smoke] cleanup ok");
  }
}

main()
  .then(() => {
    console.log("frontend api smoke test passed");
  })
  .catch((error) => {
    console.error(`frontend api smoke test failed: ${error.message}`);
    process.exitCode = 1;
  });
