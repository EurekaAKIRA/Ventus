import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  Card,
  Form,
  Input,
  Select,
  Button,
  Upload,
  Typography,
  message,
  Space,
  Row,
  Col,
  Switch,
  Tag,
  Alert,
  Segmented,
} from "antd";
import { RobotOutlined, UploadOutlined } from "@ant-design/icons";
import { createTask, DEFAULT_REQUIREMENT_RAG_ENABLED, fetchTaskDraftAgent } from "../api/tasks";
import { useAuth } from "../auth/AuthContext";
import VueAgentDialogueMount from "../components/VueAgentDialogueMount";
import type { TaskDraftAgentPayload } from "../types";

const { Text } = Typography;
const { TextArea } = Input;
const DEFAULT_TARGET_SYSTEM =
  (import.meta.env.VITE_PLATFORM_API_BASE as string | undefined)?.trim() || "http://127.0.0.1:8001";
const DEFAULT_ENVIRONMENT_OPTIONS = [
  { value: "test", label: "测试环境" },
  { value: "staging", label: "预发布环境" },
  { value: "production", label: "生产环境" },
];

function deriveTaskNameFromFileName(fileName: string): string {
  const trimmed = String(fileName || "").trim();
  if (!trimmed) {
    return "";
  }
  const lastDotIndex = trimmed.lastIndexOf(".");
  if (lastDotIndex <= 0) {
    return trimmed;
  }
  return trimmed.slice(0, lastDotIndex).trim();
}

function extractBaseUrlFromRequirementText(text: string): string {
  const content = String(text || "").trim();
  if (!content) {
    return "";
  }

  const labeledPatterns = [
    /(?:base\s*url|baseurl|服务地址|服务域名|接口地址|接口域名|请求地址|环境地址)\s*[:：|]\s*`?(https?:\/\/[^\s)`>"']+)`?/im,
    /^\s*[-*]?\s*(?:默认\s*)?(?:base\s*url|baseurl|服务地址|服务域名|接口地址|接口域名|请求地址|环境地址)\s+`?(https?:\/\/[^\s)`>"']+)`?\s*$/im,
  ];
  for (const pattern of labeledPatterns) {
    const match = content.match(pattern);
    if (match?.[1]) {
      return match[1].replace(/\/+$/, "");
    }
  }

  const absoluteUrls = Array.from(content.matchAll(/https?:\/\/[^\s)`>"']+/gim))
    .map((item) => item[0].replace(/\/+$/, ""))
    .filter(Boolean);
  if (absoluteUrls.length === 1) {
    return absoluteUrls[0];
  }
  return "";
}

function shouldAutoFillTargetSystem(currentValue: string): boolean {
  const normalized = String(currentValue || "").trim().toLowerCase();
  if (!normalized) {
    return true;
  }
  return normalized === DEFAULT_TARGET_SYSTEM.trim().toLowerCase();
}

function getAgentCheckTagColor(status: string): string {
  switch (status) {
    case "ready":
      return "success";
    case "warning":
      return "warning";
    case "attention":
      return "default";
    default:
      return "default";
  }
}

function getAgentCheckLabel(status: string): string {
  switch (status) {
    case "ready":
      return "已就绪";
    case "warning":
      return "需核对";
    case "attention":
      return "待补充";
    default:
      return status || "未知";
  }
}

function getAgentSignalToneClass(tone?: string): string {
  switch (tone) {
    case "success":
      return "is-success";
    case "warning":
      return "is-warning";
    default:
      return "is-default";
  }
}

function getAgentConfidenceLabel(level?: string): string {
  switch (level) {
    case "high":
      return "高";
    case "medium":
      return "中";
    case "low":
      return "低";
    default:
      return level || "未知";
  }
}

function getAgentFieldLabel(field: string): string {
  switch (field) {
    case "task_name":
      return "任务名称";
    case "target_system":
      return "目标系统";
    case "environment":
      return "执行环境";
    case "requirement_text":
      return "需求描述";
    default:
      return field || "字段";
  }
}

function getAgentFollowUpActionLabel(item: {
  action_label?: string;
  action_kind?: string;
  field?: string;
}): string {
  if (item.action_label) {
    return item.action_label;
  }
  switch (item.action_kind) {
    case "apply_document_action":
      return "立即修正";
    case "apply_form_patch":
      return "直接应用";
    case "focus_field":
      return item.field === "environment" ? "去选择" : "去填写";
    default:
      return "去处理";
  }
}

function getAgentFollowUpPriorityWeight(priority?: string): number {
  switch (priority) {
    case "high":
      return 3;
    case "medium":
      return 2;
    case "low":
      return 1;
    default:
      return 0;
  }
}

function getAgentCheckKeyLabel(key: string): string {
  switch (key) {
    case "environment_target_alignment":
      return "环境对齐";
    default:
      return getAgentFieldLabel(key);
  }
}

function mergeRequirementTextWithAction(
  currentText: string,
  action: {
    mode?: string;
    content: string;
  },
): string {
  const normalizedCurrent = String(currentText ?? "");
  const snippet = String(action.content ?? "");
  if (!snippet.trim()) {
    return normalizedCurrent;
  }
  if (String(action.mode ?? "").toLowerCase() === "prepend") {
    return `${snippet}${normalizedCurrent}`.trim();
  }
  return `${normalizedCurrent.trimEnd()}\n${snippet}`.trim();
}

function formatAgentRatio(value?: number): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "--";
  }
  return `${Math.round(value * 100)}%`;
}

function formatAgentScenarioShape(value?: string): string {
  return String(value || "").trim() || "待补充";
}

function getAgentResourceStatusLabel(status?: string): string {
  switch (status) {
    case "complete":
      return "完整链路";
    case "needs_source":
      return "缺资源来源";
    case "read_only":
      return "只读链路";
    case "single_step":
      return "单步骤";
    default:
      return status || "未知";
  }
}

function getAgentResourceStatusColor(status?: string): string {
  switch (status) {
    case "complete":
      return "success";
    case "needs_source":
      return "error";
    case "read_only":
      return "processing";
    case "single_step":
      return "default";
    default:
      return "default";
  }
}

function getAgentPlanStatusLabel(status?: string): string {
  switch (status) {
    case "done":
      return "已完成";
    case "next":
      return "下一步";
    case "review":
      return "需审阅";
    case "blocked":
      return "阻断";
    default:
      return status || "未知";
  }
}

function getAgentPlanStatusColor(status?: string): string {
  switch (status) {
    case "done":
      return "success";
    case "next":
      return "processing";
    case "review":
      return "warning";
    case "blocked":
      return "error";
    default:
      return "default";
  }
}

function getAgentQualityGateStatusLabel(status?: string): string {
  switch (status) {
    case "pass":
      return "通过";
    case "warn":
      return "需核对";
    case "block":
      return "阻断";
    default:
      return status || "未知";
  }
}

function getAgentQualityGateStatusColor(status?: string): string {
  switch (status) {
    case "pass":
      return "success";
    case "warn":
      return "warning";
    case "block":
      return "error";
    default:
      return "default";
  }
}

function getAgentVerdictColor(severity?: string): string {
  switch (severity) {
    case "success":
      return "success";
    case "error":
      return "error";
    case "warning":
      return "warning";
    default:
      return "default";
  }
}

function getAgentBlueprintStatusLabel(status?: string): string {
  switch (status) {
    case "ready":
      return "可生成";
    case "needs_context":
      return "缺上下文";
    case "read_only":
      return "只读";
    case "single_step":
      return "单接口";
    default:
      return status || "未知";
  }
}

function getAgentBlueprintStatusColor(status?: string): string {
  switch (status) {
    case "ready":
      return "success";
    case "needs_context":
      return "error";
    case "read_only":
      return "processing";
    case "single_step":
      return "default";
    default:
      return "default";
  }
}

function buildAgentSnapshotKey(values: {
  task_name?: string;
  requirement_text?: string;
  target_system?: string;
  environment?: string;
  project_id?: string;
  source_path?: string;
}): string {
  return JSON.stringify({
    task_name: String(values.task_name ?? "").trim(),
    requirement_text: String(values.requirement_text ?? "").trim(),
    target_system: String(values.target_system ?? "").trim(),
    environment: String(values.environment ?? "").trim(),
    project_id: String(values.project_id ?? "").trim(),
    source_path: String(values.source_path ?? "").trim(),
  });
}

type TaskCreateProps = {
  mode?: "create" | "agent";
};

export default function TaskCreate({ mode = "create" }: TaskCreateProps) {
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const [readingFile, setReadingFile] = useState(false);
  const [uploadedFileName, setUploadedFileName] = useState<string>("");
  const [agentLoading, setAgentLoading] = useState(false);
  const [agentPayload, setAgentPayload] = useState<TaskDraftAgentPayload | null>(null);
  const [agentSnapshotKey, setAgentSnapshotKey] = useState("");
  const [agentAutoAppliedLabels, setAgentAutoAppliedLabels] = useState<string[]>([]);
  const [agentFocusedField, setAgentFocusedField] = useState("");
  const [agentFollowUpAnswers, setAgentFollowUpAnswers] = useState<Record<string, string>>({});
  const [agentFollowUpHandledCount, setAgentFollowUpHandledCount] = useState(0);
  const [agentStudioView, setAgentStudioView] = useState<"overview" | "followups" | "document" | "knowledge">("overview");
  const agentInFlightSnapshotKeyRef = useRef("");
  const agentRequestTokenRef = useRef(0);
  const programmaticFieldKeysRef = useRef<Set<string>>(new Set());
  const userEditedFieldsRef = useRef<Set<string>>(new Set());
  const agentFocusTimerRef = useRef<number | null>(null);
  const { currentProjectId, projects, isAuthenticated } = useAuth();
  const isAgentStudio = mode === "agent" || location.pathname.startsWith("/agent");
  const watchedTaskName = Form.useWatch("task_name", form);
  const watchedRequirementText = Form.useWatch("requirement_text", form);
  const watchedTargetSystem = Form.useWatch("target_system", form);
  const watchedEnvironment = Form.useWatch("environment", form);
  const watchedProjectId = Form.useWatch("project_id", form);
  const watchedRagEnabled = Form.useWatch("rag_enabled", form);
  const environmentOptions = [
    ...DEFAULT_ENVIRONMENT_OPTIONS,
    ...Array.from(
      new Map(
        (agentPayload?.environment_candidates ?? []).map((item) => [
          item.name,
          {
            value: item.name,
            label: item.description ? `${item.name} · ${item.description}` : item.name,
          },
        ]),
      ).values(),
    ),
  ];
  const currentAgentSnapshotKey = buildAgentSnapshotKey({
    task_name: watchedTaskName,
    requirement_text: watchedRequirementText,
    target_system: watchedTargetSystem,
    environment: watchedEnvironment,
    project_id: watchedProjectId || currentProjectId || "",
    source_path: uploadedFileName,
  });
  const agentSuggestionStale = Boolean(agentPayload && agentSnapshotKey && agentSnapshotKey !== currentAgentSnapshotKey);
  const shouldAutoAnalyzeAgent = isAgentStudio
    ? Boolean(uploadedFileName) || String(watchedRequirementText ?? "").trim().length >= 24
    : Boolean(uploadedFileName);
  const sortedFollowUpQuestions = useMemo(
    () =>
      [...(agentPayload?.follow_up_questions ?? [])].sort((left, right) => {
        const priorityGap = getAgentFollowUpPriorityWeight(right.priority) - getAgentFollowUpPriorityWeight(left.priority);
        if (priorityGap !== 0) {
          return priorityGap;
        }
        return String(left.key ?? "").localeCompare(String(right.key ?? ""));
      }),
    [agentPayload?.follow_up_questions],
  );
  const routeState = useMemo(
    () =>
      (location.state as
        | {
            draft?: Record<string, unknown>;
            agentView?: "overview" | "followups" | "document" | "knowledge";
          }
        | undefined) ?? undefined,
    [location.state],
  );
  const routeDraft = routeState?.draft ?? null;
  const routeAgentView = routeState?.agentView;

  useEffect(() => {
    const currentValue = String(form.getFieldValue("project_id") ?? "").trim();
    if (!currentValue && currentProjectId) {
      form.setFieldValue("project_id", currentProjectId);
    }
  }, [currentProjectId, form]);

  useEffect(() => {
    if (!routeDraft || typeof routeDraft !== "object") {
      return;
    }
    const nextValues: Record<string, unknown> = {};
    for (const key of ["task_name", "requirement_text", "target_system", "environment", "rag_enabled", "project_id"]) {
      if (key in routeDraft) {
        nextValues[key] = routeDraft[key];
      }
    }
    if (Object.keys(nextValues).length) {
      markProgrammaticFields(Object.keys(nextValues));
      form.setFieldsValue(nextValues);
    }
    setUploadedFileName(String(routeDraft.uploadedFileName ?? routeDraft.source_path ?? "").trim());
    setAgentPayload(null);
    setAgentSnapshotKey("");
    setAgentAutoAppliedLabels([]);
    setAgentFollowUpHandledCount(0);
    setAgentFollowUpAnswers({});
    userEditedFieldsRef.current.clear();
    navigate(
      {
        pathname: location.pathname,
        search: location.search,
      },
      { replace: true, state: null },
    );
  }, [form, location.pathname, location.search, navigate, routeDraft]);

  useEffect(() => {
    if (!routeAgentView) {
      return;
    }
    setAgentStudioView(routeAgentView);
    navigate(
      {
        pathname: location.pathname,
        search: location.search,
      },
      { replace: true, state: null },
    );
  }, [location.pathname, location.search, navigate, routeAgentView]);

  useEffect(
    () => () => {
      if (agentFocusTimerRef.current !== null) {
        window.clearTimeout(agentFocusTimerRef.current);
      }
    },
    [],
  );

  const markProgrammaticFields = (fieldKeys: string[]) => {
    programmaticFieldKeysRef.current = new Set(fieldKeys);
    window.setTimeout(() => {
      programmaticFieldKeysRef.current = new Set();
    }, 0);
  };

  const buildSafeAutoApplyPatch = (
    formPatch: Record<string, string>,
    currentValues: Record<string, unknown>,
  ): Record<string, string> => {
    const nextPatch: Record<string, string> = {};
    for (const [field, rawValue] of Object.entries(formPatch)) {
      const value = String(rawValue ?? "").trim();
      if (!value || userEditedFieldsRef.current.has(field)) {
        continue;
      }
      const currentValue = String(currentValues[field] ?? "").trim();
      if (field === "task_name" && !currentValue) {
        nextPatch[field] = value;
        continue;
      }
      if (field === "target_system" && shouldAutoFillTargetSystem(currentValue)) {
        nextPatch[field] = value;
        continue;
      }
      if (field === "environment" && (!currentValue || currentValue === "test")) {
        nextPatch[field] = value;
      }
    }
    return nextPatch;
  };

  const generateAgentSuggestion = async ({
    silentError = false,
    snapshotKey,
  }: {
    silentError?: boolean;
    snapshotKey?: string;
  } = {}) => {
    const values = form.getFieldsValue(["task_name", "requirement_text", "target_system", "environment", "project_id"]);
    const nextSnapshotKey =
      snapshotKey ||
      buildAgentSnapshotKey({
        ...values,
        project_id: values.project_id || currentProjectId || undefined,
        source_path: uploadedFileName || undefined,
      });

    if (agentInFlightSnapshotKeyRef.current === nextSnapshotKey) {
      return;
    }

    const requestToken = agentRequestTokenRef.current + 1;
    agentRequestTokenRef.current = requestToken;
    agentInFlightSnapshotKeyRef.current = nextSnapshotKey;
    setAgentLoading(true);
    try {
      const payload = await fetchTaskDraftAgent({
        task_name: values.task_name,
        requirement_text: values.requirement_text,
        source_path: uploadedFileName || undefined,
        target_system: values.target_system,
        environment: values.environment,
        project_id: values.project_id || currentProjectId || undefined,
      });
      if (requestToken !== agentRequestTokenRef.current) {
        return;
      }
      const autoApplyPatch = buildSafeAutoApplyPatch(
        payload.form_patch ?? {},
        form.getFieldsValue(["task_name", "target_system", "environment"]),
      );
      let finalSnapshotKey = nextSnapshotKey;
      let nextPayload = payload;
      const autoApplyFieldKeys = Object.keys(autoApplyPatch);
      if (autoApplyFieldKeys.length) {
        const autoApplyResult = applyAgentPatch(autoApplyPatch);
        finalSnapshotKey = autoApplyResult.snapshotKey;
        const remainingFormPatch = { ...(payload.form_patch ?? {}) };
        for (const key of autoApplyFieldKeys) {
          delete remainingFormPatch[key];
        }
        nextPayload = {
          ...payload,
          form_patch: remainingFormPatch,
          selected_environment: autoApplyPatch.environment ?? payload.selected_environment ?? null,
        };
        setAgentAutoAppliedLabels(autoApplyFieldKeys.map((item) => getAgentFieldLabel(item)));
      } else {
        setAgentAutoAppliedLabels([]);
      }
      setAgentPayload(nextPayload);
      setAgentSnapshotKey(finalSnapshotKey);
    } catch (error) {
      if (!silentError) {
        message.error((error as Error).message || "获取 Agent 建议失败");
      }
    } finally {
      if (requestToken === agentRequestTokenRef.current) {
        agentInFlightSnapshotKeyRef.current = "";
        setAgentLoading(false);
      }
    }
  };

  useEffect(() => {
    if (!shouldAutoAnalyzeAgent || readingFile || submitting) {
      return undefined;
    }
    if (agentLoading || agentInFlightSnapshotKeyRef.current === currentAgentSnapshotKey) {
      return undefined;
    }
    if (agentPayload && agentSnapshotKey === currentAgentSnapshotKey && !agentSuggestionStale) {
      return undefined;
    }
    const timer = window.setTimeout(() => {
      void generateAgentSuggestion({
        silentError: true,
        snapshotKey: currentAgentSnapshotKey,
      });
    }, uploadedFileName ? 320 : 900);
    return () => window.clearTimeout(timer);
  }, [
    agentLoading,
    agentPayload,
    agentSnapshotKey,
    agentSuggestionStale,
    currentAgentSnapshotKey,
    readingFile,
    shouldAutoAnalyzeAgent,
    submitting,
    uploadedFileName,
  ]);

  const handleSubmit = async (values: Record<string, any>) => {
    const targetSystem = String(values.target_system ?? "").trim();
    if (targetSystem) {
      try {
        const parsed = new URL(targetSystem);
        if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
          message.error("target_system must start with http:// or https://");
          return;
        }
      } catch {
        message.error("target_system is not a valid URL");
        return;
      }
    }

    setSubmitting(true);
    try {
      const normalizedTaskName = String(values.task_name ?? "").trim();
      const sourcePath = uploadedFileName || undefined;
      const result = await createTask({
        task_name: normalizedTaskName,
        source_type: sourcePath ? "file" : "text",
        requirement_text: values.requirement_text,
        source_path: sourcePath,
        target_system: targetSystem || undefined,
        environment: values.environment || undefined,
        rag_enabled: Boolean(values.rag_enabled),
        project_id: values.project_id || currentProjectId || undefined,
      });
      message.success("任务创建成功");
      navigate(`/tasks/${encodeURIComponent(result.task_id)}?from=create`);
    } catch {
      message.error("创建失败，请重试");
    } finally {
      setSubmitting(false);
    }
  };

  const handleGenerateAgentSuggestion = async () => {
    await generateAgentSuggestion();
  };

  const applyAgentPatch = (patch: Record<string, string>) => {
    const sanitizedPatch = Object.entries(patch).reduce<Record<string, string>>((acc, [key, value]) => {
      if (String(value ?? "").trim()) {
        acc[key] = value;
      }
      return acc;
    }, {});
    const patchKeys = Object.keys(sanitizedPatch);
    if (!patchKeys.length) {
      return { count: 0, patchKeys: [], snapshotKey: agentSnapshotKey };
    }
    const currentValues = form.getFieldsValue(["task_name", "requirement_text", "target_system", "environment", "project_id"]);
    markProgrammaticFields(patchKeys);
    form.setFieldsValue(sanitizedPatch);
    const nextSnapshotKey = buildAgentSnapshotKey({
      ...currentValues,
      ...sanitizedPatch,
      project_id: currentValues.project_id || currentProjectId || undefined,
      source_path: uploadedFileName || undefined,
    });
    setAgentSnapshotKey(nextSnapshotKey);
    return { count: patchKeys.length, patchKeys, snapshotKey: nextSnapshotKey };
  };

  const focusAgentField = (field: string) => {
    const normalizedField = String(field || "").trim();
    if (!normalizedField) {
      return;
    }
    form.scrollToField(normalizedField, {
      behavior: "smooth",
      block: "center",
    });
    setAgentFocusedField(normalizedField);
    if (agentFocusTimerRef.current !== null) {
      window.clearTimeout(agentFocusTimerRef.current);
    }
    agentFocusTimerRef.current = window.setTimeout(() => {
      setAgentFocusedField("");
      agentFocusTimerRef.current = null;
    }, 1800);
    window.setTimeout(() => {
      const selectors = [
        `.create-task-field--${normalizedField} textarea`,
        `.create-task-field--${normalizedField} .ant-input`,
        `.create-task-field--${normalizedField} .ant-select-selector`,
        `#task-create-${normalizedField}`,
      ];
      for (const selector of selectors) {
        const element = document.querySelector<HTMLElement>(selector);
        if (!element) {
          continue;
        }
        if (normalizedField === "environment" && typeof element.click === "function") {
          element.click();
        }
        if (typeof element.focus === "function") {
          element.focus();
        }
        break;
      }
    }, 80);
  };

  const handleApplyAgentSuggestion = () => {
    if (!agentPayload) {
      message.info("请先生成 Agent 建议");
      return;
    }
    if (agentSuggestionStale) {
      message.warning("当前表单已变化，请重新生成建议后再应用");
      return;
    }
    const applied = applyAgentPatch(agentPayload.form_patch ?? {});
    if (!applied.count) {
      message.info("当前没有需要回填的建议");
      return;
    }
    setAgentAutoAppliedLabels([]);
    setAgentPayload({
      ...agentPayload,
      form_patch: {},
      selected_environment: agentPayload.form_patch?.environment ?? agentPayload.selected_environment ?? null,
    });
    message.success(`已应用 ${applied.count} 项建议`);
  };

  const handleApplySingleSuggestion = (field: string, value: string) => {
    if (!agentPayload) {
      return;
    }
    if (agentSuggestionStale) {
      message.warning("当前表单已变化，请重新生成建议后再应用");
      return;
    }
    const applied = applyAgentPatch({ [field]: value });
    if (!applied.count) {
      message.info("当前建议无需回填");
      return;
    }
    setAgentAutoAppliedLabels([]);
    const nextFormPatch = { ...(agentPayload.form_patch ?? {}) };
    delete nextFormPatch[field];
    setAgentPayload({
      ...agentPayload,
      form_patch: nextFormPatch,
      selected_environment: field === "environment" ? value : agentPayload.selected_environment ?? null,
    });
    message.success(`已应用${getAgentFieldLabel(field)}建议`);
  };

  const handleApplyDocumentAction = (actionKey: string) => {
    if (!agentPayload) {
      return;
    }
    const action = agentPayload.document_actions.find((item) => item.key === actionKey);
    if (!action) {
      return;
    }
    const currentRequirementText = String(form.getFieldValue("requirement_text") ?? "");
    const nextRequirementText = mergeRequirementTextWithAction(currentRequirementText, action);
    if (nextRequirementText === currentRequirementText) {
      message.info("当前片段无需再插入");
      return;
    }
    markProgrammaticFields(["requirement_text"]);
    form.setFieldValue("requirement_text", nextRequirementText);
    const nextSnapshotKey = buildAgentSnapshotKey({
      task_name: form.getFieldValue("task_name"),
      requirement_text: nextRequirementText,
      target_system: form.getFieldValue("target_system"),
      environment: form.getFieldValue("environment"),
      project_id: form.getFieldValue("project_id") || currentProjectId || "",
      source_path: uploadedFileName,
    });
    setAgentSnapshotKey(nextSnapshotKey);
    setAgentAutoAppliedLabels([]);
    setAgentPayload({
      ...agentPayload,
      document_actions: agentPayload.document_actions.filter((item) => item.key !== actionKey),
      document_preview: null,
    });
    message.success(`已插入：${action.title}`);
    requestImmediateAgentRefresh(nextSnapshotKey);
  };

  const handleApplyAllDocumentActions = () => {
    if (!agentPayload?.document_actions.length) {
      message.info("当前没有可插入的修正片段");
      return;
    }
    if (agentSuggestionStale) {
      message.warning("当前表单已变化，请等待 Agent 自动刷新后再批量插入");
      return;
    }
    const currentRequirementText = String(form.getFieldValue("requirement_text") ?? "");
    let nextRequirementText = currentRequirementText;
    for (const action of agentPayload.document_actions) {
      nextRequirementText = mergeRequirementTextWithAction(nextRequirementText, action);
    }
    if (nextRequirementText === currentRequirementText) {
      message.info("当前片段无需重复插入");
      return;
    }
    markProgrammaticFields(["requirement_text"]);
    form.setFieldValue("requirement_text", nextRequirementText);
    const nextSnapshotKey = buildAgentSnapshotKey({
      task_name: form.getFieldValue("task_name"),
      requirement_text: nextRequirementText,
      target_system: form.getFieldValue("target_system"),
      environment: form.getFieldValue("environment"),
      project_id: form.getFieldValue("project_id") || currentProjectId || "",
      source_path: uploadedFileName,
    });
    setAgentSnapshotKey(nextSnapshotKey);
    setAgentAutoAppliedLabels([]);
    setAgentPayload({
      ...agentPayload,
      document_actions: [],
      document_preview: null,
    });
    message.success(`已插入 ${agentPayload.document_actions.length} 条修正片段`);
    requestImmediateAgentRefresh(nextSnapshotKey);
  };

  const handleApplyDocumentPreview = () => {
    if (!agentPayload?.document_preview?.content) {
      return;
    }
    markProgrammaticFields(["requirement_text"]);
    form.setFieldValue("requirement_text", agentPayload.document_preview.content);
    const nextSnapshotKey = buildAgentSnapshotKey({
      task_name: form.getFieldValue("task_name"),
      requirement_text: agentPayload.document_preview.content,
      target_system: form.getFieldValue("target_system"),
      environment: form.getFieldValue("environment"),
      project_id: form.getFieldValue("project_id") || currentProjectId || "",
      source_path: uploadedFileName,
    });
    setAgentSnapshotKey(nextSnapshotKey);
    setAgentAutoAppliedLabels([]);
    setAgentPayload({
      ...agentPayload,
      document_actions: [],
      document_preview: null,
    });
    message.success("已替换为 Agent 规范化草稿");
    requestImmediateAgentRefresh(nextSnapshotKey);
  };

  const requestImmediateAgentRefresh = (snapshotKey?: string) => {
    void generateAgentSuggestion({
      silentError: true,
      snapshotKey:
        snapshotKey ||
        buildAgentSnapshotKey({
          task_name: form.getFieldValue("task_name"),
          requirement_text: form.getFieldValue("requirement_text"),
          target_system: form.getFieldValue("target_system"),
          environment: form.getFieldValue("environment"),
          project_id: form.getFieldValue("project_id") || currentProjectId || "",
          source_path: uploadedFileName,
        }),
    });
  };

  const handleApplyFollowUpAnswer = (item: TaskDraftAgentPayload["follow_up_questions"][number]) => {
    const answer = String(agentFollowUpAnswers[item.key] ?? "").trim();
    if (!answer) {
      message.info("请先输入回答内容");
      return;
    }
    if (item.answer_mode === "field" && item.field) {
      markProgrammaticFields([item.field]);
      form.setFieldValue(item.field, answer);
      const nextSnapshotKey = buildAgentSnapshotKey({
        task_name: form.getFieldValue("task_name"),
        requirement_text: form.getFieldValue("requirement_text"),
        target_system: item.field === "target_system" ? answer : form.getFieldValue("target_system"),
        environment: item.field === "environment" ? answer : form.getFieldValue("environment"),
        project_id: form.getFieldValue("project_id") || currentProjectId || "",
        source_path: uploadedFileName,
      });
      setAgentSnapshotKey(nextSnapshotKey);
      setAgentFollowUpAnswers((current) => ({ ...current, [item.key]: "" }));
      setAgentFollowUpHandledCount((current) => current + 1);
      setAgentAutoAppliedLabels([]);
      setAgentPayload((current) =>
        current
          ? {
              ...current,
              follow_up_questions: current.follow_up_questions.filter((question) => question.key !== item.key),
            }
          : current,
      );
      message.success(`已写入${getAgentFieldLabel(item.field)}`);
      requestImmediateAgentRefresh(nextSnapshotKey);
      return;
    }
    if (item.answer_mode === "append_requirement") {
      const currentRequirementText = String(form.getFieldValue("requirement_text") ?? "");
      const answerTemplate = String(item.answer_template ?? "{answer}");
      const snippet = answerTemplate.replace("{answer}", answer);
      const nextRequirementText = `${currentRequirementText.trimEnd()}\n${snippet}`.trim();
      if (nextRequirementText === currentRequirementText) {
        message.info("当前回答无需重复追加");
        return;
      }
      markProgrammaticFields(["requirement_text"]);
      form.setFieldValue("requirement_text", nextRequirementText);
      const nextSnapshotKey = buildAgentSnapshotKey({
        task_name: form.getFieldValue("task_name"),
        requirement_text: nextRequirementText,
        target_system: form.getFieldValue("target_system"),
        environment: form.getFieldValue("environment"),
        project_id: form.getFieldValue("project_id") || currentProjectId || "",
        source_path: uploadedFileName,
      });
      setAgentSnapshotKey(nextSnapshotKey);
      setAgentFollowUpAnswers((current) => ({ ...current, [item.key]: "" }));
      setAgentFollowUpHandledCount((current) => current + 1);
      setAgentAutoAppliedLabels([]);
      setAgentPayload((current) =>
        current
          ? {
              ...current,
              follow_up_questions: current.follow_up_questions.filter((question) => question.key !== item.key),
              document_preview: null,
            }
          : current,
      );
      message.success("已将回答写入需求描述");
      requestImmediateAgentRefresh(nextSnapshotKey);
    }
  };

  const handleResolveFollowUpQuestion = (item: TaskDraftAgentPayload["follow_up_questions"][number]) => {
    if (item.action_kind === "apply_document_action" && item.document_action_key) {
      if (agentSuggestionStale) {
        message.warning("当前表单已变化，请等待 Agent 自动刷新后再应用修正动作");
        return;
      }
      handleApplyDocumentAction(item.document_action_key);
      return;
    }
    if (item.action_kind === "apply_form_patch" && item.field && agentPayload?.form_patch?.[item.field]) {
      if (agentSuggestionStale) {
        message.warning("当前表单已变化，请重新生成建议后再应用");
        return;
      }
      handleApplySingleSuggestion(item.field, agentPayload.form_patch[item.field]);
      return;
    }
    if (item.field) {
      focusAgentField(item.field);
      message.info(`已定位到${getAgentFieldLabel(item.field)}`);
    }
  };

  const handleOpenAgentStudio = (agentView: "overview" | "followups" | "document" | "knowledge" = "overview") => {
    navigate("/agent", {
      state: {
        draft: {
          ...form.getFieldsValue(["task_name", "requirement_text", "target_system", "environment", "rag_enabled", "project_id"]),
          uploadedFileName,
        },
        agentView,
      },
    });
  };

  const handleOpenCreateView = () => {
    navigate("/tasks/create", {
      state: {
        draft: {
          ...form.getFieldsValue(["task_name", "requirement_text", "target_system", "environment", "rag_enabled", "project_id"]),
          uploadedFileName,
        },
      },
    });
  };

  const hasOverviewContent = Boolean(
    agentPayload?.signals.length ||
      agentPayload?.scenario_outlook ||
      agentPayload?.resource_groups?.length ||
      agentPayload?.action_plan?.length ||
      agentPayload?.scenario_blueprint?.length ||
      agentPayload?.quality_gates?.length ||
      agentPayload?.coverage_gaps?.length ||
      agentPayload?.recognized_endpoints.length ||
      agentPayload?.highlights.length ||
      agentPayload?.checks.length ||
      agentPayload?.suggestions.length ||
      agentPayload?.next_actions.length,
  );
  const hasFollowUpContent = Boolean(
    sortedFollowUpQuestions.length || agentPayload?.risks.length || agentPayload?.warnings.length,
  );
  const hasDocumentContent = Boolean(
    agentPayload?.document_fixes.length ||
      agentPayload?.document_actions.length ||
      agentPayload?.document_preview?.content,
  );
  const hasKnowledgeContent = Boolean(agentPayload?.knowledge_hits.length);
  const showCompactSections = !isAgentStudio;
  const showOverviewSections = isAgentStudio && agentStudioView === "overview";
  const showFollowUpSections = isAgentStudio && agentStudioView === "followups";
  const showDocumentSections = isAgentStudio && agentStudioView === "document";
  const showKnowledgeSections = isAgentStudio && agentStudioView === "knowledge";
  const compactWorkbenchItemCount =
    sortedFollowUpQuestions.length +
    (agentPayload?.document_actions.length ?? 0) +
    (agentPayload?.knowledge_hits.length ?? 0) +
    (agentPayload?.quality_gates?.filter((item) => item.status === "block" || item.status === "warn").length ?? 0) +
    (agentPayload?.coverage_gaps?.length ?? 0) +
    (agentPayload?.risks.length ?? 0) +
    (agentPayload?.warnings.length ?? 0);
  const activeStudioViewHasContent =
    !isAgentStudio ||
    (agentStudioView === "overview" && hasOverviewContent) ||
    (agentStudioView === "followups" && hasFollowUpContent) ||
    (agentStudioView === "document" && hasDocumentContent) ||
    (agentStudioView === "knowledge" && hasKnowledgeContent);
  const handleOpenAgentFocus = (view: "overview" | "followups" | "document" | "knowledge") => {
    if (isAgentStudio) {
      setAgentStudioView(view);
      return;
    }
    handleOpenAgentStudio(view);
  };
  const agentDecisionItems = useMemo(() => {
    if (!agentPayload) {
      return [];
    }
    const items: Array<{
      key: string;
      title: string;
      detail: string;
      view: "overview" | "followups" | "document" | "knowledge";
      actionLabel: string;
    }> = [];
    if (sortedFollowUpQuestions.length) {
      items.push({
        key: "followups",
        title: `还有 ${sortedFollowUpQuestions.length} 个关键信息待确认`,
        detail: sortedFollowUpQuestions[0]?.question || "先补齐缺失信息后再创建任务。",
        view: "followups",
        actionLabel: "去回答",
      });
    }
    if (agentPayload.document_actions.length) {
      items.push({
        key: "document_actions",
        title: `文档还缺 ${agentPayload.document_actions.length} 处规范片段`,
        detail: agentPayload.document_actions[0]?.title || "先补齐关键模板片段。",
        view: "document",
        actionLabel: "去修正",
      });
    }
    if (agentPayload.scenario_outlook?.uncovered_live_resource_endpoints?.length) {
      items.push({
        key: "resources",
        title: "存在活资源链路缺口",
        detail: `例如 ${agentPayload.scenario_outlook.uncovered_live_resource_endpoints[0]} 仍缺资源来源。`,
        view: "overview",
        actionLabel: "看链路",
      });
    }
    const blockingGates = (agentPayload.quality_gates ?? []).filter((item) => item.status === "block");
    if (blockingGates.length) {
      items.push({
        key: "quality_gates",
        title: `${blockingGates.length} 个质量门禁未通过`,
        detail: blockingGates[0]?.detail || "先处理阻断项再创建任务会更稳。",
        view: "overview",
        actionLabel: "看门禁",
      });
    }
    if (agentPayload.risks.length) {
      items.push({
        key: "risks",
        title: `当前有 ${agentPayload.risks.length} 条风险提醒`,
        detail: agentPayload.risks[0],
        view: "followups",
        actionLabel: "去处理",
      });
    }
    if (agentPayload.knowledge_hits.length) {
      items.push({
        key: "knowledge",
        title: `已命中 ${agentPayload.knowledge_hits.length} 条知识依据`,
        detail: agentPayload.knowledge_hits[0]?.title || "可以用来解释当前建议来源。",
        view: "knowledge",
        actionLabel: "看依据",
      });
    }
    return items.slice(0, isAgentStudio ? 4 : 3);
  }, [agentPayload, isAgentStudio, sortedFollowUpQuestions]);
  const agentDecisionSummary = useMemo(() => {
    if (!agentPayload) {
      return {
        tone: "default",
        title: isAgentStudio ? "先导入文档，再让 Agent 开始诊断" : "导入文档后，创建助手会先帮你补全草案",
        description: isAgentStudio
          ? "工作台只负责追问、文档修正和知识依据，创建与执行仍回到工作流完成。"
          : "创建页只保留快速补全；复杂问题再进入 Agent 工作台。",
      };
    }
    if (agentPayload.summary.ready_to_execute) {
      return {
        tone: "success",
        title: isAgentStudio ? "当前草案可以带回工作流" : "当前可以创建并执行",
        description: isAgentStudio
          ? "任务草案、执行环境和主要依赖已经基本齐备，建议回到创建页提交。"
          : "任务草案、执行环境和主要依赖已经基本齐备，可以直接推进。",
      };
    }
    if (agentPayload.summary.ready_to_create) {
      return {
        tone: "warning",
        title: isAgentStudio ? "草案可回填，但执行前还有待确认项" : "当前可以创建，但执行前还有待确认项",
        description: isAgentStudio
          ? "建议先处理追问或风险，再把草案带回创建页。"
          : "建议先看追问或风险，再决定是否立即执行。",
      };
    }
    return {
      tone: "warning",
      title: isAgentStudio
        ? `回到工作流前还需处理 ${Math.max(agentDecisionItems.length, 1)} 项关键问题`
        : `创建前还需处理 ${Math.max(agentDecisionItems.length, 1)} 项关键问题`,
      description: agentDecisionItems[0]?.detail || "先补齐文档和依赖信息，再创建任务会更稳。",
    };
  }, [agentDecisionItems, agentPayload, isAgentStudio]);

  const agentPanel = (
    <Card bordered={false} className={`create-task-agent-card${isAgentStudio ? " create-task-agent-card--studio" : ""}`}>
      <div className="create-task-agent-card__head">
        <Space size={8}>
          <RobotOutlined />
          <Text strong>{isAgentStudio ? "Agent 工作台" : "创建助手"}</Text>
        </Space>
        <Tag color={agentLoading ? "processing" : "success"}>{agentLoading ? "分析中" : "在线"}</Tag>
      </div>
      <div className="create-task-agent-card__body">
        <div className="create-task-agent-actions">
          <Button block onClick={() => void handleGenerateAgentSuggestion()} loading={agentLoading}>
            {agentPayload ? "重新分析" : "生成建议"}
          </Button>
          <Button
            block
            type="primary"
            ghost
            onClick={handleApplyAgentSuggestion}
            disabled={!agentPayload || !Object.keys(agentPayload.form_patch ?? {}).length || agentSuggestionStale}
          >
            一键回填
          </Button>
        </div>
        {agentPayload ? (
          <>
            {agentAutoAppliedLabels.length ? (
              <Alert
                type="success"
                showIcon
                message={`Agent 已自动回填：${agentAutoAppliedLabels.join("、")}`}
              />
            ) : null}
            {agentSuggestionStale ? (
              <Alert type="warning" showIcon message="表单内容已变化，Agent 将自动刷新分析，请稍候。" />
            ) : null}
            <Alert type="info" showIcon message={agentPayload.reply} />
            {agentPayload.diagnostic_verdict ? (
              <div className={`create-task-agent-verdict is-${agentPayload.diagnostic_verdict.severity || "default"}`}>
                <div className="create-task-agent-verdict__head">
                  <div className="create-task-agent-verdict__copy">
                    <Text type="secondary">诊断结论</Text>
                    <Text strong className="create-task-agent-verdict__title">
                      {agentPayload.diagnostic_verdict.label}
                    </Text>
                    <Text type="secondary">{agentPayload.diagnostic_verdict.summary}</Text>
                  </div>
                  <Tag color={getAgentVerdictColor(agentPayload.diagnostic_verdict.severity)}>
                    {agentPayload.diagnostic_verdict.primary_action}
                  </Tag>
                </div>
                <div className="create-task-agent-verdict__metrics">
                  <span>
                    自动修复 <strong>{agentPayload.diagnostic_verdict.auto_fix_count}</strong>
                  </span>
                  <span>
                    待人工确认 <strong>{agentPayload.diagnostic_verdict.manual_action_count}</strong>
                  </span>
                  <span>
                    预计场景 <strong>{agentPayload.diagnostic_verdict.estimated_scenario_count}</strong>
                  </span>
                  <span>
                    阻断接口 <strong>{agentPayload.diagnostic_verdict.blocked_endpoint_count}</strong>
                  </span>
                </div>
                {agentPayload.diagnostic_verdict.blockers.length ? (
                  <div className="create-task-agent-verdict__blockers">
                    {agentPayload.diagnostic_verdict.blockers.slice(0, 3).map((item) => (
                      <Text key={item} type="secondary">
                        {item}
                      </Text>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : null}
            <div className={`create-task-agent-decision is-${agentDecisionSummary.tone}`}>
              <div className="create-task-agent-decision__copy">
                <Text type="secondary">当前结论</Text>
                <Text strong className="create-task-agent-decision__title">
                  {agentDecisionSummary.title}
                </Text>
                <Text type="secondary">{agentDecisionSummary.description}</Text>
              </div>
              <div className="create-task-agent-decision__actions">
                {agentDecisionItems[0] ? (
                  <Button size="small" type="primary" ghost onClick={() => handleOpenAgentFocus(agentDecisionItems[0].view)}>
                    {isAgentStudio ? agentDecisionItems[0].actionLabel : "去工作台处理"}
                  </Button>
                ) : null}
                {!isAgentStudio && compactWorkbenchItemCount ? (
                  <Button size="small" type="link" onClick={() => handleOpenAgentStudio("overview")}>
                    打开完整工作台
                  </Button>
                ) : null}
              </div>
            </div>
            {agentDecisionItems.length ? (
              <div className="create-task-agent-decision-list">
                {agentDecisionItems.map((item) => (
                  <div key={item.key} className="create-task-agent-decision-item">
                    <div className="create-task-agent-decision-item__copy">
                      <Text strong>{item.title}</Text>
                      <Text type="secondary">{item.detail}</Text>
                    </div>
                    <Button size="small" type="link" onClick={() => handleOpenAgentFocus(item.view)}>
                      {isAgentStudio ? item.actionLabel : "去工作台"}
                    </Button>
                  </div>
                ))}
              </div>
            ) : null}
            <div className="create-task-agent-meta">
              <span className="surface-chip">
                就绪度 <strong>{agentPayload.summary.ready_score}/{agentPayload.summary.max_score}</strong>
              </span>
              <span className="surface-chip">
                字数 <strong>{agentPayload.summary.requirement_chars}</strong>
              </span>
              <span className="surface-chip">
                {isAgentStudio ? "可带回" : "可创建"} <strong>{agentPayload.summary.ready_to_create ? "是" : "否"}</strong>
              </span>
              <span className="surface-chip">
                {isAgentStudio ? "执行准备" : "可执行"} <strong>{agentPayload.summary.ready_to_execute ? "是" : "否"}</strong>
              </span>
              <span className="surface-chip">
                亮点 <strong>{agentPayload.summary.highlight_count ?? agentPayload.highlights.length}</strong>
              </span>
              <span className="surface-chip">
                风险 <strong>{agentPayload.summary.risk_count ?? agentPayload.risks.length}</strong>
              </span>
              <span className="surface-chip">
                可信度{" "}
                <strong>
                  {agentPayload.summary.confidence_score ?? 0} / {getAgentConfidenceLabel(agentPayload.summary.confidence_level)}
                </strong>
              </span>
            </div>
            {isAgentStudio ? (
              <Segmented
                block
                className="create-task-agent-view-switch"
                value={agentStudioView}
                onChange={(value) => setAgentStudioView(value as "overview" | "followups" | "document" | "knowledge")}
                options={[
                  { label: "概览", value: "overview" },
                  {
                    label: (
                      <span className="create-task-agent-view-option">
                        追问
                        {sortedFollowUpQuestions.length ? (
                          <span className="create-task-agent-view-badge">{sortedFollowUpQuestions.length}</span>
                        ) : null}
                      </span>
                    ),
                    value: "followups",
                  },
                  {
                    label: (
                      <span className="create-task-agent-view-option">
                        修正
                        {agentPayload.document_actions.length ? (
                          <span className="create-task-agent-view-badge">{agentPayload.document_actions.length}</span>
                        ) : null}
                      </span>
                    ),
                    value: "document",
                  },
                  {
                    label: (
                      <span className="create-task-agent-view-option">
                        依据
                        {agentPayload.knowledge_hits.length ? (
                          <span className="create-task-agent-view-badge">{agentPayload.knowledge_hits.length}</span>
                        ) : null}
                      </span>
                    ),
                    value: "knowledge",
                  },
                ]}
              />
            ) : (
              <div className="create-task-agent-compact-intro">
                <Text type="secondary">
                  这里只保留快速补全；追问、文档修正和知识依据统一放到 Agent 工作台处理。
                </Text>
                {compactWorkbenchItemCount ? (
                  <Button type="link" size="small" onClick={() => handleOpenAgentStudio()}>
                    打开完整工作台，继续处理 {compactWorkbenchItemCount} 项
                  </Button>
                ) : null}
              </div>
            )}
            <div className={`create-task-agent-sections${isAgentStudio ? " is-studio" : ""}`}>
              {showOverviewSections && agentPayload.action_plan?.length ? (
                <div className="create-task-agent-section create-task-agent-section--wide">
                  <Text strong className="create-task-agent-section__title">
                    Agent 行动计划
                  </Text>
                  <div className="create-task-agent-plan">
                    {agentPayload.action_plan.map((item, index) => (
                      <div key={item.key} className={`create-task-agent-plan__item is-${item.status || "default"}`}>
                        <span className="create-task-agent-plan__step">{index + 1}</span>
                        <div className="create-task-agent-plan__copy">
                          <div className="create-task-agent-list__row">
                            <Text strong>{item.title}</Text>
                            <Tag color={getAgentPlanStatusColor(item.status)}>{getAgentPlanStatusLabel(item.status)}</Tag>
                          </div>
                          <Text type="secondary">{item.detail}</Text>
                        </div>
                        {item.target_view ? (
                          <Button
                            size="small"
                            type="link"
                            onClick={() => handleOpenAgentFocus(item.target_view as "overview" | "followups" | "document" | "knowledge")}
                          >
                            {item.action_label || "查看"}
                          </Button>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
              {showOverviewSections && agentPayload.quality_gates?.length ? (
                <div className="create-task-agent-section">
                  <Text strong className="create-task-agent-section__title">
                    质量门禁
                  </Text>
                  <div className="create-task-agent-list">
                    {agentPayload.quality_gates.map((item) => (
                      <div
                        key={item.key}
                        className={`create-task-agent-list__item${item.status === "block" || item.status === "warn" ? " is-warning" : ""}`}
                      >
                        <div className="create-task-agent-list__row">
                          <Text strong>{item.label}</Text>
                          <Tag color={getAgentQualityGateStatusColor(item.status)}>
                            {getAgentQualityGateStatusLabel(item.status)}
                          </Tag>
                        </div>
                        <Text type="secondary">{item.detail}</Text>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
              {showOverviewSections && agentPayload.signals.length ? (
                <div className="create-task-agent-section">
                  <Text strong className="create-task-agent-section__title">
                    识别信号
                  </Text>
                  <div className="create-task-agent-signal-grid">
                    {agentPayload.signals.map((item) => (
                      <div
                        key={item.key}
                        className={`create-task-agent-signal-card ${getAgentSignalToneClass(item.tone)}`}
                      >
                        <Text type="secondary">{item.label}</Text>
                        <Text strong>{item.value}</Text>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
              {showOverviewSections && agentPayload.scenario_outlook ? (
                <div className="create-task-agent-section">
                  <Text strong className="create-task-agent-section__title">
                    场景预估
                  </Text>
                  <div className="create-task-agent-meta">
                    <span className="surface-chip">
                      预计场景 <strong>{agentPayload.scenario_outlook.estimated_scenario_count ?? 0}</strong>
                    </span>
                    <span className="surface-chip">
                      资源组 <strong>{agentPayload.scenario_outlook.resource_group_count ?? 0}</strong>
                    </span>
                    <span className="surface-chip">
                      依赖链 <strong>{agentPayload.scenario_outlook.lifecycle_chain_count ?? 0}</strong>
                    </span>
                    <span className="surface-chip">
                      形态 <strong>{formatAgentScenarioShape(agentPayload.scenario_outlook.scenario_shape)}</strong>
                    </span>
                  </div>
                  <div className="create-task-agent-list">
                    <div className="create-task-agent-list__item">
                      <div className="create-task-agent-list__row">
                        <Text strong>接口分布</Text>
                        <Text type="secondary">
                          写接口 {agentPayload.scenario_outlook.write_endpoint_count ?? 0} / 只读 {agentPayload.scenario_outlook.read_only_endpoint_count ?? 0}
                        </Text>
                      </div>
                      <Text type="secondary">
                        当前文档大致会形成 {agentPayload.scenario_outlook.estimated_scenario_count ?? 0} 个场景，适合先用来判断覆盖率和依赖链是否完整。
                      </Text>
                    </div>
                    {agentPayload.scenario_outlook.uncovered_live_resource_endpoints?.length ? (
                      <div className="create-task-agent-list__item is-warning">
                        <Text strong>仍缺活资源来源的接口</Text>
                        <div className="create-task-agent-endpoint-list">
                          {agentPayload.scenario_outlook.uncovered_live_resource_endpoints.map((item) => (
                            <span key={item} className="surface-chip create-task-agent-endpoint-chip">
                              {item}
                            </span>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </div>
                </div>
              ) : null}
              {showOverviewSections && agentPayload.scenario_blueprint?.length ? (
                <div className="create-task-agent-section create-task-agent-section--wide">
                  <Text strong className="create-task-agent-section__title">
                    场景蓝图
                  </Text>
                  <div className="create-task-agent-list">
                    {agentPayload.scenario_blueprint.map((item) => (
                      <div key={item.key} className={`create-task-agent-list__item${item.status === "needs_context" ? " is-warning" : ""}`}>
                        <div className="create-task-agent-list__row">
                          <Text strong>{item.title}</Text>
                          <Tag color={getAgentBlueprintStatusColor(item.status)}>{getAgentBlueprintStatusLabel(item.status)}</Tag>
                        </div>
                        <Text>{item.objective}</Text>
                        <Text type="secondary">{item.dependency}</Text>
                        {item.endpoints.length ? (
                          <div className="create-task-agent-endpoint-list">
                            {item.endpoints.map((endpoint) => (
                              <span key={endpoint} className="surface-chip create-task-agent-endpoint-chip">
                                {endpoint}
                              </span>
                            ))}
                          </div>
                        ) : null}
                        {item.gaps?.length ? (
                          <div className="create-task-agent-endpoint-list">
                            {item.gaps.map((gap) => (
                              <Tag key={gap} color="warning">
                                {gap}
                              </Tag>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
              {showOverviewSections && agentPayload.coverage_gaps?.length ? (
                <div className="create-task-agent-section">
                  <Text strong className="create-task-agent-section__title">
                    覆盖缺口
                  </Text>
                  <div className="create-task-agent-list">
                    {agentPayload.coverage_gaps.map((item) => (
                      <div key={item} className="create-task-agent-list__item is-warning">
                        <Text>{item}</Text>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
              {showOverviewSections && agentPayload.resource_groups?.length ? (
                <div className="create-task-agent-section">
                  <Text strong className="create-task-agent-section__title">
                    资源链路
                  </Text>
                  <div className="create-task-agent-list">
                    {agentPayload.resource_groups.map((item) => (
                      <div
                        key={`${item.resource_key}-${item.status}`}
                        className={`create-task-agent-list__item${item.status === "needs_source" ? " is-warning" : ""}`}
                      >
                        <div className="create-task-agent-list__row">
                          <Text strong>{item.resource_key}</Text>
                          <Tag color={getAgentResourceStatusColor(item.status)}>{getAgentResourceStatusLabel(item.status)}</Tag>
                        </div>
                        <Text type="secondary">
                          方法 {item.methods.join(" / ")} · 预计场景 {item.estimated_scenarios ?? 0}
                        </Text>
                        <div className="create-task-agent-endpoint-list">
                          {item.endpoints.map((endpoint) => (
                            <span key={endpoint} className="surface-chip create-task-agent-endpoint-chip">
                              {endpoint}
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
              {showOverviewSections && agentPayload.recognized_endpoints.length ? (
                <div className="create-task-agent-section">
                  <Text strong className="create-task-agent-section__title">
                    识别接口
                  </Text>
                  <div className="create-task-agent-endpoint-list">
                    {agentPayload.recognized_endpoints.map((item) => (
                      <span key={item} className="surface-chip create-task-agent-endpoint-chip">
                        {item}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
              {(showOverviewSections || showCompactSections) && agentPayload.highlights.length ? (
                <div className="create-task-agent-section">
                  <Text strong className="create-task-agent-section__title">
                    关键结论
                  </Text>
                  <div className="create-task-agent-list">
                    {agentPayload.highlights.map((item) => (
                      <div key={item} className="create-task-agent-list__item">
                        <Text>{item}</Text>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
              {showKnowledgeSections && agentPayload.knowledge_hits.length ? (
                <div className="create-task-agent-section create-task-agent-section--wide">
                  <div className="create-task-agent-list__row">
                    <Text strong className="create-task-agent-section__title">
                      知识参考
                    </Text>
                    <Space size={6} wrap>
                      {agentPayload.rag_support?.query_count ? (
                        <span className="surface-chip">
                          查询 {agentPayload.rag_support.query_count}
                        </span>
                      ) : null}
                      {agentPayload.rag_support?.source_file_count ? (
                        <span className="surface-chip">
                          来源 {agentPayload.rag_support.source_file_count}
                        </span>
                      ) : null}
                      {typeof agentPayload.rag_support?.source_file_diversity === "number" ? (
                        <span className="surface-chip">
                          多样性 {formatAgentRatio(agentPayload.rag_support.source_file_diversity)}
                        </span>
                      ) : null}
                    </Space>
                  </div>
                  {agentPayload.knowledge_summary ? <Text type="secondary">{agentPayload.knowledge_summary}</Text> : null}
                  {agentPayload.rag_support?.query_variants_preview?.length ? (
                    <div className="create-task-agent-endpoint-list">
                      {agentPayload.rag_support.query_variants_preview.map((item) => (
                        <span key={item} className="surface-chip create-task-agent-endpoint-chip">
                          {item}
                        </span>
                      ))}
                    </div>
                  ) : null}
                  <div className="create-task-agent-list">
                    {agentPayload.knowledge_hits.map((item) => (
                      <div key={`${item.source_file}-${item.title}`} className="create-task-agent-list__item">
                        <div className="create-task-agent-list__row">
                          <Text strong>{item.title}</Text>
                          <Space size={6}>
                            {item.query_match_count ? <Tag color="geekblue">命中 {item.query_match_count} 条查询</Tag> : null}
                            <Tag color="blue">{item.doc_type || "knowledge"}</Tag>
                          </Space>
                        </div>
                        <Text type="secondary">{item.source_file}</Text>
                        <Text>{item.excerpt}</Text>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
              {showFollowUpSections && sortedFollowUpQuestions.length ? (
                <div className="create-task-agent-section create-task-agent-section--wide">
                  <div className="create-task-agent-list__row">
                    <Text strong className="create-task-agent-section__title">
                      待确认问题
                    </Text>
                    <Space size={6}>
                      <span className="surface-chip">
                        待确认 <strong>{sortedFollowUpQuestions.length}</strong>
                      </span>
                      {agentFollowUpHandledCount ? (
                        <span className="surface-chip">
                          已处理 <strong>{agentFollowUpHandledCount}</strong>
                        </span>
                      ) : null}
                    </Space>
                  </div>
                  <div className="create-task-agent-list">
                    {sortedFollowUpQuestions.map((item) => (
                      <div key={item.key} className="create-task-agent-list__item">
                        <div className="create-task-agent-list__row">
                          <Text strong>{item.question}</Text>
                          <Space size={6}>
                            {item.priority ? <Tag color={item.priority === "high" ? "error" : item.priority === "medium" ? "warning" : "default"}>{item.priority}</Tag> : null}
                            {(item.action_kind || item.field) ? (
                              <Button size="small" type="link" onClick={() => handleResolveFollowUpQuestion(item)}>
                                {getAgentFollowUpActionLabel(item)}
                              </Button>
                            ) : null}
                          </Space>
                        </div>
                        {item.field ? <Text type="secondary">建议补充到：{getAgentFieldLabel(item.field)}</Text> : null}
                        {item.reason ? <Text type="secondary">{item.reason}</Text> : null}
                        {item.answer_mode ? (
                          <div className="create-task-agent-follow-up-answer">
                            <Input
                              size="small"
                              value={agentFollowUpAnswers[item.key] ?? ""}
                              placeholder={item.answer_placeholder || "请输入回答"}
                              onChange={(event) =>
                                setAgentFollowUpAnswers((current) => ({
                                  ...current,
                                  [item.key]: event.target.value,
                                }))
                              }
                            />
                            <Button size="small" type="primary" ghost onClick={() => handleApplyFollowUpAnswer(item)}>
                              应用回答
                            </Button>
                          </div>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
              {showFollowUpSections && agentPayload.risks.length ? (
                <div className="create-task-agent-section">
                  <Text strong className="create-task-agent-section__title">
                    风险提醒
                  </Text>
                  <div className="create-task-agent-list">
                    {agentPayload.risks.map((item) => (
                      <div key={item} className="create-task-agent-list__item is-warning">
                        <Text>{item}</Text>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
              {showDocumentSections && agentPayload.document_fixes.length ? (
                <div className="create-task-agent-section">
                  <Text strong className="create-task-agent-section__title">
                    文档修正建议
                  </Text>
                  <div className="create-task-agent-list">
                    {agentPayload.document_fixes.map((item) => (
                      <div key={item} className="create-task-agent-list__item">
                        <Text>{item}</Text>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
              {showDocumentSections && agentPayload.document_actions.length ? (
                <div className="create-task-agent-section create-task-agent-section--wide">
                  <div className="create-task-agent-list__row">
                    <Text strong className="create-task-agent-section__title">
                      可插入片段
                    </Text>
                    <Button size="small" type="link" onClick={handleApplyAllDocumentActions}>
                      全部插入
                    </Button>
                  </div>
                  <div className="create-task-agent-list">
                    {agentPayload.document_actions.map((item) => (
                      <div key={item.key} className="create-task-agent-list__item">
                        <div className="create-task-agent-list__row">
                          <Text strong>{item.title}</Text>
                          <Button size="small" type="link" onClick={() => handleApplyDocumentAction(item.key)}>
                            插入
                          </Button>
                        </div>
                        {item.reason ? <Text type="secondary">{item.reason}</Text> : null}
                        <pre className="create-task-agent-snippet-preview">{item.content}</pre>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
              {showDocumentSections && agentPayload.document_preview?.content ? (
                <div className="create-task-agent-section create-task-agent-section--wide">
                  <div className="create-task-agent-list__row">
                    <Text strong className="create-task-agent-section__title">
                      规范化草稿预览
                    </Text>
                    <Button size="small" type="primary" ghost onClick={handleApplyDocumentPreview}>
                      一键替换
                    </Button>
                  </div>
                  {agentPayload.document_preview.summary ? (
                    <Text type="secondary">{agentPayload.document_preview.summary}</Text>
                  ) : null}
                  <pre className="create-task-agent-snippet-preview create-task-agent-snippet-preview--large">
                    {agentPayload.document_preview.content}
                  </pre>
                </div>
              ) : null}
              {(showOverviewSections || showCompactSections) && agentPayload.checks.length ? (
                <div className="create-task-agent-section">
                  <Text strong className="create-task-agent-section__title">
                    状态检查
                  </Text>
                  <div className="create-task-agent-list">
                    {agentPayload.checks.map((item) => (
                      <div key={item.key} className="create-task-agent-list__item">
                        <div className="create-task-agent-list__row">
                          <Text strong>{getAgentCheckKeyLabel(item.key)}</Text>
                          <Tag color={getAgentCheckTagColor(item.status)}>{getAgentCheckLabel(item.status)}</Tag>
                        </div>
                        <Text type="secondary">{item.message}</Text>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
              {(showOverviewSections || showCompactSections) && agentPayload.suggestions.length ? (
                <div className="create-task-agent-section">
                  <Text strong className="create-task-agent-section__title">
                    回填建议
                  </Text>
                  <div className="create-task-agent-list">
                    {agentPayload.suggestions.map((item) => (
                      <div key={`${item.field}-${item.value}`} className="create-task-agent-list__item">
                        <div className="create-task-agent-list__row">
                          <Text strong>{getAgentFieldLabel(item.field)}</Text>
                          <Space size={6}>
                            {agentPayload.form_patch?.[item.field] ? <Tag color="success">可回填</Tag> : null}
                            <Button
                              size="small"
                              type="link"
                              onClick={() => handleApplySingleSuggestion(item.field, item.value)}
                              disabled={!agentPayload.form_patch?.[item.field] || agentSuggestionStale}
                            >
                              应用
                            </Button>
                          </Space>
                        </div>
                        <Text>{item.value}</Text>
                        {item.reason ? <Text type="secondary">{item.reason}</Text> : null}
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
              {(showOverviewSections || showCompactSections) && agentPayload.next_actions.length ? (
                <div className="create-task-agent-section">
                  <Text strong className="create-task-agent-section__title">
                    下一步
                  </Text>
                  <div className="create-task-agent-list">
                    {agentPayload.next_actions.map((item) => (
                      <div key={item} className="create-task-agent-list__item">
                        <Text>{item}</Text>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
              {showFollowUpSections && agentPayload.warnings.length ? (
                <div className="create-task-agent-section">
                  <Text strong className="create-task-agent-section__title">
                    额外提醒
                  </Text>
                  <div className="create-task-agent-list">
                    {agentPayload.warnings.map((item) => (
                      <div key={item} className="create-task-agent-list__item is-warning">
                        <Text>{item}</Text>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
            {isAgentStudio && !activeStudioViewHasContent ? (
              <div className="create-task-agent-empty-view">
                <Text type="secondary">当前视图暂时没有可展示内容，先切换到其他视图或重新分析文档。</Text>
              </div>
            ) : null}
          </>
        ) : (
          <Text type="secondary">
            {isAgentStudio
              ? "导入文档后会自动分析；这里更适合先处理追问、资源链路和场景预估，再带回创建页。"
              : "导入文档后会自动分析；也可以手动生成建议，先识别任务草案，再判断风险和执行环境。"}
          </Text>
        )}
      </div>
    </Card>
  );

  return (
    <Space
      direction="vertical"
      size={20}
      style={{ width: "100%" }}
      className={`create-task-page${isAgentStudio ? " agent-studio-page" : ""}`}
    >
      {isAgentStudio ? (
        <div className="agent-studio-hero">
          <div className="agent-studio-hero__copy">
            <Text type="secondary">Agent Studio</Text>
            <Typography.Title level={2} className="agent-studio-hero__title">
              文档诊断、追问与场景预估工作台
            </Typography.Title>
            <Text className="agent-studio-hero__desc">
              在独立工作台里先把需求文档修到稳定可解析，再带回创建页由工作流创建和执行。
            </Text>
          </div>
          <div className="agent-studio-hero__meta">
            <span className="surface-chip">
              追问待处理 <strong>{sortedFollowUpQuestions.length}</strong>
            </span>
            {agentPayload?.scenario_outlook?.estimated_scenario_count ? (
              <span className="surface-chip">
                预计场景 <strong>{agentPayload.scenario_outlook.estimated_scenario_count}</strong>
              </span>
            ) : null}
            {agentPayload?.summary?.confidence_score ? (
              <span className="surface-chip">
                可信度 <strong>{agentPayload.summary.confidence_score}</strong>
              </span>
            ) : null}
          </div>
        </div>
      ) : null}
      <Row
        gutter={20}
        align="top"
        className={`create-task-layout${isAgentStudio ? " is-agent-studio" : ""}`}
      >
        <Col xs={24} xl={isAgentStudio ? 10 : 19}>
          <Card bordered={false} className="panel-card panel-card--form create-task-card">
            {isAgentStudio ? (
              <div className="agent-studio-panel-head">
                <div>
                  <Text type="secondary">Document Workspace</Text>
                  <Typography.Title level={4} className="agent-studio-panel-head__title">
                    文档工作区
                  </Typography.Title>
                </div>
                <Text type="secondary">上传文档、补正文案，再交给 Agent 做诊断和追问。</Text>
              </div>
            ) : null}
            <Form
              form={form}
              layout="vertical"
              initialValues={{
                requirement_text: "",
                environment: "test",
                target_system: DEFAULT_TARGET_SYSTEM,
                rag_enabled: DEFAULT_REQUIREMENT_RAG_ENABLED,
                project_id: currentProjectId || undefined,
              }}
              onValuesChange={(changedValues) => {
                const changedKeys = Object.keys(changedValues);
                if (!changedKeys.length) {
                  return;
                }
                const programmaticKeys = programmaticFieldKeysRef.current;
                let userChanged = false;
                for (const key of changedKeys) {
                  if (!programmaticKeys.has(key)) {
                    userEditedFieldsRef.current.add(key);
                    userChanged = true;
                  }
                }
                if (userChanged && agentAutoAppliedLabels.length) {
                  setAgentAutoAppliedLabels([]);
                }
              }}
              onFinish={isAgentStudio ? undefined : handleSubmit}
            >
              {!isAgentStudio ? (
                <div className="create-task-mode-hint">
                  <span className="surface-chip">文档已成型：创建并进入工作流</span>
                  <span className="surface-chip">文档不确定：Agent 诊断后回填</span>
                </div>
              ) : null}
              {isAgentStudio ? (
                <>
                  <div className="create-task-upload-wrap">
                    <Upload.Dragger
                      className="create-task-uploader"
                      accept=".md,.txt"
                      multiple={false}
                      showUploadList={false}
                      disabled={readingFile}
                      beforeUpload={async (file) => {
                        try {
                          setReadingFile(true);
                          setUploadedFileName(file.name);
                          const text = await file.text();
                          const currentTaskName = String(form.getFieldValue("task_name") ?? "").trim();
                          const currentTargetSystem = String(form.getFieldValue("target_system") ?? "").trim();
                          const nextTaskName = currentTaskName || deriveTaskNameFromFileName(file.name);
                          const detectedBaseUrl = extractBaseUrlFromRequirementText(text);
                          const nextValues: Record<string, string> = {
                            requirement_text: text,
                            task_name: nextTaskName,
                          };
                          if (detectedBaseUrl && shouldAutoFillTargetSystem(currentTargetSystem)) {
                            nextValues.target_system = detectedBaseUrl;
                          }
                          userEditedFieldsRef.current.clear();
                          setAgentAutoAppliedLabels([]);
                          setAgentFollowUpHandledCount(0);
                          setAgentFollowUpAnswers({});
                          markProgrammaticFields(Object.keys(nextValues));
                          form.setFieldsValue(nextValues);
                          setAgentPayload(null);
                          setAgentSnapshotKey("");
                          message.success(`已导入文件：${file.name}`);
                        } catch {
                          message.error("读取文件失败，请重试");
                        } finally {
                          setReadingFile(false);
                        }
                        return false;
                      }}
                    >
                      <p className="ant-upload-drag-icon">
                        <UploadOutlined />
                      </p>
                      <p className="create-task-upload-title">
                        {readingFile ? "读取中..." : "拖拽或选择文档"}
                      </p>
                      {uploadedFileName ? (
                        <div className="create-task-upload-file">{uploadedFileName}</div>
                      ) : null}
                    </Upload.Dragger>
                  </div>

                  <Form.Item
                    name="requirement_text"
                    label="需求描述"
                    className={`create-task-field create-task-field--requirement_text${agentFocusedField === "requirement_text" ? " is-agent-focused" : ""}`}
                    rules={[{ required: true, message: "请输入需求描述（或从右侧导入文件）" }]}
                  >
                    <TextArea
                      id="task-create-requirement_text"
                      className="create-task-textarea"
                      rows={16}
                      placeholder="请输入测试需求描述，例如：用户输入正确账号密码后登录成功并进入个人中心"
                    />
                  </Form.Item>
                </>
              ) : (
                <>
                  <Row gutter={16}>
                    <Col xs={24} xl={16}>
                      <Form.Item
                        name="task_name"
                        label="任务名称"
                        className={`create-task-field create-task-field--task_name${agentFocusedField === "task_name" ? " is-agent-focused" : ""}`}
                      >
                        <Input id="task-create-task_name" placeholder="例如：用户登录功能测试；留空则自动取文档文件名" />
                      </Form.Item>
                    </Col>
                    <Col xs={24} xl={8}>
                      <Form.Item
                        name="project_id"
                        label="所属项目"
                      >
                        <Select
                          allowClear
                          placeholder={isAuthenticated ? "请选择项目" : "登录后可按项目归属"}
                          disabled={!isAuthenticated}
                          options={projects.map((project) => ({
                            value: project.id,
                            label: project.is_default ? `${project.name}（默认）` : project.name,
                          }))}
                        />
                      </Form.Item>
                    </Col>
                  </Row>

                  <Row gutter={20} align="top">
                    <Col xs={24} xl={16}>
                      <Form.Item
                        name="requirement_text"
                        label="需求描述"
                        className={`create-task-field create-task-field--requirement_text${agentFocusedField === "requirement_text" ? " is-agent-focused" : ""}`}
                        rules={[{ required: true, message: "请输入需求描述（或从右侧导入文件）" }]}
                      >
                        <TextArea
                          id="task-create-requirement_text"
                          className="create-task-textarea"
                          rows={14}
                          placeholder="请输入测试需求描述，例如：用户输入正确账号密码后登录成功并进入个人中心"
                        />
                      </Form.Item>
                    </Col>
                    <Col xs={24} xl={8}>
                      <div className="create-task-side-stack">
                        <div className="create-task-upload-wrap">
                          <Upload.Dragger
                            className="create-task-uploader"
                            accept=".md,.txt"
                            multiple={false}
                            showUploadList={false}
                            disabled={readingFile}
                            beforeUpload={async (file) => {
                              try {
                                setReadingFile(true);
                                setUploadedFileName(file.name);
                                const text = await file.text();
                                const currentTaskName = String(form.getFieldValue("task_name") ?? "").trim();
                                const currentTargetSystem = String(form.getFieldValue("target_system") ?? "").trim();
                                const nextTaskName = currentTaskName || deriveTaskNameFromFileName(file.name);
                                const detectedBaseUrl = extractBaseUrlFromRequirementText(text);
                                const nextValues: Record<string, string> = {
                                  requirement_text: text,
                                  task_name: nextTaskName,
                                };
                                if (detectedBaseUrl && shouldAutoFillTargetSystem(currentTargetSystem)) {
                                  nextValues.target_system = detectedBaseUrl;
                                }
                                userEditedFieldsRef.current.clear();
                                setAgentAutoAppliedLabels([]);
                                setAgentFollowUpHandledCount(0);
                                setAgentFollowUpAnswers({});
                                markProgrammaticFields(Object.keys(nextValues));
                                form.setFieldsValue(nextValues);
                                setAgentPayload(null);
                                setAgentSnapshotKey("");
                                message.success(`已导入文件：${file.name}`);
                              } catch {
                                message.error("读取文件失败，请重试");
                              } finally {
                                setReadingFile(false);
                              }
                              return false;
                            }}
                          >
                            <p className="ant-upload-drag-icon">
                              <UploadOutlined />
                            </p>
                            <p className="create-task-upload-title">
                              {readingFile ? "读取中..." : "拖拽或选择文档"}
                            </p>
                            {uploadedFileName ? (
                              <div className="create-task-upload-file">{uploadedFileName}</div>
                            ) : null}
                          </Upload.Dragger>
                        </div>

                        <Form.Item
                          name="target_system"
                          label="目标系统地址"
                          className={`create-task-field create-task-field--target_system${agentFocusedField === "target_system" ? " is-agent-focused" : ""}`}
                          rules={[{ type: "url", message: "请输入合法 URL（如 http://127.0.0.1:8001）" }]}
                        >
                          <Input id="task-create-target_system" placeholder="自动识别或手动填写" />
                        </Form.Item>

                        <Row gutter={16}>
                          <Col xs={24} md={12} xl={14}>
                            <Form.Item
                              name="environment"
                              label="执行环境"
                              className={`create-task-field create-task-field--environment${agentFocusedField === "environment" ? " is-agent-focused" : ""}`}
                            >
                              <Select
                                id="task-create-environment"
                                options={environmentOptions}
                              />
                            </Form.Item>
                          </Col>
                          <Col xs={24} md={12} xl={10}>
                            <Form.Item
                              name="rag_enabled"
                              label="RAG"
                              valuePropName="checked"
                            >
                              <Switch checkedChildren="开" unCheckedChildren="关" />
                            </Form.Item>
                          </Col>
                        </Row>
                      </div>
                    </Col>
                  </Row>

                  <Form.Item className="create-task-actions">
                    <Space>
                      <Button type="primary" htmlType="submit" loading={submitting}>
                        创建任务
                      </Button>
                      <Button onClick={() => handleOpenAgentStudio()}>先用 Agent 诊断文档</Button>
                      <Button onClick={() => navigate("/tasks")}>取消</Button>
                    </Space>
                  </Form.Item>
                </>
              )}
            </Form>
          </Card>
        </Col>

        <Col xs={24} xl={isAgentStudio ? 14 : 5} className="create-task-agent-column">
          {isAgentStudio ? (
            <Card bordered={false} className="agent-studio-draft-card agent-studio-handoff-card">
              <div className="agent-studio-draft-card__head">
                <div>
                  <Text type="secondary">Handoff</Text>
                  <Typography.Title level={4} className="agent-studio-draft-card__title">
                    回到工作流创建
                  </Typography.Title>
                </div>
                <Tag color={getAgentVerdictColor(agentPayload?.diagnostic_verdict?.severity)}>
                  {agentPayload?.diagnostic_verdict?.label || (agentPayload?.summary?.ready_to_create ? "可交付" : "待完善")}
                </Tag>
              </div>
              <Text type="secondary" className="agent-studio-handoff-card__copy">
                {agentPayload?.diagnostic_verdict?.summary ||
                  "Agent 只负责诊断、补全和质量门禁；任务创建、执行、重试与报告沉淀统一交给工作流。"}
              </Text>
              <div className="agent-studio-handoff-flow">
                <div className="agent-studio-handoff-flow__item">
                  <span>1</span>
                  <Text>导入或粘贴需求文档</Text>
                </div>
                <div className="agent-studio-handoff-flow__item">
                  <span>2</span>
                  <Text>处理追问、补齐资源链路</Text>
                </div>
                <div className="agent-studio-handoff-flow__item">
                  <span>3</span>
                  <Text>带回创建页提交工作流</Text>
                </div>
              </div>
              <div className="agent-studio-draft-grid">
                <div className="agent-studio-draft-item">
                  <Text type="secondary">任务名称</Text>
                  <Text strong>{String(watchedTaskName || "待识别")}</Text>
                </div>
                <div className="agent-studio-draft-item">
                  <Text type="secondary">所属项目</Text>
                  <Text strong>{projects.find((item) => item.id === (watchedProjectId || currentProjectId))?.name || "未选择"}</Text>
                </div>
                <div className="agent-studio-draft-item">
                  <Text type="secondary">目标系统</Text>
                  <Text strong>{String(watchedTargetSystem || "待识别")}</Text>
                </div>
                <div className="agent-studio-draft-item">
                  <Text type="secondary">执行环境</Text>
                  <Text strong>{String(watchedEnvironment || "未选择")}</Text>
                </div>
                <div className="agent-studio-draft-item">
                  <Text type="secondary">RAG</Text>
                  <Text strong>{watchedRagEnabled ? "开启" : "关闭"}</Text>
                </div>
              </div>
              <div className="agent-studio-draft-actions">
                <Button type="primary" onClick={handleOpenCreateView}>
                  带回创建页
                </Button>
                <Button onClick={() => void handleGenerateAgentSuggestion()} loading={agentLoading}>
                  {agentPayload ? "刷新 Agent" : "启动分析"}
                </Button>
              </div>
            </Card>
          ) : (
            <VueAgentDialogueMount
              payload={agentPayload}
              loading={agentLoading}
              stale={agentSuggestionStale}
              activeView={agentStudioView}
              onAnalyze={() => void handleGenerateAgentSuggestion()}
              onApply={handleApplyAgentSuggestion}
              canApply={Boolean(agentPayload && Object.keys(agentPayload.form_patch ?? {}).length && !agentSuggestionStale)}
            />
          )}
        </Col>
      </Row>
      {isAgentStudio ? <div className="agent-studio-agent-panel">{agentPanel}</div> : null}
    </Space>
  );
}
