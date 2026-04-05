from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.config import get_settings, reset_settings_cache
from app.db.database import get_session_factory, reset_database_cache
from app.services.annotation_service import (
    create_annotation_task,
    get_annotation_task_detail,
    get_annotation_task,
    list_annotation_tasks,
    submit_annotation_task_result,
    update_annotation_task_samples,
)
from app.services.registry_service import bind_dataset_to_capability, initialize_database, register_capability


class AnnotationServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.host_root = Path(self.temp_dir.name)
        (self.host_root / "data").mkdir()
        (self.host_root / "datasets").mkdir()

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

    def test_create_annotation_task_requires_bound_dataset(self) -> None:
        with get_session_factory()() as session:
            register_capability(session, capability_name="face_detect", display_name="Face Detect")
            with self.assertRaises(ValueError):
                create_annotation_task(
                    session=session,
                    capability_name="face_detect",
                    task_name="首批标注",
                    sample_total=10,
                )

    def test_submit_annotation_task_persists_result_and_updates_status(self) -> None:
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
            created = create_annotation_task(
                session=session,
                capability_name="face_detect",
                task_name="首批标注",
                sample_total=2,
            )
            updated = submit_annotation_task_result(
                session=session,
                annotation_tasks_root=get_settings().annotation_tasks_root,
                task_id=created.task_id,
                annotations=[{"sample_id": "1", "label": "ok"}],
            )
            completed = submit_annotation_task_result(
                session=session,
                annotation_tasks_root=get_settings().annotation_tasks_root,
                task_id=created.task_id,
                annotations=[
                    {"sample_id": "1", "label": "ok"},
                    {"sample_id": "2", "label": "ng"},
                ],
            )

        self.assertEqual(updated.status, "annotating")
        self.assertEqual(updated.labeled_count, 1)
        self.assertEqual(completed.status, "completed")
        self.assertTrue(completed.result_path)

        payload = json.loads(Path(completed.result_path).read_text(encoding="utf-8"))
        self.assertEqual(payload["task_name"], "首批标注")
        self.assertEqual(payload["labeled_count"], 2)
        self.assertEqual(len(payload["annotations"]), 2)

    def test_list_and_get_annotation_tasks(self) -> None:
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
            created = create_annotation_task(
                session=session,
                capability_name="doc_audit",
                task_name="文档审核标注",
                sample_total=5,
            )
            items = list_annotation_tasks(session)
            detail = get_annotation_task(session, created.task_id)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].task_name, "文档审核标注")
        self.assertEqual(detail.task_id, created.task_id)
        self.assertEqual(detail.status, "pending")

    def test_submit_annotation_task_rejects_empty_item(self) -> None:
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
            created = create_annotation_task(
                session=session,
                capability_name="face_detect",
                task_name="异常校验",
                sample_total=1,
            )

            with self.assertRaises(ValueError):
                submit_annotation_task_result(
                    session=session,
                    annotation_tasks_root=get_settings().annotation_tasks_root,
                    task_id=created.task_id,
                    annotations=[{}],
                )

    def test_update_annotation_task_samples_exposes_sample_level_detail(self) -> None:
        datasets_root = get_settings().datasets_root
        (datasets_root / "layout_review").mkdir()

        with get_session_factory()() as session:
            register_capability(session, capability_name="layout_review", display_name="Layout Review")
            bind_dataset_to_capability(
                session=session,
                datasets_root=datasets_root,
                capability_name="layout_review",
                dataset_path="layout_review",
            )
            created = create_annotation_task(
                session=session,
                capability_name="layout_review",
                task_name="版面样本标注",
                sample_total=2,
            )
            updated = update_annotation_task_samples(
                session=session,
                annotation_tasks_root=get_settings().annotation_tasks_root,
                task_id=created.task_id,
                annotations=[{"sample_id": "sample_1", "label": "title", "bbox": [0, 0, 10, 10]}],
                mark_submitted=False,
            )
            detail = get_annotation_task_detail(
                session=session,
                annotation_tasks_root=get_settings().annotation_tasks_root,
                task_id=created.task_id,
            )

        self.assertEqual(updated.status, "annotating")
        self.assertEqual(len(detail.sample_items), 2)
        self.assertEqual(detail.sample_items[0]["status"], "labeled")
        self.assertEqual(detail.sample_items[0]["annotation"]["label"], "title")
        self.assertEqual(detail.sample_items[1]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
