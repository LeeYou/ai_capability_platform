from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.db.models import CustomerModel, KeyPairModel, LicenseIssueRecordModel, LicensePolicyModel, LicenseToolReleaseModel
from app.services.audit_service import append_audit_log, now_cst_iso
from app.services.crypto_service import generate_hardware_fingerprint, generate_key_pair_files, sign_payload, verify_signature
from app.services.license_errors import (
    CustomerNotFoundError,
    KeyPairNotFoundError,
    LicenseIssueNotFoundError,
    LicensePolicyNotFoundError,
    LicenseToolReleaseNotFoundError,
)
from app.services.license_tool_release_service import (
    export_license_tool_release as _export_license_tool_release,
    get_license_tool_release as _get_license_tool_release,
    list_license_tool_releases as _list_license_tool_releases,
    sync_default_license_tool_release as _sync_default_license_tool_release,
)
from app.services.license_export_service import export_license_issue as _export_license_issue
from app.services.license_issue_service import (
    issue_license as _issue_license,
    validate_license_issue as _validate_license_issue,
)
from app.services.customer_service import (
    create_customer as _create_customer,
    get_customer as _get_customer,
    list_customers as _list_customers,
)
from app.services.key_pair_service import (
    create_key_pair as _create_key_pair,
    get_key_pair as _get_key_pair,
    isolate_key_pair as _isolate_key_pair,
    list_key_pairs as _list_key_pairs,
    rotate_key_pair as _rotate_key_pair,
)
from app.services.policy_service import (
    create_license_policy as _create_license_policy,
    get_license_policy as _get_license_policy,
    list_license_policies as _list_license_policies,
)
from app.services.validation_contracts import (
    DIAGNOSTICS_VERSION,
    build_validation_contract,
    build_validation_vectors,
    evaluate_license_payload,
    parse_cst_datetime,
)


CST = timezone(timedelta(hours=8))
REPO_ROOT = Path(__file__).resolve().parents[5]
LICENSE_TOOL_NAME = "license_tool"
LICENSE_TOOL_VERSION = "1.0.0"
LICENSE_TOOL_SOURCE_FILES = {
    "CMakeLists.txt": REPO_ROOT / "apps/shared/license_tool_src/CMakeLists.txt",
    "src/license_tool.cpp": REPO_ROOT / "apps/shared/license_tool_src/src/license_tool.cpp",
    "src/license_common.cpp": REPO_ROOT / "apps/shared/license_tool_src/src/license_common.cpp",
    "src/license_common.h": REPO_ROOT / "apps/shared/license_tool_src/src/license_common.h",
}
LICENSE_TOOL_SUPPORTED_TARGETS = ["linux_x86_64", "linux_aarch64", "windows_x86", "windows_x86_64"]
ALLOWED_OPERATING_SYSTEMS = {"windows", "linux", "android", "ios"}


def initialize_database() -> None:
    from app.db.database import Base, get_engine
    from app.db import models  # noqa: F401

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    if "license_issue_record" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("license_issue_record")}
    statements: list[str] = []
    if "last_validation_code" not in columns:
        statements.append("ALTER TABLE license_issue_record ADD COLUMN last_validation_code VARCHAR(64)")
    if "last_validation_details_json" not in columns:
        statements.append("ALTER TABLE license_issue_record ADD COLUMN last_validation_details_json TEXT")
    if "operating_system" not in columns:
        statements.append("ALTER TABLE license_issue_record ADD COLUMN operating_system VARCHAR(32) DEFAULT 'linux'")
    if "min_operating_system_version" not in columns:
        statements.append("ALTER TABLE license_issue_record ADD COLUMN min_operating_system_version VARCHAR(64)")
    if "system_architecture" not in columns:
        statements.append("ALTER TABLE license_issue_record ADD COLUMN system_architecture VARCHAR(64)")
    if "application_name" not in columns:
        statements.append("ALTER TABLE license_issue_record ADD COLUMN application_name VARCHAR(255) DEFAULT 'ai-capability-platform'")
    policy_columns = {column["name"] for column in inspector.get_columns("license_policy")}
    if "operating_system" not in policy_columns:
        statements.append("ALTER TABLE license_policy ADD COLUMN operating_system VARCHAR(32) DEFAULT 'linux'")
    if "min_operating_system_version" not in policy_columns:
        statements.append("ALTER TABLE license_policy ADD COLUMN min_operating_system_version VARCHAR(64)")
    if "system_architecture" not in policy_columns:
        statements.append("ALTER TABLE license_policy ADD COLUMN system_architecture VARCHAR(64)")
    if "application_name" not in policy_columns:
        statements.append("ALTER TABLE license_policy ADD COLUMN application_name VARCHAR(255) DEFAULT 'ai-capability-platform'")
    if statements:
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))


def _normalize_policy_times(start_at_cst: str, expire_at_cst: str) -> tuple[str, str]:
    start = parse_cst_datetime(start_at_cst)
    expire = parse_cst_datetime(expire_at_cst)
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
        "rotation_version": key_pair.rotation_version,
        "predecessor_key_pair_id": key_pair.predecessor_key_pair_id,
        "status_changed_at_cst": key_pair.status_changed_at_cst,
        "status_reason": key_pair.status_reason,
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
        "operating_system": policy.operating_system,
        "min_operating_system_version": policy.min_operating_system_version,
        "system_architecture": policy.system_architecture,
        "application_name": policy.application_name,
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
        "last_validation_details": json.loads(issue.last_validation_details_json)
        if issue.last_validation_details_json
        else {},
        "payload": payload,
    }


def _tool_release_item(release: LicenseToolReleaseModel) -> dict[str, object]:
    return {
        "release_id": release.id,
        "tool_name": release.tool_name,
        "version": release.version,
        "status": release.status,
        "archive_path": release.archive_path,
        "manifest_path": release.manifest_path,
        "readme_path": release.readme_path,
        "checksum_sha256": release.checksum_sha256,
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _normalize_key_name(raw_value: str, *, field_name: str = "密钥名称") -> str:
    normalized = raw_value.strip()
    if not normalized:
        raise ValueError(f"{field_name}不能为空。")
    return normalized


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


def _build_license_tool_release_materials(license_tools_root: Path, *, version: str) -> tuple[Path, Path, Path]:
    release_root = (license_tools_root / f"{LICENSE_TOOL_NAME}_v{version}").resolve()
    if not (release_root == license_tools_root or license_tools_root in release_root.parents):
        raise ValueError("license_tool 发布目录非法。")
    if release_root.exists():
        shutil.rmtree(release_root)
    release_root.mkdir(parents=True, exist_ok=True)

    for relative_path, source_path in LICENSE_TOOL_SOURCE_FILES.items():
        destination = release_root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)

    manifest_path = release_root / "manifest.json"
    readme_path = release_root / "README.md"
    error_codes_path = release_root / "ERROR_CODES.md"
    hardware_guide_path = release_root / "HARDWARE_FINGERPRINT.md"
    diagnostics_path = release_root / "LICENSE_DIAGNOSTICS.json"
    validation_vectors_path = release_root / "VALIDATION_VECTORS.json"
    _write_text(release_root / "VERSION", version + "\n")
    _write_text(diagnostics_path, json.dumps(build_validation_contract(), ensure_ascii=False, indent=2, sort_keys=True))
    _write_text(validation_vectors_path, json.dumps(build_validation_vectors(), ensure_ascii=False, indent=2, sort_keys=True))
    _write_text(
        manifest_path,
        json.dumps(
            {
                "tool_name": LICENSE_TOOL_NAME,
                "version": version,
                "bundle_format": "source_bundle",
                "entrypoint": "src/license_tool.cpp",
                "build_system": "cmake",
                "diagnostics_version": DIAGNOSTICS_VERSION,
                "supported_targets": LICENSE_TOOL_SUPPORTED_TARGETS,
                "source_files": sorted(LICENSE_TOOL_SOURCE_FILES),
                "documents": ["README.md", "ERROR_CODES.md", "HARDWARE_FINGERPRINT.md", "LICENSE_DIAGNOSTICS.json", "VALIDATION_VECTORS.json"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
    )
    _write_text(
        readme_path,
        "\n".join(
            [
                "# license_tool",
                "",
                f"- 工具名称：`{LICENSE_TOOL_NAME}`",
                f"- 版本：`{version}`",
                "- 交付形态：标准 C++ source bundle",
                "",
                "## 目录说明",
                "",
                "- `src/`：`license_tool` 与 `license_common` 参考实现源码",
                "- `CMakeLists.txt`：最小 CMake 构建入口",
                "- `ERROR_CODES.md`：退出码说明",
                "- `HARDWARE_FINGERPRINT.md`：硬件指纹采集说明",
                "",
                "## 构建方式",
                "",
                "```bash",
                "cmake -S . -B build",
                "cmake --build build --parallel",
                "```",
                "",
                "## 用法",
                "",
                "```bash",
                "./build/license_tool verify /path/to/license.bin",
                "./build/license_tool generate /path/to/license.bin customer_name capability_a,capability_b --operating-system linux --application-name ai-prod",
                "```",
                "",
                "## 版本兼容性",
                "",
                "- 当前 bundle 已对齐 ai-license-mgr 与 ai-prod 的 license 版本约束语义。",
                "- 授权载荷已支持 `operating_system` / `min_operating_system_version` / `system_architecture` / `application_name` 字段。",
                f"- 当前 bundle 诊断契约版本：`{DIAGNOSTICS_VERSION}`，稳定字段定义见 `LICENSE_DIAGNOSTICS.json`。",
                "- 金标准测试向量见 `VALIDATION_VECTORS.json`，供 runtime / SDK / license_tool 做一致性回归。",
                "- 交付时需配套 `license.bin`、`pubkey.pem` 与本文档一并提供。",
                "",
            ]
        ),
    )
    _write_text(
        error_codes_path,
        "\n".join(
            [
                "# ERROR_CODES",
                "",
                "| 退出码 | 含义 |",
                "| --- | --- |",
                "| 1 | 参数不足或 mode 非法 |",
                "| 2 | generate 参数错误或 bool 选项非法 |",
                "| 3 | 生成 license 文件失败 |",
                "| 4 | 解析 license 文件失败 |",
                "| 5 | 验证 license 失败 |",
                "| 6 | 未知 mode |",
                "",
                "## 稳定诊断 code",
                "",
                "| code | 含义 |",
                "| --- | --- |",
                "| license_valid | 校验通过 |",
                "| signature_invalid | 签名校验失败 |",
                "| time_window_not_started | 尚未生效 |",
                "| time_window_expired | 已过期 |",
                "| hardware_fingerprint_mismatch | 硬件指纹不匹配 |",
                "| capability_scope_denied | 能力范围不匹配 |",
                "| version_constraints_denied | 版本约束不匹配 |",
                "| operating_system_denied | 操作系统不匹配 |",
                "| operating_system_version_denied | 系统版本低于 license 最低要求 |",
                "| system_architecture_denied | 系统架构不匹配 |",
                "",
            ]
        ),
    )
    _write_text(
        hardware_guide_path,
        "\n".join(
            [
                "# HARDWARE_FINGERPRINT",
                "",
                "硬件指纹采用 `key=value` 形式按 key 排序后，以 `|` 连接并计算 SHA256。",
                "",
                "示例：",
                "",
                "```text",
                "cpu=intel-i7|disk=nvme-sn-001|mac=00:11:22:33:44:55",
                "```",
                "",
                "若现场需要预先计算硬件指纹，可通过 ai-license-mgr `/api/v1/hardware-fingerprint` 接口统一生成。",
                "平台授权建议同时记录操作系统、最低系统版本与系统架构；`application_name` 仅用于标识交付对象。",
                "",
            ]
        ),
    )

    archive_base = release_root.parent / release_root.name
    archive_path = Path(shutil.make_archive(str(archive_base), "gztar", root_dir=release_root.parent, base_dir=release_root.name))
    return archive_path.resolve(), manifest_path.resolve(), readme_path.resolve()


def list_customers(session: Session) -> list[dict[str, object]]:
    return _list_customers(session)


def get_customer(session: Session, customer_id: int) -> dict[str, object]:
    return _get_customer(session, customer_id)


def create_customer(
    session: Session,
    audit_log_path: Path,
    *,
    customer_code: str,
    customer_name: str,
    contact_name: str | None,
    contact_email: str | None,
) -> dict[str, object]:
    return _create_customer(
        session,
        audit_log_path,
        customer_code=customer_code,
        customer_name=customer_name,
        contact_name=contact_name,
        contact_email=contact_email,
    )


def list_key_pairs(session: Session) -> list[dict[str, object]]:
    return _list_key_pairs(session)


def get_key_pair(session: Session, key_pair_id: int) -> dict[str, object]:
    return _get_key_pair(session, key_pair_id)


def create_key_pair(
    session: Session,
    key_pairs_root: Path,
    audit_log_path: Path,
    *,
    key_name: str,
) -> dict[str, object]:
    return _create_key_pair(
        session,
        key_pairs_root,
        audit_log_path,
        key_name=key_name,
    )


def rotate_key_pair(
    session: Session,
    key_pairs_root: Path,
    audit_log_path: Path,
    *,
    key_pair_id: int,
    new_key_name: str | None,
    reason: str | None,
) -> dict[str, object]:
    return _rotate_key_pair(
        session,
        key_pairs_root,
        audit_log_path,
        key_pair_id=key_pair_id,
        new_key_name=new_key_name,
        reason=reason,
    )


def isolate_key_pair(
    session: Session,
    audit_log_path: Path,
    *,
    key_pair_id: int,
    reason: str,
) -> dict[str, object]:
    return _isolate_key_pair(
        session,
        audit_log_path,
        key_pair_id=key_pair_id,
        reason=reason,
    )


def list_license_policies(session: Session) -> list[dict[str, object]]:
    return _list_license_policies(session)


def get_license_policy(session: Session, policy_id: int) -> dict[str, object]:
    return _get_license_policy(session, policy_id)


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
    return _create_license_policy(
        session,
        audit_log_path,
        policy_name=policy_name,
        customer_id=customer_id,
        key_pair_id=key_pair_id,
        capability_scope=capability_scope,
        version_constraints=version_constraints,
        hardware_fingerprint=hardware_fingerprint,
        operating_system=operating_system,
        min_operating_system_version=min_operating_system_version,
        system_architecture=system_architecture,
        application_name=application_name,
        start_at_cst=start_at_cst,
        expire_at_cst=expire_at_cst,
        notes=notes,
    )


def issue_license(
    session: Session,
    license_root: Path,
    issue_records_root: Path,
    audit_log_path: Path,
    *,
    policy_id: int,
) -> dict[str, object]:
    return _issue_license(
        session,
        license_root,
        issue_records_root,
        audit_log_path,
        policy_id=policy_id,
    )


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
    operating_system: str | None,
    operating_system_version: str | None,
    system_architecture: str | None,
) -> dict[str, object]:
    return _validate_license_issue(
        session,
        audit_log_path,
        issue_record_id=issue_record_id,
        hardware_fingerprint=hardware_fingerprint,
        capability_name=capability_name,
        product_version=product_version,
        operating_system=operating_system,
        operating_system_version=operating_system_version,
        system_architecture=system_architecture,
        version_checker=_is_version_allowed,
    )


def export_license_issue(
    session: Session,
    exports_root: Path,
    audit_log_path: Path,
    *,
    issue_record_id: int,
    export_format: str,
) -> Path:
    return _export_license_issue(
        session,
        exports_root,
        audit_log_path,
        issue_record_id=issue_record_id,
        export_format=export_format,
    )


def list_license_tool_releases(session: Session) -> list[dict[str, object]]:
    return _list_license_tool_releases(session)


def get_license_tool_release(session: Session, release_id: int) -> dict[str, object]:
    return _get_license_tool_release(session, release_id)


def sync_default_license_tool_release(
    session: Session,
    license_tools_root: Path,
    audit_log_path: Path,
) -> dict[str, object]:
    return _sync_default_license_tool_release(session, license_tools_root, audit_log_path)


def export_license_tool_release(
    session: Session,
    exports_root: Path,
    audit_log_path: Path,
    *,
    release_id: int,
    export_format: str,
) -> Path:
    return _export_license_tool_release(
        session,
        exports_root,
        audit_log_path,
        release_id=release_id,
        export_format=export_format,
    )


def build_hardware_fingerprint(features: dict[str, str]) -> str:
    return generate_hardware_fingerprint(features)


def get_license_validation_contract() -> dict[str, object]:
    return build_validation_contract()


def get_license_validation_vectors() -> dict[str, object]:
    return build_validation_vectors()
