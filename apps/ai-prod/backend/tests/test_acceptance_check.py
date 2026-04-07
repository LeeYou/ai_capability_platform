from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest


_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "acceptance_check.py"
_SPEC = spec_from_file_location("ai_prod_acceptance_check", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
acceptance_check = module_from_spec(_SPEC)
sys.modules[_SPEC.name] = acceptance_check
_SPEC.loader.exec_module(acceptance_check)


class AcceptanceCheckTestCase(unittest.TestCase):
    def _build_args(self, **overrides: object) -> SimpleNamespace:
        payload = {
            "base_url": "http://127.0.0.1:26004",
            "timeout": 10.0,
            "health_max_ms": 1000,
            "capabilities_max_ms": 1000,
            "license_max_ms": 1000,
            "catalog_max_ms": 1000,
            "metrics_max_ms": 1000,
            "infer_max_ms": 5000,
            "capability": "",
            "infer_payload": '{"image":"demo"}',
            "input_type": "json",
            "prefer_device": "auto",
            "run_admin_checks": False,
            "run_transition_checks": False,
        }
        payload.update(overrides)
        return SimpleNamespace(**payload)

    def test_run_acceptance_passes_basic_public_checks(self) -> None:
        responses = {
            ("GET", "/api/v1/health"): (200, {"status": "ok", "runtime_revision_id": 1}, 10),
            ("GET", "/api/v1/capabilities"): (200, {"items": [{"capability_name": "face_detect"}]}, 12),
            (
                "GET",
                "/api/v1/license/status",
            ): (
                200,
                {
                    "valid": True,
                    "reason": "ok",
                    "result": "passed",
                    "code": "license_valid",
                    "stage": "success",
                    "details": {},
                    "diagnostics_version": 1,
                },
                11,
            ),
            (
                "GET",
                "/api/v1/admin/catalog",
            ): (
                200,
                {
                    "items": [
                        {
                            "capability_name": "face_detect",
                            "max_batch_size": 4,
                            "queue_wait_timeout_ms": 200,
                            "configured_max_pending_request_count": 8,
                            "pending_request_count": 0,
                            "queue_timeout_count": 0,
                            "admission_checklist": {"ready": True},
                        }
                    ]
                },
                13,
            ),
            (
                "GET",
                "/api/v1/admin/metrics",
            ): (
                200,
                {
                    "endpoint_metrics": {},
                    "pool_summary": {"pending_request_count": 0},
                    "request_summary": {"queued_request_count": 0},
                },
                15,
            ),
            ("GET", "/api/v1/admin/revisions"): (404, {"message": "not found"}, 9),
            (
                "POST",
                "/api/v1/infer/face_detect",
            ): (
                200,
                {"capability_name": "face_detect", "runtime_revision_id": 1},
                30,
            ),
        }

        def requester(base_url: str, path: str, *, method: str = "GET", body=None, timeout: float = 10.0):
            self.assertEqual(base_url, "http://127.0.0.1:26004")
            self.assertIsNotNone(timeout)
            return responses[(method, path)]

        summary = acceptance_check.run_acceptance(self._build_args(), requester=requester)
        self.assertTrue(all(item["passed"] for item in summary["results"]))

    def test_run_acceptance_covers_reload_and_rollback_chain(self) -> None:
        responses = {
            ("GET", "/api/v1/health"): [
                (200, {"status": "ok", "runtime_revision_id": 1}, 10),
                (200, {"status": "ok", "runtime_revision_id": 2}, 10),
                (200, {"status": "ok", "runtime_revision_id": 3}, 10),
            ],
            ("GET", "/api/v1/capabilities"): [
                (200, {"items": [{"capability_name": "face_detect"}]}, 10),
            ],
            (
                "GET",
                "/api/v1/license/status",
            ): [
                (
                    200,
                    {
                        "valid": True,
                        "reason": "ok",
                        "result": "passed",
                        "code": "license_valid",
                        "stage": "success",
                        "details": {},
                        "diagnostics_version": 1,
                    },
                    10,
                )
            ],
            (
                "GET",
                "/api/v1/admin/catalog",
            ): [
                (
                    200,
                    {
                        "items": [
                            {
                                "capability_name": "face_detect",
                                "max_batch_size": 4,
                                "queue_wait_timeout_ms": 200,
                                "configured_max_pending_request_count": 8,
                                "pending_request_count": 0,
                                "queue_timeout_count": 0,
                                "admission_checklist": {"ready": True},
                            }
                        ]
                    },
                    10,
                ),
                (
                    200,
                    {
                        "items": [
                            {
                                "capability_name": "face_detect",
                                "max_batch_size": 4,
                                "queue_wait_timeout_ms": 200,
                                "configured_max_pending_request_count": 8,
                                "pending_request_count": 0,
                                "queue_timeout_count": 0,
                                "admission_checklist": {"ready": True},
                            }
                        ]
                    },
                    10,
                ),
                (
                    200,
                    {
                        "items": [
                            {
                                "capability_name": "face_detect",
                                "max_batch_size": 4,
                                "queue_wait_timeout_ms": 200,
                                "configured_max_pending_request_count": 8,
                                "pending_request_count": 0,
                                "queue_timeout_count": 0,
                                "admission_checklist": {"ready": True},
                            }
                        ]
                    },
                    10,
                ),
            ],
            (
                "GET",
                "/api/v1/admin/metrics",
            ): [
                (
                    200,
                    {
                        "endpoint_metrics": {},
                        "pool_summary": {"pending_request_count": 0},
                        "request_summary": {"queued_request_count": 0},
                    },
                    10,
                )
            ],
            ("GET", "/api/v1/admin/revisions"): [(404, {"message": "not found"}, 10)],
            (
                "POST",
                "/api/v1/infer/face_detect",
            ): [
                (200, {"capability_name": "face_detect", "runtime_revision_id": 1}, 20),
                (200, {"capability_name": "face_detect", "runtime_revision_id": 2}, 20),
                (200, {"capability_name": "face_detect", "runtime_revision_id": 3}, 20),
            ],
            (
                "POST",
                "/api/v1/admin/reload",
            ): [
                (200, {"revision": {"revision_id": 2, "action": "reload"}, "active_capability_count": 1}, 50),
            ],
            (
                "POST",
                "/api/v1/admin/rollback",
            ): [
                (
                    200,
                    {
                        "revision": {
                            "revision_id": 3,
                            "action": "rollback",
                            "rollback_of_revision_id": 1,
                        },
                        "active_capability_count": 1,
                    },
                    50,
                ),
            ],
        }

        def requester(base_url: str, path: str, *, method: str = "GET", body=None, timeout: float = 10.0):
            queue = responses[(method, path)]
            result = queue.pop(0)
            if method == "POST" and path == "/api/v1/admin/rollback":
                self.assertEqual(body, {"target_revision_id": 1})
            return result

        summary = acceptance_check.run_acceptance(
            self._build_args(run_transition_checks=True),
            requester=requester,
        )
        result_by_name = {item["name"]: item for item in summary["results"]}
        self.assertTrue(result_by_name["reload"]["passed"])
        self.assertTrue(result_by_name["rollback"]["passed"])
        self.assertTrue(result_by_name["infer_after_reload"]["passed"])
        self.assertTrue(result_by_name["infer_after_rollback"]["passed"])


if __name__ == "__main__":
    unittest.main()
