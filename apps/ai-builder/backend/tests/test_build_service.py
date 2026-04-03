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
)
from app.services.catalog_service import get_builder_catalog, write_builder_catalog_snapshot


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
                    "artifact_path": str((self.host_root / "models" / "face_detect" / "v1_0_0").resolve()),
                    "manifest_path": str((self.host_root / "models" / "face_detect" / "v1_0_0" / "manifest.json").resolve()),
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
        self.assertTrue((Path(task_detail["delivery_package_dir"]) / "docs" / "DEPLOYMENT.md").is_file())
        manifest_payload = json.loads((Path(task_detail["delivery_package_dir"]) / "package_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest_payload["stage_status"]["B10"], "completed")
        self.assertIn("ai-prod_image_build_context.tar.gz", manifest_payload["docker"]["archive_path"])
        self.assertTrue((self.host_root / "libs" / "linux_x86_64" / "face_detect" / "include" / "face_detect.h").is_file())
        self.assertTrue((self.host_root / "libs" / "linux_x86_64" / "face_detect" / "license" / "license.bin").is_file())
        self.assertIsNotNone(task_detail["manifest"])

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
