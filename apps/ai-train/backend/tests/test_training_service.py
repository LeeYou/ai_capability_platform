from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.config import get_settings, reset_settings_cache
from app.db.database import get_session_factory, reset_database_cache
from app.services.annotation_service import create_annotation_task, submit_annotation_task_result
from app.services.registry_service import bind_dataset_to_capability, initialize_database, register_capability
from app.services.training_service import (
    append_training_task_log,
    create_training_task,
    get_training_task,
    list_training_tasks,
    update_training_task_status,
)


class TrainingServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.host_root = Path(self.temp_dir.name)
        (self.host_root / "data").mkdir()
        (self.host_root / "datasets").mkdir()
        (self.host_root / "logs").mkdir()

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

    def test_create_training_task_requires_completed_annotation_task(self) -> None:
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
            annotation_task = create_annotation_task(
                session=session,
                capability_name="face_detect",
                task_name="首批标注",
                sample_total=2,
            )

            with self.assertRaises(ValueError):
                create_training_task(
                    session=session,
                    training_logs_root=get_settings().training_logs_root,
                    capability_name="face_detect",
                    task_name="首轮训练",
                    framework="pytorch",
                    backend_type="cpu",
                    annotation_task_id=annotation_task.task_id,
                    train_params={"epochs": 1},
                )

    def test_training_task_status_and_log_flow(self) -> None:
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
            annotation_task = create_annotation_task(
                session=session,
                capability_name="doc_audit",
                task_name="文档标注",
                sample_total=1,
            )
            submit_annotation_task_result(
                session=session,
                annotation_tasks_root=get_settings().annotation_tasks_root,
                task_id=annotation_task.task_id,
                annotations=[{"sample_id": "1", "label": "ok"}],
            )

            created = create_training_task(
                session=session,
                training_logs_root=get_settings().training_logs_root,
                capability_name="doc_audit",
                task_name="文档训练",
                framework="pytorch",
                backend_type="cpu",
                annotation_task_id=annotation_task.task_id,
                train_params={"epochs": 3},
            )
            running = update_training_task_status(session, created.task_id, "running")
            logged = append_training_task_log(
                session=session,
                training_logs_root=get_settings().training_logs_root,
                task_id=created.task_id,
                message="epoch=1 loss=0.123",
            )
            completed = update_training_task_status(session, created.task_id, "completed")
            items = list_training_tasks(session)
            detail = get_training_task(session, created.task_id)

        self.assertEqual(running.status, "running")
        self.assertEqual(logged.task_id, created.task_id)
        self.assertEqual(completed.status, "completed")
        self.assertTrue(completed.log_path)
        self.assertEqual(len(items), 1)
        self.assertEqual(detail.task_name, "文档训练")
        log_content = Path(completed.log_path).read_text(encoding="utf-8")
        self.assertIn("训练任务已创建", log_content)
        self.assertIn("epoch=1 loss=0.123", log_content)

    def test_training_task_retry_increments_counter(self) -> None:
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
            created = create_training_task(
                session=session,
                training_logs_root=get_settings().training_logs_root,
                capability_name="ocr_review",
                task_name="OCR 训练",
                framework="pytorch",
                backend_type="cpu",
                annotation_task_id=None,
                train_params={},
            )
            update_training_task_status(session, created.task_id, "failed")
            retried = update_training_task_status(session, created.task_id, "running")

        self.assertEqual(retried.retry_count, 1)
        self.assertEqual(retried.status, "running")


if __name__ == "__main__":
    unittest.main()
