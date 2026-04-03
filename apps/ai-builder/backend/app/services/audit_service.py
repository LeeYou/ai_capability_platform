from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path


CST = timezone(timedelta(hours=8))


def now_cst_iso() -> str:
    return datetime.now(CST).isoformat()


def append_audit_log(
    audit_log_path: Path,
    *,
    action: str,
    entity_type: str,
    entity_id: str,
    detail: dict[str, object],
) -> None:
    audit_log_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "happened_at_cst": now_cst_iso(),
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "detail": detail,
    }
    with audit_log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def list_audit_logs(audit_log_path: Path, limit: int = 100) -> list[dict[str, object]]:
    if limit <= 0:
        return []
    if not audit_log_path.exists():
        return []
    lines = audit_log_path.read_text(encoding="utf-8").splitlines()
    items = [json.loads(line) for line in lines if line.strip()]
    return items[-limit:][::-1]
