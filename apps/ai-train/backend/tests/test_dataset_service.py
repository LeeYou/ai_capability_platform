from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import uuid

from app.services.dataset_service import scan_dataset_bindings


class DatasetServiceTestCase(unittest.TestCase):
    def test_scan_dataset_bindings_returns_sorted_directories(self) -> None:
        with TemporaryDirectory() as temp_dir:
            datasets_root = Path(temp_dir)
            (datasets_root / "face_detect").mkdir()
            (datasets_root / "doc_audit").mkdir()
            (datasets_root / "notes.txt").write_text("ignore", encoding="utf-8")

            items = scan_dataset_bindings(datasets_root)

            self.assertEqual([item.capability_name for item in items], ["doc_audit", "face_detect"])
            self.assertTrue(all(item.dataset_status == "ready" for item in items))

    def test_scan_dataset_bindings_returns_empty_list_when_root_missing(self) -> None:
        missing_path = Path("/tmp") / f"ai-capability-platform-missing-{uuid.uuid4()}"
        items = scan_dataset_bindings(missing_path)
        self.assertEqual(items, [])


if __name__ == "__main__":
    unittest.main()
