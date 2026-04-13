export type PlatformTargetItem = {
  target_name: string
  os_name: string
  arch_name: string
  artifact_format: string
  toolchain_name: string
  supports_native_build: boolean
  supports_jni: boolean
}

export type CatalogModelItem = {
  artifact_id: number | null
  capability_name: string
  model_version: string
  artifact_path: string
  manifest_path: string
  backend_type: string
  checksum: string
  status: string
}

export type LicenseIssueItem = {
  issue_record_id: number
  customer_code: string
  key_name: string
  status: string
  capability_scope: string[]
  license_path: string
  issued_at_cst: string
}

export type CatalogResponse = {
  capabilities: { capability_name: string; display_name: string; dataset_status: string }[]
  models: CatalogModelItem[]
  license_issues: LicenseIssueItem[]
  license_policies: { policy_id: number; policy_name: string; customer_code: string; status: string }[]
  synced_at: string | null
}

export type BuildTaskItem = {
  task_id: number
  task_name: string
  capability_name: string
  model_version: string
  issue_record_id: number
  requested_targets: string[]
  jni_enabled: boolean
  status: string
  build_root_path: string
  log_path: string
  manifest_path?: string | null
  delivery_package_dir?: string | null
  delivery_package_archive_path?: string | null
  started_at?: string | null
  completed_at?: string | null
}

export type BuildTargetItem = {
  target_id: number
  task_id: number
  target_name: string
  os_name: string
  arch_name: string
  artifact_format: string
  build_mode: string
  toolchain_name: string
  jni_enabled: boolean
  status: string
  output_dir: string
  binary_path: string
  header_dir: string
  manifest_path: string
  checksum: string
  log_path: string
  download_archive_path: string
}

export type BuildArtifactItem = {
  artifact_id: number
  task_id: number
  target_id: number
  artifact_type: string
  relative_path: string
  absolute_path: string
  checksum: string
}

export type BuildTaskDetail = BuildTaskItem & {
  targets: BuildTargetItem[]
  artifacts: BuildArtifactItem[]
  manifest: {
    manifest_version: string
    manifest_path: string
    dependency_summary: Record<string, unknown>
    manifest: Record<string, unknown>
  } | null
}

export type AuditLogItem = {
  happened_at_cst: string
  action: string
  entity_type: string
  entity_id: string
  detail: Record<string, unknown>
}

export type ListResponse<T> = { items: T[] }

export type DashboardState = {
  platforms: PlatformTargetItem[]
  catalog: CatalogResponse
  buildTasks: BuildTaskItem[]
  auditLogs: AuditLogItem[]
}

export type BuildFormState = {
  task_name: string
  capability_name: string
  model_version: string
  issue_record_id: string
  requested_targets: string
  jni_enabled: boolean
}

export const initialDashboardState: DashboardState = {
  platforms: [],
  catalog: {
    capabilities: [],
    models: [],
    license_issues: [],
    license_policies: [],
    synced_at: null,
  },
  buildTasks: [],
  auditLogs: [],
}

export const initialBuildForm: BuildFormState = {
  task_name: '',
  capability_name: '',
  model_version: '',
  issue_record_id: '',
  requested_targets: '',
  jni_enabled: false,
}
