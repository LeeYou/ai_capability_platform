from __future__ import annotations

from pathlib import Path
import shutil

from sqlalchemy.orm import Session

from app.db.models import LicenseIssueRecordModel
from app.services.audit_service import append_audit_log
from app.services.license_errors import LicenseIssueNotFoundError


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
