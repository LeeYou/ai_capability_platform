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
    args = parser.parse_args()

    results: list[CheckResult] = []

    health_status, health_payload, health_latency = request_json(args.base_url, "/api/v1/health", timeout=args.timeout)
    results.append(
        run_check(
            "health",
            status_code=health_status,
            latency_ms=health_latency,
            max_latency_ms=args.health_max_ms,
            predicate=isinstance(health_payload, dict) and health_payload.get("status") == "ok",
            detail=f"status={health_status}, payload={health_payload}",
        )
    )

    capabilities_status, capabilities_payload, capabilities_latency = request_json(args.base_url, "/api/v1/capabilities", timeout=args.timeout)
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

    license_status, license_payload, license_latency = request_json(args.base_url, "/api/v1/license/status", timeout=args.timeout)
    results.append(
        run_check(
            "license_status",
            status_code=license_status,
            latency_ms=license_latency,
            max_latency_ms=args.license_max_ms,
            predicate=isinstance(license_payload, dict) and "valid" in license_payload and "reason" in license_payload,
            detail=f"status={license_status}, payload={license_payload}",
        )
    )

    catalog_status, catalog_payload, catalog_latency = request_json(args.base_url, "/api/v1/admin/catalog", timeout=args.timeout)
    results.append(
        run_check(
            "catalog",
            status_code=catalog_status,
            latency_ms=catalog_latency,
            max_latency_ms=args.catalog_max_ms,
            predicate=isinstance(catalog_payload, dict)
            and "items" in catalog_payload
            and all(
                isinstance(item, dict)
                and "max_batch_size" in item
                and "pending_request_count" in item
                and "queue_timeout_count" in item
                for item in catalog_payload.get("items", [])
            ),
            detail=f"status={catalog_status}, payload={catalog_payload}",
        )
    )

    metrics_status, metrics_payload, metrics_latency = request_json(args.base_url, "/api/v1/admin/metrics", timeout=args.timeout)
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

    public_internal_status, public_internal_payload, public_internal_latency = request_json(
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
        admin_status, admin_payload, admin_latency = request_json(
            args.base_url,
            "/api/v1/admin/license-reload",
            method="POST",
            body={},
            timeout=args.timeout,
        )
        results.append(
            CheckResult(
                name="license_reload",
                passed=admin_status < 400,
                status_code=admin_status,
                latency_ms=admin_latency,
                detail=f"status={admin_status}, payload={admin_payload}",
            )
        )

    selected_capability = args.capability.strip() or (
        capability_items[0].get("capability_name", "") if capability_items and isinstance(capability_items[0], dict) else ""
    )
    if selected_capability:
        infer_status, infer_payload, infer_latency = request_json(
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
                predicate=isinstance(infer_payload, dict) and infer_payload.get("capability_name") == selected_capability,
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

    summary = {"base_url": args.base_url, "results": [asdict(item) for item in results]}
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    failed = [item for item in results if not item.passed]
    if failed:
        print(f"ai-prod acceptance failed: {[item.name for item in failed]}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
