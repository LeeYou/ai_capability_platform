export type CapabilityItem = {
  capability_name: string
  display_name: string
  task_type: string
  dataset_path: string
  dataset_status: string
  source: string
  annotation_schema: Record<string, unknown>
  template_bundle: Record<string, unknown>
}

export type AnnotationSampleItem = {
  sample_id: string
  status: string
  annotation: Record<string, unknown> | null
  updated_at?: string | null
}

export type AnnotationTaskItem = {
  task_id: number
  capability_name: string
  task_type: string
  task_name: string
  dataset_path: string
  status: string
  sample_total: number
  labeled_count: number
  result_path?: string | null
  completion_ratio?: number
  sample_items?: AnnotationSampleItem[]
  annotation_schema?: Record<string, unknown>
}

export type TrainingTaskItem = {
  task_id: number
  capability_name: string
  task_type: string
  task_name: string
  dataset_path: string
  status: string
  framework: string
  backend_type: string
  annotation_task_id?: number | null
  retry_count: number
  log_path?: string | null
  workspace_path?: string | null
  started_at?: string | null
  completed_at?: string | null
  latest_logs?: string[]
  execution_plan?: Record<string, unknown> | null
  result_summary?: Record<string, unknown> | null
  training_input_path?: string | null
  template_bundle_path?: string | null
  export_dir?: string | null
}

export type ModelArtifactItem = {
  artifact_id: number
  capability_name: string
  task_type: string
  model_version: string
  source_training_task_id: number
  artifact_path: string
  manifest_path: string
  backend_type: string
  checksum: string
  status: string
  manifest_preview?: Record<string, unknown> | null
  delivery_metadata?: Record<string, unknown> | null
  runtime_contract?: Record<string, unknown> | null
}

export type ApiListResponse<T> = { items: T[] }

export type DashboardData = {
  capabilities: CapabilityItem[]
  annotationTasks: AnnotationTaskItem[]
  trainingTasks: TrainingTaskItem[]
  modelArtifacts: ModelArtifactItem[]
}

export type AnnotationDraft = {
  label: string
  note: string
  attributesJson: string
  objectsJson: string
  text: string
  regionsJson: string
  fieldsJson: string
  confidenceJson: string
}

export type DatasetItem = {
  capability_name: string
  dataset_path: string
  dataset_status: string
  source: string
}
