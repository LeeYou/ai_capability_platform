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


def _create_license_bundle(license_root: Path, *, hardware_fingerprint: str) -> None:
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    payload = {
        "customer_code": "cust_prod",
        "capability_scope": ["face_detect", "ocr"],
        "hardware_fingerprint": hardware_fingerprint,
        "start_at_cst": (datetime.now(CST) - timedelta(days=1)).isoformat(),
        "expire_at_cst": (datetime.now(CST) + timedelta(days=30)).isoformat(),
        "version_constraints": {"min_version": "v1_0_0", "max_version": "v9_9_9"},
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


def _create_model_and_plugin(base_root: Path, *, capability_name: str, model_version: str, target_name: str, source: str) -> None:
    model_manifest = {
        "capability_name": capability_name,
        "model_version": model_version,
        "backend_type": "onnxruntime",
        "source": source,
    }
    _write_text(base_root / "models" / capability_name / model_version / "manifest.json", json.dumps(model_manifest, ensure_ascii=False))
    _write_text(base_root / "models" / capability_name / model_version / "model.onnx", "fake-model")
    plugin_manifest = {
        "capability_name": capability_name,
        "model_version": model_version,
        "target_name": target_name,
        "build_mode": "native" if source == "host" else "baseline",
        "toolchain_name": "cmake-native",
    }
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
        reset_settings_cache()
        reset_database_cache()
        initialize_database()

        fingerprint = hashlib.sha256("cpu=intel-i7|mac=00:11:22:33:44:55".encode("utf-8")).hexdigest()
        _create_license_bundle(self.host_root / "license", hardware_fingerprint=fingerprint)
        _create_model_and_plugin(self.host_root, capability_name="face_detect", model_version="v1_0_0", target_name="linux_x86_64", source="host")
        _create_model_and_plugin(self.image_root, capability_name="ocr", model_version="v2_0_0", target_name="linux_x86_64", source="image")

    def tearDown(self) -> None:
        reset_database_cache()
        reset_settings_cache()
        os.environ.pop("AI_CAP_HOST_ROOT", None)
        os.environ.pop("AI_CAP_GPU_AVAILABLE", None)
        os.environ.pop("AI_CAP_HARDWARE_FEATURES", None)
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
            )

        self.assertTrue(payload["license_status"]["valid"])
        capabilities = list_capabilities()
        self.assertEqual(len(capabilities), 2)
        self.assertTrue(settings.runtime_snapshot_path.is_file())

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
            )
            revisions_before = list_runtime_revisions(session)
            _create_model_and_plugin(self.host_root, capability_name="plate_detect", model_version="v3_0_0", target_name="linux_x86_64", source="host")
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
            )
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
            )

        self.assertGreater(reloaded["active_capability_count"], rolled_back["active_capability_count"])
        self.assertGreaterEqual(len(list_runtime_operations(session)), 2)
        revisions_after = list_runtime_revisions(session)
        self.assertEqual(revisions_after[-1]["action"], "rollback")

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
            )

        status = get_license_status(license_root=settings.license_root, hardware_features=settings.hardware_features)
        logs = list_audit_logs(settings.audit_log_path, limit=20)
        self.assertTrue(status["valid"])
        self.assertGreaterEqual(len(logs), 1)
