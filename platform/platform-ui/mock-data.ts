import type {
  AnalysisReport,
  ExecutionResult,
  ParsedRequirement,
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

export const mockTaskDetail: TaskDetailPayload = {
  task_context: mockTaskContext,
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
