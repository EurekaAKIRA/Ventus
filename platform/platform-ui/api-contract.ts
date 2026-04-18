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
  status: string;
  duration_ms: number;
  passed_steps: number;
  failed_steps: number;
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
