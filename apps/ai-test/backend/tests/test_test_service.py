from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.config import get_settings, reset_settings_cache
from app.db.database import get_session_factory, reset_database_cache
from app.services.model_sync_service import write_model_catalog_snapshot
from app.services.report_service import export_test_report, get_test_report
from app.services.test_service import (
    TestCaseInputPayload,
    create_test_task,
    get_test_task,
    initialize_database,
    list_test_tasks,
)


class TestServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.host_root = Path(self.temp_dir.name)
        (self.host_root / "data").mkdir()
        (self.host_root / "datasets").mkdir()
        (self.host_root / "exports").mkdir()
        os.environ["AI_CAP_HOST_ROOT"] = str(self.host_root)
        reset_settings_cache()
        reset_database_cache()
        initialize_database()
        write_model_catalog_snapshot(
            snapshot_path=get_settings().model_catalog_snapshot_path,
            models=[
                {
                    "capability_name": "ocr_review",
                    "model_version": "v1.0.0",
                    "source_training_task_id": 1,
                    "artifact_path": str((self.host_root / "models" / "ocr_review" / "v1.0.0").resolve()),
                    "manifest_path": str((self.host_root / "models" / "ocr_review" / "v1.0.0" / "manifest.json").resolve()),
                    "backend_type": "cpu",
                    "checksum": "abc123",
                    "status": "ready",
                }
            ],
            capabilities=[
                {
                    "capability_name": "ocr_review",
                    "display_name": "OCR Review",
                    "dataset_path": "ocr_review",
                    "dataset_status": "ready",
                    "source": "manual",
                }
            ],
        )
        (self.host_root / "datasets" / "ocr_review").mkdir()
        (self.host_root / "datasets" / "ocr_review" / "sample_1.jpg").write_text("data", encoding="utf-8")
        (self.host_root / "datasets" / "ocr_review" / "sample_2.pdf").write_text("pdf", encoding="utf-8")

    def tearDown(self) -> None:
        reset_database_cache()
        reset_settings_cache()
        os.environ.pop("AI_CAP_HOST_ROOT", None)
        self.temp_dir.cleanup()

    def test_create_single_test_task_generates_report(self) -> None:
        with get_session_factory()() as session:
            payload = create_test_task(
                session=session,
                model_catalog_snapshot_path=get_settings().model_catalog_snapshot_path,
                ai_train_api_base_url=get_settings().ai_train_api_base_url,
                datasets_root=get_settings().datasets_root,
                test_reports_root=get_settings().test_reports_root,
                task_type="single",
                capability_name="ocr_review",
                model_version="v1.0.0",
                requested_backend="auto",
                timeout_seconds=10,
                cases=[
                    TestCaseInputPayload(
                        case_name="单测样例",
                        input_path="ocr_review/sample_1.jpg",
                        expected_output=None,
                    )
                ],
            )
            report = get_test_report(session, int(payload["report_id"]))
            delivery_report = get_test_report(session, int(payload["report_id"]), template_type="delivery")

        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["total_cases"], 1)
        self.assertTrue(Path(report["json_report_path"]).is_file())
        self.assertEqual(report["active_template_type"], "research")
        self.assertEqual(delivery_report["active_template_type"], "delivery")
        self.assertIn("report_templates", report["summary"])
        self.assertIn("template_summary", delivery_report["summary"])

    def test_batch_test_gpu_request_falls_back_to_cpu(self) -> None:
        with get_session_factory()() as session:
            payload = create_test_task(
                session=session,
                model_catalog_snapshot_path=get_settings().model_catalog_snapshot_path,
                ai_train_api_base_url=get_settings().ai_train_api_base_url,
                datasets_root=get_settings().datasets_root,
                test_reports_root=get_settings().test_reports_root,
                task_type="batch",
                capability_name="ocr_review",
                model_version="v1.0.0",
                requested_backend="gpu",
                timeout_seconds=10,
                cases=[
                    TestCaseInputPayload(case_name="样例1", input_path="ocr_review/sample_1.jpg", expected_output=None),
                    TestCaseInputPayload(case_name="样例2", input_path="ocr_review/sample_2.pdf", expected_output="positive"),
                ],
            )
            items = list_test_tasks(session)
            detail = get_test_task(session, int(payload["task_id"]))

        self.assertEqual(payload["execution_backend"], "cpu")
        self.assertEqual(len(items), 1)
        self.assertEqual(len(detail["cases"]), 2)

    def test_export_report_copies_to_exports(self) -> None:
        with get_session_factory()() as session:
            payload = create_test_task(
                session=session,
                model_catalog_snapshot_path=get_settings().model_catalog_snapshot_path,
                ai_train_api_base_url=get_settings().ai_train_api_base_url,
                datasets_root=get_settings().datasets_root,
                test_reports_root=get_settings().test_reports_root,
                task_type="single",
                capability_name="ocr_review",
                model_version="v1.0.0",
                requested_backend="cpu",
                timeout_seconds=10,
                cases=[
                    TestCaseInputPayload(case_name="导出样例", input_path="ocr_review/sample_1.jpg", expected_output=None)
                ],
            )
            exported_path = export_test_report(
                session,
                get_settings().exports_root,
                int(payload["report_id"]),
                "json",
                template_type="delivery",
            )

        exported_summary = Path(exported_path).read_text(encoding="utf-8")
        self.assertTrue(Path(exported_path).is_file())
        self.assertIn('"active_template_type": "delivery"', exported_summary)
