export type TaskStatus =
  | "received"
  | "parsed"
  | "scenario_generated"
  | "running"
  | "passed"
  | "failed";

export interface TaskContext {
  task_id: string;
  task_name: string;
  source_type: string;
  source_path: string | null;
  created_at: string;
  language: string;
  status: TaskStatus | string;
  notes: string[];
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
        source: string;
        op: string;
        expected?: unknown;
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

export interface ValidationReport {
  feature_name: string;
  passed: boolean;
  errors: string[];
  warnings: string[];
  metrics: Record<string, unknown>;
}

export interface AnalysisReport {
  task_id: string;
  task_name: string;
  quality_status: string;
  summary: Record<string, unknown>;
  findings: string[];
  chart_data: Record<string, unknown>;
}

export interface TaskListItem extends TaskContext {}

export interface TaskDetailPayload {
  task_context: TaskContext;
  parsed_requirement?: ParsedRequirement;
  retrieved_context?: RetrievedChunk[];
  scenarios?: ScenarioModel[];
  test_case_dsl?: TestCaseDSL;
  execution_result?: ExecutionResult;
  validation_report?: ValidationReport;
  analysis_report?: AnalysisReport;
  feature_text?: string;
}
