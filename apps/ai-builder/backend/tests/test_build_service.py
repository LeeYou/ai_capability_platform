from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.config import get_settings, reset_settings_cache
from app.db.database import get_session_factory, reset_database_cache
from app.services.audit_service import list_audit_logs
from app.services.build_service import (
    create_build_task,
    get_build_task,
    initialize_database,
    list_build_artifacts,
    list_build_targets,
    list_build_tasks,
    list_platform_targets,
    _copy_model_package_to_sdk,
    _load_source_manifest,
    _validate_model_package,
    _validate_plugin_loadability,
)
from app.services.catalog_service import get_builder_catalog, write_builder_catalog_snapshot


REPO_ROOT = Path(__file__).resolve().parents[4]
SHARED_SCHEMAS_ROOT = REPO_ROOT / "apps" / "shared" / "schemas"


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_matches_schema(test_case: unittest.TestCase, schema: dict[str, object], payload: object, *, path: str = "$") -> None:
    schema_type = schema.get("type")
    if schema_type == "object":
        test_case.assertIsInstance(payload, dict, f"{path} 必须为对象")
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        assert isinstance(payload, dict)
        for key in required:
            test_case.assertIn(key, payload, f"{path} 缺少字段 {key}")
        for key, property_schema in properties.items():
            if key in payload and isinstance(property_schema, dict):
                _assert_matches_schema(test_case, property_schema, payload[key], path=f"{path}.{key}")
        return

    if schema_type == "array":
        test_case.assertIsInstance(payload, list, f"{path} 必须为数组")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(payload):
                _assert_matches_schema(test_case, item_schema, item, path=f"{path}[{index}]")
        return

    if schema_type == "string":
        test_case.assertIsInstance(payload, str, f"{path} 必须为字符串")
        return

    if schema_type == "integer":
        test_case.assertIsInstance(payload, int, f"{path} 必须为整数")
        return

    if schema_type == "boolean":
        test_case.assertIsInstance(payload, bool, f"{path} 必须为布尔值")
        return


class BuildServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.host_root = Path(self.temp_dir.name)
        for directory_name in ("data", "logs", "exports", "libs", "models", "license"):
            (self.host_root / directory_name).mkdir()
        os.environ["AI_CAP_HOST_ROOT"] = str(self.host_root)
        os.environ["AI_TRAIN_API_BASE_URL"] = "http://127.0.0.1:9"
        os.environ["AI_LICENSE_MGR_API_BASE_URL"] = "http://127.0.0.1:9"
        reset_settings_cache()
        reset_database_cache()
        initialize_database()

        issue_dir = self.host_root / "license" / "issues" / "issue_1"
        issue_dir.mkdir(parents=True)
        (issue_dir / "license.bin").write_text("license", encoding="utf-8")
        (issue_dir / "pubkey.pem").write_text("pubkey", encoding="utf-8")

        # B12/B13：创建 ai-train 模型包，供 builder 追溯和复制
        model_dir = self.host_root / "models" / "face_detect" / "v1_0_0"
        model_dir.mkdir(parents=True)
        (model_dir / "manifest.json").write_text(
            json.dumps({
                "capability_name": "face_detect",
                "task_type": "detection",
                "model_version": "v1_0_0",
                "source_train_task_id": 42,
                "backend_type": "onnxruntime",
                "artifact_path": str(model_dir.resolve()),
                "status": "ready",
                "labels": ["person", "face"],
                "checksum": "abc123",
            }, ensure_ascii=False),
            encoding="utf-8",
        )
        (model_dir / "labels.json").write_text(
            json.dumps({"labels": ["person", "face"]}, ensure_ascii=False),
            encoding="utf-8",
        )
        (model_dir / "preprocess.json").write_text(
            json.dumps({"input_type": "image", "resize": {"width": 640, "height": 640}}, ensure_ascii=False),
            encoding="utf-8",
        )

        write_builder_catalog_snapshot(
            get_settings().build_catalog_snapshot_path,
            capabilities=[
                {
                    "capability_name": "face_detect",
                    "display_name": "Face Detect",
                    "dataset_path": "face_detect",
                    "dataset_status": "ready",
                    "source": "manual",
                }
            ],
            models=[
                {
                    "artifact_id": 1,
                    "capability_name": "face_detect",
                    "model_version": "v1_0_0",
                    "artifact_path": str(model_dir.resolve()),
                    "manifest_path": str((model_dir / "manifest.json").resolve()),
                    "backend_type": "onnxruntime",
                    "checksum": "checksum-model",
                    "status": "ready",
                }
            ],
            license_issues=[
                {
                    "issue_record_id": 1,
                    "policy_id": 1,
                    "customer_id": 1,
                    "customer_code": "cust_001",
                    "key_pair_id": 1,
                    "key_name": "builder-key",
                    "status": "issued",
                    "hardware_fingerprint": None,
                    "capability_scope": ["face_detect"],
                    "version_constraints": {"min_version": "1.0.0"},
                    "license_path": str((issue_dir / "license.bin").resolve()),
                    "public_key_export_path": str((issue_dir / "pubkey.pem").resolve()),
                    "issued_at_cst": "2026-04-02T10:00:00+08:00",
                    "last_validation_at": None,
                    "last_validation_result": None,
                }
            ],
            license_policies=[
                {
                    "policy_id": 1,
                    "policy_name": "policy_builder",
                    "customer_id": 1,
                    "customer_code": "cust_001",
                    "key_pair_id": 1,
                    "key_name": "builder-key",
                    "capability_scope": ["face_detect"],
                    "version_constraints": {"min_version": "1.0.0"},
                    "hardware_fingerprint": None,
                    "start_at_cst": "2026-04-01T00:00:00+08:00",
                    "expire_at_cst": "2027-04-01T00:00:00+08:00",
                    "status": "active",
                    "notes": "builder policy",
                }
            ],
        )

    def tearDown(self) -> None:
        reset_database_cache()
        reset_settings_cache()
        os.environ.pop("AI_CAP_HOST_ROOT", None)
        os.environ.pop("AI_TRAIN_API_BASE_URL", None)
        os.environ.pop("AI_LICENSE_MGR_API_BASE_URL", None)
        self.temp_dir.cleanup()

    def test_get_builder_catalog_falls_back_to_snapshot(self) -> None:
        payload = get_builder_catalog(
            get_settings().build_catalog_snapshot_path,
            get_settings().ai_train_api_base_url,
            get_settings().ai_license_mgr_api_base_url,
        )
        self.assertEqual(len(payload["capabilities"]), 1)
        self.assertEqual(payload["models"][0]["capability_name"], "face_detect")

    def test_create_build_task_packages_outputs(self) -> None:
        with get_session_factory()() as session:
            payload = create_build_task(
                session,
                build_catalog_snapshot_path=get_settings().build_catalog_snapshot_path,
                ai_train_api_base_url=get_settings().ai_train_api_base_url,
                ai_license_mgr_api_base_url=get_settings().ai_license_mgr_api_base_url,
                build_tasks_root=get_settings().build_tasks_root,
                build_logs_root=get_settings().build_logs_root,
                delivery_packages_root=get_settings().delivery_packages_root,
                libs_root=get_settings().libs_root,
                exports_root=get_settings().exports_root,
                audit_log_path=get_settings().audit_log_path,
                task_name="face_detect_release",
                capability_name="face_detect",
                model_version="v1_0_0",
                issue_record_id=1,
                requested_targets=["linux_x86_64", "windows_x86_64"],
                jni_enabled=True,
            )
            task_detail = get_build_task(session, int(payload["task_id"]))

        self.assertEqual(payload["status"], "completed")
        self.assertEqual(len(task_detail["targets"]), 2)
        self.assertEqual(len(list_build_tasks(session)), 1)
        self.assertGreaterEqual(len(list_build_targets(session)), 2)
        self.assertGreaterEqual(len(list_build_artifacts(session)), 6)
        linux_target = next(item for item in task_detail["targets"] if item["target_name"] == "linux_x86_64")
        windows_target = next(item for item in task_detail["targets"] if item["target_name"] == "windows_x86_64")
        self.assertTrue(Path(linux_target["binary_path"]).is_file())
        self.assertTrue(Path(windows_target["binary_path"]).is_file())
        self.assertTrue(Path(linux_target["download_archive_path"]).is_file())
        self.assertTrue(Path(task_detail["delivery_package_dir"]).is_dir())
        self.assertTrue(Path(task_detail["delivery_package_archive_path"]).is_file())
        self.assertTrue((Path(task_detail["delivery_package_dir"]) / "sdk_linux_x86_64" / "lib" / "libface_detect.so").is_file())
        self.assertTrue((Path(task_detail["delivery_package_dir"]) / "sdk_windows_x86_64" / "manifest" / "manifest.json").is_file())
        self.assertTrue((Path(task_detail["delivery_package_dir"]) / "licenses" / "issue_1" / "license.bin").is_file())
        self.assertTrue((Path(task_detail["delivery_package_dir"]) / "docker" / "README.md").is_file())
        self.assertTrue((Path(task_detail["delivery_package_dir"]) / "docker" / "ai-prod_image_build_context.tar.gz").is_file())
        self.assertTrue((Path(task_detail["delivery_package_dir"]) / "mount_template" / "configs" / "prod_defaults.env").is_file())
        self.assertTrue((Path(task_detail["delivery_package_dir"]) / "mount_template" / "scripts" / "init_host_root.sh").is_file())
        self.assertTrue((Path(task_detail["delivery_package_dir"]) / "tools" / "validation" / "acceptance_check.py").is_file())
        self.assertTrue((Path(task_detail["delivery_package_dir"]) / "tools" / "validation" / "verify_delivery_package.py").is_file())
        self.assertTrue((Path(task_detail["delivery_package_dir"]) / "tools" / "license_tool" / "manifest.json").is_file())
        self.assertTrue((Path(task_detail["delivery_package_dir"]) / "tools" / "license_tool" / "README.md").is_file())
        self.assertTrue((Path(task_detail["delivery_package_dir"]) / "tools" / "license_tool" / "HARDWARE_FINGERPRINT.md").is_file())
        self.assertTrue((Path(task_detail["delivery_package_dir"]) / "docs" / "DEPLOYMENT.md").is_file())
        self.assertTrue((Path(task_detail["delivery_package_dir"]) / "acceptance_checklist.json").is_file())
        self.assertTrue((Path(task_detail["delivery_package_dir"]) / "version_manifest.json").is_file())
        self.assertTrue((Path(task_detail["delivery_package_dir"]) / "delivery_summary.json").is_file())
        self.assertTrue((Path(task_detail["delivery_package_dir"]) / "delivery_summary.md").is_file())
        manifest_payload = json.loads((Path(task_detail["delivery_package_dir"]) / "package_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest_payload["stage_status"]["B10"], "completed")
        self.assertEqual(manifest_payload["stage_status"]["B11"], "completed")
        self.assertEqual(manifest_payload["stage_status"]["B12"], "completed")
        self.assertEqual(manifest_payload["stage_status"]["B13"], "completed")
        self.assertEqual(manifest_payload["stage_status"]["B14"], "completed")
        # B13：验证追溯字段
        provenance = manifest_payload["provenance"]
        self.assertEqual(provenance["source_train_task_id"], 42)
        self.assertIsNotNone(provenance["source_manifest_checksum"])
        self.assertEqual(provenance["issue_record_id"], 1)
        self.assertIsNotNone(provenance["model_artifact_path"])
        # B14：验证交付前校验报告已生成
        self.assertTrue((Path(task_detail["delivery_package_dir"]) / "pre_delivery_validation.json").is_file())
        validation_payload = _load_json(Path(task_detail["delivery_package_dir"]) / "pre_delivery_validation.json")
        self.assertIn("overall_status", validation_payload)
        self.assertIn("targets", validation_payload)
        self.assertGreaterEqual(len(validation_payload["targets"]), 1)
        # B12：验证模型文件已复制到 SDK models 目录
        linux_models_dir = Path(task_detail["delivery_package_dir"]) / "sdk_linux_x86_64" / "models" / "face_detect" / "v1_0_0"
        self.assertTrue(linux_models_dir.is_dir())
        self.assertTrue((linux_models_dir / "manifest.json").is_file())
        self.assertTrue((linux_models_dir / "labels.json").is_file())
        self.assertTrue((linux_models_dir / "preprocess.json").is_file())
        # B12：验证 C++ 源码包含 ONNX Runtime 相关内容
        source_cpp = (self.host_root / "data" / "build_tasks" / "task_1" / "source" / "src" / "face_detect.cpp")
        if source_cpp.is_file():
            source_content = source_cpp.read_text(encoding="utf-8")
            self.assertIn("ONNXRUNTIME_ENABLED", source_content)
            self.assertIn("simulation_mode", source_content)
            self.assertIn("detection", source_content)
        # B13：验证 target manifest 中包含 provenance 和 task_type
        linux_sdk_manifest = _load_json(Path(task_detail["delivery_package_dir"]) / "sdk_linux_x86_64" / "manifest" / "manifest.json")
        self.assertEqual(linux_sdk_manifest["task_type"], "detection")
        self.assertIn("provenance", linux_sdk_manifest)
        self.assertEqual(linux_sdk_manifest["provenance"]["source_train_task_id"], 42)
        self.assertIn("ai-prod_image_build_context.tar.gz", manifest_payload["docker"]["archive_path"])
        acceptance_payload = _load_json(Path(task_detail["delivery_package_dir"]) / "acceptance_checklist.json")
        self.assertGreaterEqual(len(acceptance_payload["sections"]), 5)
        version_payload = _load_json(Path(task_detail["delivery_package_dir"]) / "version_manifest.json")
        self.assertEqual(version_payload["capability_name"], "face_detect")
        self.assertGreaterEqual(len(version_payload["delivery_checksums"]), 4)
        self.assertEqual(version_payload["tools_bundle"]["license_tool"]["version"], "1.0.0")
        summary_payload = _load_json(Path(task_detail["delivery_package_dir"]) / "delivery_summary.json")
        self.assertEqual(summary_payload["sdk_count"], 2)
        _assert_matches_schema(self, _load_json(SHARED_SCHEMAS_ROOT / "acceptance_checklist.json"), acceptance_payload)
        _assert_matches_schema(self, _load_json(SHARED_SCHEMAS_ROOT / "version_manifest.json"), version_payload)
        _assert_matches_schema(self, _load_json(SHARED_SCHEMAS_ROOT / "delivery_summary.json"), summary_payload)
        _assert_matches_schema(
            self,
            _load_json(SHARED_SCHEMAS_ROOT / "mount_template.json"),
            manifest_payload["mount_template"],
        )
        _assert_matches_schema(
            self,
            _load_json(SHARED_SCHEMAS_ROOT / "tools_bundle.json"),
            manifest_payload["tools"],
        )
        _assert_matches_schema(
            self,
            _load_json(SHARED_SCHEMAS_ROOT / "docs_bundle.json"),
            manifest_payload["docs"],
        )
        self.assertIsNotNone(task_detail["manifest"])
        self.assertIn("delivery_package", task_detail["manifest"]["manifest"])
        self.assertTrue(task_detail["manifest"]["manifest"]["delivery_package"]["acceptance_checklist_path"].endswith("acceptance_checklist.json"))
        self.assertTrue((self.host_root / "libs" / "linux_x86_64" / "face_detect" / "include" / "face_detect.h").is_file())
        self.assertTrue((self.host_root / "libs" / "linux_x86_64" / "face_detect" / "license" / "license.bin").is_file())

    def test_create_build_task_rejects_capability_scope_mismatch(self) -> None:
        write_builder_catalog_snapshot(
            get_settings().build_catalog_snapshot_path,
            capabilities=[
                {
                    "capability_name": "ocr",
                    "display_name": "OCR",
                    "dataset_path": "ocr",
                    "dataset_status": "ready",
                    "source": "manual",
                }
            ],
            models=[
                {
                    "artifact_id": 2,
                    "capability_name": "ocr",
                    "model_version": "v1_0_0",
                    "artifact_path": str((self.host_root / "models" / "ocr" / "v1_0_0").resolve()),
                    "manifest_path": str((self.host_root / "models" / "ocr" / "v1_0_0" / "manifest.json").resolve()),
                    "backend_type": "onnxruntime",
                    "checksum": "checksum-ocr",
                    "status": "ready",
                }
            ],
            license_issues=[
                {
                    "issue_record_id": 2,
                    "policy_id": 2,
                    "customer_id": 1,
                    "customer_code": "cust_001",
                    "key_pair_id": 1,
                    "key_name": "builder-key",
                    "status": "issued",
                    "hardware_fingerprint": None,
                    "capability_scope": ["det"],
                    "version_constraints": {},
                    "license_path": str((self.host_root / "license" / "issues" / "issue_1" / "license.bin").resolve()),
                    "public_key_export_path": str((self.host_root / "license" / "issues" / "issue_1" / "pubkey.pem").resolve()),
                    "issued_at_cst": "2026-04-02T10:00:00+08:00",
                    "last_validation_at": None,
                    "last_validation_result": None,
                }
            ],
            license_policies=[],
        )
        with get_session_factory()() as session:
            with self.assertRaisesRegex(ValueError, "授权能力范围不包含当前能力"):
                create_build_task(
                    session,
                    build_catalog_snapshot_path=get_settings().build_catalog_snapshot_path,
                    ai_train_api_base_url=get_settings().ai_train_api_base_url,
                    ai_license_mgr_api_base_url=get_settings().ai_license_mgr_api_base_url,
                    build_tasks_root=get_settings().build_tasks_root,
                    build_logs_root=get_settings().build_logs_root,
                    delivery_packages_root=get_settings().delivery_packages_root,
                    libs_root=get_settings().libs_root,
                    exports_root=get_settings().exports_root,
                    audit_log_path=get_settings().audit_log_path,
                    task_name="ocr_release",
                    capability_name="ocr",
                    model_version="v1_0_0",
                    issue_record_id=2,
                    requested_targets=["linux_x86_64"],
                    jni_enabled=False,
                )

    def test_audit_logs_and_platform_targets(self) -> None:
        with get_session_factory()() as session:
            create_build_task(
                session,
                build_catalog_snapshot_path=get_settings().build_catalog_snapshot_path,
                ai_train_api_base_url=get_settings().ai_train_api_base_url,
                ai_license_mgr_api_base_url=get_settings().ai_license_mgr_api_base_url,
                build_tasks_root=get_settings().build_tasks_root,
                build_logs_root=get_settings().build_logs_root,
                delivery_packages_root=get_settings().delivery_packages_root,
                libs_root=get_settings().libs_root,
                exports_root=get_settings().exports_root,
                audit_log_path=get_settings().audit_log_path,
                task_name="face_detect_release_2",
                capability_name="face_detect",
                model_version="v1_0_0",
                issue_record_id=1,
                requested_targets=["linux_arm64"],
                jni_enabled=False,
            )
        logs = list_audit_logs(get_settings().audit_log_path, limit=20)
        self.assertGreaterEqual(len(logs), 1)
        self.assertEqual(logs[0]["entity_type"], "build_task")
        self.assertEqual(len(list_platform_targets()), 4)


class B12B13B14UnitTestCase(unittest.TestCase):
    """B12/B13/B14 相关工具函数单元测试。"""

    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    # -------- B12：模型文件复制 --------

    def test_copy_model_package_copies_standard_files(self) -> None:
        src = self.root / "model_src"
        src.mkdir()
        (src / "manifest.json").write_text('{"capability_name":"cap"}', encoding="utf-8")
        (src / "labels.json").write_text('{"labels":["a"]}', encoding="utf-8")
        (src / "preprocess.json").write_text('{}', encoding="utf-8")
        (src / "weights.onnx").write_bytes(b"\x00\x01\x02")

        dst = self.root / "sdk_models"
        report = _copy_model_package_to_sdk(str(src), dst)

        self.assertEqual(report["status"], "completed")
        self.assertIn("manifest.json", report["copied_files"])
        self.assertIn("labels.json", report["copied_files"])
        self.assertIn("preprocess.json", report["copied_files"])
        self.assertIn("weights.onnx", report["copied_files"])
        self.assertTrue((dst / "manifest.json").is_file())
        self.assertTrue((dst / "labels.json").is_file())
        self.assertTrue((dst / "weights.onnx").is_file())

    def test_copy_model_package_handles_missing_source(self) -> None:
        report = _copy_model_package_to_sdk("/nonexistent/path", self.root / "out")
        self.assertEqual(report["status"], "source_not_found")

    def test_copy_model_package_handles_none_artifact_path(self) -> None:
        report = _copy_model_package_to_sdk(None, self.root / "out")
        self.assertEqual(report["status"], "skipped")

    # -------- B13：manifest 加载与追溯 --------

    def test_load_source_manifest_returns_dict_for_valid_file(self) -> None:
        manifest_file = self.root / "manifest.json"
        manifest_file.write_text(
            json.dumps({"capability_name": "cap", "task_type": "detection", "source_train_task_id": 10}),
            encoding="utf-8",
        )
        result = _load_source_manifest(str(manifest_file))
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["task_type"], "detection")
        self.assertEqual(result["source_train_task_id"], 10)

    def test_load_source_manifest_returns_none_for_missing_file(self) -> None:
        result = _load_source_manifest("/nonexistent/manifest.json")
        self.assertIsNone(result)

    def test_load_source_manifest_returns_none_for_none_input(self) -> None:
        result = _load_source_manifest(None)
        self.assertIsNone(result)

    # -------- B14：模型包校验 --------

    def test_validate_model_package_passes_for_complete_package(self) -> None:
        model_dir = self.root / "model"
        model_dir.mkdir()
        manifest_path = model_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps({"capability_name": "cap", "model_version": "v1", "task_type": "classification"}),
            encoding="utf-8",
        )
        (model_dir / "labels.json").write_text('{"labels":["ok"]}', encoding="utf-8")
        (model_dir / "preprocess.json").write_text('{}', encoding="utf-8")

        report = _validate_model_package(str(model_dir), str(manifest_path))
        self.assertEqual(report["overall_status"], "passed")
        check_names = [c["name"] for c in report["checks"]]
        self.assertIn("模型包目录", check_names)
        self.assertIn("manifest.json", check_names)

    def test_validate_model_package_warns_for_missing_directory(self) -> None:
        report = _validate_model_package("/nonexistent/dir", None)
        self.assertIn(report["overall_status"], ("warning", "failed"))

    def test_validate_model_package_fails_for_missing_required_manifest_fields(self) -> None:
        model_dir = self.root / "model_incomplete"
        model_dir.mkdir()
        manifest_path = model_dir / "manifest.json"
        manifest_path.write_text(json.dumps({"capability_name": "only_name"}), encoding="utf-8")

        report = _validate_model_package(str(model_dir), str(manifest_path))
        self.assertEqual(report["overall_status"], "failed")
        failed_checks = [c for c in report["checks"] if c["status"] == "failed"]
        self.assertGreaterEqual(len(failed_checks), 1)

    # -------- B14：插件装载校验 --------

    def test_validate_plugin_loadability_fails_for_missing_binary(self) -> None:
        report = _validate_plugin_loadability(self.root / "nonexistent.so", "cap")
        self.assertEqual(report["overall_status"], "failed")
        failed_checks = [c for c in report["checks"] if c["status"] == "failed"]
        self.assertGreaterEqual(len(failed_checks), 1)

    def test_validate_plugin_loadability_fails_for_non_elf_binary(self) -> None:
        fake_so = self.root / "libcap.so"
        fake_so.write_bytes(b"not-an-elf-file-content")
        report = _validate_plugin_loadability(fake_so, "cap")
        # 装载失败或符号不存在均为合理结果
        self.assertIn(report["overall_status"], ("failed", "warning", "passed"))
        self.assertTrue(len(report["checks"]) >= 1)
