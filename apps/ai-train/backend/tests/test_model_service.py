from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.config import get_settings, reset_settings_cache
from app.db.database import get_session_factory, reset_database_cache
from app.services.registry_service import bind_dataset_to_capability, initialize_database, register_capability
from app.services.training_service import create_training_task, update_training_task_status
from app.services.model_service import create_model_artifact, get_model_artifact, list_model_artifacts


class ModelServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.host_root = Path(self.temp_dir.name)
        (self.host_root / "data").mkdir()
        (self.host_root / "datasets").mkdir()
        (self.host_root / "logs").mkdir()
        (self.host_root / "models").mkdir()

        os.environ["AI_CAP_HOST_ROOT"] = str(self.host_root)
        reset_settings_cache()
        reset_database_cache()
        initialize_database()

    def tearDown(self) -> None:
        reset_database_cache()
        reset_settings_cache()
        os.environ.pop("AI_CAP_HOST_ROOT", None)
        os.environ.pop("AI_CAP_DATABASE_PATH", None)
        self.temp_dir.cleanup()

    def test_create_model_artifact_requires_completed_training_task(self) -> None:
        datasets_root = get_settings().datasets_root
        (datasets_root / "doc_audit").mkdir()

        with get_session_factory()() as session:
            register_capability(session, capability_name="doc_audit", display_name="Doc Audit")
            bind_dataset_to_capability(
                session=session,
                datasets_root=datasets_root,
                capability_name="doc_audit",
                dataset_path="doc_audit",
            )
            training_task = create_training_task(
                session=session,
                training_logs_root=get_settings().training_logs_root,
                capability_name="doc_audit",
                task_name="文档训练",
                framework="pytorch",
                backend_type="cpu",
                annotation_task_id=None,
                train_params={"epochs": 2},
            )

            with self.assertRaises(ValueError):
                create_model_artifact(
                    session=session,
                    models_root=get_settings().models_root,
                    capability_name="doc_audit",
                    model_version="v1.0.0",
                    source_training_task_id=training_task.task_id,
                )

    def test_create_model_artifact_writes_manifest(self) -> None:
        datasets_root = get_settings().datasets_root
        (datasets_root / "ocr_review").mkdir()

        with get_session_factory()() as session:
            register_capability(session, capability_name="ocr_review", display_name="OCR Review")
            bind_dataset_to_capability(
                session=session,
                datasets_root=datasets_root,
                capability_name="ocr_review",
                dataset_path="ocr_review",
            )
            training_task = create_training_task(
                session=session,
                training_logs_root=get_settings().training_logs_root,
                capability_name="ocr_review",
                task_name="OCR 训练",
                framework="pytorch",
                backend_type="cpu",
                annotation_task_id=None,
                train_params={"epochs": 1},
            )
            update_training_task_status(session, training_task.task_id, "running")
            update_training_task_status(session, training_task.task_id, "completed")

            created = create_model_artifact(
                session=session,
                models_root=get_settings().models_root,
                capability_name="ocr_review",
                model_version="v1.0.0",
                source_training_task_id=training_task.task_id,
            )
            items = list_model_artifacts(session)
            detail = get_model_artifact(session, created.artifact_id)

        self.assertEqual(len(items), 1)
        self.assertEqual(detail.model_version, "v1.0.0")
        manifest = json.loads(Path(created.manifest_path).read_text(encoding="utf-8"))
        self.assertEqual(manifest["capability_name"], "ocr_review")
        self.assertEqual(manifest["source_train_task_id"], training_task.task_id)
        self.assertEqual(manifest["checksum"], created.checksum)
        self.assertIn("preprocessing", manifest)
        self.assertIn("labels", manifest)
        self.assertIn("delivery_metadata", manifest)
        self.assertTrue((Path(created.artifact_path) / "preprocess.json").is_file())
        self.assertTrue((Path(created.artifact_path) / "labels.json").is_file())
        self.assertTrue((Path(created.artifact_path) / "validation" / "acceptance_checklist.json").is_file())

    def test_create_model_artifact_rejects_duplicate_version(self) -> None:
        datasets_root = get_settings().datasets_root
        (datasets_root / "face_detect").mkdir()

        with get_session_factory()() as session:
            register_capability(session, capability_name="face_detect", display_name="Face Detect")
            bind_dataset_to_capability(
                session=session,
                datasets_root=datasets_root,
                capability_name="face_detect",
                dataset_path="face_detect",
            )
            training_task = create_training_task(
                session=session,
                training_logs_root=get_settings().training_logs_root,
                capability_name="face_detect",
                task_name="人脸训练",
                framework="pytorch",
                backend_type="cpu",
                annotation_task_id=None,
                train_params={},
            )
            update_training_task_status(session, training_task.task_id, "running")
            update_training_task_status(session, training_task.task_id, "completed")
            create_model_artifact(
                session=session,
                models_root=get_settings().models_root,
                capability_name="face_detect",
                model_version="v1.0.0",
                source_training_task_id=training_task.task_id,
            )

            with self.assertRaises(ValueError):
                create_model_artifact(
                    session=session,
                    models_root=get_settings().models_root,
                    capability_name="face_detect",
                    model_version="v1.0.0",
                    source_training_task_id=training_task.task_id,
                )


if __name__ == "__main__":
    unittest.main()
