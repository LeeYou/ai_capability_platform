from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import sys
import time
import urllib.error
import urllib.request
from collections import Counter


def perform_request(base_url: str, path: str, *, method: str, body: dict[str, object] | None, timeout: float) -> tuple[bool, int | None, int, str]:
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
            response.read()
            latency_ms = int((time.perf_counter() - started_at) * 1000)
            return True, response.status, latency_ms, ""
    except urllib.error.HTTPError as exc:
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return False, exc.code, latency_ms, exc.read().decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return False, None, latency_ms, str(exc)


def percentile(values: list[int], ratio: float) -> int:
    if not values:
        return 0
    index = min(len(values) - 1, max(0, math.ceil(len(values) * ratio) - 1))
    return sorted(values)[index]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a lightweight concurrent smoke benchmark for ai-prod public APIs.")
    parser.add_argument("--base-url", default="http://127.0.0.1:26005")
    parser.add_argument("--path", default="/api/v1/health")
    parser.add_argument("--method", default="GET", choices=["GET", "POST"])
    parser.add_argument("--body-json", default="")
    parser.add_argument("--requests", type=int, default=32)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--min-success-rate", type=float, default=1.0)
    parser.add_argument("--max-p95-ms", type=int, default=5000)
    args = parser.parse_args()

    if args.requests < 1 or args.concurrency < 1:
        raise SystemExit("requests 和 concurrency 必须大于 0")

    body = json.loads(args.body_json) if args.body_json else None

    started_at = time.perf_counter()
    outcomes: list[tuple[bool, int | None, int, str]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = [
            executor.submit(
                perform_request,
                args.base_url,
                args.path,
                method=args.method,
                body=body,
                timeout=args.timeout,
            )
            for _ in range(args.requests)
        ]
        for future in concurrent.futures.as_completed(futures):
            outcomes.append(future.result())
    total_duration_s = max(time.perf_counter() - started_at, 0.001)

    latencies = [item[2] for item in outcomes]
    successful = [item for item in outcomes if item[0]]
    status_counter = Counter("transport_error" if item[1] is None else str(item[1]) for item in outcomes)
    success_rate = len(successful) / len(outcomes)

    summary = {
        "base_url": args.base_url,
        "path": args.path,
        "method": args.method,
        "requests": args.requests,
        "concurrency": args.concurrency,
        "success_rate": round(success_rate, 4),
        "throughput_rps": round(len(outcomes) / total_duration_s, 2),
        "latency_ms": {
            "min": min(latencies) if latencies else 0,
            "p50": percentile(latencies, 0.50),
            "p95": percentile(latencies, 0.95),
            "p99": percentile(latencies, 0.99),
            "max": max(latencies) if latencies else 0,
        },
        "status_codes": dict(status_counter),
    }

    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if success_rate < args.min_success_rate:
        print("ai-prod pressure smoke failed: success rate below threshold", file=sys.stderr)
        return 1
    if summary["latency_ms"]["p95"] > args.max_p95_ms:
        print("ai-prod pressure smoke failed: p95 latency above threshold", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
