from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest

from app.config import get_settings, reset_settings_cache
from app.db.database import get_session_factory, reset_database_cache
from app.services.registry_service import (
    bind_dataset_to_capability,
    initialize_database,
    list_capabilities,
    list_dataset_bindings,
    register_capability,
    sync_dataset_bindings_from_filesystem,
)


class RegistryServiceTestCase(unittest.TestCase):
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

    def test_register_capability_and_bind_dataset(self) -> None:
        datasets_root = get_settings().datasets_root
        (datasets_root / "face_detect").mkdir()

        with get_session_factory()() as session:
            register_capability(session, capability_name="face_detect", display_name="Face Detect")
            bind_dataset_to_capability(
                session,
                datasets_root=datasets_root,
                capability_name="face_detect",
                dataset_path="face_detect",
            )

            capabilities = list_capabilities(session)
            datasets = list_dataset_bindings(session)

        self.assertEqual(len(capabilities), 1)
        self.assertEqual(capabilities[0].capability_name, "face_detect")
        self.assertEqual(capabilities[0].dataset_status, "ready")
        self.assertEqual(len(datasets), 1)
        self.assertEqual(datasets[0].dataset_path, str((datasets_root / "face_detect").resolve()))

    def test_sync_dataset_bindings_from_filesystem_bootstraps_registry(self) -> None:
        datasets_root = get_settings().datasets_root
        (datasets_root / "doc_audit").mkdir()
        (datasets_root / "ocr_review").mkdir()

        with get_session_factory()() as session:
            sync_dataset_bindings_from_filesystem(session, datasets_root)
            capabilities = list_capabilities(session)
            datasets = list_dataset_bindings(session)

        self.assertEqual([item.capability_name for item in capabilities], ["doc_audit", "ocr_review"])
        self.assertEqual([item.capability_name for item in datasets], ["doc_audit", "ocr_review"])
        self.assertTrue(all(item.source == "datasets_root" for item in datasets))

    def test_sync_dataset_bindings_marks_missing_directory(self) -> None:
        datasets_root = get_settings().datasets_root
        dataset_dir = datasets_root / "face_detect"
        dataset_dir.mkdir()

        with get_session_factory()() as session:
            sync_dataset_bindings_from_filesystem(session, datasets_root)

        dataset_dir.rmdir()

        with get_session_factory()() as session:
            sync_dataset_bindings_from_filesystem(session, datasets_root)
            capabilities = list_capabilities(session)

        self.assertEqual(capabilities[0].dataset_status, "missing")

    def test_bind_dataset_rejects_path_outside_root(self) -> None:
        with get_session_factory()() as session:
            register_capability(session, capability_name="face_detect", display_name="Face Detect")

            with self.assertRaises(ValueError):
                bind_dataset_to_capability(
                    session,
                    datasets_root=get_settings().datasets_root,
                    capability_name="face_detect",
                    dataset_path="../outside",
                )


if __name__ == "__main__":
    unittest.main()
