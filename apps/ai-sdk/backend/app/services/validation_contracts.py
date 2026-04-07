from __future__ import annotations


DIAGNOSTICS_VERSION = "1.0"


def build_validation_contract() -> dict[str, object]:
    return {
        "diagnostics_version": DIAGNOSTICS_VERSION,
        "fields": {
            "result": ["passed", "failed"],
            "code": [
                "license_valid",
                "signature_invalid",
                "time_window_not_started",
                "time_window_expired",
                "hardware_fingerprint_mismatch",
                "capability_scope_denied",
                "version_constraints_denied",
                "operating_system_denied",
                "operating_system_version_denied",
                "system_architecture_denied",
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
            "license_valid": {"result": "passed", "stage": "success", "message": "license 校验通过。"},
            "signature_invalid": {"result": "failed", "stage": "signature", "message": "签名校验失败。"},
            "time_window_not_started": {"result": "failed", "stage": "time_window", "message": "license 尚未生效。"},
            "time_window_expired": {"result": "failed", "stage": "time_window", "message": "license 已过期。"},
            "hardware_fingerprint_mismatch": {
                "result": "failed",
                "stage": "hardware_fingerprint",
                "message": "硬件指纹不匹配。",
            },
            "capability_scope_denied": {"result": "failed", "stage": "capability_scope", "message": "能力范围不匹配。"},
            "version_constraints_denied": {"result": "failed", "stage": "version_constraints", "message": "版本约束不匹配。"},
            "operating_system_denied": {"result": "failed", "stage": "operating_system", "message": "操作系统不匹配。"},
            "operating_system_version_denied": {
                "result": "failed",
                "stage": "operating_system_version",
                "message": "系统版本低于 license 最低要求。",
            },
            "system_architecture_denied": {"result": "failed", "stage": "system_architecture", "message": "系统架构不匹配。"},
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
                "vector_id": "platform_linux_x86_64_pass",
                "payload": {
                    "application_name": "agile-demo",
                    "operating_system": "linux",
                    "min_operating_system_version": "5.4.0",
                    "system_architecture": "x86_64",
                },
                "request_context": {
                    "operating_system": "linux",
                    "operating_system_version": "5.15.0",
                    "system_architecture": "amd64",
                },
                "expected_code": "license_valid",
                "expected_valid": True,
            },
            {
                "vector_id": "platform_android_version_reject",
                "payload": {
                    "application_name": "agile-demo",
                    "operating_system": "android",
                    "min_operating_system_version": "13.0.0",
                    "system_architecture": "arm64",
                },
                "request_context": {
                    "operating_system": "android",
                    "operating_system_version": "12.0.0",
                    "system_architecture": "arm64",
                },
                "expected_code": "operating_system_version_denied",
                "expected_valid": False,
            },
        ],
    }
