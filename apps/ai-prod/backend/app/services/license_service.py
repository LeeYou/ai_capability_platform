from __future__ import annotations

from base64 import b64decode
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from app.services.audit_service import now_cst_iso


CST = timezone(timedelta(hours=8))


class LicenseValidationError(ValueError):
    """license 校验失败。"""


def _canonical_json_bytes(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _parse_cst_datetime(raw_value: str) -> datetime:
    parsed = datetime.fromisoformat(raw_value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=CST)
    return parsed.astimezone(CST)


def _version_tuple(raw_value: str) -> tuple[int, ...]:
    normalized = raw_value.strip()
    if not normalized:
        return tuple()
    parts: list[int] = []
    for segment in normalized.split("."):
        digits = "".join(ch for ch in segment if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def _is_version_allowed(product_version: str | None, version_constraints: dict[str, Any]) -> bool:
    if not version_constraints:
        return True
    if not product_version:
        return False
    normalized_version = product_version.strip()
    allowed_versions = version_constraints.get("allowed_versions")
    if isinstance(allowed_versions, list) and allowed_versions and normalized_version not in {str(item) for item in allowed_versions}:
        return False
    prefix = version_constraints.get("prefix")
    if isinstance(prefix, str) and prefix.strip() and not normalized_version.startswith(prefix.strip()):
        return False
    current = _version_tuple(normalized_version)
    min_version = version_constraints.get("min_version")
    if isinstance(min_version, str) and min_version.strip() and current < _version_tuple(min_version):
        return False
    max_version = version_constraints.get("max_version")
    if isinstance(max_version, str) and max_version.strip() and current > _version_tuple(max_version):
        return False
    return True


def verify_signature(public_key_path: Path, payload: dict[str, object], signature_base64: str) -> bool:
    public_key = serialization.load_pem_public_key(public_key_path.read_bytes())
    if not isinstance(public_key, ed25519.Ed25519PublicKey):
        raise ValueError("仅支持 ed25519 公钥。")
    try:
        public_key.verify(b64decode(signature_base64), _canonical_json_bytes(payload))
        return True
    except InvalidSignature:
        return False


def generate_hardware_fingerprint(features: dict[str, str]) -> str:
    normalized = "|".join(f"{key.strip().lower()}={value.strip()}" for key, value in sorted(features.items()))
    if not normalized:
        raise ValueError("至少需要一个硬件特征。")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def read_license_bundle(license_root: Path) -> dict[str, Any]:
    license_path = (license_root / "license.bin").resolve()
    pubkey_path = (license_root / "pubkey.pem").resolve()
    if not license_path.exists() or not pubkey_path.exists():
        raise LicenseValidationError("标准 license 文件不存在。")
    payload = json.loads(license_path.read_bytes().decode("utf-8"))
    if not isinstance(payload, dict):
        raise LicenseValidationError("license 文件格式非法。")
    return {
        "license_path": license_path,
        "pubkey_path": pubkey_path,
        "payload": payload.get("payload"),
        "signature": payload.get("signature"),
        "algorithm": payload.get("algorithm"),
    }


def validate_license_bundle(
    license_root: Path,
    *,
    hardware_features: dict[str, str],
    capability_name: str | None = None,
    product_version: str | None = None,
) -> dict[str, Any]:
    bundle = read_license_bundle(license_root)
    payload = bundle["payload"]
    signature = bundle["signature"]
    if not isinstance(payload, dict) or not isinstance(signature, str):
        raise LicenseValidationError("license 文件内容非法。")

    checked_at_cst = now_cst_iso()
    if not verify_signature(bundle["pubkey_path"], payload, signature):
        valid = False
        reason = "签名校验失败。"
    else:
        now_cst = _parse_cst_datetime(checked_at_cst)
        start_at = _parse_cst_datetime(str(payload["start_at_cst"]))
        expire_at = _parse_cst_datetime(str(payload["expire_at_cst"]))
        capability_scope = payload.get("capability_scope", [])
        version_constraints = payload.get("version_constraints", {})
        expected_fingerprint = payload.get("hardware_fingerprint")
        hardware_fingerprint = generate_hardware_fingerprint(hardware_features) if hardware_features else None

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
        elif product_version is not None and not _is_version_allowed(product_version, version_constraints):
            valid = False
            reason = "版本约束不匹配。"
        else:
            valid = True
            reason = "license 校验通过。"
    return {
        "valid": valid,
        "reason": reason,
        "checked_at_cst": checked_at_cst,
        "customer_code": payload.get("customer_code"),
        "capability_scope": payload.get("capability_scope", []),
        "version_constraints": payload.get("version_constraints", {}),
        "hardware_fingerprint": payload.get("hardware_fingerprint"),
    }
