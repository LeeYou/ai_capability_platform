from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.config import get_settings, reset_settings_cache
from app.db.database import get_session_factory, reset_database_cache
from app.services.audit_service import list_audit_logs
from app.services.sdk_service import (
    create_sdk_package,
    get_sdk_catalog,
    get_sdk_package,
    initialize_database,
    list_sdk_packages,
    list_sdk_targets,
)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _prepare_builder_output(host_root: Path, *, capability_name: str, model_version: str, target_name: str, jni_enabled: bool) -> None:
    artifact_format = "so" if target_name.startswith("linux") else "dll"
    binary_name = f"lib{capability_name}.so" if artifact_format == "so" else f"{capability_name}.dll"
    target_root = host_root / "libs" / target_name / capability_name
    _write_text(target_root / "lib" / binary_name, "binary")
    _write_text(target_root / "include" / f"{capability_name}.h", f"int {capability_name}_predict(const char*, char*, unsigned int);")
    _write_text(target_root / "license" / "license.bin", "license")
    _write_text(target_root / "license" / "pubkey.pem", "pubkey")
    _write_text(
        target_root / "manifest" / "manifest.json",
        json.dumps(
            {
                "capability_name": capability_name,
                "model_version": model_version,
                "target_name": target_name,
                "artifact_format": artifact_format,
                "build_mode": "native" if target_name == "linux_x86_64" else "template",
            },
            ensure_ascii=False,
        ),
    )
    if jni_enabled:
        jni_name = f"lib{capability_name}_jni.so" if artifact_format == "so" else f"{capability_name}_jni.dll"
        _write_text(target_root / "jni" / jni_name, "jni-binary")


def _prepare_model(host_root: Path, *, capability_name: str, model_version: str) -> None:
    model_root = host_root / "models" / capability_name / model_version
    _write_text(model_root / "manifest.json", json.dumps({"capability_name": capability_name, "model_version": model_version}, ensure_ascii=False))
    _write_text(model_root / "model.onnx", "fake-model")
    _write_text(model_root / "labels.txt", "label-a\nlabel-b\n")


class SdkServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.host_root = Path(self.temp_dir.name)
        for directory_name in ("data", "logs", "exports", "libs", "models", "license"):
            (self.host_root / directory_name).mkdir(parents=True, exist_ok=True)
        os.environ["AI_CAP_HOST_ROOT"] = str(self.host_root)
        reset_settings_cache()
        reset_database_cache()
        initialize_database()
        _prepare_model(self.host_root, capability_name="face_detect", model_version="v1_0_0")
        _prepare_builder_output(self.host_root, capability_name="face_detect", model_version="v1_0_0", target_name="linux_x86_64", jni_enabled=True)
        _prepare_builder_output(self.host_root, capability_name="face_detect", model_version="v1_0_0", target_name="windows_x86_64", jni_enabled=True)

    def tearDown(self) -> None:
        reset_database_cache()
        reset_settings_cache()
        os.environ.pop("AI_CAP_HOST_ROOT", None)
        self.temp_dir.cleanup()

    def test_catalog_scans_models_and_builder_outputs(self) -> None:
        payload = get_sdk_catalog(get_settings().libs_root, get_settings().models_root)
        self.assertEqual(len(payload["capabilities"]), 1)
        self.assertEqual(payload["capabilities"][0]["capability_name"], "face_detect")
        self.assertEqual(payload["capabilities"][0]["available_targets"], ["linux_x86_64", "windows_x86_64"])

    def test_create_sdk_package_generates_linux_and_windows_archives(self) -> None:
        with get_session_factory()() as session:
            payload = create_sdk_package(
                session,
                sdk_packages_root=get_settings().sdk_packages_root,
                sdk_logs_root=get_settings().sdk_logs_root,
                libs_root=get_settings().libs_root,
                models_root=get_settings().models_root,
                exports_root=get_settings().exports_root,
                audit_log_path=get_settings().audit_log_path,
                package_name="face_detect_sdk_release",
                capability_name="face_detect",
                model_version="v1_0_0",
                requested_targets=["linux_x86_64", "windows_x86_64"],
                jni_enabled=False,
            )
            package_detail = get_sdk_package(session, int(payload["package_id"]))
            package_list = list_sdk_packages(session)

        self.assertEqual(payload["status"], "completed")
        self.assertEqual(len(package_list), 1)
        self.assertEqual(len(package_detail["targets"]), 2)
        linux_target = next(item for item in package_detail["targets"] if item["target_name"] == "linux_x86_64")
        self.assertTrue(Path(linux_target["binary_path"]).is_file())
        self.assertTrue(Path(linux_target["download_archive_path"]).is_file())
        self.assertTrue(Path(package_detail["manifest_path"]).is_file())
        self.assertTrue((Path(linux_target["output_dir"]) / "docs" / "README_集成说明.md").is_file())
        self.assertTrue((Path(linux_target["output_dir"]) / "examples" / "sample_c_api.c").is_file())
        self.assertTrue((Path(linux_target["output_dir"]) / "include" / "ai_sdk_error_codes.h").is_file())
        self.assertEqual(Path(linux_target["output_dir"]).name, "sdk_linux_x86_64")
        self.assertTrue((Path(linux_target["output_dir"]) / "manifest" / "manifest.json").is_file())
        self.assertTrue((Path(linux_target["output_dir"]) / "tools" / "license_tool" / "manifest.json").is_file())
        self.assertTrue((Path(linux_target["output_dir"]) / "validation" / "verify_sdk_package.py").is_file())
        package_manifest = json.loads(Path(package_detail["manifest_path"]).read_text(encoding="utf-8"))
        self.assertTrue(package_manifest["delivery_package_alignment"])
        self.assertEqual(package_manifest["stage_status"]["S9"], "completed")
        self.assertTrue((Path(payload["package_root_path"]) / "acceptance_checklist.json").is_file())
        self.assertTrue((Path(payload["package_root_path"]) / "version_manifest.json").is_file())
        self.assertTrue((Path(payload["package_root_path"]) / "delivery_summary.json").is_file())
        self.assertTrue((Path(payload["package_root_path"]) / "delivery_summary.md").is_file())
        self.assertEqual(package_manifest["version_manifest_path"], "version_manifest.json")
        self.assertEqual(package_manifest["delivery_summary"]["target_count"], 2)
        version_manifest = json.loads((Path(payload["package_root_path"]) / "version_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(version_manifest["sdk_items"]), 2)
        self.assertGreaterEqual(len(version_manifest["delivery_checksums"]), 2)

    def test_create_sdk_package_with_jni_outputs_java_and_jni_files(self) -> None:
        with get_session_factory()() as session:
            payload = create_sdk_package(
                session,
                sdk_packages_root=get_settings().sdk_packages_root,
                sdk_logs_root=get_settings().sdk_logs_root,
                libs_root=get_settings().libs_root,
                models_root=get_settings().models_root,
                exports_root=get_settings().exports_root,
                audit_log_path=get_settings().audit_log_path,
                package_name="face_detect_sdk_jni",
                capability_name="face_detect",
                model_version="v1_0_0",
                requested_targets=["linux_x86_64"],
                jni_enabled=True,
            )
            package_detail = get_sdk_package(session, int(payload["package_id"]))

        target = package_detail["targets"][0]
        self.assertTrue((Path(target["output_dir"]) / "jni").is_dir())
        self.assertTrue((Path(target["output_dir"]) / "examples" / "NativeBridge.java").is_file())
        self.assertTrue((Path(target["output_dir"]) / "docs" / "ACCEPTANCE_CHECKLIST.md").is_file())
        self.assertTrue((Path(target["output_dir"]) / "docs" / "DEPLOYMENT_GUIDE.md").is_file())
        self.assertTrue((Path(target["output_dir"]) / "docs" / "LICENSE_TOOL.md").is_file())
        delivery_summary = json.loads((Path(payload["package_root_path"]) / "delivery_summary.json").read_text(encoding="utf-8"))
        self.assertTrue(delivery_summary["jni_enabled"])
        self.assertEqual(delivery_summary["target_count"], 1)

    def test_audit_logs_and_target_listing(self) -> None:
        with get_session_factory()() as session:
            create_sdk_package(
                session,
                sdk_packages_root=get_settings().sdk_packages_root,
                sdk_logs_root=get_settings().sdk_logs_root,
                libs_root=get_settings().libs_root,
                models_root=get_settings().models_root,
                exports_root=get_settings().exports_root,
                audit_log_path=get_settings().audit_log_path,
                package_name="face_detect_sdk_audit",
                capability_name="face_detect",
                model_version="v1_0_0",
                requested_targets=["linux_x86_64"],
                jni_enabled=False,
            )
        logs = list_audit_logs(get_settings().audit_log_path, limit=20)
        self.assertGreaterEqual(len(logs), 1)
        self.assertEqual(logs[0]["entity_type"], "sdk_package")
        self.assertEqual(len(list_sdk_targets()), 4)

    def test_verify_sdk_package_script_passes_for_generated_target(self) -> None:
        with get_session_factory()() as session:
            payload = create_sdk_package(
                session,
                sdk_packages_root=get_settings().sdk_packages_root,
                sdk_logs_root=get_settings().sdk_logs_root,
                libs_root=get_settings().libs_root,
                models_root=get_settings().models_root,
                exports_root=get_settings().exports_root,
                audit_log_path=get_settings().audit_log_path,
                package_name="face_detect_sdk_verify",
                capability_name="face_detect",
                model_version="v1_0_0",
                requested_targets=["linux_x86_64"],
                jni_enabled=False,
            )
            package_detail = get_sdk_package(session, int(payload["package_id"]))

        target = package_detail["targets"][0]
        verify_script = Path(target["output_dir"]) / "validation" / "verify_sdk_package.py"
        exit_code = os.system(f'python "{verify_script}" "{Path(target["output_dir"])}" > /dev/null')
        self.assertEqual(exit_code, 0)
