from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.config import get_settings, reset_settings_cache
from app.db.database import get_session_factory, reset_database_cache
from app.main import create_app
from app.services.acceptance_service import AcceptanceTaskCreatePayload, create_acceptance_task, get_acceptance_task, list_acceptance_tasks
from app.services.test_service import initialize_database


def _mock_subprocess_run(command: list[str], *, capture_output: bool, text: bool, check: bool, timeout: int):
    script_name = Path(command[1]).name
    if script_name == "acceptance_check.py":
        payload = {
            "base_url": "http://127.0.0.1:26004",
            "results": [
                {"name": "health", "passed": True, "status_code": 200, "latency_ms": 15, "detail": "ok"},
                {"name": "infer", "passed": True, "status_code": 200, "latency_ms": 80, "detail": "ok"},
            ],
        }
    elif script_name == "pressure_smoke.py":
        payload = {
            "base_url": "http://127.0.0.1:26004",
            "path": "/api/v1/infer/ocr_review",
            "success_rate": 1.0,
            "latency_ms": {"min": 20, "p50": 60, "p95": 120, "p99": 150, "max": 180},
            "status_codes": {"200": 32},
        }
    else:
        raise AssertionError(f"unexpected script: {script_name}")

    return __import__("subprocess").CompletedProcess(
        args=command,
        returncode=0,
        stdout=json.dumps(payload, ensure_ascii=False),
        stderr="",
    )


class AcceptanceServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.host_root = Path(self.temp_dir.name)
        (self.host_root / "data").mkdir()
        (self.host_root / "exports").mkdir()
        os.environ["AI_CAP_HOST_ROOT"] = str(self.host_root)
        reset_settings_cache()
        reset_database_cache()
        initialize_database()

    def tearDown(self) -> None:
        reset_database_cache()
        reset_settings_cache()
        os.environ.pop("AI_CAP_HOST_ROOT", None)
        self.temp_dir.cleanup()

    @patch("app.services.acceptance_service.subprocess.run", side_effect=_mock_subprocess_run)
    def test_create_acceptance_task_generates_report(self, _mock_run) -> None:
        with get_session_factory()() as session:
            payload = create_acceptance_task(
                session=session,
                test_reports_root=get_settings().test_reports_root,
                payload=AcceptanceTaskCreatePayload(
                    image_uri="registry.local/ai-prod:test",
                    target_base_url="http://127.0.0.1:26004",
                    capability_name="ocr_review",
                    input_type="json",
                    infer_payload='{"image":"demo"}',
                    prefer_device="auto",
                    acceptance_timeout_seconds=10,
                    run_admin_checks=False,
                    pressure_requests=32,
                    pressure_concurrency=8,
                    pressure_timeout_seconds=10,
                    pressure_min_success_rate=0.95,
                    pressure_max_p95_ms=5000,
                ),
            )
            items = list_acceptance_tasks(session)
            detail = get_acceptance_task(session, int(payload["acceptance_task_id"]))

        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["passed_cases"], 2)
        self.assertEqual(len(items), 1)
        self.assertEqual(detail["script_results"][0]["case_name"], "acceptance_check")
        self.assertTrue((get_settings().test_reports_root / f"task_{payload['task_id']}" / "report.json").is_file())

    @patch("app.services.acceptance_service.subprocess.run", side_effect=_mock_subprocess_run)
    def test_acceptance_routes(self, _mock_run) -> None:
        client = TestClient(create_app())
        response = client.post(
            "/api/v1/acceptance-tasks",
            json={
                "image_uri": "registry.local/ai-prod:test",
                "target_base_url": "http://127.0.0.1:26004",
                "capability_name": "ocr_review",
                "input_type": "json",
                "infer_payload": '{"image":"demo"}',
                "prefer_device": "auto",
                "acceptance_timeout_seconds": 10,
                "pressure_requests": 16,
                "pressure_concurrency": 4,
                "pressure_timeout_seconds": 10,
                "pressure_min_success_rate": 0.9,
                "pressure_max_p95_ms": 3000,
            },
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["image_uri"], "registry.local/ai-prod:test")

        list_response = client.get("/api/v1/acceptance-tasks")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()["items"]), 1)

        detail_response = client.get(f"/api/v1/acceptance-tasks/{payload['acceptance_task_id']}")
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(len(detail_response.json()["script_results"]), 2)
