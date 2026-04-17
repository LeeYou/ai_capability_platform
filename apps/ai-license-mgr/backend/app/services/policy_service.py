from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import CustomerModel, KeyPairModel, LicensePolicyModel
from app.services.audit_service import append_audit_log
from app.services.license_errors import CustomerNotFoundError, KeyPairNotFoundError, LicensePolicyNotFoundError
from app.services.validation_contracts import parse_cst_datetime


ALLOWED_OPERATING_SYSTEMS = {"windows", "linux", "android", "ios"}


def _normalize_policy_times(start_at_cst: str, expire_at_cst: str) -> tuple[str, str]:
    start = parse_cst_datetime(start_at_cst)
    expire = parse_cst_datetime(expire_at_cst)
    if expire <= start:
        raise ValueError("到期时间必须晚于生效时间。")
    return start.isoformat(), expire.isoformat()


def _normalize_operating_system(raw_value: str) -> str:
    normalized = raw_value.strip().lower()
    if not normalized:
        raise ValueError("操作系统不能为空。")
    if normalized not in ALLOWED_OPERATING_SYSTEMS:
        raise ValueError("操作系统仅支持 windows/linux/android/ios。")
    return normalized


def _normalize_optional_text(raw_value: str | None, *, field_name: str, max_length: int) -> str | None:
    if raw_value is None:
        return None
    normalized = raw_value.strip()
    if not normalized:
        return None
    if len(normalized) > max_length:
        raise ValueError(f"{field_name}长度不能超过 {max_length}。")
    return normalized


def _ensure_key_pair_is_active(key_pair: KeyPairModel, *, action_name: str) -> None:
    if key_pair.status != "active":
        raise ValueError(f"密钥 `{key_pair.key_name}` 当前状态为 `{key_pair.status}`，不可用于{action_name}。")


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
        "operating_system": policy.operating_system,
        "min_operating_system_version": policy.min_operating_system_version,
        "system_architecture": policy.system_architecture,
        "application_name": policy.application_name,
        "start_at_cst": policy.start_at_cst,
        "expire_at_cst": policy.expire_at_cst,
        "status": policy.status,
        "notes": policy.notes,
    }


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
    operating_system: str,
    min_operating_system_version: str | None,
    system_architecture: str | None,
    application_name: str,
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
    _ensure_key_pair_is_active(key_pair, action_name="创建授权策略")

    normalized_name = policy_name.strip()
    if not normalized_name:
        raise ValueError("策略名称不能为空。")
    if session.query(LicensePolicyModel).filter(LicensePolicyModel.policy_name == normalized_name).first() is not None:
        raise ValueError("策略名称已存在。")

    start_at_iso, expire_at_iso = _normalize_policy_times(start_at_cst, expire_at_cst)
    clean_scope = sorted({item.strip() for item in capability_scope if item.strip()})
    normalized_operating_system = _normalize_operating_system(operating_system)
    normalized_min_operating_system_version = _normalize_optional_text(
        min_operating_system_version,
        field_name="最低操作系统版本",
        max_length=64,
    )
    normalized_system_architecture = _normalize_optional_text(
        system_architecture,
        field_name="系统架构",
        max_length=64,
    )
    normalized_application_name = _normalize_optional_text(
        application_name,
        field_name="应用名称",
        max_length=255,
    )
    if normalized_application_name is None:
        raise ValueError("应用名称不能为空。")

    policy = LicensePolicyModel(
        policy_name=normalized_name,
        customer_id=customer.id,
        key_pair_id=key_pair.id,
        capability_scope_json=json.dumps(clean_scope, ensure_ascii=False, sort_keys=True),
        version_constraints_json=json.dumps(version_constraints, ensure_ascii=False, sort_keys=True),
        hardware_fingerprint=hardware_fingerprint.strip() if hardware_fingerprint else None,
        operating_system=normalized_operating_system,
        min_operating_system_version=normalized_min_operating_system_version,
        system_architecture=normalized_system_architecture,
        application_name=normalized_application_name,
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
