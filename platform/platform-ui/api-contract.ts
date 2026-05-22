export type TaskStatus =
  | "received"
  | "parsed"
  | "generated"
  | "running"
  | "passed"
  | "failed"
  | "stopped"
  | "archived";

export interface TaskContext {
  task_id: string;
  task_name: string;
  source_type: string;
  source_path: string | null;
  created_at: string;
  language: string;
  status: TaskStatus | string;
  notes: string[];
  /** Vector RAG preference at task creation (embeddings + vector ranking). Does not disable LLM enhancement. */
  rag_enabled?: boolean | null;
  project_id?: string;
  created_by?: string;
  target_system?: string | null;
}

export interface RetrievedChunk {
  chunk_id: string;
  content: string;
  score: number;
  section_title: string;
  source_file: string;
}

export interface ParsedRequirement {
  objective: string;
  actors: string[];
  entities: string[];
  preconditions: string[];
  actions: string[];
  expected_results: string[];
  constraints: string[];
  ambiguities: string[];
  source_chunks: string[];
}

export interface ScenarioStep {
  type: string;
  text: string;
}

export interface ScenarioModel {
  scenario_id: string;
  name: string;
  goal: string;
  steps: ScenarioStep[];
  assertions: string[];
  source_chunks: string[];
  priority: string;
  preconditions: string[];
}

export interface TestCaseStep {
  assertion_quality?: Record<string, unknown>;
  step_id: string;
  step_type: string;
  text: string;
  request?: {
    method?: string;
    url?: string;
    headers?: Record<string, string>;
    params?: Record<string, string>;
    json?: unknown;
    data?: unknown;
    timeout?: number;
  };
  assertions?: Array<
    | string
    | {
        assertion_id?: string;
        source: string;
        op: string;
        expected?: unknown;
        severity?: string;
        category?: string;
        confidence?: number;
        generated_by?: string;
        reasoning?: string;
        fallback_used?: boolean;
      }
  >;
  uses_context?: string[];
  saves_context?: string[];
  save_context?: Record<string, string>;
}

export interface TestCaseDslScenario {
  scenario_id: string;
  name: string;
  goal?: string;
  priority?: string;
  preconditions?: string[];
  source_chunks?: string[];
  steps: TestCaseStep[];
}

export interface TestCaseDSL {
  dsl_version: string;
  task_id: string;
  task_name: string;
  feature_name: string;
  execution_mode: string;
  scenarios: TestCaseDslScenario[];
  metadata: Record<string, unknown>;
}

export interface ExecutionScenarioResult {
  scenario_id: string;
  scenario_name: string;
  name?: string;
  status: string;
  duration_ms: number;
  passed_steps: number;
  failed_steps: number;
  steps?: Array<{
    step_id?: string;
    step_type?: string;
    text?: string;
    status?: string;
    message?: string;
    error_category?: string;
    request?: Record<string, unknown>;
    request_summary?: Record<string, unknown>;
    response?: Record<string, unknown>;
    response_summary?: Record<string, unknown>;
    assertion_summary?: Record<string, unknown>;
    assertion_failures?: Array<Record<string, unknown>>;
  }>;
}

export interface ExecutionLog {
  time: string;
  level: string;
  message: string;
}

export interface ExecutionResult {
  task_id: string;
  executor: string;
  status: string;
  scenario_results: ExecutionScenarioResult[];
  metrics: Record<string, unknown>;
  logs: ExecutionLog[];
  metadata?: Record<string, unknown>;
}

export interface TaskArtifactItem {
  type: string;
  label: string;
  updated_at: string;
}

export interface TaskArtifactContent {
  type: string;
  content: unknown;
}

export interface ValidationReport {
  feature_name: string;
  passed: boolean;
  errors: string[];
  warnings: string[];
  metrics: Record<string, unknown>;
}

export interface ParsePerformance {
  elapsed_ms: number;
  target_ms: number;
  within_target: boolean;
  slow_reason: string;
  /**
   * Fine-grained parse timings (ms). Includes:
   * document_load_parse_ms, chunk_contract_ms, index_build_ms, retrieval_ms, rules_parse_ms,
   * pre_llm_enhancement, llm_enhancement, llm_compose_prompt_ms, llm_gateway_chat_ms, llm_normalize_response_ms.
   */
  phase_timings_ms?: Record<string, number>;
}

export interface ParseRetrievalMetrics {
  returned_count: number;
  requested_top_k: number;
  coverage_ratio: number;
  duplicate_ratio: number;
  score_avg: number;
  rerank_applied: boolean;
  embedded_chunk_count: number;
  embedding_coverage: number;
  embedding_error: string;
  embedding_error_detail: string;
}

export interface ParseRetrievalScoring {
  lexical_weight: number;
  vector_weight: number;
  rerank_vector_weight: number;
  rerank_lexical_weight: number;
  rerank_title_boost: number;
  rerank_content_boost: number;
}

export interface ParseMetadata {
  parse_mode: string;
  llm_attempted: boolean;
  llm_used: boolean;
  /** Vector RAG was on for this parse (embeddings + vector ranking). Mirrors request `rag_enabled`. */
  rag_enabled: boolean;
  /** Deprecated alias of `rag_enabled`; kept for older stored tasks. */
  rag_used: boolean;
  rag_fallback_reason: string;
  fallback_reason: string;
  llm_error_type: string;
  llm_provider_profile: string;
  model_profile?: string;
  retrieval_mode: string;
  retrieval_top_k: number;
  rerank_enabled: boolean;
  detected_base_url?: string;
  document_char_count: number;
  cleaned_char_count: number;
  chunk_count: number;
  embedding_batch_size: number;
  estimated_embedding_calls: number;
  processing_tier: string;
  large_document_warning: string;
  retrieval_metrics: ParseRetrievalMetrics;
  retrieval_scoring: ParseRetrievalScoring;
  performance: ParsePerformance;
}

export interface AnalysisReport {
  task_id: string;
  task_name: string;
  quality_status: string;
  summary: Record<string, unknown>;
  step_assertion_quality?: Array<Record<string, unknown>>;
  findings: string[];
  chart_data: Record<string, unknown>;
}

export interface AnalysisProgressPayload {
  task_id: string;
  kind: "analysis" | string;
  stage: string;
  percent: number;
  status: "idle" | "running" | "completed" | "failed" | string;
  message: string;
  updated_at: string;
  detail?: Record<string, unknown>;
}

export interface TaskListItem extends TaskContext {}

export interface TaskDetailPayload {
  task_context: TaskContext;
  parse_metadata?: ParseMetadata;
  parsed_requirement?: ParsedRequirement;
  retrieved_context?: RetrievedChunk[];
  scenarios?: ScenarioModel[];
  test_case_dsl?: TestCaseDSL;
  execution_result?: ExecutionResult;
  validation_report?: ValidationReport;
  analysis_report?: AnalysisReport;
  feature_text?: string;
}

export interface HistoryTaskItem extends TaskContext {
  finished_at?: string;
}

export interface ExecutionHistoryItem {
  task_id: string;
  task_name: string;
  environment: string;
  execution_mode: string;
  status: string;
  executor: string;
  executed_at: string;
  metrics?: Record<string, unknown>;
  analysis_summary?: {
    success_rate?: number;
    failed_steps?: number;
    avg_elapsed_ms?: number;
    [key: string]: unknown;
  };
}

export interface TaskDashboardPayload {
  task: TaskContext;
  analysis_report?: AnalysisReport;
  dashboard?: Record<string, unknown>;
  dashboard_summary?: Record<string, unknown>;
  summary?: Record<string, unknown>;
  task_summary?: Record<string, unknown>;
  execution_overview?: Record<string, unknown>;
  performance_stats?: Record<string, unknown>;
  assertion_stats?: Record<string, unknown>;
  context_stats?: Record<string, unknown>;
  task_summary_text?: string;
  findings?: string[];
  chart_data?: Record<string, unknown>;
  report_sections?: unknown[];
  failed_steps?: unknown[];
  failure_reasons?: string[];
  validation_report?: ValidationReport;
  execution?: ExecutionResult;
  dsl?: TestCaseDSL;
}

export interface PreflightCheckItem {
  name: string;
  status: "passed" | "warning" | "failed" | string;
  elapsed_ms?: number;
  message?: string;
}

export interface PreflightCheckPayload {
  task_id: string;
  overall_status: "passed" | "warning" | "failed" | string;
  blocking: boolean;
  checks: PreflightCheckItem[];
  blocking_issues?: string[];
  suggestions?: string[];
}

export interface ExecutionExplanationPayload {
  task_id: string;
  execution_id?: string;
  summary?: Record<string, unknown>;
  llm_diagnosis?: {
    summary?: string;
    root_cause?: string;
    confidence?: number;
    next_actions?: string[];
  } | null;
  llm_metadata?: {
    attempted?: boolean;
    used?: boolean;
    fallback_reason?: string;
    error_type?: string;
    provider_profile?: string;
  };
  defect_summaries?: Array<{
    step_id?: string;
    title: string;
    severity?: "low" | "medium" | "high" | "critical" | string;
    expected_result?: string;
    actual_result?: string;
    reproduction_steps?: string;
    generated_by?: "rules" | "llm" | string;
  }>;
  failure_groups?: Array<{
    category: string;
    count: number;
    examples?: string[];
    recommended_actions?: string[];
  }>;
  top_reasons?: string[];
}

export interface RegressionDiffPayload {
  task_id: string;
  base_execution_id?: string;
  target_execution_id?: string;
  metrics_diff?: Record<string, unknown>;
  failure_type_diff?: Array<Record<string, unknown>>;
  verdict?: "improved" | "regressed" | "unchanged" | string;
}

export interface UserProfile {
  id: string;
  username: string;
  email?: string | null;
  display_name?: string | null;
  avatar_url?: string | null;
  workspace_id?: string | null;
  last_login_at?: string | null;
  is_platform_admin?: boolean;
  platform_role?: "admin" | "user" | string;
}

export interface ProjectSummary {
  id: string;
  workspace_id?: string | null;
  name: string;
  description?: string | null;
  owner_user_id?: string | null;
  is_default?: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface ProjectMemberPayload {
  id?: string;
  project_id?: string;
  user_id?: string;
  username?: string;
  display_name?: string;
  avatar_url?: string | null;
  role: string;
  created_at?: string;
  joined_at?: string;
}

export interface AuthLoginPayload {
  access_token: string;
  refresh_token?: string;
  token_type?: string;
  expires_in?: number;
  session_id?: string;
  user?: UserProfile | null;
  projects?: ProjectSummary[];
}

export interface AuthRegisterPayload {
  user: UserProfile;
  projects?: ProjectSummary[];
}

export interface AuthMePayload {
  user: UserProfile | null;
  projects: ProjectSummary[];
}

export interface CreateProjectPayload extends ProjectSummary {}

export interface EnvironmentPayload {
  name: string;
  base_url?: string;
  default_headers?: Record<string, string>;
  auth?: Record<string, unknown>;
  cookies?: Record<string, unknown>;
  description?: string;
  project_id?: string;
  default_headers_masked?: boolean;
  auth_masked?: boolean;
  cookies_masked?: boolean;
  masked_header_keys?: string[];
}

export interface AuditLogPayload {
  id: string;
  user_id?: string | null;
  username?: string | null;
  display_name?: string | null;
  action: string;
  resource_type: string;
  resource_id?: string | null;
  detail_json?: Record<string, unknown> | unknown[] | null;
  ip_address?: string | null;
  created_at?: string | null;
}

export interface AuditLogListPayload {
  items: AuditLogPayload[];
  total: number;
  page: number;
  page_size: number;
}

export type DefectStatus = "open" | "in_progress" | "resolved" | "closed";
export type DefectSeverity = "low" | "medium" | "high" | "critical";

export interface DefectPayload {
  id: string;
  defect_key: string;
  project_id: string;
  task_id?: string | null;
  task_name?: string | null;
  reporter_user_id: string;
  reporter_username?: string | null;
  reporter_display_name?: string | null;
  assignee_user_id?: string | null;
  assignee_username?: string | null;
  assignee_display_name?: string | null;
  title: string;
  description: string;
  severity: DefectSeverity | string;
  status: DefectStatus | string;
  source: string;
  reproduction_steps: string;
  expected_result: string;
  actual_result: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface DefectListPayload {
  items: DefectPayload[];
  total: number;
  page: number;
  page_size: number;
}

export interface InterfaceAssetPayload {
  id: string;
  project_id: string;
  method: string;
  path: string;
  name?: string;
  description?: string;
  source: string;
  status: "active" | "deprecated" | "draft" | string;
  version: string;
  tags: string[];
  request_example?: unknown;
  response_example?: unknown;
  schema?: unknown;
  last_seen_task_id?: string | null;
  created_by?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface InterfaceAssetListPayload {
  items: InterfaceAssetPayload[];
  total: number;
  page: number;
  page_size: number;
}

export interface InterfaceAssetImportPayload {
  task_id: string;
  project_id: string;
  items: InterfaceAssetPayload[];
  imported_count: number;
}

export interface InterfaceAssetOpenApiImportPayload {
  project_id: string;
  source_name: string;
  items: InterfaceAssetPayload[];
  imported_count: number;
  endpoint_count: number;
}

export interface InterfaceAssetDebugPayload {
  asset: InterfaceAssetPayload;
  request: {
    method: string;
    url: string;
    headers: Record<string, string>;
    has_auth: boolean;
  };
  response: {
    status_code: number;
    headers: Record<string, string>;
    json?: unknown;
    body_preview: string;
    elapsed_ms: number;
    error: string;
    ok: boolean;
  };
}

export interface TestCaseAssetPayload {
  id: string;
  project_id: string;
  case_key: string;
  name: string;
  description?: string;
  priority: string;
  status: "active" | "draft" | "disabled" | "archived" | string;
  source: string;
  source_task_id?: string | null;
  tags: string[];
  dsl_scenario: TestCaseDslScenario | Record<string, unknown>;
  assertions: unknown[];
  created_by?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface TestCaseAssetListPayload {
  items: TestCaseAssetPayload[];
  total: number;
  page: number;
  page_size: number;
}

export interface TestCaseAssetImportPayload {
  task_id: string;
  project_id: string;
  items: TestCaseAssetPayload[];
  imported_count: number;
}

export interface TestCaseAssetExecutionPayload {
  case: TestCaseAssetPayload;
  execution_result: ExecutionResult;
  executed_at: string;
}

export interface TestSuiteAssetPayload {
  id: string;
  project_id: string;
  name: string;
  description?: string;
  status: "active" | "draft" | "disabled" | "archived" | string;
  source: string;
  case_ids: string[];
  tags: string[];
  created_by?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface TestSuiteAssetListPayload {
  items: TestSuiteAssetPayload[];
  total: number;
  page: number;
  page_size: number;
}

export interface TestSuiteAssetExecutionPayload {
  suite: TestSuiteAssetPayload;
  status: string;
  case_results: Array<{
    case?: TestCaseAssetPayload;
    case_id?: string;
    status: string;
    execution_result?: ExecutionResult;
    error?: unknown;
  }>;
  metrics: {
    case_count: number;
    passed: number;
    failed: number;
    duration_ms: number;
  };
  executed_at: string;
}

export interface TaskDraftAgentSuggestion {
  field: string;
  value: string;
  reason?: string;
}

export interface TaskDraftAgentCheck {
  key: string;
  status: "ready" | "attention" | "warning" | string;
  message: string;
}

export interface TaskDraftAgentEnvironmentCandidate {
  name: string;
  base_url?: string;
  description?: string;
  match_type: "exact_base_url" | "same_host" | "selected_environment" | string;
}

export interface TaskDraftAgentSignal {
  key: string;
  label: string;
  value: string;
  tone?: "success" | "warning" | "default" | string;
}

export interface TaskDraftAgentDocumentAction {
  key: string;
  title: string;
  mode: "prepend" | "append" | string;
  reason?: string;
  content: string;
}

export interface TaskDraftAgentDocumentPreview {
  content: string;
  summary: string;
  action_count: number;
  applied_action_keys: string[];
}

export interface TaskDraftAgentKnowledgeHit {
  title: string;
  source_file: string;
  doc_type: string;
  score: number;
  query_match_count?: number;
  excerpt: string;
}

export interface TaskDraftAgentResourceGroup {
  resource_key: string;
  methods: string[];
  endpoints: string[];
  status: "complete" | "needs_source" | "read_only" | "single_step" | string;
  has_create?: boolean;
  has_context_flow?: boolean;
  has_live_resource?: boolean;
  has_list_source?: boolean;
  estimated_scenarios?: number;
}

export interface TaskDraftAgentFollowUpQuestion {
  key: string;
  field?: string;
  priority?: "high" | "medium" | "low" | string;
  question: string;
  reason?: string;
  action_kind?: "focus_field" | "apply_document_action" | "apply_form_patch" | string;
  action_label?: string;
  document_action_key?: string;
  answer_mode?: "field" | "append_requirement" | string;
  answer_placeholder?: string;
  answer_template?: string;
}

export interface TaskDraftAgentActionPlanItem {
  key: string;
  title: string;
  detail: string;
  status: "done" | "next" | "review" | "blocked" | string;
  action_label?: string;
  target_view?: "overview" | "followups" | "document" | "knowledge" | string;
}

export interface TaskDraftAgentScenarioBlueprint {
  key: string;
  title: string;
  objective: string;
  endpoints: string[];
  dependency: string;
  status: "ready" | "needs_context" | "read_only" | "single_step" | string;
  gaps?: string[];
}

export interface TaskDraftAgentQualityGate {
  key: string;
  label: string;
  status: "pass" | "warn" | "block" | string;
  detail: string;
}

export interface TaskDraftAgentAssertionSuggestion {
  key: string;
  title: string;
  scope: string;
  priority: "high" | "medium" | "low" | string;
  assertions: string[];
  reason?: string;
}

export interface TaskDraftAgentExecutionPhase {
  key: string;
  title: string;
  detail: string;
  required: boolean;
}

export interface TaskDraftAgentExecutionStrategy {
  mode: "ready" | "prepare" | string;
  smoke_path: string;
  data_setup: "required" | "optional" | string;
  rerun_policy: string;
  phases: TaskDraftAgentExecutionPhase[];
  notes: string[];
}

export interface TaskDraftAgentRiskPriority {
  key: string;
  title: string;
  severity: "high" | "medium" | "low" | string;
  impact: string;
  mitigation: string;
  source: "quality_gate" | "diagnostic" | "coverage" | string;
}

export interface TaskDraftAgentHandoff {
  workflow_safe: boolean;
  applied_to_workflow: boolean;
  handoff_status: "ready" | "blocked" | "draft" | string;
  blocked_by: string[];
  generation_context: {
    recognized_endpoints: string[];
    estimated_scenario_count: number;
    scenario_shape: string;
    resource_group_count: number;
  };
  assertion_intents: Array<{
    key: string;
    title: string;
    priority: string;
    examples: string[];
  }>;
  execution_precheck: {
    mode: string;
    smoke_path: string;
    data_setup: string;
    required_phase_keys: string[];
  };
  document_snapshot: {
    has_preview: boolean;
    action_count: number;
    applied_action_keys: string[];
  };
}

export interface TaskDraftAgentDiagnosticVerdict {
  status: "pass" | "fixable" | "blocked" | string;
  severity: "success" | "warning" | "error" | string;
  label: string;
  summary: string;
  primary_action: string;
  can_handoff: boolean;
  can_execute: boolean;
  blockers: string[];
  auto_fix_count: number;
  manual_action_count: number;
  endpoint_count: number;
  estimated_scenario_count: number;
  blocked_endpoint_count: number;
}

export interface TaskDraftAgentPayload {
  reply: string;
  summary: {
    ready_score: number;
    max_score: number;
    requirement_chars: number;
    ready_to_create?: boolean;
    ready_to_execute?: boolean;
    highlight_count?: number;
    risk_count?: number;
    confidence_score?: number;
    confidence_level?: "high" | "medium" | "low" | string;
  };
  diagnostic_verdict?: TaskDraftAgentDiagnosticVerdict;
  suggested_task_name?: string;
  detected_base_url?: string;
  selected_environment?: string | null;
  recommended_environment?: string | null;
  environment_candidates: TaskDraftAgentEnvironmentCandidate[];
  checks: TaskDraftAgentCheck[];
  form_patch: Record<string, string>;
  signals: TaskDraftAgentSignal[];
  recognized_endpoints: string[];
  scenario_outlook?: {
    estimated_scenario_count?: number;
    endpoint_count?: number;
    resource_group_count?: number;
    write_endpoint_count?: number;
    read_only_endpoint_count?: number;
    lifecycle_chain_count?: number;
    standalone_endpoint_count?: number;
    uncovered_live_resource_endpoints?: string[];
    scenario_shape?: string;
  };
  resource_groups?: TaskDraftAgentResourceGroup[];
  action_plan?: TaskDraftAgentActionPlanItem[];
  scenario_blueprint?: TaskDraftAgentScenarioBlueprint[];
  quality_gates?: TaskDraftAgentQualityGate[];
  assertion_suggestions?: TaskDraftAgentAssertionSuggestion[];
  execution_strategy?: TaskDraftAgentExecutionStrategy;
  risk_priorities?: TaskDraftAgentRiskPriority[];
  agent_handoff?: TaskDraftAgentHandoff;
  coverage_gaps?: string[];
  highlights: string[];
  risks: string[];
  document_fixes: string[];
  document_actions: TaskDraftAgentDocumentAction[];
  document_preview?: TaskDraftAgentDocumentPreview | null;
  knowledge_hits: TaskDraftAgentKnowledgeHit[];
  knowledge_summary?: string;
  rag_support?: {
    knowledge_applied?: boolean;
    knowledge_chunk_count?: number;
    retrieved_hit_count?: number;
    query_count?: number;
    query_variants_preview?: string[];
    source_file_count?: number;
    source_file_diversity?: number;
    doc_type_count?: number;
  };
  follow_up_questions: TaskDraftAgentFollowUpQuestion[];
  warnings: string[];
  next_actions: string[];
  suggestions: TaskDraftAgentSuggestion[];
  capabilities: {
    backend_ready: boolean;
    mcp_direct_supported: boolean;
    requires_backend_proxy: boolean;
    auto_analysis_supported?: boolean;
    diagnostics_supported?: boolean;
    document_actions_supported?: boolean;
    knowledge_rag_supported?: boolean;
  };
}

export interface TaskAgentChatPayload {
  reply: string;
  agent_payload: TaskDraftAgentPayload;
}

export interface TaskAgentTrackingContext {
  task_id?: string;
  task_name?: string;
  task_status?: string;
  execution_status?: string;
  environment?: string | null;
  target_system?: string | null;
  scenario_total?: number;
  scenario_passed?: number;
  scenario_failed?: number;
  failed_scenarios?: unknown[];
  failed_steps?: unknown[];
  latest_logs?: unknown[];
  validation_passed?: boolean;
  validation_errors?: string[];
  validation_warnings?: string[];
  analysis_findings?: unknown[];
  failure_reasons?: string[];
  preflight_blocking?: boolean;
  preflight_issues?: string[];
  execution_explanations?: unknown;
}
