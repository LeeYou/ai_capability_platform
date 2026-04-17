from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.config import get_settings, reset_settings_cache
from app.db.database import get_session_factory, reset_database_cache
from app.services.capability_adapters import register_test_adapter
from app.services.model_sync_service import write_model_catalog_snapshot
from app.services.report_service import export_test_report, get_test_report
from app.services.test_service import (
    TASK_TYPE_OUTPUT_SCHEMAS,
    TASK_TYPE_REGRESSION_TEMPLATES,
    TestCaseInputPayload,
    create_template_regression_task,
    create_test_task,
    get_capability_test_template,
    get_test_task,
    initialize_database,
    list_test_tasks,
    _extract_task_type,
    _validate_expected_output,
    _simulate_case_execution,
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

        # TT12/TT13：创建带 manifest 的模型包（ocr 任务类型）
        ocr_model_dir = self.host_root / "models" / "ocr_review" / "v1.0.0"
        ocr_model_dir.mkdir(parents=True)
        (ocr_model_dir / "manifest.json").write_text(
            json.dumps({
                "capability_name": "ocr_review",
                "model_version": "v1.0.0",
                "task_type": "ocr",
                "source_train_task_id": 5,
                "backend_type": "cpu",
                "status": "ready",
            }, ensure_ascii=False),
            encoding="utf-8",
        )

        # TT14：创建带 manifest 的 detection 类型模型包
        detect_model_dir = self.host_root / "models" / "face_detect" / "v1_0_0"
        detect_model_dir.mkdir(parents=True)
        (detect_model_dir / "manifest.json").write_text(
            json.dumps({
                "capability_name": "face_detect",
                "model_version": "v1_0_0",
                "task_type": "detection",
                "source_train_task_id": 42,
                "backend_type": "onnxruntime",
                "status": "ready",
            }, ensure_ascii=False),
            encoding="utf-8",
        )

        write_model_catalog_snapshot(
            snapshot_path=get_settings().model_catalog_snapshot_path,
            models=[
                {
                    "capability_name": "ocr_review",
                    "model_version": "v1.0.0",
                    "source_training_task_id": 5,
                    "artifact_path": str(ocr_model_dir.resolve()),
                    "manifest_path": str((ocr_model_dir / "manifest.json").resolve()),
                    "backend_type": "cpu",
                    "checksum": "abc123",
                    "status": "ready",
                },
                {
                    "capability_name": "face_detect",
                    "model_version": "v1_0_0",
                    "source_training_task_id": 42,
                    "artifact_path": str(detect_model_dir.resolve()),
                    "manifest_path": str((detect_model_dir / "manifest.json").resolve()),
                    "backend_type": "onnxruntime",
                    "checksum": "def456",
                    "status": "ready",
                },
            ],
            capabilities=[
                {
                    "capability_name": "ocr_review",
                    "display_name": "OCR Review",
                    "dataset_path": "ocr_review",
                    "dataset_status": "ready",
                    "source": "manual",
                },
                {
                    "capability_name": "face_detect",
                    "display_name": "Face Detect",
                    "dataset_path": "face_detect",
                    "dataset_status": "ready",
                    "source": "manual",
                },
            ],
        )
        (self.host_root / "datasets" / "ocr_review").mkdir()
        (self.host_root / "datasets" / "ocr_review" / "sample_1.jpg").write_text("data", encoding="utf-8")
        (self.host_root / "datasets" / "ocr_review" / "sample_2.pdf").write_text("pdf", encoding="utf-8")
        (self.host_root / "datasets" / "face_detect").mkdir()
        (self.host_root / "datasets" / "face_detect" / "sample.jpg").write_text("img", encoding="utf-8")

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
        self.assertEqual(payload["execution_mode"], "simulated")
        self.assertIsNotNone(payload["execution_risk"])
        self.assertEqual(report["execution_mode"], "simulated")
        # TT13：验证报告 summary 中包含 evidence_chain
        self.assertIn("evidence_chain", report["summary"])
        self.assertIsNotNone(report["summary"]["evidence_chain"])
        evidence = report["summary"]["evidence_chain"]
        self.assertIn("model", evidence)
        self.assertEqual(evidence["model"]["capability_name"], "ocr_review")
        self.assertEqual(evidence["execution"]["execution_mode"], "simulated")
        # TT12：验证 task_type 从 manifest 中正确提取（ocr）
        self.assertEqual(evidence["model"]["task_type"], "ocr")
        self.assertEqual(evidence["model"]["source_train_task_id"], 5)

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

    def test_real_adapter_task_marks_execution_mode_real(self) -> None:
        adapter_model_dir = self.host_root / "models" / "adapter_demo" / "v2"
        adapter_model_dir.mkdir(parents=True)
        (adapter_model_dir / "manifest.json").write_text(
            json.dumps({
                "capability_name": "adapter_demo",
                "model_version": "v2",
                "task_type": "classification",
                "source_train_task_id": 8,
                "backend_type": "cpu",
                "status": "ready",
            }, ensure_ascii=False),
            encoding="utf-8",
        )
        write_model_catalog_snapshot(
            snapshot_path=get_settings().model_catalog_snapshot_path,
            models=[
                {
                    "capability_name": "ocr_review",
                    "model_version": "v1.0.0",
                    "source_training_task_id": 5,
                    "artifact_path": str((self.host_root / "models" / "ocr_review" / "v1.0.0").resolve()),
                    "manifest_path": str((self.host_root / "models" / "ocr_review" / "v1.0.0" / "manifest.json").resolve()),
                    "backend_type": "cpu",
                    "checksum": "abc123",
                    "status": "ready",
                },
                {
                    "capability_name": "face_detect",
                    "model_version": "v1_0_0",
                    "source_training_task_id": 42,
                    "artifact_path": str((self.host_root / "models" / "face_detect" / "v1_0_0").resolve()),
                    "manifest_path": str((self.host_root / "models" / "face_detect" / "v1_0_0" / "manifest.json").resolve()),
                    "backend_type": "onnxruntime",
                    "checksum": "def456",
                    "status": "ready",
                },
                {
                    "capability_name": "adapter_demo",
                    "model_version": "v2",
                    "source_training_task_id": 8,
                    "artifact_path": str(adapter_model_dir.resolve()),
                    "manifest_path": str((adapter_model_dir / "manifest.json").resolve()),
                    "backend_type": "cpu",
                    "checksum": "ghi789",
                    "status": "ready",
                },
            ],
            capabilities=[
                {
                    "capability_name": "ocr_review",
                    "display_name": "OCR Review",
                    "dataset_path": "ocr_review",
                    "dataset_status": "ready",
                    "source": "manual",
                },
                {
                    "capability_name": "face_detect",
                    "display_name": "Face Detect",
                    "dataset_path": "face_detect",
                    "dataset_status": "ready",
                    "source": "manual",
                },
                {
                    "capability_name": "adapter_demo",
                    "display_name": "Adapter Demo",
                    "dataset_path": "adapter_demo",
                    "dataset_status": "ready",
                    "source": "manual",
                },
            ],
        )
        (self.host_root / "datasets" / "adapter_demo").mkdir()
        (self.host_root / "datasets" / "adapter_demo" / "sample.txt").write_text("demo", encoding="utf-8")

        class DemoTestAdapter:
            def infer(self, **kwargs):
                return {
                    "actual_output": "positive",
                    "score": 0.99,
                    "raw_output": {"label": "positive", "score": 0.99},
                    "duration_ms": 12,
                }

        register_test_adapter("adapter_demo", DemoTestAdapter())

        with get_session_factory()() as session:
            payload = create_test_task(
                session=session,
                model_catalog_snapshot_path=get_settings().model_catalog_snapshot_path,
                ai_train_api_base_url=get_settings().ai_train_api_base_url,
                datasets_root=get_settings().datasets_root,
                test_reports_root=get_settings().test_reports_root,
                task_type="single",
                capability_name="adapter_demo",
                model_version="v2",
                requested_backend="cpu",
                timeout_seconds=10,
                cases=[
                    TestCaseInputPayload(
                        case_name="真实推理样例",
                        input_path="adapter_demo/sample.txt",
                        expected_output="positive",
                    )
                ],
            )
            report = get_test_report(session, int(payload["report_id"]))

        self.assertEqual(payload["execution_mode"], "real")
        self.assertIsNone(payload["execution_risk"])
        self.assertEqual(report["execution_mode"], "real")
        self.assertEqual(report["summary"]["execution_mode"], "real")

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


class TT12TT13TT14UnitTestCase(unittest.TestCase):
    """TT12/TT13/TT14 单元测试。"""

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

        detect_model_dir = self.host_root / "models" / "face_detect" / "v1_0_0"
        detect_model_dir.mkdir(parents=True)
        (detect_model_dir / "manifest.json").write_text(
            json.dumps({"capability_name": "face_detect", "model_version": "v1_0_0", "task_type": "detection", "source_train_task_id": 42}),
            encoding="utf-8",
        )
        write_model_catalog_snapshot(
            snapshot_path=get_settings().model_catalog_snapshot_path,
            models=[{
                "capability_name": "face_detect", "model_version": "v1_0_0",
                "artifact_path": str(detect_model_dir.resolve()),
                "manifest_path": str((detect_model_dir / "manifest.json").resolve()),
                "backend_type": "onnxruntime", "checksum": "xyz", "status": "ready",
            }],
            capabilities=[{"capability_name": "face_detect", "display_name": "Face Detect", "dataset_path": "face_detect", "dataset_status": "ready", "source": "manual"}],
        )
        (self.host_root / "datasets" / "face_detect").mkdir()
        (self.host_root / "datasets" / "face_detect" / "sample.jpg").write_text("img", encoding="utf-8")

    def tearDown(self) -> None:
        reset_database_cache()
        reset_settings_cache()
        os.environ.pop("AI_CAP_HOST_ROOT", None)
        self.temp_dir.cleanup()

    def test_tt12_simulate_detection_output_has_objects(self) -> None:
        result = _simulate_case_execution("face_detect", "v1_0_0", "CPUExecutionProvider", "test", "sample.jpg", "detection")
        self.assertIn("objects", result["raw_output"])
        self.assertEqual(result["task_type"], "detection")

    def test_tt12_simulate_ocr_output_has_text(self) -> None:
        result = _simulate_case_execution("cap", "v1", "CPUExecutionProvider", "test", "img.jpg", "ocr")
        self.assertIn("text", result["raw_output"])

    def test_tt12_validate_expected_output_classification_label(self) -> None:
        check = _validate_expected_output("positive", "classification")
        self.assertEqual(check["status"], "label_string")

    def test_tt12_validate_expected_output_schema_mismatch(self) -> None:
        check = _validate_expected_output('{"score": 0.9}', "detection")
        self.assertEqual(check["status"], "schema_mismatch")

    def test_tt12_extract_task_type_from_manifest(self) -> None:
        model = {"capability_name": "face_detect", "model_version": "v1_0_0"}
        manifest = {"task_type": "detection"}
        result = _extract_task_type(model, manifest)
        self.assertEqual(result, "detection")

    def test_tt13_task_detail_has_evidence_chain(self) -> None:
        with get_session_factory()() as session:
            payload = create_test_task(
                session=session,
                model_catalog_snapshot_path=get_settings().model_catalog_snapshot_path,
                ai_train_api_base_url=get_settings().ai_train_api_base_url,
                datasets_root=get_settings().datasets_root,
                test_reports_root=get_settings().test_reports_root,
                task_type="single", capability_name="face_detect", model_version="v1_0_0",
                requested_backend="auto", timeout_seconds=10,
                cases=[TestCaseInputPayload(case_name="smoke", input_path="face_detect/sample.jpg", expected_output=None)],
            )
        self.assertIn("evidence_chain", payload)
        evidence = payload["evidence_chain"]
        self.assertIsNotNone(evidence)
        self.assertEqual(evidence["model"]["capability_name"], "face_detect")
        self.assertEqual(evidence["model"]["task_type"], "detection")
        self.assertEqual(evidence["model"]["source_train_task_id"], 42)
        self.assertIn("plugin", evidence)
        self.assertIn("license", evidence)

    def test_tt14_get_capability_test_template(self) -> None:
        for task_type in ("classification", "detection", "ocr", "structured_extraction"):
            tmpl = get_capability_test_template(task_type)
            self.assertEqual(tmpl["task_type"], task_type)
            self.assertIn("template_cases", tmpl)
            self.assertGreaterEqual(len(tmpl["template_cases"]), 1)
            self.assertIn("output_schema", tmpl)

    def test_tt14_create_template_regression_task(self) -> None:
        with get_session_factory()() as session:
            payload = create_template_regression_task(
                session=session,
                model_catalog_snapshot_path=get_settings().model_catalog_snapshot_path,
                ai_train_api_base_url=get_settings().ai_train_api_base_url,
                datasets_root=get_settings().datasets_root,
                test_reports_root=get_settings().test_reports_root,
                capability_name="face_detect", model_version="v1_0_0",
                sample_input_path="face_detect/sample.jpg",
            )
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["task_type"], "batch")
        self.assertGreaterEqual(payload["total_cases"], 2)
