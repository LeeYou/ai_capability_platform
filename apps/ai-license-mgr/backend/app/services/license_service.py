from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import CustomerModel, KeyPairModel, LicenseIssueRecordModel, LicensePolicyModel
from app.services.audit_service import append_audit_log, now_cst_iso
from app.services.crypto_service import generate_hardware_fingerprint, generate_key_pair_files, sign_payload, verify_signature


CST = timezone(timedelta(hours=8))


class CustomerNotFoundError(ValueError):
    """客户不存在。"""


class KeyPairNotFoundError(ValueError):
    """密钥对不存在。"""


class LicensePolicyNotFoundError(ValueError):
    """授权策略不存在。"""


class LicenseIssueNotFoundError(ValueError):
    """签发记录不存在。"""


def initialize_database() -> None:
    from app.db.database import Base, get_engine
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=get_engine())


def _parse_cst_datetime(raw_value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(raw_value)
    except ValueError as exc:
        raise ValueError("时间必须为 ISO 8601 格式。") from exc
    if parsed.tzinfo is None:
        raise ValueError("时间必须显式包含 CST 时区信息。")
    normalized = parsed.astimezone(CST)
    if normalized.utcoffset() != timedelta(hours=8):
        raise ValueError("时间必须使用 CST(+08:00) 时区。")
    return normalized


def _normalize_policy_times(start_at_cst: str, expire_at_cst: str) -> tuple[str, str]:
    start = _parse_cst_datetime(start_at_cst)
    expire = _parse_cst_datetime(expire_at_cst)
    if expire <= start:
        raise ValueError("到期时间必须晚于生效时间。")
    return start.isoformat(), expire.isoformat()


def _version_tuple(raw_value: str) -> tuple[int, ...]:
    normalized = raw_value.strip()
    if not normalized:
        return tuple()
    parts: list[int] = []
    for segment in normalized.split("."):
        digits = "".join(ch for ch in segment if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def _is_version_allowed(product_version: str | None, constraints: dict[str, Any]) -> bool:
    if not constraints:
        return True
    if not product_version:
        return False

    normalized_version = product_version.strip()
    allowed_versions = constraints.get("allowed_versions")
    if isinstance(allowed_versions, list) and allowed_versions and normalized_version not in allowed_versions:
        return False

    prefix = constraints.get("prefix")
    if isinstance(prefix, str) and prefix.strip() and not normalized_version.startswith(prefix.strip()):
        return False

    current = _version_tuple(normalized_version)
    min_version = constraints.get("min_version")
    if isinstance(min_version, str) and min_version.strip() and current < _version_tuple(min_version):
        return False

    max_version = constraints.get("max_version")
    if isinstance(max_version, str) and max_version.strip() and current > _version_tuple(max_version):
        return False

    return True


def _customer_item(customer: CustomerModel) -> dict[str, object]:
    return {
        "customer_id": customer.id,
        "customer_code": customer.customer_code,
        "customer_name": customer.customer_name,
        "contact_name": customer.contact_name,
        "contact_email": customer.contact_email,
        "status": customer.status,
    }


def _key_pair_item(key_pair: KeyPairModel) -> dict[str, object]:
    return {
        "key_pair_id": key_pair.id,
        "key_name": key_pair.key_name,
        "algorithm": key_pair.algorithm,
        "public_key_path": key_pair.public_key_path,
        "private_key_path": key_pair.private_key_path,
        "status": key_pair.status,
    }


def _policy_item(policy: LicensePolicyModel) -> dict[str, object]:
    return {
        "policy_id": policy.id,
        "policy_name": policy.policy_name,
        "customer_id": policy.customer_id,
        "customer_code": policy.customer.customer_code,
        "key_pair_id": policy.key_pair_id,
        "key_name": policy.key_pair.key_name,
        "capability_scope": json.loads(policy.capability_scope_json),
        "version_constraints": json.loads(policy.version_constraints_json),
        "hardware_fingerprint": policy.hardware_fingerprint,
        "start_at_cst": policy.start_at_cst,
        "expire_at_cst": policy.expire_at_cst,
        "status": policy.status,
        "notes": policy.notes,
    }


def _issue_item(issue: LicenseIssueRecordModel) -> dict[str, object]:
    payload = json.loads(issue.payload_json)
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
        "license_path": issue.license_path,
        "public_key_export_path": issue.public_key_export_path,
        "issued_at_cst": issue.issued_at_cst,
        "last_validation_at": issue.last_validation_at,
        "last_validation_result": issue.last_validation_result,
        "payload": payload,
    }


def list_customers(session: Session) -> list[dict[str, object]]:
    return [_customer_item(item) for item in session.query(CustomerModel).order_by(CustomerModel.id.asc()).all()]


def get_customer(session: Session, customer_id: int) -> dict[str, object]:
    customer = session.get(CustomerModel, customer_id)
    if customer is None:
        raise CustomerNotFoundError("客户不存在。")
    return _customer_item(customer)


def create_customer(
    session: Session,
    audit_log_path: Path,
    *,
    customer_code: str,
    customer_name: str,
    contact_name: str | None,
    contact_email: str | None,
) -> dict[str, object]:
    normalized_code = customer_code.strip()
    if not normalized_code:
        raise ValueError("客户编码不能为空。")
    if session.query(CustomerModel).filter(CustomerModel.customer_code == normalized_code).first() is not None:
        raise ValueError("客户编码已存在。")

    customer = CustomerModel(
        customer_code=normalized_code,
        customer_name=customer_name.strip(),
        contact_name=contact_name.strip() if contact_name else None,
        contact_email=contact_email.strip() if contact_email else None,
        status="active",
    )
    session.add(customer)
    session.commit()
    session.refresh(customer)
    append_audit_log(
        audit_log_path,
        action="create",
        entity_type="customer",
        entity_id=str(customer.id),
        detail={"customer_code": customer.customer_code},
    )
    return _customer_item(customer)


def list_key_pairs(session: Session) -> list[dict[str, object]]:
    return [_key_pair_item(item) for item in session.query(KeyPairModel).order_by(KeyPairModel.id.asc()).all()]


def get_key_pair(session: Session, key_pair_id: int) -> dict[str, object]:
    key_pair = session.get(KeyPairModel, key_pair_id)
    if key_pair is None:
        raise KeyPairNotFoundError("密钥对不存在。")
    return _key_pair_item(key_pair)


def create_key_pair(
    session: Session,
    key_pairs_root: Path,
    audit_log_path: Path,
    *,
    key_name: str,
) -> dict[str, object]:
    normalized_name = key_name.strip()
    if not normalized_name:
        raise ValueError("密钥名称不能为空。")
    if session.query(KeyPairModel).filter(KeyPairModel.key_name == normalized_name).first() is not None:
        raise ValueError("密钥名称已存在。")

    private_key_path, public_key_path = generate_key_pair_files(key_pairs_root, normalized_name)
    key_pair = KeyPairModel(
        key_name=normalized_name,
        algorithm="ed25519",
        private_key_path=str(private_key_path),
        public_key_path=str(public_key_path),
        status="active",
    )
    session.add(key_pair)
    session.commit()
    session.refresh(key_pair)
    append_audit_log(
        audit_log_path,
        action="create",
        entity_type="key_pair",
        entity_id=str(key_pair.id),
        detail={"key_name": key_pair.key_name},
    )
    return _key_pair_item(key_pair)


def list_license_policies(session: Session) -> list[dict[str, object]]:
    return [_policy_item(item) for item in session.query(LicensePolicyModel).order_by(LicensePolicyModel.id.asc()).all()]


def get_license_policy(session: Session, policy_id: int) -> dict[str, object]:
    policy = session.get(LicensePolicyModel, policy_id)
    if policy is None:
        raise LicensePolicyNotFoundError("授权策略不存在。")
    return _policy_item(policy)


def create_license_policy(
    session: Session,
    audit_log_path: Path,
    *,
    policy_name: str,
    customer_id: int,
    key_pair_id: int,
    capability_scope: list[str],
    version_constraints: dict[str, Any],
    hardware_fingerprint: str | None,
    start_at_cst: str,
    expire_at_cst: str,
    notes: str | None,
) -> dict[str, object]:
    customer = session.get(CustomerModel, customer_id)
    if customer is None:
        raise CustomerNotFoundError("客户不存在。")
    key_pair = session.get(KeyPairModel, key_pair_id)
    if key_pair is None:
        raise KeyPairNotFoundError("密钥对不存在。")
    normalized_name = policy_name.strip()
    if not normalized_name:
        raise ValueError("策略名称不能为空。")
    if session.query(LicensePolicyModel).filter(LicensePolicyModel.policy_name == normalized_name).first() is not None:
        raise ValueError("策略名称已存在。")

    start_at_iso, expire_at_iso = _normalize_policy_times(start_at_cst, expire_at_cst)
    clean_scope = sorted({item.strip() for item in capability_scope if item.strip()})
    policy = LicensePolicyModel(
        policy_name=normalized_name,
        customer_id=customer.id,
        key_pair_id=key_pair.id,
        capability_scope_json=json.dumps(clean_scope, ensure_ascii=False, sort_keys=True),
        version_constraints_json=json.dumps(version_constraints, ensure_ascii=False, sort_keys=True),
        hardware_fingerprint=hardware_fingerprint.strip() if hardware_fingerprint else None,
        start_at_cst=start_at_iso,
        expire_at_cst=expire_at_iso,
        status="active",
        notes=notes.strip() if notes else None,
    )
    session.add(policy)
    session.commit()
    session.refresh(policy)
    append_audit_log(
        audit_log_path,
        action="create",
        entity_type="license_policy",
        entity_id=str(policy.id),
        detail={"policy_name": policy.policy_name, "customer_code": customer.customer_code},
    )
    return _policy_item(policy)


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

    issued_at_cst = now_cst_iso()
    payload = {
        "customer_id": policy.customer.id,
        "customer_code": policy.customer.customer_code,
        "customer_name": policy.customer.customer_name,
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
    return _issue_item(issue)


def list_license_issues(session: Session) -> list[dict[str, object]]:
    return [
        {key: value for key, value in _issue_item(item).items() if key != "payload"}
        for item in session.query(LicenseIssueRecordModel).order_by(LicenseIssueRecordModel.id.asc()).all()
    ]


def get_license_issue(session: Session, issue_record_id: int) -> dict[str, object]:
    issue = session.get(LicenseIssueRecordModel, issue_record_id)
    if issue is None:
        raise LicenseIssueNotFoundError("签发记录不存在。")
    return _issue_item(issue)


def validate_license_issue(
    session: Session,
    audit_log_path: Path,
    *,
    issue_record_id: int,
    hardware_fingerprint: str | None,
    capability_name: str | None,
    product_version: str | None,
) -> dict[str, object]:
    issue = session.get(LicenseIssueRecordModel, issue_record_id)
    if issue is None:
        raise LicenseIssueNotFoundError("签发记录不存在。")

    payload = json.loads(issue.payload_json)
    signature_valid = verify_signature(Path(issue.public_key_export_path), payload, issue.signature_base64)
    checked_at_cst = now_cst_iso()

    if not signature_valid:
        valid = False
        reason = "签名校验失败。"
    else:
        now_cst = _parse_cst_datetime(checked_at_cst)
        start_at = _parse_cst_datetime(payload["start_at_cst"])
        expire_at = _parse_cst_datetime(payload["expire_at_cst"])
        capability_scope = payload.get("capability_scope", [])
        version_constraints = payload.get("version_constraints", {})
        expected_fingerprint = payload.get("hardware_fingerprint")

        if now_cst < start_at:
            valid = False
            reason = "license 尚未生效。"
        elif now_cst > expire_at:
            valid = False
            reason = "license 已过期。"
        elif expected_fingerprint and hardware_fingerprint != expected_fingerprint:
            valid = False
            reason = "硬件指纹不匹配。"
        elif capability_name and capability_scope and capability_name not in capability_scope:
            valid = False
            reason = "能力范围不匹配。"
        elif not _is_version_allowed(product_version, version_constraints):
            valid = False
            reason = "版本约束不匹配。"
        else:
            valid = True
            reason = "license 校验通过。"

    issue.last_validation_at = checked_at_cst
    issue.last_validation_result = "passed" if valid else "failed"
    session.commit()
    append_audit_log(
        audit_log_path,
        action="validate",
        entity_type="license_issue_record",
        entity_id=str(issue.id),
        detail={"valid": valid, "reason": reason},
    )
    return {
        "valid": valid,
        "reason": reason,
        "issue_record_id": issue.id,
        "checked_at_cst": checked_at_cst,
    }


def export_license_issue(
    session: Session,
    exports_root: Path,
    audit_log_path: Path,
    *,
    issue_record_id: int,
    export_format: str,
) -> Path:
    issue = session.get(LicenseIssueRecordModel, issue_record_id)
    if issue is None:
        raise LicenseIssueNotFoundError("签发记录不存在。")
    source_map = {
        "bin": Path(issue.license_path),
        "pubkey": Path(issue.public_key_export_path),
    }
    if export_format not in source_map:
        raise ValueError("仅支持导出 bin/pubkey。")

    export_dir = (exports_root / "ai-license-mgr").resolve()
    if not (export_dir == exports_root or exports_root in export_dir.parents):
        raise ValueError("导出目录非法。")
    export_dir.mkdir(parents=True, exist_ok=True)

    suffix = "license.bin" if export_format == "bin" else "pubkey.pem"
    destination = export_dir / f"issue_{issue.id}_{suffix}"
    shutil.copyfile(source_map[export_format], destination)
    append_audit_log(
        audit_log_path,
        action="export",
        entity_type="license_issue_record",
        entity_id=str(issue.id),
        detail={"export_format": export_format, "exported_path": str(destination.resolve())},
    )
    return destination.resolve()


def build_hardware_fingerprint(features: dict[str, str]) -> str:
    return generate_hardware_fingerprint(features)
