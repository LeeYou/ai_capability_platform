from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import json
from typing import Any


CST = timezone(timedelta(hours=8))
DIAGNOSTICS_VERSION = "1.0"
VALIDATION_RESULT_PASSED = "passed"
VALIDATION_RESULT_FAILED = "failed"
VALIDATION_CODE_LICENSE_VALID = "license_valid"
VALIDATION_CODE_SIGNATURE_INVALID = "signature_invalid"
VALIDATION_CODE_NOT_YET_VALID = "time_window_not_started"
VALIDATION_CODE_EXPIRED = "time_window_expired"
VALIDATION_CODE_HARDWARE_MISMATCH = "hardware_fingerprint_mismatch"
VALIDATION_CODE_CAPABILITY_DENIED = "capability_scope_denied"
VALIDATION_CODE_VERSION_DENIED = "version_constraints_denied"
VALIDATION_CODE_OPERATING_SYSTEM_DENIED = "operating_system_denied"
VALIDATION_CODE_OPERATING_SYSTEM_VERSION_DENIED = "operating_system_version_denied"
VALIDATION_CODE_SYSTEM_ARCHITECTURE_DENIED = "system_architecture_denied"


@dataclass(frozen=True)
class ValidationEvaluation:
    valid: bool
    result: str
    code: str
    reason: str
    stage: str
    details: dict[str, Any]

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


def canonical_json_bytes(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def parse_cst_datetime(raw_value: str) -> datetime:
    parsed = datetime.fromisoformat(raw_value)
    if parsed.tzinfo is None:
        raise ValueError("时间必须显式包含 CST 时区信息。")
    normalized = parsed.astimezone(CST)
    if normalized.utcoffset() != timedelta(hours=8):
        raise ValueError("时间必须使用 CST(+08:00) 时区。")
    return normalized


def _normalize_operating_system(raw_value: Any) -> str | None:
    if raw_value is None:
        return None
    normalized = str(raw_value).strip().lower().replace("-", "").replace("_", "").replace(" ", "")
    if not normalized:
        return None
    alias_map = {
        "win": "windows",
        "windows": "windows",
        "linux": "linux",
        "android": "android",
        "ios": "ios",
        "iphoneos": "ios",
    }
    return alias_map.get(normalized, str(raw_value).strip().lower())


def _normalize_system_architecture(raw_value: Any) -> str | None:
    if raw_value is None:
        return None
    normalized = str(raw_value).strip().lower().replace("-", "").replace("_", "").replace(" ", "")
    if not normalized:
        return None
    alias_map = {
        "x8664": "x86_64",
        "amd64": "x86_64",
        "x64": "x86_64",
        "x86": "x86",
        "i386": "x86",
        "i686": "x86",
        "arm64": "arm64",
        "aarch64": "arm64",
        "armv8": "arm64",
        "armv8l": "arm64",
        "armv7": "armv7",
        "armv7l": "armv7",
    }
    return alias_map.get(normalized, str(raw_value).strip().lower())


def _version_tuple(raw_value: Any) -> tuple[int, ...]:
    normalized = str(raw_value).strip()
    if not normalized:
        return tuple()
    parts: list[int] = []
    for segment in normalized.split("."):
        digits = "".join(ch for ch in segment if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def _meets_minimum_version(current_version: Any, minimum_version: Any) -> bool:
    return _version_tuple(current_version) >= _version_tuple(minimum_version)


def build_validation_contract() -> dict[str, object]:
    return {
        "diagnostics_version": DIAGNOSTICS_VERSION,
        "fields": {
            "result": ["passed", "failed"],
            "code": [
                VALIDATION_CODE_LICENSE_VALID,
                VALIDATION_CODE_SIGNATURE_INVALID,
                VALIDATION_CODE_NOT_YET_VALID,
                VALIDATION_CODE_EXPIRED,
                VALIDATION_CODE_HARDWARE_MISMATCH,
                VALIDATION_CODE_CAPABILITY_DENIED,
                VALIDATION_CODE_VERSION_DENIED,
                VALIDATION_CODE_OPERATING_SYSTEM_DENIED,
                VALIDATION_CODE_OPERATING_SYSTEM_VERSION_DENIED,
                VALIDATION_CODE_SYSTEM_ARCHITECTURE_DENIED,
            ],
            "stage": [
                "signature",
                "time_window",
                "hardware_fingerprint",
                "capability_scope",
                "version_constraints",
                "operating_system",
                "operating_system_version",
                "system_architecture",
                "success",
            ],
        },
        "code_catalog": {
            VALIDATION_CODE_LICENSE_VALID: {
                "result": VALIDATION_RESULT_PASSED,
                "stage": "success",
                "message": "license 校验通过。",
            },
            VALIDATION_CODE_SIGNATURE_INVALID: {
                "result": VALIDATION_RESULT_FAILED,
                "stage": "signature",
                "message": "签名校验失败。",
            },
            VALIDATION_CODE_NOT_YET_VALID: {
                "result": VALIDATION_RESULT_FAILED,
                "stage": "time_window",
                "message": "license 尚未生效。",
            },
            VALIDATION_CODE_EXPIRED: {
                "result": VALIDATION_RESULT_FAILED,
                "stage": "time_window",
                "message": "license 已过期。",
            },
            VALIDATION_CODE_HARDWARE_MISMATCH: {
                "result": VALIDATION_RESULT_FAILED,
                "stage": "hardware_fingerprint",
                "message": "硬件指纹不匹配。",
            },
            VALIDATION_CODE_CAPABILITY_DENIED: {
                "result": VALIDATION_RESULT_FAILED,
                "stage": "capability_scope",
                "message": "能力范围不匹配。",
            },
            VALIDATION_CODE_VERSION_DENIED: {
                "result": VALIDATION_RESULT_FAILED,
                "stage": "version_constraints",
                "message": "版本约束不匹配。",
            },
            VALIDATION_CODE_OPERATING_SYSTEM_DENIED: {
                "result": VALIDATION_RESULT_FAILED,
                "stage": "operating_system",
                "message": "操作系统不匹配。",
            },
            VALIDATION_CODE_OPERATING_SYSTEM_VERSION_DENIED: {
                "result": VALIDATION_RESULT_FAILED,
                "stage": "operating_system_version",
                "message": "系统版本低于 license 最低要求。",
            },
            VALIDATION_CODE_SYSTEM_ARCHITECTURE_DENIED: {
                "result": VALIDATION_RESULT_FAILED,
                "stage": "system_architecture",
                "message": "系统架构不匹配。",
            },
        },
    }


def build_validation_vectors() -> dict[str, object]:
    return {
        "diagnostics_version": DIAGNOSTICS_VERSION,
        "fingerprint_vectors": [
            {
                "vector_id": "fp_sorted_sha256",
                "features": {"cpu": "intel-i7", "disk": "nvme-sn-001", "mac": "00:11:22:33:44:55"},
                "expected_fingerprint": "e3c78d6abed016ebd1aa71fc916ee9128f5578bc609ba8e8afa3da401836fd18",
            }
        ],
        "version_constraint_vectors": [
            {
                "vector_id": "version_prefix_range_pass",
                "constraints": {"prefix": "v1.", "min_version": "v1.2.0", "max_version": "v1.10.0"},
                "product_version": "v1.8.0",
                "expected_allowed": True,
            },
            {
                "vector_id": "version_allowed_versions_reject",
                "constraints": {"allowed_versions": ["v1.0.0", "v1.0.1"]},
                "product_version": "v1.2.0",
                "expected_allowed": False,
            },
            {
                "vector_id": "version_missing_product_reject",
                "constraints": {"allowed_versions": ["v1.0.0"]},
                "product_version": None,
                "expected_allowed": False,
            },
        ],
        "license_validation_vectors": [
            {
                "vector_id": "license_valid",
                "checked_at_cst": "2026-04-07T10:00:00+08:00",
                "signature_valid": True,
                "payload": {
                    "customer_code": "cust_vector",
                    "application_name": "agile-demo",
                    "operating_system": "linux",
                    "min_operating_system_version": "5.4.0",
                    "system_architecture": "x86_64",
                    "capability_scope": ["ocr", "face_detect"],
                    "hardware_fingerprint": "fp-demo-001",
                    "start_at_cst": "2026-04-01T00:00:00+08:00",
                    "expire_at_cst": "2026-05-01T00:00:00+08:00",
                    "version_constraints": {"min_version": "1.0.0", "max_version": "2.0.0"},
                },
                "request_context": {
                    "hardware_fingerprint": "fp-demo-001",
                    "capability_name": "ocr",
                    "product_version": "1.2.0",
                    "operating_system": "linux",
                    "operating_system_version": "5.15.0",
                    "system_architecture": "amd64",
                },
                "expected_code": VALIDATION_CODE_LICENSE_VALID,
                "expected_valid": True,
            },
            {
                "vector_id": "operating_system_denied",
                "checked_at_cst": "2026-04-07T10:00:00+08:00",
                "signature_valid": True,
                "payload": {
                    "customer_code": "cust_vector",
                    "application_name": "agile-demo",
                    "operating_system": "windows",
                    "min_operating_system_version": None,
                    "system_architecture": None,
                    "capability_scope": ["ocr"],
                    "hardware_fingerprint": None,
                    "start_at_cst": "2026-04-01T00:00:00+08:00",
                    "expire_at_cst": "2026-05-01T00:00:00+08:00",
                    "version_constraints": {},
                },
                "request_context": {
                    "hardware_fingerprint": None,
                    "capability_name": "ocr",
                    "product_version": "1.0.0",
                    "operating_system": "linux",
                    "operating_system_version": "5.15.0",
                    "system_architecture": "x86_64",
                },
                "expected_code": VALIDATION_CODE_OPERATING_SYSTEM_DENIED,
                "expected_valid": False,
            },
            {
                "vector_id": "operating_system_version_denied",
                "checked_at_cst": "2026-04-07T10:00:00+08:00",
                "signature_valid": True,
                "payload": {
                    "customer_code": "cust_vector",
                    "application_name": "agile-demo",
                    "operating_system": "android",
                    "min_operating_system_version": "13.0.0",
                    "system_architecture": None,
                    "capability_scope": ["ocr"],
                    "hardware_fingerprint": None,
                    "start_at_cst": "2026-04-01T00:00:00+08:00",
                    "expire_at_cst": "2026-05-01T00:00:00+08:00",
                    "version_constraints": {},
                },
                "request_context": {
                    "hardware_fingerprint": None,
                    "capability_name": "ocr",
                    "product_version": "1.0.0",
                    "operating_system": "android",
                    "operating_system_version": "12.1.0",
                    "system_architecture": "arm64",
                },
                "expected_code": VALIDATION_CODE_OPERATING_SYSTEM_VERSION_DENIED,
                "expected_valid": False,
            },
            {
                "vector_id": "system_architecture_denied",
                "checked_at_cst": "2026-04-07T10:00:00+08:00",
                "signature_valid": True,
                "payload": {
                    "customer_code": "cust_vector",
                    "application_name": "agile-demo",
                    "operating_system": "linux",
                    "min_operating_system_version": None,
                    "system_architecture": "arm64",
                    "capability_scope": ["ocr"],
                    "hardware_fingerprint": None,
                    "start_at_cst": "2026-04-01T00:00:00+08:00",
                    "expire_at_cst": "2026-05-01T00:00:00+08:00",
                    "version_constraints": {},
                },
                "request_context": {
                    "hardware_fingerprint": None,
                    "capability_name": "ocr",
                    "product_version": "1.0.0",
                    "operating_system": "linux",
                    "operating_system_version": "5.15.0",
                    "system_architecture": "x86_64",
                },
                "expected_code": VALIDATION_CODE_SYSTEM_ARCHITECTURE_DENIED,
                "expected_valid": False,
            },
        ],
    }


def evaluate_license_payload(
    *,
    payload: dict[str, Any],
    signature_valid: bool,
    checked_at_cst: str,
    hardware_fingerprint: str | None,
    capability_name: str | None,
    product_version: str | None,
    operating_system: str | None,
    operating_system_version: str | None,
    system_architecture: str | None,
    version_checker: callable,
) -> ValidationEvaluation:
    contract = build_validation_contract()["code_catalog"]
    if not signature_valid:
        code = VALIDATION_CODE_SIGNATURE_INVALID
        spec = contract[code]
        return ValidationEvaluation(
            valid=False,
            result=str(spec["result"]),
            code=code,
            reason=str(spec["message"]),
            stage=str(spec["stage"]),
            details={"check": "signature", "signature_valid": False},
        )

    now_cst = parse_cst_datetime(checked_at_cst)
    start_at = parse_cst_datetime(str(payload["start_at_cst"]))
    expire_at = parse_cst_datetime(str(payload["expire_at_cst"]))
    capability_scope = payload.get("capability_scope", [])
    version_constraints = payload.get("version_constraints", {})
    expected_fingerprint = payload.get("hardware_fingerprint")
    required_operating_system = _normalize_operating_system(payload.get("operating_system"))
    provided_operating_system = _normalize_operating_system(operating_system)
    required_system_architecture = _normalize_system_architecture(payload.get("system_architecture"))
    provided_system_architecture = _normalize_system_architecture(system_architecture)
    minimum_operating_system_version = payload.get("min_operating_system_version")

    if now_cst < start_at:
        code = VALIDATION_CODE_NOT_YET_VALID
        spec = contract[code]
        return ValidationEvaluation(
            valid=False,
            result=str(spec["result"]),
            code=code,
            reason=str(spec["message"]),
            stage=str(spec["stage"]),
            details={"check": "time_window", "checked_at_cst": checked_at_cst, "start_at_cst": str(payload["start_at_cst"])},
        )
    if now_cst > expire_at:
        code = VALIDATION_CODE_EXPIRED
        spec = contract[code]
        return ValidationEvaluation(
            valid=False,
            result=str(spec["result"]),
            code=code,
            reason=str(spec["message"]),
            stage=str(spec["stage"]),
            details={"check": "time_window", "checked_at_cst": checked_at_cst, "expire_at_cst": str(payload["expire_at_cst"])},
        )
    if expected_fingerprint and hardware_fingerprint != expected_fingerprint:
        code = VALIDATION_CODE_HARDWARE_MISMATCH
        spec = contract[code]
        return ValidationEvaluation(
            valid=False,
            result=str(spec["result"]),
            code=code,
            reason=str(spec["message"]),
            stage=str(spec["stage"]),
            details={
                "check": "hardware_fingerprint",
                "expected_hardware_fingerprint": expected_fingerprint,
                "provided_hardware_fingerprint": hardware_fingerprint,
            },
        )
    if capability_name and capability_scope and capability_name not in capability_scope:
        code = VALIDATION_CODE_CAPABILITY_DENIED
        spec = contract[code]
        return ValidationEvaluation(
            valid=False,
            result=str(spec["result"]),
            code=code,
            reason=str(spec["message"]),
            stage=str(spec["stage"]),
            details={
                "check": "capability_scope",
                "requested_capability": capability_name,
                "allowed_capabilities": list(capability_scope) if isinstance(capability_scope, list) else [],
            },
        )
    if product_version is not None and not version_checker(product_version, version_constraints if isinstance(version_constraints, dict) else {}):
        code = VALIDATION_CODE_VERSION_DENIED
        spec = contract[code]
        return ValidationEvaluation(
            valid=False,
            result=str(spec["result"]),
            code=code,
            reason=str(spec["message"]),
            stage=str(spec["stage"]),
            details={
                "check": "version_constraints",
                "requested_product_version": product_version,
                "constraints": version_constraints if isinstance(version_constraints, dict) else {},
            },
        )
    if required_operating_system and provided_operating_system != required_operating_system:
        code = VALIDATION_CODE_OPERATING_SYSTEM_DENIED
        spec = contract[code]
        return ValidationEvaluation(
            valid=False,
            result=str(spec["result"]),
            code=code,
            reason=str(spec["message"]),
            stage=str(spec["stage"]),
            details={
                "check": "operating_system",
                "required_operating_system": required_operating_system,
                "provided_operating_system": provided_operating_system,
            },
        )
    if minimum_operating_system_version:
        normalized_min_version = str(minimum_operating_system_version).strip()
        normalized_current_version = str(operating_system_version).strip() if operating_system_version is not None else ""
        if not normalized_current_version or not _meets_minimum_version(normalized_current_version, normalized_min_version):
            code = VALIDATION_CODE_OPERATING_SYSTEM_VERSION_DENIED
            spec = contract[code]
            return ValidationEvaluation(
                valid=False,
                result=str(spec["result"]),
                code=code,
                reason=str(spec["message"]),
                stage=str(spec["stage"]),
                details={
                    "check": "operating_system_version",
                    "required_min_operating_system_version": normalized_min_version,
                    "provided_operating_system_version": normalized_current_version or None,
                },
            )
    if required_system_architecture and provided_system_architecture != required_system_architecture:
        code = VALIDATION_CODE_SYSTEM_ARCHITECTURE_DENIED
        spec = contract[code]
        return ValidationEvaluation(
            valid=False,
            result=str(spec["result"]),
            code=code,
            reason=str(spec["message"]),
            stage=str(spec["stage"]),
            details={
                "check": "system_architecture",
                "required_system_architecture": required_system_architecture,
                "provided_system_architecture": provided_system_architecture,
            },
        )

    code = VALIDATION_CODE_LICENSE_VALID
    spec = contract[code]
    return ValidationEvaluation(
        valid=True,
        result=str(spec["result"]),
        code=code,
        reason=str(spec["message"]),
        stage=str(spec["stage"]),
        details={
            "check": "success",
            "requested_capability": capability_name,
            "requested_product_version": product_version,
            "provided_hardware_fingerprint": hardware_fingerprint,
            "requested_operating_system": provided_operating_system,
            "requested_operating_system_version": operating_system_version,
            "requested_system_architecture": provided_system_architecture,
            "application_name": payload.get("application_name"),
        },
    )
