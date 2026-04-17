from __future__ import annotations

import json
from pathlib import Path
import shutil

from sqlalchemy.orm import Session

from app.db.models import LicenseIssueRecordModel, LicensePolicyModel
from app.services.audit_service import append_audit_log, now_cst_iso
from app.services.crypto_service import sign_payload, verify_signature
from app.services.license_errors import LicenseIssueNotFoundError, LicensePolicyNotFoundError
from app.services.validation_contracts import DIAGNOSTICS_VERSION, evaluate_license_payload


def issue_license(
    session: Session,
    license_root: Path,
    issue_records_root: Path,
    audit_log_path: Path,
    *,
    policy_id: int,
) -> dict[str, object]:
    policy = session.get(LicensePolicyModel, policy_id)
    if policy is None:
        raise LicensePolicyNotFoundError("授权策略不存在。")
    if policy.status != "active":
        raise ValueError("仅可签发 active 状态策略。")
    if policy.key_pair.status != "active":
        raise ValueError(f"密钥 `{policy.key_pair.key_name}` 当前状态为 `{policy.key_pair.status}`，不可用于签发 license。")

    issued_at_cst = now_cst_iso()
    payload = {
        "customer_id": policy.customer.id,
        "customer_code": policy.customer.customer_code,
        "customer_name": policy.customer.customer_name,
        "application_name": policy.application_name,
        "operating_system": policy.operating_system,
        "min_operating_system_version": policy.min_operating_system_version,
        "system_architecture": policy.system_architecture,
        "capability_scope": json.loads(policy.capability_scope_json),
        "hardware_fingerprint": policy.hardware_fingerprint,
        "start_at_cst": policy.start_at_cst,
        "expire_at_cst": policy.expire_at_cst,
        "version_constraints": json.loads(policy.version_constraints_json),
        "issued_at_cst": issued_at_cst,
        "issuer_key_name": policy.key_pair.key_name,
        "policy_id": policy.id,
    }
    signature_base64 = sign_payload(Path(policy.key_pair.private_key_path), payload)

    issue = LicenseIssueRecordModel(
        policy_id=policy.id,
        customer_id=policy.customer_id,
        key_pair_id=policy.key_pair_id,
        status="issued",
        payload_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
        signature_base64=signature_base64,
        license_path="",
        public_key_export_path="",
        hardware_fingerprint=policy.hardware_fingerprint,
        capability_scope_json=policy.capability_scope_json,
        version_constraints_json=policy.version_constraints_json,
        operating_system=policy.operating_system,
        min_operating_system_version=policy.min_operating_system_version,
        system_architecture=policy.system_architecture,
        application_name=policy.application_name,
        issued_at_cst=issued_at_cst,
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)

    issue_dir = (issue_records_root / f"issue_{issue.id}").resolve()
    if not (issue_dir == issue_records_root or issue_records_root in issue_dir.parents):
        raise ValueError("签发目录非法。")
    issue_dir.mkdir(parents=True, exist_ok=True)

    issue_license_path = issue_dir / "license.bin"
    issue_public_key_path = issue_dir / "pubkey.pem"
    license_payload = {
        "algorithm": policy.key_pair.algorithm,
        "payload": payload,
        "signature": signature_base64,
    }
    issue_license_path.write_bytes(json.dumps(license_payload, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    issue_public_key_path.write_bytes(Path(policy.key_pair.public_key_path).read_bytes())

    standard_license_path = (license_root / "license.bin").resolve()
    standard_public_key_path = (license_root / "pubkey.pem").resolve()
    shutil.copyfile(issue_license_path, standard_license_path)
    shutil.copyfile(issue_public_key_path, standard_public_key_path)

    issue.license_path = str(issue_license_path.resolve())
    issue.public_key_export_path = str(issue_public_key_path.resolve())
    session.commit()
    session.refresh(issue)

    append_audit_log(
        audit_log_path,
        action="issue",
        entity_type="license_issue_record",
        entity_id=str(issue.id),
        detail={"policy_id": policy.id, "customer_code": policy.customer.customer_code},
    )

    payload_loaded = json.loads(issue.payload_json)
    return {
        "issue_record_id": issue.id,
        "policy_id": issue.policy_id,
        "customer_id": issue.customer_id,
        "customer_code": issue.customer.customer_code,
        "key_pair_id": issue.key_pair_id,
        "key_name": issue.key_pair.key_name,
        "status": issue.status,
        "hardware_fingerprint": issue.hardware_fingerprint,
        "capability_scope": json.loads(issue.capability_scope_json),
        "version_constraints": json.loads(issue.version_constraints_json),
        "operating_system": issue.operating_system,
        "min_operating_system_version": issue.min_operating_system_version,
        "system_architecture": issue.system_architecture,
        "application_name": issue.application_name,
        "license_path": issue.license_path,
        "public_key_export_path": issue.public_key_export_path,
        "issued_at_cst": issue.issued_at_cst,
        "last_validation_at": issue.last_validation_at,
        "last_validation_result": issue.last_validation_result,
        "last_validation_code": issue.last_validation_code,
        "last_validation_details": json.loads(issue.last_validation_details_json) if issue.last_validation_details_json else {},
        "payload": payload_loaded,
    }


def validate_license_issue(
    session: Session,
    audit_log_path: Path,
    *,
    issue_record_id: int,
    hardware_fingerprint: str | None,
    capability_name: str | None,
    product_version: str | None,
    operating_system: str | None,
    operating_system_version: str | None,
    system_architecture: str | None,
    version_checker,
) -> dict[str, object]:
    issue = session.get(LicenseIssueRecordModel, issue_record_id)
    if issue is None:
        raise LicenseIssueNotFoundError("签发记录不存在。")

    payload = json.loads(issue.payload_json)
    signature_valid = verify_signature(Path(issue.public_key_export_path), payload, issue.signature_base64)
    checked_at_cst = now_cst_iso()
    evaluation = evaluate_license_payload(
        payload=payload,
        signature_valid=signature_valid,
        checked_at_cst=checked_at_cst,
        hardware_fingerprint=hardware_fingerprint,
        capability_name=capability_name,
        product_version=product_version,
        operating_system=operating_system,
        operating_system_version=operating_system_version,
        system_architecture=system_architecture,
        version_checker=version_checker,
    )

    issue.last_validation_at = checked_at_cst
    issue.last_validation_result = evaluation.result
    issue.last_validation_code = evaluation.code
    issue.last_validation_details_json = json.dumps(evaluation.details, ensure_ascii=False, sort_keys=True)
    session.commit()
    append_audit_log(
        audit_log_path,
        action="validate",
        entity_type="license_issue_record",
        entity_id=str(issue.id),
        detail={"valid": evaluation.valid, "code": evaluation.code, "stage": evaluation.stage, "details": evaluation.details},
    )
    return {
        "valid": evaluation.valid,
        "reason": evaluation.reason,
        "result": evaluation.result,
        "code": evaluation.code,
        "stage": evaluation.stage,
        "details": evaluation.details,
        "diagnostics_version": DIAGNOSTICS_VERSION,
        "issue_record_id": issue.id,
        "checked_at_cst": checked_at_cst,
    }
