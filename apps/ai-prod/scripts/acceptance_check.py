from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass


@dataclass
class CheckResult:
    name: str
    passed: bool
    status_code: int | None
    latency_ms: int
    detail: str


def _extract_revision_id(payload: object) -> int | None:
    if not isinstance(payload, dict):
        return None
    revision_id = payload.get("runtime_revision_id")
    return revision_id if isinstance(revision_id, int) and revision_id > 0 else None


def _catalog_items(payload: object) -> list[dict[str, object]]:
    if not isinstance(payload, dict):
        return []
    items = payload.get("items", [])
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def _catalog_predicate(payload: object) -> bool:
    return all(
        "max_batch_size" in item
        and "queue_wait_timeout_ms" in item
        and "configured_max_pending_request_count" in item
        and "pending_request_count" in item
        and "queue_timeout_count" in item
        and "admission_checklist" in item
        for item in _catalog_items(payload)
    )


def _license_predicate(payload: object) -> bool:
    return isinstance(payload, dict) and all(
        key in payload for key in ("valid", "reason", "result", "code", "stage", "details", "diagnostics_version")
    )


def request_json(base_url: str, path: str, *, method: str = "GET", body: dict[str, object] | None = None, timeout: float = 10.0) -> tuple[int, object, int]:
    payload = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=payload,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    started_at = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw_body = response.read().decode("utf-8")
            latency_ms = int((time.perf_counter() - started_at) * 1000)
            return response.status, json.loads(raw_body) if raw_body else {}, latency_ms
    except urllib.error.HTTPError as exc:
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        raw_body = exc.read().decode("utf-8")
        payload_json: object
        try:
            payload_json = json.loads(raw_body) if raw_body else {}
        except json.JSONDecodeError:
            payload_json = {"raw_body": raw_body}
        return exc.code, payload_json, latency_ms


def run_check(name: str, *, status_code: int, latency_ms: int, max_latency_ms: int, predicate: bool, detail: str) -> CheckResult:
    return CheckResult(
        name=name,
        passed=status_code < 400 and latency_ms <= max_latency_ms and predicate,
        status_code=status_code,
        latency_ms=latency_ms,
        detail=detail,
    )


def run_acceptance(
    args: argparse.Namespace,
    *,
    requester=request_json,
) -> dict[str, object]:
    results: list[CheckResult] = []

    health_status, health_payload, health_latency = requester(args.base_url, "/api/v1/health", timeout=args.timeout)
    initial_revision_id = _extract_revision_id(health_payload)
    results.append(
        run_check(
            "health",
            status_code=health_status,
            latency_ms=health_latency,
            max_latency_ms=args.health_max_ms,
            predicate=isinstance(health_payload, dict)
            and health_payload.get("status") == "ok"
            and initial_revision_id is not None,
            detail=f"status={health_status}, payload={health_payload}",
        )
    )

    capabilities_status, capabilities_payload, capabilities_latency = requester(
        args.base_url,
        "/api/v1/capabilities",
        timeout=args.timeout,
    )
    capability_items = capabilities_payload.get("items", []) if isinstance(capabilities_payload, dict) else []
    results.append(
        run_check(
            "capabilities",
            status_code=capabilities_status,
            latency_ms=capabilities_latency,
            max_latency_ms=args.capabilities_max_ms,
            predicate=isinstance(capability_items, list),
            detail=f"status={capabilities_status}, capability_count={len(capability_items)}",
        )
    )

    license_status, license_payload, license_latency = requester(
        args.base_url,
        "/api/v1/license/status",
        timeout=args.timeout,
    )
    results.append(
        run_check(
            "license_status",
            status_code=license_status,
            latency_ms=license_latency,
            max_latency_ms=args.license_max_ms,
            predicate=_license_predicate(license_payload),
            detail=f"status={license_status}, payload={license_payload}",
        )
    )

    catalog_status, catalog_payload, catalog_latency = requester(
        args.base_url,
        "/api/v1/admin/catalog",
        timeout=args.timeout,
    )
    results.append(
        run_check(
            "catalog",
            status_code=catalog_status,
            latency_ms=catalog_latency,
            max_latency_ms=args.catalog_max_ms,
            predicate=isinstance(catalog_payload, dict) and "items" in catalog_payload and _catalog_predicate(catalog_payload),
            detail=f"status={catalog_status}, payload={catalog_payload}",
        )
    )

    metrics_status, metrics_payload, metrics_latency = requester(
        args.base_url,
        "/api/v1/admin/metrics",
        timeout=args.timeout,
    )
    results.append(
        run_check(
            "metrics",
            status_code=metrics_status,
            latency_ms=metrics_latency,
            max_latency_ms=args.metrics_max_ms,
            predicate=isinstance(metrics_payload, dict)
            and "endpoint_metrics" in metrics_payload
            and "pool_summary" in metrics_payload
            and "request_summary" in metrics_payload
            and "queued_request_count" in metrics_payload.get("request_summary", {})
            and "pending_request_count" in metrics_payload.get("pool_summary", {}),
            detail=f"status={metrics_status}, payload={metrics_payload}",
        )
    )

    public_internal_status, public_internal_payload, public_internal_latency = requester(
        args.base_url,
        "/api/v1/admin/revisions",
        timeout=args.timeout,
    )
    results.append(
        CheckResult(
            name="internal_boundary",
            passed=public_internal_status == 404,
            status_code=public_internal_status,
            latency_ms=public_internal_latency,
            detail=f"status={public_internal_status}, payload={public_internal_payload}",
        )
    )

    if args.run_admin_checks:
        admin_status, admin_payload, admin_latency = requester(
            args.base_url,
            "/api/v1/admin/license-reload",
            method="POST",
            body={},
            timeout=args.timeout,
        )
        results.append(
            CheckResult(
                name="license_reload",
                passed=admin_status < 400 and isinstance(admin_payload, dict) and "license_status" in admin_payload,
                status_code=admin_status,
                latency_ms=admin_latency,
                detail=f"status={admin_status}, payload={admin_payload}",
            )
        )

    selected_capability = args.capability.strip() or (
        capability_items[0].get("capability_name", "") if capability_items and isinstance(capability_items[0], dict) else ""
    )
    if selected_capability:
        infer_status, infer_payload, infer_latency = requester(
            args.base_url,
            f"/api/v1/infer/{selected_capability}",
            method="POST",
            body={
                "input_type": args.input_type,
                "payload": args.infer_payload,
                "prefer_device": args.prefer_device,
                "options": {},
            },
            timeout=args.timeout,
        )
        results.append(
            run_check(
                "infer",
                status_code=infer_status,
                latency_ms=infer_latency,
                max_latency_ms=args.infer_max_ms,
                predicate=isinstance(infer_payload, dict)
                and infer_payload.get("capability_name") == selected_capability
                and infer_payload.get("runtime_revision_id") == initial_revision_id,
                detail=f"status={infer_status}, payload={infer_payload}",
            )
        )
    else:
        results.append(
            CheckResult(
                name="infer",
                passed=True,
                status_code=None,
                latency_ms=0,
                detail="skipped: no capability provided and runtime returned no capabilities",
            )
        )

    if args.run_transition_checks:
        reload_status, reload_payload, reload_latency = requester(
            args.base_url,
            "/api/v1/admin/reload",
            method="POST",
            body={"action": "reload"},
            timeout=args.timeout,
        )
        reload_revision_id = None
        if isinstance(reload_payload, dict) and isinstance(reload_payload.get("revision"), dict):
            candidate = reload_payload["revision"].get("revision_id")
            if isinstance(candidate, int) and candidate > 0:
                reload_revision_id = candidate
        results.append(
            CheckResult(
                name="reload",
                passed=reload_status < 400
                and isinstance(reload_payload, dict)
                and isinstance(reload_payload.get("revision"), dict)
                and reload_payload["revision"].get("action") == "reload"
                and reload_revision_id is not None
                and reload_revision_id != initial_revision_id,
                status_code=reload_status,
                latency_ms=reload_latency,
                detail=f"status={reload_status}, payload={reload_payload}",
            )
        )

        health_after_reload_status, health_after_reload_payload, health_after_reload_latency = requester(
            args.base_url,
            "/api/v1/health",
            timeout=args.timeout,
        )
        results.append(
            run_check(
                "health_after_reload",
                status_code=health_after_reload_status,
                latency_ms=health_after_reload_latency,
                max_latency_ms=args.health_max_ms,
                predicate=isinstance(health_after_reload_payload, dict)
                and health_after_reload_payload.get("status") == "ok"
                and health_after_reload_payload.get("runtime_revision_id") == reload_revision_id,
                detail=f"status={health_after_reload_status}, payload={health_after_reload_payload}",
            )
        )

        catalog_after_reload_status, catalog_after_reload_payload, catalog_after_reload_latency = requester(
            args.base_url,
            "/api/v1/admin/catalog",
            timeout=args.timeout,
        )
        results.append(
            run_check(
                "catalog_after_reload",
                status_code=catalog_after_reload_status,
                latency_ms=catalog_after_reload_latency,
                max_latency_ms=args.catalog_max_ms,
                predicate=isinstance(catalog_after_reload_payload, dict) and _catalog_predicate(catalog_after_reload_payload),
                detail=f"status={catalog_after_reload_status}, payload={catalog_after_reload_payload}",
            )
        )

        if selected_capability:
            infer_after_reload_status, infer_after_reload_payload, infer_after_reload_latency = requester(
                args.base_url,
                f"/api/v1/infer/{selected_capability}",
                method="POST",
                body={
                    "input_type": args.input_type,
                    "payload": args.infer_payload,
                    "prefer_device": args.prefer_device,
                    "options": {},
                },
                timeout=args.timeout,
            )
            results.append(
                run_check(
                    "infer_after_reload",
                    status_code=infer_after_reload_status,
                    latency_ms=infer_after_reload_latency,
                    max_latency_ms=args.infer_max_ms,
                    predicate=isinstance(infer_after_reload_payload, dict)
                    and infer_after_reload_payload.get("capability_name") == selected_capability
                    and infer_after_reload_payload.get("runtime_revision_id") == reload_revision_id,
                    detail=f"status={infer_after_reload_status}, payload={infer_after_reload_payload}",
                )
            )

        rollback_status, rollback_payload, rollback_latency = requester(
            args.base_url,
            "/api/v1/admin/rollback",
            method="POST",
            body={"target_revision_id": initial_revision_id},
            timeout=args.timeout,
        )
        rollback_revision_id = None
        if isinstance(rollback_payload, dict) and isinstance(rollback_payload.get("revision"), dict):
            candidate = rollback_payload["revision"].get("revision_id")
            if isinstance(candidate, int) and candidate > 0:
                rollback_revision_id = candidate
        results.append(
            CheckResult(
                name="rollback",
                passed=rollback_status < 400
                and isinstance(rollback_payload, dict)
                and isinstance(rollback_payload.get("revision"), dict)
                and rollback_payload["revision"].get("action") == "rollback"
                and rollback_payload["revision"].get("rollback_of_revision_id") == initial_revision_id
                and rollback_revision_id is not None
                and rollback_revision_id != reload_revision_id,
                status_code=rollback_status,
                latency_ms=rollback_latency,
                detail=f"status={rollback_status}, payload={rollback_payload}",
            )
        )

        health_after_rollback_status, health_after_rollback_payload, health_after_rollback_latency = requester(
            args.base_url,
            "/api/v1/health",
            timeout=args.timeout,
        )
        results.append(
            run_check(
                "health_after_rollback",
                status_code=health_after_rollback_status,
                latency_ms=health_after_rollback_latency,
                max_latency_ms=args.health_max_ms,
                predicate=isinstance(health_after_rollback_payload, dict)
                and health_after_rollback_payload.get("status") == "ok"
                and health_after_rollback_payload.get("runtime_revision_id") == rollback_revision_id,
                detail=f"status={health_after_rollback_status}, payload={health_after_rollback_payload}",
            )
        )

        catalog_after_rollback_status, catalog_after_rollback_payload, catalog_after_rollback_latency = requester(
            args.base_url,
            "/api/v1/admin/catalog",
            timeout=args.timeout,
        )
        results.append(
            run_check(
                "catalog_after_rollback",
                status_code=catalog_after_rollback_status,
                latency_ms=catalog_after_rollback_latency,
                max_latency_ms=args.catalog_max_ms,
                predicate=isinstance(catalog_after_rollback_payload, dict) and _catalog_predicate(catalog_after_rollback_payload),
                detail=f"status={catalog_after_rollback_status}, payload={catalog_after_rollback_payload}",
            )
        )

        if selected_capability:
            infer_after_rollback_status, infer_after_rollback_payload, infer_after_rollback_latency = requester(
                args.base_url,
                f"/api/v1/infer/{selected_capability}",
                method="POST",
                body={
                    "input_type": args.input_type,
                    "payload": args.infer_payload,
                    "prefer_device": args.prefer_device,
                    "options": {},
                },
                timeout=args.timeout,
            )
            results.append(
                run_check(
                    "infer_after_rollback",
                    status_code=infer_after_rollback_status,
                    latency_ms=infer_after_rollback_latency,
                    max_latency_ms=args.infer_max_ms,
                    predicate=isinstance(infer_after_rollback_payload, dict)
                    and infer_after_rollback_payload.get("capability_name") == selected_capability
                    and infer_after_rollback_payload.get("runtime_revision_id") == rollback_revision_id,
                    detail=f"status={infer_after_rollback_status}, payload={infer_after_rollback_payload}",
                )
            )

    summary = {"base_url": args.base_url, "results": [asdict(item) for item in results]}
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ai-prod delivery acceptance checks against the public C++ entrypoint.")
    parser.add_argument("--base-url", default="http://127.0.0.1:26004")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--health-max-ms", type=int, default=1000)
    parser.add_argument("--capabilities-max-ms", type=int, default=1000)
    parser.add_argument("--license-max-ms", type=int, default=1000)
    parser.add_argument("--catalog-max-ms", type=int, default=1000)
    parser.add_argument("--metrics-max-ms", type=int, default=1000)
    parser.add_argument("--infer-max-ms", type=int, default=5000)
    parser.add_argument("--capability", default="")
    parser.add_argument("--infer-payload", default='{"image":"demo"}')
    parser.add_argument("--input-type", default="json", choices=["json", "image", "video", "pdf"])
    parser.add_argument("--prefer-device", default="auto", choices=["auto", "gpu", "cpu"])
    parser.add_argument("--run-admin-checks", action="store_true")
    parser.add_argument("--run-transition-checks", action="store_true")
    args = parser.parse_args()

    summary = run_acceptance(args)
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    failed = [item for item in summary["results"] if not item["passed"]]
    if failed:
        print(f"ai-prod acceptance failed: {[item['name'] for item in failed]}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
