from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.database import get_db_session
from app.models import (
    AuditLogItem,
    AuditLogListResponse,
    CreateCustomerRequest,
    CreateKeyPairRequest,
    CreateLicensePolicyRequest,
    CustomerItem,
    CustomerListResponse,
    ExportLicenseResponse,
    GenerateFingerprintRequest,
    GenerateFingerprintResponse,
    HealthResponse,
    IssueLicenseRequest,
    KeyPairItem,
    KeyPairListResponse,
    LicenseIssueDetailResponse,
    LicenseIssueItem,
    LicenseIssueListResponse,
    LicensePolicyItem,
    LicensePolicyListResponse,
    LicenseToolReleaseItem,
    LicenseToolReleaseListResponse,
    ValidateLicenseRequest,
    ValidateLicenseResponse,
)
from app.services.audit_service import list_audit_logs
from app.services.license_service import (
    CustomerNotFoundError,
    KeyPairNotFoundError,
    LicenseIssueNotFoundError,
    LicensePolicyNotFoundError,
    LicenseToolReleaseNotFoundError,
    build_hardware_fingerprint,
    create_customer,
    create_key_pair,
    create_license_policy,
    export_license_issue,
    export_license_tool_release,
    get_customer,
    get_key_pair,
    get_license_issue,
    get_license_policy,
    get_license_tool_release,
    issue_license,
    list_customers,
    list_key_pairs,
    list_license_issues,
    list_license_policies,
    list_license_tool_releases,
    sync_default_license_tool_release,
    validate_license_issue,
)


router = APIRouter(prefix="/api/v1")


@router.get("/health", response_model=HealthResponse, tags=["system"])
def get_health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        company_name=settings.company_name,
        company_domain=settings.company_domain,
        license_root=str(settings.license_root),
    )


@router.get("/customers", response_model=CustomerListResponse, tags=["customer"])
def get_customers(session: Session = Depends(get_db_session)) -> CustomerListResponse:
    return CustomerListResponse(items=[CustomerItem(**item) for item in list_customers(session)])


@router.get("/customers/{customer_id}", response_model=CustomerItem, tags=["customer"])
def get_customer_detail(customer_id: int, session: Session = Depends(get_db_session)) -> CustomerItem:
    try:
        return CustomerItem(**get_customer(session, customer_id))
    except CustomerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/customers", response_model=CustomerItem, status_code=status.HTTP_201_CREATED, tags=["customer"])
def create_customer_route(
    request: CreateCustomerRequest,
    session: Session = Depends(get_db_session),
) -> CustomerItem:
    settings = get_settings()
    try:
        payload = create_customer(
            session,
            settings.audit_log_path,
            customer_code=request.customer_code,
            customer_name=request.customer_name,
            contact_name=request.contact_name,
            contact_email=request.contact_email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return CustomerItem(**payload)


@router.get("/key-pairs", response_model=KeyPairListResponse, tags=["key"])
def get_key_pairs(session: Session = Depends(get_db_session)) -> KeyPairListResponse:
    return KeyPairListResponse(items=[KeyPairItem(**item) for item in list_key_pairs(session)])


@router.get("/key-pairs/{key_pair_id}", response_model=KeyPairItem, tags=["key"])
def get_key_pair_detail(key_pair_id: int, session: Session = Depends(get_db_session)) -> KeyPairItem:
    try:
        return KeyPairItem(**get_key_pair(session, key_pair_id))
    except KeyPairNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/key-pairs", response_model=KeyPairItem, status_code=status.HTTP_201_CREATED, tags=["key"])
def create_key_pair_route(
    request: CreateKeyPairRequest,
    session: Session = Depends(get_db_session),
) -> KeyPairItem:
    settings = get_settings()
    try:
        payload = create_key_pair(
            session,
            settings.key_pairs_root,
            settings.audit_log_path,
            key_name=request.key_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return KeyPairItem(**payload)


@router.get("/license-policies", response_model=LicensePolicyListResponse, tags=["license"])
def get_license_policies(session: Session = Depends(get_db_session)) -> LicensePolicyListResponse:
    return LicensePolicyListResponse(items=[LicensePolicyItem(**item) for item in list_license_policies(session)])


@router.get("/license-policies/{policy_id}", response_model=LicensePolicyItem, tags=["license"])
def get_license_policy_detail(policy_id: int, session: Session = Depends(get_db_session)) -> LicensePolicyItem:
    try:
        return LicensePolicyItem(**get_license_policy(session, policy_id))
    except LicensePolicyNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/license-policies", response_model=LicensePolicyItem, status_code=status.HTTP_201_CREATED, tags=["license"])
def create_license_policy_route(
    request: CreateLicensePolicyRequest,
    session: Session = Depends(get_db_session),
) -> LicensePolicyItem:
    settings = get_settings()
    try:
        payload = create_license_policy(
            session,
            settings.audit_log_path,
            policy_name=request.policy_name,
            customer_id=request.customer_id,
            key_pair_id=request.key_pair_id,
            capability_scope=request.capability_scope,
            version_constraints=request.version_constraints,
            hardware_fingerprint=request.hardware_fingerprint,
            start_at_cst=request.start_at_cst,
            expire_at_cst=request.expire_at_cst,
            notes=request.notes,
        )
    except (ValueError, CustomerNotFoundError, KeyPairNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return LicensePolicyItem(**payload)


@router.post("/hardware-fingerprint", response_model=GenerateFingerprintResponse, tags=["license"])
def generate_hardware_fingerprint_route(request: GenerateFingerprintRequest) -> GenerateFingerprintResponse:
    try:
        fingerprint = build_hardware_fingerprint(request.features)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return GenerateFingerprintResponse(hardware_fingerprint=fingerprint)


@router.get("/license-issues", response_model=LicenseIssueListResponse, tags=["license"])
def get_license_issues(session: Session = Depends(get_db_session)) -> LicenseIssueListResponse:
    return LicenseIssueListResponse(items=[LicenseIssueItem(**item) for item in list_license_issues(session)])


@router.get("/license-issues/{issue_record_id}", response_model=LicenseIssueDetailResponse, tags=["license"])
def get_license_issue_detail(issue_record_id: int, session: Session = Depends(get_db_session)) -> LicenseIssueDetailResponse:
    try:
        return LicenseIssueDetailResponse(**get_license_issue(session, issue_record_id))
    except LicenseIssueNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/license-issues", response_model=LicenseIssueDetailResponse, status_code=status.HTTP_201_CREATED, tags=["license"])
def issue_license_route(
    request: IssueLicenseRequest,
    session: Session = Depends(get_db_session),
) -> LicenseIssueDetailResponse:
    settings = get_settings()
    try:
        payload = issue_license(
            session,
            settings.license_root,
            settings.issue_records_root,
            settings.audit_log_path,
            policy_id=request.policy_id,
        )
    except (ValueError, LicensePolicyNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return LicenseIssueDetailResponse(**payload)


@router.post("/license-issues/{issue_record_id}/validate", response_model=ValidateLicenseResponse, tags=["license"])
def validate_license_route(
    issue_record_id: int,
    request: ValidateLicenseRequest,
    session: Session = Depends(get_db_session),
) -> ValidateLicenseResponse:
    settings = get_settings()
    try:
        payload = validate_license_issue(
            session,
            settings.audit_log_path,
            issue_record_id=issue_record_id,
            hardware_fingerprint=request.hardware_fingerprint,
            capability_name=request.capability_name,
            product_version=request.product_version,
        )
    except LicenseIssueNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ValidateLicenseResponse(**payload)


@router.get("/license-issues/{issue_record_id}/export", tags=["license"])
def export_license_route(
    issue_record_id: int,
    export_format: str = Query(default="bin", pattern="^(bin|pubkey)$"),
    session: Session = Depends(get_db_session),
) -> FileResponse:
    settings = get_settings()
    try:
        exported_path = export_license_issue(
            session,
            settings.exports_root,
            settings.audit_log_path,
            issue_record_id=issue_record_id,
            export_format=export_format,
        )
    except (LicenseIssueNotFoundError, ValueError) as exc:
        status_code = status.HTTP_404_NOT_FOUND if isinstance(exc, LicenseIssueNotFoundError) else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    media_type = "application/octet-stream" if export_format == "bin" else "application/x-pem-file"
    return FileResponse(path=exported_path, filename=exported_path.name, media_type=media_type)


@router.get("/tool-releases", response_model=LicenseToolReleaseListResponse, tags=["tools"])
def get_license_tool_releases(session: Session = Depends(get_db_session)) -> LicenseToolReleaseListResponse:
    return LicenseToolReleaseListResponse(items=[LicenseToolReleaseItem(**item) for item in list_license_tool_releases(session)])


@router.get("/tool-releases/{release_id}", response_model=LicenseToolReleaseItem, tags=["tools"])
def get_license_tool_release_detail(release_id: int, session: Session = Depends(get_db_session)) -> LicenseToolReleaseItem:
    try:
        return LicenseToolReleaseItem(**get_license_tool_release(session, release_id))
    except LicenseToolReleaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/tool-releases/sync-default", response_model=LicenseToolReleaseItem, tags=["tools"])
def sync_default_license_tool_release_route(
    session: Session = Depends(get_db_session),
) -> LicenseToolReleaseItem:
    settings = get_settings()
    try:
        payload = sync_default_license_tool_release(session, settings.license_tools_root, settings.audit_log_path)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return LicenseToolReleaseItem(**payload)


@router.get("/tool-releases/{release_id}/export", tags=["tools"])
def export_license_tool_release_route(
    release_id: int,
    export_format: str = Query(default="archive", pattern="^(archive|manifest|readme)$"),
    session: Session = Depends(get_db_session),
) -> FileResponse:
    settings = get_settings()
    try:
        exported_path = export_license_tool_release(
            session,
            settings.exports_root,
            settings.audit_log_path,
            release_id=release_id,
            export_format=export_format,
        )
    except (LicenseToolReleaseNotFoundError, ValueError) as exc:
        status_code = status.HTTP_404_NOT_FOUND if isinstance(exc, LicenseToolReleaseNotFoundError) else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    media_type = "application/gzip" if export_format == "archive" else "text/markdown" if export_format == "readme" else "application/json"
    return FileResponse(path=exported_path, filename=exported_path.name, media_type=media_type)


@router.get("/audit-logs", response_model=AuditLogListResponse, tags=["audit"])
def get_audit_logs(limit: int = Query(default=100, ge=1, le=500)) -> AuditLogListResponse:
    settings = get_settings()
    return AuditLogListResponse(items=[AuditLogItem(**item) for item in list_audit_logs(settings.audit_log_path, limit)])
