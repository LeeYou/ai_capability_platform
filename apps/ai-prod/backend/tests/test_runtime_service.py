from __future__ import annotations

from base64 import b64encode
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from app.config import get_settings, reset_settings_cache
from app.db.database import get_session_factory, reset_database_cache
from app.services.audit_service import list_audit_logs
from app.services.runtime_service import (
    bootstrap_runtime,
    get_license_status,
    infer,
    initialize_database,
    list_capabilities,
    list_runtime_operations,
    list_runtime_revisions,
    reload_runtime,
)


CST = timezone(timedelta(hours=8))


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _canonical_json_bytes(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _create_license_bundle(
    license_root: Path,
    *,
    hardware_fingerprint: str,
    capability_scope: list[str] | None = None,
    min_version: str = "v1_0_0",
    max_version: str = "v9_9_9",
    operating_system: str = "linux",
    min_operating_system_version: str | None = "5.4.0",
    system_architecture: str | None = "x86_64",
    application_name: str = "ai-prod",
) -> None:
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    payload = {
        "customer_code": "cust_prod",
        "application_name": application_name,
        "operating_system": operating_system,
        "min_operating_system_version": min_operating_system_version,
        "system_architecture": system_architecture,
        "capability_scope": capability_scope or ["face_detect", "ocr"],
        "hardware_fingerprint": hardware_fingerprint,
        "start_at_cst": (datetime.now(CST) - timedelta(days=1)).isoformat(),
        "expire_at_cst": (datetime.now(CST) + timedelta(days=30)).isoformat(),
        "version_constraints": {"min_version": min_version, "max_version": max_version},
    }
    signature = private_key.sign(_canonical_json_bytes(payload))
    license_payload = {
        "algorithm": "ed25519",
        "payload": payload,
        "signature": b64encode(signature).decode("ascii"),
    }
    license_root.mkdir(parents=True, exist_ok=True)
    (license_root / "license.bin").write_text(json.dumps(license_payload, ensure_ascii=False), encoding="utf-8")
    (license_root / "pubkey.pem").write_bytes(
        public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )


def _create_model_and_plugin(
    base_root: Path,
    *,
    capability_name: str,
    model_version: str,
    target_name: str,
    source: str,
    max_batch_size: int = 1,
    instance_count: int = 0,
) -> None:
    model_root = base_root / "models" / capability_name / model_version
    preprocess_path = model_root / "preprocess.json"
    labels_path = model_root / "labels.json"
    validation_path = model_root / "validation" / "acceptance_checklist.json"
    delivery_metadata_path = model_root / "delivery_metadata.json"
    runtime_contract_path = model_root / "runtime_contract.json"
    _write_text(preprocess_path, json.dumps({"input_type": "image", "resize": {"width": 640, "height": 640}, "normalize": {"mean": [0.5], "std": [0.5]}}, ensure_ascii=False))
    _write_text(labels_path, json.dumps({"labels": ["ok", "ng"]}, ensure_ascii=False))
    _write_text(validation_path, json.dumps({"required_cases": ["acceptance_check"]}, ensure_ascii=False))
    _write_text(delivery_metadata_path, json.dumps({"ai_builder": {"manifest_schema_path": "apps/shared/schemas/manifest_model.json"}}, ensure_ascii=False))
    runtime_contract = {
        "task_type": "detection",
        "annotation_schema": {"type": "object"},
        "template_bundle": {"name": capability_name},
        "model_files": ["model.onnx"],
        "runtime_inputs": {
            "preprocess_path": str(preprocess_path.resolve()),
            "labels_path": str(labels_path.resolve()),
        },
    }
    _write_text(runtime_contract_path, json.dumps(runtime_contract, ensure_ascii=False))
    model_manifest = {
        "capability_name": capability_name,
        "task_type": "detection",
        "model_version": model_version,
        "source_train_task_id": 1,
        "task_name": f"{capability_name}_task",
        "backend_type": "onnxruntime",
        "artifact_path": str(model_root.resolve()),
        "status": "ready",
        "checksum": f"checksum-{capability_name}-{model_version}",
        "preprocessing": {"input_type": "image", "resize": {"width": 640, "height": 640}, "normalize": {"mean": [0.5], "std": [0.5]}},
        "thresholds": {"score_threshold": 0.5, "nms_threshold": 0.45},
        "labels": ["ok", "ng"],
        "validation": {
            "artifacts": [
                "preprocess.json",
                "labels.json",
                "validation/acceptance_checklist.json",
                "delivery_metadata.json",
                "runtime_contract.json",
            ]
        },
        "runtime_contract": runtime_contract,
        "delivery_metadata": {"ai_test": {"task_type": "acceptance"}, "ai_builder": {"manifest_schema_path": "apps/shared/schemas/manifest_model.json"}, "training_summary": {"backend_type": "onnxruntime"}},
        "source": source,
        "max_batch_size": max_batch_size,
    }
    if instance_count > 0:
        model_manifest["instance_count"] = instance_count
    _write_text(model_root / "manifest.json", json.dumps(model_manifest, ensure_ascii=False))
    _write_text(model_root / "model.onnx", "fake-model")
    plugin_manifest = {
        "capability_name": capability_name,
        "model_version": model_version,
        "target_name": target_name,
        "artifact_format": "so",
        "build_mode": "native",
        "toolchain_name": "cmake-native",
        "jni_enabled": False,
        "customer_code": "cust_prod",
        "issue_record_id": 1,
        "dependency_summary": {
            "runtime": "onnxruntime",
            "abi": "cxx17",
            "license_required": True,
            "build_params_controlled": True,
        },
        "max_batch_size": max_batch_size,
    }
    if instance_count > 0:
        plugin_manifest["instance_count"] = instance_count
    _write_text(
        base_root / "libs" / target_name / capability_name / "manifest" / "manifest.json",
        json.dumps(plugin_manifest, ensure_ascii=False),
    )
    _write_text(base_root / "libs" / target_name / capability_name / "lib" / f"lib{capability_name}.so", "fake-lib")


class RuntimeServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.host_root = Path(self.temp_dir.name) / "host"
        self.image_root = Path(self.temp_dir.name) / "image"
        for root in (self.host_root, self.image_root):
            for directory_name in ("data", "logs", "exports", "libs", "models", "license", "configs"):
                (root / directory_name).mkdir(parents=True, exist_ok=True)
        os.environ["AI_CAP_HOST_ROOT"] = str(self.host_root)
        os.environ["AI_CAP_GPU_AVAILABLE"] = "1"
        os.environ["AI_CAP_HARDWARE_FEATURES"] = json.dumps({"cpu": "intel-i7", "mac": "00:11:22:33:44:55"})
        os.environ["AI_CAP_OPERATING_SYSTEM"] = "linux"
        os.environ["AI_CAP_OPERATING_SYSTEM_VERSION"] = "5.15.0"
        os.environ["AI_CAP_SYSTEM_ARCHITECTURE"] = "x86_64"
        os.environ["AI_CAP_APPLICATION_NAME"] = "ai-prod"
        reset_settings_cache()
        reset_database_cache()
        initialize_database()

        fingerprint = hashlib.sha256("cpu=intel-i7|mac=00:11:22:33:44:55".encode("utf-8")).hexdigest()
        _create_license_bundle(self.host_root / "license", hardware_fingerprint=fingerprint)
        _create_model_and_plugin(self.host_root, capability_name="face_detect", model_version="v1_0_0", target_name="linux_x86_64", source="host", max_batch_size=4, instance_count=3)
        _create_model_and_plugin(self.image_root, capability_name="ocr", model_version="v2_0_0", target_name="linux_x86_64", source="image", max_batch_size=2, instance_count=2)

    def tearDown(self) -> None:
        reset_database_cache()
        reset_settings_cache()
        os.environ.pop("AI_CAP_HOST_ROOT", None)
        os.environ.pop("AI_CAP_GPU_AVAILABLE", None)
        os.environ.pop("AI_CAP_HARDWARE_FEATURES", None)
        os.environ.pop("AI_CAP_OPERATING_SYSTEM", None)
        os.environ.pop("AI_CAP_OPERATING_SYSTEM_VERSION", None)
        os.environ.pop("AI_CAP_SYSTEM_ARCHITECTURE", None)
        os.environ.pop("AI_CAP_APPLICATION_NAME", None)
        self.temp_dir.cleanup()

    def test_bootstrap_runtime_scans_host_and_image_resources(self) -> None:
        settings = get_settings()
        with get_session_factory()() as session:
            payload = bootstrap_runtime(
                session,
                runtime_snapshot_path=settings.runtime_snapshot_path,
                runtime_log_path=settings.runtime_log_path,
                audit_log_path=settings.audit_log_path,
                host_root=settings.host_root,
                image_resource_root=self.image_root,
                license_root=settings.license_root,
                hardware_features=settings.hardware_features,
                pool_size=settings.pool_size,
                gpu_available=settings.gpu_available,
                service_name=settings.service_name,
                company_name=settings.company_name,
                company_domain=settings.company_domain,
                operating_system=settings.operating_system,
                operating_system_version=settings.operating_system_version,
                system_architecture=settings.system_architecture,
            )

        self.assertTrue(payload["license_status"]["valid"])
        self.assertEqual(payload["license_status"]["code"], "license_valid")
        self.assertEqual(payload["license_status"]["stage"], "success")
        capabilities = list_capabilities()
        self.assertEqual(len(capabilities), 2)
        self.assertTrue(settings.runtime_snapshot_path.is_file())
        snapshot_payload = json.loads(settings.runtime_snapshot_path.read_text(encoding="utf-8"))
        self.assertEqual(snapshot_payload["snapshot_version"], 1)
        self.assertEqual(snapshot_payload["capability_count"], 2)
        self.assertEqual(len(snapshot_payload["capabilities"]), 2)
        self.assertEqual(snapshot_payload["service_name"], settings.service_name)
        capabilities_by_name = {item["capability_name"]: item for item in capabilities}
        self.assertEqual(capabilities_by_name["face_detect"]["max_batch_size"], 4)
        self.assertEqual(capabilities_by_name["face_detect"]["pool_size"], 3)
        self.assertTrue(capabilities_by_name["face_detect"]["admission_checklist"]["ready"])
        checklist_items = {
            item["code"]: item for item in capabilities_by_name["face_detect"]["admission_checklist"]["items"]
        }
        self.assertEqual(checklist_items["runtime_probe"]["status"], "not_applicable")
        self.assertTrue(snapshot_payload["capabilities"][0]["admission_checklist"]["ready"])

    def test_infer_uses_dual_layer_license_validation_and_gpu_fallback(self) -> None:
        settings = get_settings()
        with get_session_factory()() as session:
            bootstrap_runtime(
                session,
                runtime_snapshot_path=settings.runtime_snapshot_path,
                runtime_log_path=settings.runtime_log_path,
                audit_log_path=settings.audit_log_path,
                host_root=settings.host_root,
                image_resource_root=self.image_root,
                license_root=settings.license_root,
                hardware_features=settings.hardware_features,
                pool_size=settings.pool_size,
                gpu_available=settings.gpu_available,
                service_name=settings.service_name,
                company_name=settings.company_name,
                company_domain=settings.company_domain,
                operating_system=settings.operating_system,
                operating_system_version=settings.operating_system_version,
                system_architecture=settings.system_architecture,
            )
            payload = infer(
                runtime_log_path=settings.runtime_log_path,
                audit_log_path=settings.audit_log_path,
                license_root=settings.license_root,
                hardware_features=settings.hardware_features,
                capability_name="face_detect",
                input_type="json",
                payload='{"image":"demo"}',
                prefer_device="gpu",
                options={"threshold": 0.5},
                operating_system=settings.operating_system,
                operating_system_version=settings.operating_system_version,
                system_architecture=settings.system_architecture,
            )

        self.assertEqual(payload["capability_name"], "face_detect")
        self.assertEqual(payload["device"], "gpu")
        self.assertTrue(payload["license_valid"])

    def test_reload_and_rollback_record_runtime_history(self) -> None:
        settings = get_settings()
        with get_session_factory()() as session:
            bootstrap_runtime(
                session,
                runtime_snapshot_path=settings.runtime_snapshot_path,
                runtime_log_path=settings.runtime_log_path,
                audit_log_path=settings.audit_log_path,
                host_root=settings.host_root,
                image_resource_root=self.image_root,
                license_root=settings.license_root,
                hardware_features=settings.hardware_features,
                pool_size=settings.pool_size,
                gpu_available=settings.gpu_available,
                service_name=settings.service_name,
                company_name=settings.company_name,
                company_domain=settings.company_domain,
                operating_system=settings.operating_system,
                operating_system_version=settings.operating_system_version,
                system_architecture=settings.system_architecture,
            )
            revisions_before = list_runtime_revisions(session)
            capabilities_before = {item["capability_name"]: item for item in list_capabilities()}
            self.assertEqual(capabilities_before["face_detect"]["model_version"], "v1_0_0")
            _create_model_and_plugin(self.host_root, capability_name="face_detect", model_version="v3_0_0", target_name="linux_x86_64", source="host", max_batch_size=6, instance_count=4)
            _create_model_and_plugin(self.host_root, capability_name="plate_detect", model_version="v3_0_0", target_name="linux_x86_64", source="host")
            fingerprint = hashlib.sha256("cpu=intel-i7|mac=00:11:22:33:44:55".encode("utf-8")).hexdigest()
            _create_license_bundle(
                self.host_root / "license",
                hardware_fingerprint=fingerprint,
                capability_scope=["face_detect", "ocr", "plate_detect"],
            )
            reloaded = reload_runtime(
                session,
                runtime_snapshot_path=settings.runtime_snapshot_path,
                runtime_log_path=settings.runtime_log_path,
                audit_log_path=settings.audit_log_path,
                host_root=settings.host_root,
                image_resource_root=self.image_root,
                license_root=settings.license_root,
                hardware_features=settings.hardware_features,
                pool_size=settings.pool_size,
                gpu_available=settings.gpu_available,
                action="reload",
                target_revision_id=None,
                service_name=settings.service_name,
                company_name=settings.company_name,
                company_domain=settings.company_domain,
                operating_system=settings.operating_system,
                operating_system_version=settings.operating_system_version,
                system_architecture=settings.system_architecture,
            )
            infer_after_reload = infer(
                runtime_log_path=settings.runtime_log_path,
                audit_log_path=settings.audit_log_path,
                license_root=settings.license_root,
                hardware_features=settings.hardware_features,
                capability_name="face_detect",
                input_type="json",
                payload='{"image":"after-reload"}',
                prefer_device="gpu",
                options={},
                operating_system=settings.operating_system,
                operating_system_version=settings.operating_system_version,
                system_architecture=settings.system_architecture,
            )
            capabilities_after_reload = {item["capability_name"]: item for item in list_capabilities()}
            self.assertEqual(capabilities_after_reload["face_detect"]["model_version"], "v3_0_0")
            self.assertEqual(capabilities_after_reload["face_detect"]["max_batch_size"], 6)
            self.assertEqual(capabilities_after_reload["face_detect"]["pool_size"], 4)
            rolled_back = reload_runtime(
                session,
                runtime_snapshot_path=settings.runtime_snapshot_path,
                runtime_log_path=settings.runtime_log_path,
                audit_log_path=settings.audit_log_path,
                host_root=settings.host_root,
                image_resource_root=self.image_root,
                license_root=settings.license_root,
                hardware_features=settings.hardware_features,
                pool_size=settings.pool_size,
                gpu_available=settings.gpu_available,
                action="rollback",
                target_revision_id=revisions_before[-1]["revision_id"],
                service_name=settings.service_name,
                company_name=settings.company_name,
                company_domain=settings.company_domain,
                operating_system=settings.operating_system,
                operating_system_version=settings.operating_system_version,
                system_architecture=settings.system_architecture,
            )
            infer_after_rollback = infer(
                runtime_log_path=settings.runtime_log_path,
                audit_log_path=settings.audit_log_path,
                license_root=settings.license_root,
                hardware_features=settings.hardware_features,
                capability_name="face_detect",
                input_type="json",
                payload='{"image":"after-rollback"}',
                prefer_device="gpu",
                options={},
                operating_system=settings.operating_system,
                operating_system_version=settings.operating_system_version,
                system_architecture=settings.system_architecture,
            )

        self.assertGreater(reloaded["active_capability_count"], rolled_back["active_capability_count"])
        self.assertGreaterEqual(len(list_runtime_operations(session)), 2)
        revisions_after = list_runtime_revisions(session)
        self.assertEqual(revisions_after[-1]["action"], "rollback")
        self.assertEqual(infer_after_reload["model_version"], "v3_0_0")
        self.assertEqual(infer_after_reload["runtime_revision_id"], reloaded["revision"]["revision_id"])
        self.assertEqual(infer_after_rollback["model_version"], "v1_0_0")
        self.assertEqual(infer_after_rollback["runtime_revision_id"], rolled_back["revision"]["revision_id"])
        capabilities_after_rollback = {item["capability_name"]: item for item in list_capabilities()}
        self.assertEqual(capabilities_after_rollback["face_detect"]["model_version"], "v1_0_0")
        self.assertEqual(capabilities_after_rollback["face_detect"]["max_batch_size"], 4)
        self.assertEqual(capabilities_after_rollback["face_detect"]["pool_size"], 3)

    def test_bootstrap_skips_invalid_manifest_contracts(self) -> None:
        settings = get_settings()
        _create_model_and_plugin(
            self.host_root,
            capability_name="broken_cap",
            model_version="v1_0_0",
            target_name="linux_x86_64",
            source="host",
        )
        broken_plugin_manifest_path = self.host_root / "libs" / "linux_x86_64" / "broken_cap" / "manifest" / "manifest.json"
        broken_manifest = json.loads(broken_plugin_manifest_path.read_text(encoding="utf-8"))
        broken_manifest["model_version"] = "v9_9_9"
        broken_plugin_manifest_path.write_text(json.dumps(broken_manifest, ensure_ascii=False), encoding="utf-8")

        with get_session_factory()() as session:
            payload = bootstrap_runtime(
                session,
                runtime_snapshot_path=settings.runtime_snapshot_path,
                runtime_log_path=settings.runtime_log_path,
                audit_log_path=settings.audit_log_path,
                host_root=settings.host_root,
                image_resource_root=self.image_root,
                license_root=settings.license_root,
                hardware_features=settings.hardware_features,
                pool_size=settings.pool_size,
                gpu_available=settings.gpu_available,
                service_name=settings.service_name,
                company_name=settings.company_name,
                company_domain=settings.company_domain,
                operating_system=settings.operating_system,
                operating_system_version=settings.operating_system_version,
                system_architecture=settings.system_architecture,
            )

        snapshot_payload = json.loads(settings.runtime_snapshot_path.read_text(encoding="utf-8"))
        capability_names = {item["capability_name"] for item in list_capabilities()}
        self.assertNotIn("broken_cap", capability_names)
        self.assertEqual(len(snapshot_payload["source_summary"]["invalid_capability_failures"]), 1)

    def test_reload_rejects_capability_outside_license_scope_and_records_audit(self) -> None:
        settings = get_settings()
        with get_session_factory()() as session:
            bootstrap_runtime(
                session,
                runtime_snapshot_path=settings.runtime_snapshot_path,
                runtime_log_path=settings.runtime_log_path,
                audit_log_path=settings.audit_log_path,
                host_root=settings.host_root,
                image_resource_root=self.image_root,
                license_root=settings.license_root,
                hardware_features=settings.hardware_features,
                pool_size=settings.pool_size,
                gpu_available=settings.gpu_available,
                service_name=settings.service_name,
                company_name=settings.company_name,
                company_domain=settings.company_domain,
                operating_system=settings.operating_system,
                operating_system_version=settings.operating_system_version,
                system_architecture=settings.system_architecture,
            )
            _create_model_and_plugin(self.host_root, capability_name="plate_detect", model_version="v3_0_0", target_name="linux_x86_64", source="host")
            with self.assertRaisesRegex(Exception, "plate_detect"):
                reload_runtime(
                    session,
                    runtime_snapshot_path=settings.runtime_snapshot_path,
                    runtime_log_path=settings.runtime_log_path,
                    audit_log_path=settings.audit_log_path,
                    host_root=settings.host_root,
                    image_resource_root=self.image_root,
                    license_root=settings.license_root,
                    hardware_features=settings.hardware_features,
                    pool_size=settings.pool_size,
                    gpu_available=settings.gpu_available,
                    action="reload",
                    target_revision_id=None,
                    service_name=settings.service_name,
                    company_name=settings.company_name,
                    company_domain=settings.company_domain,
                    operating_system=settings.operating_system,
                    operating_system_version=settings.operating_system_version,
                    system_architecture=settings.system_architecture,
                )

        logs = list_audit_logs(settings.audit_log_path, limit=20)
        self.assertTrue(any(item["action"] == "reload_license_rejected" and item["entity_id"] == "plate_detect" for item in logs))

    def test_rollback_rejects_version_constrained_capability_and_records_audit(self) -> None:
        settings = get_settings()
        with get_session_factory()() as session:
            bootstrap_runtime(
                session,
                runtime_snapshot_path=settings.runtime_snapshot_path,
                runtime_log_path=settings.runtime_log_path,
                audit_log_path=settings.audit_log_path,
                host_root=settings.host_root,
                image_resource_root=self.image_root,
                license_root=settings.license_root,
                hardware_features=settings.hardware_features,
                pool_size=settings.pool_size,
                gpu_available=settings.gpu_available,
                service_name=settings.service_name,
                company_name=settings.company_name,
                company_domain=settings.company_domain,
                operating_system=settings.operating_system,
                operating_system_version=settings.operating_system_version,
                system_architecture=settings.system_architecture,
            )
            revisions_before = list_runtime_revisions(session)
            fingerprint = hashlib.sha256("cpu=intel-i7|mac=00:11:22:33:44:55".encode("utf-8")).hexdigest()
            _create_license_bundle(
                self.host_root / "license",
                hardware_fingerprint=fingerprint,
                capability_scope=["face_detect", "ocr"],
                max_version="v0_9_9",
            )
            with self.assertRaisesRegex(Exception, "face_detect"):
                reload_runtime(
                    session,
                    runtime_snapshot_path=settings.runtime_snapshot_path,
                    runtime_log_path=settings.runtime_log_path,
                    audit_log_path=settings.audit_log_path,
                    host_root=settings.host_root,
                    image_resource_root=self.image_root,
                    license_root=settings.license_root,
                    hardware_features=settings.hardware_features,
                    pool_size=settings.pool_size,
                    gpu_available=settings.gpu_available,
                    action="rollback",
                    target_revision_id=revisions_before[-1]["revision_id"],
                    service_name=settings.service_name,
                    company_name=settings.company_name,
                    company_domain=settings.company_domain,
                    operating_system=settings.operating_system,
                    operating_system_version=settings.operating_system_version,
                    system_architecture=settings.system_architecture,
                )

        logs = list_audit_logs(settings.audit_log_path, limit=20)
        self.assertTrue(any(item["action"] == "rollback_license_rejected" and item["entity_id"] == "face_detect" for item in logs))

    def test_license_status_and_audit_logs_available(self) -> None:
        settings = get_settings()
        with get_session_factory()() as session:
            bootstrap_runtime(
                session,
                runtime_snapshot_path=settings.runtime_snapshot_path,
                runtime_log_path=settings.runtime_log_path,
                audit_log_path=settings.audit_log_path,
                host_root=settings.host_root,
                image_resource_root=self.image_root,
                license_root=settings.license_root,
                hardware_features=settings.hardware_features,
                pool_size=settings.pool_size,
                gpu_available=settings.gpu_available,
                service_name=settings.service_name,
                company_name=settings.company_name,
                company_domain=settings.company_domain,
                operating_system=settings.operating_system,
                operating_system_version=settings.operating_system_version,
                system_architecture=settings.system_architecture,
            )

        status = get_license_status(
            license_root=settings.license_root,
            hardware_features=settings.hardware_features,
            operating_system=settings.operating_system,
            operating_system_version=settings.operating_system_version,
            system_architecture=settings.system_architecture,
            audit_log_path=settings.audit_log_path,
        )
        logs = list_audit_logs(settings.audit_log_path, limit=20)
        self.assertTrue(status["valid"])
        self.assertEqual(status["code"], "license_valid")
        self.assertEqual(status["stage"], "success")
        self.assertTrue(any(item["action"] == "license_status_query" for item in logs))
