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
    task_name: "Restful Booker 最小闭环测试",
    source_type: "text",
    source_path: null,
    created_at: "2026-03-29T10:00:00Z",
    language: "zh-CN",
    status: "passed",
    notes: ["已完成执行并生成报告"],
    rag_enabled: true,
    target_system: "https://restful-booker.herokuapp.com",
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
  task_name: "Restful Booker 最小闭环测试",
  source_type: "text",
  source_path: null,
  created_at: "2026-03-29T10:00:00Z",
  language: "zh-CN",
  status: "passed",
  notes: ["已完成执行并生成报告"],
  rag_enabled: true,
  target_system: "https://restful-booker.herokuapp.com",
};

export const mockParsedRequirement: ParsedRequirement = {
  objective: "验证 Restful Booker 从鉴权、创建 booking、查询 booking 到删除 booking 的完整接口闭环",
  actors: ["测试人员", "API Runner"],
  entities: ["token", "booking", "booking_id"],
  preconditions: ["目标系统可访问", "测试账号 admin/password123 可用于获取 token"],
  actions: ["获取鉴权 token", "创建 booking 资源", "查询 booking 详情", "删除 booking 资源"],
  expected_results: ["token 非空", "bookingid 可被提取", "查询结果与创建请求一致", "删除接口返回 201"],
  constraints: ["删除接口需要 Cookie: token={{token}}", "查询与删除步骤依赖创建接口返回的 booking_id"],
  ambiguities: [],
  source_chunks: ["chunk_auth", "chunk_booking"],
};

export const mockRetrievedContext: RetrievedChunk[] = [
  {
    chunk_id: "chunk_auth",
    content: "POST /auth 使用 username 和 password 获取 token，后续删除接口需要 Cookie: token={{token}}。",
    score: 4.9,
    section_title: "Authentication",
    source_file: "restful-booker-api.md",
  },
  {
    chunk_id: "chunk_booking",
    content: "POST /booking 创建 booking 后返回 bookingid；GET /booking/{id} 查询详情；DELETE /booking/{id} 删除资源。",
    score: 4.7,
    section_title: "Booking lifecycle",
    source_file: "restful-booker-api.md",
  },
];

export const mockScenarios: ScenarioModel[] = [
  {
    scenario_id: "scenario_booking_lifecycle",
    name: "鉴权后创建、查询并删除 booking",
    goal: "验证 booking 资源完整生命周期以及 token、booking_id 的上下文传递",
    steps: [
      { type: "given", text: "调用 POST /auth 获取 token 并保存为上下文变量" },
      { type: "when", text: "调用 POST /booking 创建 booking，并保存 bookingid" },
      { type: "then", text: "调用 GET /booking/{{booking_id}} 查询详情并校验关键字段" },
      { type: "cleanup", text: "调用 DELETE /booking/{{booking_id}} 清理测试资源" },
    ],
    assertions: ["token 非空", "bookingid 存在", "firstname/lastname 与创建请求一致", "删除接口返回 201"],
    source_chunks: ["chunk_auth", "chunk_booking"],
    priority: "P0",
    preconditions: ["Restful Booker 服务可访问"],
  },
  {
    scenario_id: "scenario_booking_readonly",
    name: "booking 列表与详情只读校验",
    goal: "验证 booking 列表接口和详情接口的基础可用性",
    steps: [
      { type: "given", text: "调用 GET /booking 获取 booking id 列表" },
      { type: "then", text: "抽取一个 bookingid 查询详情并校验响应结构" },
    ],
    assertions: ["列表返回 200", "bookingid 字段存在", "详情响应包含 firstname、lastname 和 bookingdates"],
    source_chunks: ["chunk_booking"],
    priority: "P1",
    preconditions: ["系统存在可查询的 booking 数据"],
  },
];

export const mockTestCaseDSL: TestCaseDSL = {
  dsl_version: "0.1.0",
  task_id: "task_20260329_001",
  task_name: "Restful Booker 最小闭环测试",
  feature_name: "Restful Booker booking 生命周期测试",
  execution_mode: "api",
  metadata: {
    source_type: "text",
    language: "zh-CN",
    execution: { base_url: "https://restful-booker.herokuapp.com" },
  },
  scenarios: [
    {
      scenario_id: "scenario_booking_lifecycle",
      name: "鉴权后创建、查询并删除 booking",
      goal: "验证 booking 资源完整生命周期以及上下文变量传递",
      priority: "P0",
      preconditions: ["Restful Booker 服务可访问"],
      source_chunks: ["chunk_auth", "chunk_booking"],
      steps: [
        {
          step_id: "auth_token",
          step_type: "given",
          text: "获取鉴权 token",
          request: {
            method: "POST",
            url: "/auth",
            json: { username: "admin", password: "password123" },
          },
          assertions: ["status == 200", "json.token exists", "json.token != ''"],
          save_context: { token: "json.token" },
          saves_context: ["token"],
        },
        {
          step_id: "create_booking",
          step_type: "when",
          text: "创建 booking 资源",
          request: {
            method: "POST",
            url: "/booking",
            headers: { "Content-Type": "application/json", Accept: "application/json" },
            json: {
              firstname: "Jim",
              lastname: "Brown",
              totalprice: 111,
              depositpaid: true,
              bookingdates: { checkin: "2026-05-01", checkout: "2026-05-03" },
              additionalneeds: "Breakfast",
            },
          },
          assertions: ["status == 200", "json.bookingid exists", "json.booking.firstname == 'Jim'"],
          save_context: { booking_id: "json.bookingid" },
          saves_context: ["booking_id"],
        },
        {
          step_id: "get_booking",
          step_type: "then",
          text: "查询创建后的 booking 详情",
          request: {
            method: "GET",
            url: "/booking/{{booking_id}}",
            headers: { Accept: "application/json" },
          },
          uses_context: ["booking_id"],
          assertions: ["status == 200", "json.firstname == 'Jim'", "json.lastname == 'Brown'", "json.bookingdates.checkin exists"],
        },
        {
          step_id: "delete_booking",
          step_type: "cleanup",
          text: "删除测试过程中创建的 booking",
          request: {
            method: "DELETE",
            url: "/booking/{{booking_id}}",
            headers: { Cookie: "token={{token}}" },
          },
          uses_context: ["token", "booking_id"],
          assertions: ["status == 201"],
        },
      ],
    },
  ],
};

export const mockExecutionResult: ExecutionResult = {
  task_id: "task_20260329_001",
  executor: "api-runner",
  status: "passed",
  scenario_results: [
    {
      scenario_id: "scenario_booking_lifecycle",
      scenario_name: "鉴权后创建、查询并删除 booking",
      status: "passed",
      duration_ms: 1486,
      passed_steps: 4,
      failed_steps: 0,
      steps: [
        { step_id: "auth_token", text: "获取鉴权 token", status: "passed", message: "提取 token 成功" },
        { step_id: "create_booking", text: "创建 booking 资源", status: "passed", message: "保存 booking_id=31842" },
        { step_id: "get_booking", text: "查询创建后的 booking 详情", status: "passed", message: "关键字段一致性校验通过" },
        { step_id: "delete_booking", text: "删除测试过程中创建的 booking", status: "passed", message: "资源清理成功" },
      ],
    },
    {
      scenario_id: "scenario_booking_readonly",
      scenario_name: "booking 列表与详情只读校验",
      status: "passed",
      duration_ms: 642,
      passed_steps: 2,
      failed_steps: 0,
      steps: [
        { step_id: "list_booking", text: "获取 booking 列表", status: "passed", message: "返回 bookingid 列表" },
        { step_id: "get_existing_booking", text: "查询详情结构", status: "passed", message: "响应结构校验通过" },
      ],
    },
  ],
  metrics: {
    total_scenarios: 2,
    passed_scenarios: 2,
    failed_scenarios: 0,
    total_steps: 6,
    passed_steps: 6,
    failed_steps: 0,
    total_assertions: 15,
    passed_assertions: 15,
    failed_assertions: 0,
    pass_rate: 1,
    average_response_time_ms: 354.7,
  },
  logs: [
    { time: "2026-03-29T10:02:01Z", level: "INFO", message: "开始执行 Restful Booker 最小闭环场景" },
    { time: "2026-03-29T10:02:02Z", level: "INFO", message: "POST /auth 返回 200，token 已写入上下文" },
    { time: "2026-03-29T10:02:03Z", level: "INFO", message: "POST /booking 返回 bookingid=31842" },
    { time: "2026-03-29T10:02:04Z", level: "INFO", message: "GET /booking/31842 字段一致性断言通过" },
    { time: "2026-03-29T10:02:05Z", level: "INFO", message: "DELETE /booking/31842 清理成功" },
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
  feature_name: "Restful Booker booking 生命周期测试",
  passed: true,
  errors: [],
  warnings: ["删除接口依赖 token，执行前需确认鉴权配置有效"],
  metrics: {
    scenario_count: 2,
    step_count: 6,
    assertion_count: 15,
    average_step_count: 3,
  },
};

export const mockParseMetadata: ParseMetadata = {
  parse_mode: "rules+rag",
  llm_attempted: true,
  llm_used: true,
  rag_enabled: true,
  rag_used: true,
  rag_fallback_reason: "",
  fallback_reason: "",
  llm_error_type: "",
  llm_provider_profile: "tencent_hunyuan_openai_compat",
  retrieval_mode: "vector_keyword_rerank",
  retrieval_top_k: 5,
  rerank_enabled: true,
  detected_base_url: "https://restful-booker.herokuapp.com",
  document_char_count: 1680,
  cleaned_char_count: 1542,
  chunk_count: 6,
  embedding_batch_size: 32,
  estimated_embedding_calls: 1,
  processing_tier: "realtime",
  large_document_warning: "",
  retrieval_metrics: {
    returned_count: 5,
    requested_top_k: 5,
    coverage_ratio: 0.92,
    duplicate_ratio: 0,
    score_avg: 4.61,
    rerank_applied: true,
    embedded_chunk_count: 6,
    embedding_coverage: 1,
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
    elapsed_ms: 845.6,
    target_ms: 8000,
    within_target: true,
    slow_reason: "",
  },
};

export const mockAnalysisReport: AnalysisReport = {
  task_id: "task_20260329_001",
  task_name: "Restful Booker 最小闭环测试",
  quality_status: "passed",
  summary: {
    scenario_count: 2,
    validation_passed: true,
    warning_count: 1,
    error_count: 0,
    total_steps: 6,
    passed_steps: 6,
    failed_steps: 0,
    total_assertions: 15,
    passed_assertions: 15,
    failed_assertions: 0,
    assertion_strength_score: 0.91,
    assertion_strength_level: "high",
    weak_assertion_step_count: 0,
  },
  findings: ["主链路执行通过", "上下文变量 token 与 booking_id 均成功传递", "删除步骤完成资源清理"],
  chart_data: {
    execution: {
      passed_scenarios: 2,
      failed_scenarios: 0,
      passed_steps: 6,
      failed_steps: 0,
    },
    assertion: {
      passed_assertions: 15,
      failed_assertions: 0,
    },
    timing: {
      average_response_time_ms: 354.7,
      total_duration_ms: 2128,
    },
  },
};

export const mockArtifactContentByType: Record<string, TaskArtifactContent> = {
  raw_requirement: {
    type: "raw_requirement",
    content: "验证 Restful Booker 从 POST /auth、POST /booking、GET /booking/{id} 到 DELETE /booking/{id} 的完整接口闭环。",
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
    content: `Feature: Restful Booker booking 生命周期测试

  Scenario: 鉴权后创建、查询并删除 booking
    Given 调用 POST /auth 获取 token
    When 调用 POST /booking 创建 booking 并保存 booking_id
    Then 调用 GET /booking/{{booking_id}} 校验创建结果
    And 调用 DELETE /booking/{{booking_id}} 清理资源`,
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
  feature_text: `Feature: Restful Booker booking 生命周期测试

  Scenario: 鉴权后创建、查询并删除 booking
    Given 调用 POST /auth 获取 token
    When 调用 POST /booking 创建 booking 并保存 booking_id
    Then 调用 GET /booking/{{booking_id}} 校验创建结果
    And 调用 DELETE /booking/{{booking_id}} 清理资源`,
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
