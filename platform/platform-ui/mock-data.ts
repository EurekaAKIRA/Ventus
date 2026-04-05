import type {
  AnalysisReport,
  ExecutionResult,
  HistoryTaskItem,
  ParsedRequirement,
  ParseMetadata,
  TaskArtifactContent,
  TaskArtifactItem,
  RetrievedChunk,
  ScenarioModel,
  TaskContext,
  TaskDetailPayload,
  TaskListItem,
  TestCaseDSL,
  ValidationReport,
} from "./api-contract";

export const mockTaskList: TaskListItem[] = [
  {
    task_id: "task_20260329_001",
    task_name: "用户登录功能测试",
    source_type: "text",
    source_path: null,
    created_at: "2026-03-29T10:00:00Z",
    language: "zh-CN",
    status: "parsed",
    notes: [],
    rag_enabled: false,
  },
  {
    task_id: "task_20260329_002",
    task_name: "订单提交流程测试",
    source_type: "file",
    source_path: "/docs/order_requirement.md",
    created_at: "2026-03-29T11:00:00Z",
    language: "zh-CN",
    status: "running",
    notes: ["已进入执行阶段"],
    rag_enabled: false,
  },
];

export const mockTaskContext: TaskContext = {
  task_id: "task_20260329_001",
  task_name: "用户登录功能测试",
  source_type: "text",
  source_path: null,
  created_at: "2026-03-29T10:00:00Z",
  language: "zh-CN",
  status: "parsed",
  notes: [],
  rag_enabled: false,
};

export const mockParsedRequirement: ParsedRequirement = {
  objective: "用户输入正确账号密码后登录成功并进入个人中心",
  actors: ["用户"],
  entities: ["账号", "密码", "个人中心"],
  preconditions: ["用户已注册有效账号"],
  actions: ["输入账号", "输入密码", "点击登录"],
  expected_results: ["登录成功", "页面跳转到个人中心", "显示用户昵称"],
  constraints: [],
  ambiguities: [],
  source_chunks: ["chunk_001", "chunk_002"],
};

export const mockRetrievedContext: RetrievedChunk[] = [
  {
    chunk_id: "chunk_001",
    content: "用户输入正确账号密码后应登录成功并进入个人中心页面。",
    score: 4.8,
    section_title: "登录流程",
    source_file: "login_requirement.md",
  },
];

export const mockScenarios: ScenarioModel[] = [
  {
    scenario_id: "scenario_001",
    name: "正常账号密码登录成功",
    goal: "验证用户可以成功登录并进入个人中心",
    steps: [
      { type: "given", text: "用户已注册且账号状态正常" },
      { type: "when", text: "用户输入正确账号和密码并点击登录" },
      { type: "then", text: "系统跳转到个人中心并显示用户昵称" },
    ],
    assertions: ["登录成功", "跳转成功", "昵称显示正确"],
    source_chunks: ["chunk_001"],
    priority: "P0",
    preconditions: ["系统服务正常"],
  },
];

export const mockTestCaseDSL: TestCaseDSL = {
  dsl_version: "0.1.0",
  task_id: "task_20260329_001",
  task_name: "用户登录功能测试",
  feature_name: "用户登录功能测试",
  execution_mode: "api",
  metadata: {
    source_type: "text",
    language: "zh-CN",
  },
  scenarios: [
    {
      scenario_id: "scenario_001",
      name: "正常账号密码登录成功",
      goal: "验证用户可以成功登录并进入个人中心",
      priority: "P0",
      preconditions: ["系统服务正常"],
      source_chunks: ["chunk_001"],
      steps: [
        {
          step_id: "step_001",
          step_type: "given",
          text: "用户已注册且账号状态正常",
        },
        {
          step_id: "step_002",
          step_type: "when",
          text: "调用登录接口提交正确账号和密码",
          request: {
            method: "POST",
            url: "/api/login",
          },
        },
        {
          step_id: "step_003",
          step_type: "then",
          text: "返回成功结果并包含用户信息",
          assertions: ["status == 200", "response.code == 0"],
        },
      ],
    },
  ],
};

export const mockExecutionResult: ExecutionResult = {
  task_id: "task_20260329_001",
  executor: "api-runner",
  status: "running",
  scenario_results: [
    {
      scenario_id: "scenario_001",
      scenario_name: "正常账号密码登录成功",
      status: "passed",
      duration_ms: 320,
      passed_steps: 3,
      failed_steps: 0,
    },
  ],
  metrics: {
    total_scenarios: 1,
    passed_scenarios: 1,
    failed_scenarios: 0,
    average_response_time_ms: 320,
  },
  logs: [
    {
      time: "2026-03-29T10:02:01Z",
      level: "INFO",
      message: "开始执行场景 scenario_001",
    },
    {
      time: "2026-03-29T10:02:02Z",
      level: "INFO",
      message: "登录接口返回 200",
    },
  ],
};

export const mockArtifacts: TaskArtifactItem[] = [
  { type: "raw_requirement", label: "原始需求文本", updated_at: "2026-03-29T10:00:03Z" },
  { type: "parsed_requirement", label: "结构化需求", updated_at: "2026-03-29T10:00:05Z" },
  { type: "retrieved_context", label: "检索上下文", updated_at: "2026-03-29T10:00:07Z" },
  { type: "scenarios", label: "测试场景", updated_at: "2026-03-29T10:00:09Z" },
  { type: "dsl", label: "DSL 文件", updated_at: "2026-03-29T10:00:10Z" },
  { type: "feature", label: "Feature 文件", updated_at: "2026-03-29T10:00:11Z" },
  { type: "validation_report", label: "校验报告", updated_at: "2026-03-29T10:00:12Z" },
  { type: "analysis_report", label: "分析报告", updated_at: "2026-03-29T10:00:13Z" },
];

export const mockValidationReport: ValidationReport = {
  feature_name: "用户登录功能测试",
  passed: true,
  errors: [],
  warnings: [],
  metrics: {
    scenario_count: 1,
    step_count: 3,
    average_step_count: 3,
  },
};

export const mockParseMetadata: ParseMetadata = {
  parse_mode: "rules",
  llm_attempted: true,
  llm_used: false,
  rag_enabled: false,
  rag_used: false,
  rag_fallback_reason: "",
  fallback_reason: "llm_config_missing",
  llm_error_type: "configuration_error",
  llm_provider_profile: "tencent_hunyuan_openai_compat",
  retrieval_mode: "keyword",
  retrieval_top_k: 5,
  rerank_enabled: false,
  document_char_count: 120,
  cleaned_char_count: 116,
  chunk_count: 2,
  embedding_batch_size: 32,
  estimated_embedding_calls: 1,
  processing_tier: "realtime",
  large_document_warning: "",
  retrieval_metrics: {
    returned_count: 2,
    requested_top_k: 5,
    coverage_ratio: 0.4,
    duplicate_ratio: 0,
    score_avg: 3.2,
    rerank_applied: false,
    embedded_chunk_count: 0,
    embedding_coverage: 0,
    embedding_error: "",
    embedding_error_detail: "",
  },
  retrieval_scoring: {
    lexical_weight: 4,
    vector_weight: 6,
    rerank_vector_weight: 7,
    rerank_lexical_weight: 2,
    rerank_title_boost: 0.2,
    rerank_content_boost: 0.2,
  },
  performance: {
    elapsed_ms: 120.5,
    target_ms: 8000,
    within_target: true,
    slow_reason: "",
  },
};

export const mockAnalysisReport: AnalysisReport = {
  task_id: "task_20260329_001",
  task_name: "用户登录功能测试",
  quality_status: "passed",
  summary: {
    scenario_count: 1,
    validation_passed: true,
    warning_count: 0,
    error_count: 0,
  },
  findings: [],
  chart_data: {
    validation: {
      passed: 1,
      failed: 0,
      warnings: 0,
    },
  },
};

export const mockArtifactContentByType: Record<string, TaskArtifactContent> = {
  raw_requirement: {
    type: "raw_requirement",
    content: "用户输入正确账号密码后登录成功并进入个人中心",
  },
  parsed_requirement: {
    type: "parsed_requirement",
    content: mockParsedRequirement,
  },
  retrieved_context: {
    type: "retrieved_context",
    content: mockRetrievedContext,
  },
  scenarios: {
    type: "scenarios",
    content: mockScenarios,
  },
  dsl: {
    type: "dsl",
    content: mockTestCaseDSL,
  },
  feature: {
    type: "feature",
    content: `Feature: 用户登录功能测试

  Scenario: 正常账号密码登录成功
    Given 用户已注册且账号状态正常
    When 用户输入正确账号和密码并点击登录
    Then 系统跳转到个人中心并显示用户昵称`,
  },
  validation_report: {
    type: "validation_report",
    content: mockValidationReport,
  },
  analysis_report: {
    type: "analysis_report",
    content: mockAnalysisReport,
  },
};

export const mockTaskDetail: TaskDetailPayload = {
  task_context: mockTaskContext,
  parse_metadata: mockParseMetadata,
  parsed_requirement: mockParsedRequirement,
  retrieved_context: mockRetrievedContext,
  scenarios: mockScenarios,
  test_case_dsl: mockTestCaseDSL,
  execution_result: mockExecutionResult,
  validation_report: mockValidationReport,
  analysis_report: mockAnalysisReport,
  feature_text: `Feature: 用户登录功能测试

  Scenario: 正常账号密码登录成功
    Given 用户已注册且账号状态正常
    When 用户输入正确账号和密码并点击登录
    Then 系统跳转到个人中心并显示用户昵称`,
};

export const mockHistoryTaskList: HistoryTaskItem[] = [
  {
    task_id: "task_20260328_003",
    task_name: "支付回调流程测试",
    source_type: "file",
    source_path: "/docs/payment_requirement.md",
    created_at: "2026-03-28T15:10:00Z",
    language: "zh-CN",
    status: "passed",
    notes: [],
    finished_at: "2026-03-28T15:26:00Z",
  },
  {
    task_id: "task_20260328_004",
    task_name: "订单取消流程测试",
    source_type: "text",
    source_path: null,
    created_at: "2026-03-28T16:00:00Z",
    language: "zh-CN",
    status: "failed",
    notes: ["断言不通过"],
    finished_at: "2026-03-28T16:08:00Z",
  },
];
