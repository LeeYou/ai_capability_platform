export type RemoteCapabilityItem = {
  capability_name: string
  display_name: string
  dataset_path: string
  dataset_status: string
  source: string
}

export type RemoteModelItem = {
  capability_name: string
  model_version: string
  artifact_path: string
  backend_type: string
  status: string
}

export type TestCaseResultItem = {
  case_id: number
  case_name: string
  input_path: string
  input_type: string
  status: string
  expected_output: string | null
  actual_output: string | null
  duration_ms: number
  score: number
  provider: string | null
}

export type TestTaskItem = {
  task_id: number
  task_type: string
  capability_name: string
  model_version: string
  requested_backend: string
  execution_backend: string | null
  timeout_seconds: number
  status: string
  total_cases: number
  passed_cases: number
  failed_cases: number
  error_message: string | null
  report_id: number | null
  started_at: string | null
  completed_at: string | null
}

export type TestTaskDetail = TestTaskItem & {
  cases: TestCaseResultItem[]
}

export type AcceptanceScriptResultItem = {
  case_name: string
  status: string
  duration_ms: number
  passed: boolean
  detail: Record<string, unknown>
  baseline_comparison: Record<string, unknown> | null
  passed_baseline: boolean | null
}

export type AcceptanceTaskItem = {
  acceptance_task_id: number
  task_id: number
  image_uri: string
  target_base_url: string
  capability_name: string | null
  input_type: string
  prefer_device: string
  status: string
  total_cases: number
  passed_cases: number
  failed_cases: number
  report_id: number | null
  created_at: string | null
  started_at: string | null
  completed_at: string | null
}

export type AcceptanceTaskDetail = AcceptanceTaskItem & {
  script_results: AcceptanceScriptResultItem[]
}

export type PerformanceBaselineItem = {
  baseline_id: number
  capability_name: string
  scenario_name: string
  p95_max_ms: number | null
  success_rate_min: number
  description: string | null
}

export type TestReportItem = {
  report_id: number
  task_id: number
  capability_name: string
  model_version: string
  status: string
  passed_cases: number
  failed_cases: number
  available_template_types: Array<'research' | 'delivery'>
  active_template_type: 'research' | 'delivery'
  json_report_path: string
  html_report_path: string
  pdf_report_path: string
  exported_at: string | null
}

export type TestReportDetail = TestReportItem & {
  summary: Record<string, unknown>
}

export type ApiListResponse<T> = {
  items: T[]
  synced_at?: string | null
}

export type SingleTestForm = {
  capability_name: string
  model_version: string
  requested_backend: 'auto' | 'gpu' | 'cpu'
  timeout_seconds: string
  case_name: string
  input_path: string
  expected_output: string
}

export type BatchTestForm = {
  capability_name: string
  model_version: string
  requested_backend: 'auto' | 'gpu' | 'cpu'
  timeout_seconds: string
  cases_text: string
}

export type AcceptanceForm = {
  image_uri: string
  target_base_url: string
  capability_name: string
  input_type: 'json' | 'image' | 'video' | 'pdf'
  infer_payload: string
  prefer_device: 'auto' | 'gpu' | 'cpu'
  acceptance_timeout_seconds: string
  run_admin_checks: boolean
  pressure_requests: string
  pressure_concurrency: string
  pressure_timeout_seconds: string
  pressure_min_success_rate: string
  pressure_max_p95_ms: string
}

export type BaselineForm = {
  capability_name: string
  scenario_name: string
  p95_max_ms: string
  success_rate_min: string
  description: string
}
