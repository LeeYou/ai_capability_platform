from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.request import urlopen


def write_json_snapshot(snapshot_path: Path, payload: dict[str, object]) -> dict[str, object]:
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def read_json_snapshot(snapshot_path: Path, *, default_payload: dict[str, object]) -> dict[str, object]:
    if not snapshot_path.exists():
        return default_payload
    return json.loads(snapshot_path.read_text(encoding="utf-8"))


def build_snapshot_payload(**sections: object) -> dict[str, object]:
    payload = dict(sections)
    payload["synced_at"] = datetime.now(timezone.utc).isoformat()
    return payload


def fetch_json(url: str, *, timeout: int = 10) -> dict[str, object]:
    with urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))
