export type CustomerItem = {
  customer_id: number
  customer_code: string
  customer_name: string
  contact_name?: string | null
  contact_email?: string | null
  status: string
}

export type KeyPairItem = {
  key_pair_id: number
  key_name: string
  algorithm: string
  public_key_path: string
  private_key_path: string
  status: string
  rotation_version: number
  predecessor_key_pair_id?: number | null
  status_changed_at_cst?: string | null
  status_reason?: string | null
}

export type LicensePolicyItem = {
  policy_id: number
  policy_name: string
  customer_id: number
  customer_code: string
  key_pair_id: number
  key_name: string
  capability_scope: string[]
  version_constraints: Record<string, unknown>
  hardware_fingerprint?: string | null
  operating_system: string
  min_operating_system_version?: string | null
  system_architecture?: string | null
  application_name: string
  start_at_cst: string
  expire_at_cst: string
  status: string
  notes?: string | null
}

export type LicenseIssueItem = {
  issue_record_id: number
  policy_id: number
  customer_id: number
  customer_code: string
  key_pair_id: number
  key_name: string
  status: string
  hardware_fingerprint?: string | null
  capability_scope: string[]
  version_constraints: Record<string, unknown>
  operating_system: string
  min_operating_system_version?: string | null
  system_architecture?: string | null
  application_name: string
  license_path: string
  public_key_export_path: string
  issued_at_cst: string
  last_validation_at?: string | null
  last_validation_result?: string | null
  last_validation_code?: string | null
  last_validation_details?: Record<string, unknown>
}

export type LicenseIssueDetail = LicenseIssueItem & {
  payload: Record<string, unknown>
}

export type ValidateLicenseResult = {
  valid: boolean
  reason: string
  result: string
  code: string
  stage: string
  details: Record<string, unknown>
  diagnostics_version: string
  issue_record_id: number
  checked_at_cst: string
}

export type LicenseToolReleaseItem = {
  release_id: number
  tool_name: string
  version: string
  status: string
  archive_path: string
  manifest_path: string
  readme_path: string
  checksum_sha256: string
}

export type AuditLogItem = {
  happened_at_cst: string
  action: string
  entity_type: string
  entity_id: string
  detail: Record<string, unknown>
}

export type ValidationContract = {
  diagnostics_version: string
  fields: Record<string, unknown>
  code_catalog: Record<string, unknown>
}

export type ValidationVectors = {
  diagnostics_version: string
  fingerprint_vectors: Array<Record<string, unknown>>
  version_constraint_vectors: Array<Record<string, unknown>>
  license_validation_vectors: Array<Record<string, unknown>>
}

export type ApiListResponse<T> = { items: T[] }

export type DashboardState = {
  customers: CustomerItem[]
  keyPairs: KeyPairItem[]
  policies: LicensePolicyItem[]
  issues: LicenseIssueItem[]
  toolReleases: LicenseToolReleaseItem[]
  auditLogs: AuditLogItem[]
  validationContract: ValidationContract | null
  validationVectors: ValidationVectors | null
}

export type CustomerFormState = {
  customer_code: string
  customer_name: string
  contact_name: string
  contact_email: string
}

export type PolicyFormState = {
  policy_name: string
  customer_id: string
  key_pair_id: string
  capability_scope: string
  version_constraints: string
  hardware_fingerprint: string
  operating_system: string
  min_operating_system_version: string
  system_architecture: string
  application_name: string
  start_at_cst: string
  expire_at_cst: string
  notes: string
}

export type ValidationFormState = {
  hardware_fingerprint: string
  capability_name: string
  product_version: string
  operating_system: string
  operating_system_version: string
  system_architecture: string
}
