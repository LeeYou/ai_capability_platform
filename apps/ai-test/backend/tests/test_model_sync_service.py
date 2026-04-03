from __future__ import annotations

import io
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app.config import get_settings, reset_settings_cache
from app.services.model_sync_service import get_model_catalog, sync_remote_model_catalog


class _FakeHttpResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False


class ModelSyncServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.host_root = Path(self.temp_dir.name)
        (self.host_root / "data").mkdir()
        os.environ["AI_CAP_HOST_ROOT"] = str(self.host_root)
        reset_settings_cache()

    def tearDown(self) -> None:
        reset_settings_cache()
        os.environ.pop("AI_CAP_HOST_ROOT", None)
        self.temp_dir.cleanup()

    def test_sync_remote_model_catalog_persists_snapshot(self) -> None:
        responses = [
            _FakeHttpResponse(json.dumps({"items": [{"capability_name": "ocr", "model_version": "v1", "source_training_task_id": 1, "artifact_path": "/models/ocr/v1", "manifest_path": "/models/ocr/v1/manifest.json", "backend_type": "cpu", "checksum": "abc", "status": "ready"}]}).encode("utf-8")),
            _FakeHttpResponse(json.dumps({"items": [{"capability_name": "ocr", "display_name": "OCR", "dataset_path": "ocr", "dataset_status": "ready", "source": "manual"}]}).encode("utf-8")),
        ]

        with patch("app.services.model_sync_service.urlopen", side_effect=responses):
            payload = sync_remote_model_catalog(
                get_settings().model_catalog_snapshot_path,
                get_settings().ai_train_api_base_url,
            )

        self.assertEqual(len(payload["models"]), 1)
        self.assertEqual(len(payload["capabilities"]), 1)
        self.assertTrue(get_settings().model_catalog_snapshot_path.is_file())

    def test_get_model_catalog_falls_back_to_snapshot(self) -> None:
        snapshot_path = get_settings().model_catalog_snapshot_path
        snapshot_path.write_text(
            json.dumps({"models": [{"capability_name": "ocr", "model_version": "v1", "source_training_task_id": 1, "artifact_path": "/models/ocr/v1", "manifest_path": "/models/ocr/v1/manifest.json", "backend_type": "cpu", "checksum": "abc", "status": "ready"}], "capabilities": [], "synced_at": "2026-04-02T00:00:00+00:00"}, ensure_ascii=False),
            encoding="utf-8",
        )

        with patch("app.services.model_sync_service.urlopen", side_effect=ValueError("boom")):
            payload = get_model_catalog(snapshot_path, get_settings().ai_train_api_base_url)

        self.assertEqual(payload["models"][0]["capability_name"], "ocr")
