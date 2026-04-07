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
        return parsed.replace(tzinfo=CST)
    return parsed.astimezone(CST)


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
            ],
            "stage": [
                "signature",
                "time_window",
                "hardware_fingerprint",
                "capability_scope",
                "version_constraints",
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
    }


def evaluate_license_payload(
    *,
    payload: dict[str, Any],
    signature_valid: bool,
    checked_at_cst: str,
    hardware_fingerprint: str | None,
    capability_name: str | None,
    product_version: str | None,
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
        },
    )
