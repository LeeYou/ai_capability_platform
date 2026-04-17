from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import KeyPairModel, LicensePolicyModel
from app.services.audit_service import append_audit_log, now_cst_iso
from app.services.crypto_service import generate_key_pair_files
from app.services.license_errors import KeyPairNotFoundError


def _key_pair_item(key_pair: KeyPairModel) -> dict[str, object]:
    return {
        "key_pair_id": key_pair.id,
        "key_name": key_pair.key_name,
        "algorithm": key_pair.algorithm,
        "public_key_path": key_pair.public_key_path,
        "private_key_path": key_pair.private_key_path,
        "status": key_pair.status,
        "rotation_version": key_pair.rotation_version,
        "predecessor_key_pair_id": key_pair.predecessor_key_pair_id,
        "status_changed_at_cst": key_pair.status_changed_at_cst,
        "status_reason": key_pair.status_reason,
    }


def _normalize_key_name(raw_value: str, *, field_name: str = "密钥名称") -> str:
    normalized = raw_value.strip()
    if not normalized:
        raise ValueError(f"{field_name}不能为空。")
    return normalized


def _ensure_key_pair_is_active(key_pair: KeyPairModel, *, action_name: str) -> None:
    if key_pair.status != "active":
        raise ValueError(f"密钥 `{key_pair.key_name}` 当前状态为 `{key_pair.status}`，不可用于{action_name}。")


def _build_rotated_key_name(session: Session, current_key_name: str, next_version: int) -> str:
    base_name = f"{current_key_name}-v{next_version}"
    candidate = base_name
    suffix = 1
    while session.query(KeyPairModel).filter(KeyPairModel.key_name == candidate).first() is not None:
        suffix += 1
        candidate = f"{base_name}-{suffix}"
    return candidate


def _build_key_pair_record(
    *,
    key_name: str,
    private_key_path: Path,
    public_key_path: Path,
    rotation_version: int = 1,
    predecessor_key_pair_id: int | None = None,
) -> KeyPairModel:
    return KeyPairModel(
        key_name=key_name,
        algorithm="ed25519",
        private_key_path=str(private_key_path),
        public_key_path=str(public_key_path),
        status="active",
        rotation_version=rotation_version,
        predecessor_key_pair_id=predecessor_key_pair_id,
    )


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
    normalized_name = _normalize_key_name(key_name)
    if session.query(KeyPairModel).filter(KeyPairModel.key_name == normalized_name).first() is not None:
        raise ValueError("密钥名称已存在。")

    private_key_path, public_key_path = generate_key_pair_files(key_pairs_root, normalized_name)
    key_pair = _build_key_pair_record(
        key_name=normalized_name,
        private_key_path=private_key_path,
        public_key_path=public_key_path,
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


def rotate_key_pair(
    session: Session,
    key_pairs_root: Path,
    audit_log_path: Path,
    *,
    key_pair_id: int,
    new_key_name: str | None,
    reason: str | None,
) -> dict[str, object]:
    source_key_pair = session.get(KeyPairModel, key_pair_id)
    if source_key_pair is None:
        raise KeyPairNotFoundError("密钥对不存在。")
    _ensure_key_pair_is_active(source_key_pair, action_name="轮转")

    next_version = int(source_key_pair.rotation_version) + 1
    normalized_new_name = (
        _normalize_key_name(new_key_name, field_name="新密钥名称")
        if new_key_name is not None
        else _build_rotated_key_name(session, source_key_pair.key_name, next_version)
    )
    if session.query(KeyPairModel).filter(KeyPairModel.key_name == normalized_new_name).first() is not None:
        raise ValueError("新密钥名称已存在。")

    private_key_path, public_key_path = generate_key_pair_files(key_pairs_root, normalized_new_name)
    target_key_pair = _build_key_pair_record(
        key_name=normalized_new_name,
        private_key_path=private_key_path,
        public_key_path=public_key_path,
        rotation_version=next_version,
        predecessor_key_pair_id=source_key_pair.id,
    )
    session.add(target_key_pair)
    session.flush()

    migrated_policy_ids: list[int] = []
    active_policies = (
        session.query(LicensePolicyModel)
        .filter(LicensePolicyModel.key_pair_id == source_key_pair.id, LicensePolicyModel.status == "active")
        .all()
    )
    for policy in active_policies:
        policy.key_pair_id = target_key_pair.id
        migrated_policy_ids.append(policy.id)

    source_key_pair.status = "rotated"
    source_key_pair.status_changed_at_cst = now_cst_iso()
    source_key_pair.status_reason = reason.strip() if reason and reason.strip() else f"已轮转至 `{target_key_pair.key_name}`"
    session.commit()
    session.refresh(source_key_pair)
    session.refresh(target_key_pair)

    append_audit_log(
        audit_log_path,
        action="rotate",
        entity_type="key_pair",
        entity_id=str(source_key_pair.id),
        detail={
            "source_key_name": source_key_pair.key_name,
            "target_key_pair_id": target_key_pair.id,
            "target_key_name": target_key_pair.key_name,
            "migrated_policy_ids": migrated_policy_ids,
        },
    )
    return {
        "source_key_pair": _key_pair_item(source_key_pair),
        "new_key_pair": _key_pair_item(target_key_pair),
        "migrated_policy_ids": migrated_policy_ids,
    }


def isolate_key_pair(
    session: Session,
    audit_log_path: Path,
    *,
    key_pair_id: int,
    reason: str,
) -> dict[str, object]:
    key_pair = session.get(KeyPairModel, key_pair_id)
    if key_pair is None:
        raise KeyPairNotFoundError("密钥对不存在。")
    _ensure_key_pair_is_active(key_pair, action_name="隔离")

    normalized_reason = reason.strip()
    if not normalized_reason:
        raise ValueError("隔离原因不能为空。")

    key_pair.status = "isolated"
    key_pair.status_changed_at_cst = now_cst_iso()
    key_pair.status_reason = normalized_reason
    session.commit()
    session.refresh(key_pair)

    append_audit_log(
        audit_log_path,
        action="isolate",
        entity_type="key_pair",
        entity_id=str(key_pair.id),
        detail={"key_name": key_pair.key_name, "reason": normalized_reason},
    )
    return _key_pair_item(key_pair)
