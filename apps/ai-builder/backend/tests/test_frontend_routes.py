from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fastapi.testclient import TestClient

from app.config import reset_settings_cache
from app.db.database import reset_database_cache
from app.main import create_app


class FrontendRoutesTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.host_root = Path(self.temp_dir.name) / "host"
        self.frontend_dist = Path(self.temp_dir.name) / "frontend-dist"
        (self.frontend_dist / "assets").mkdir(parents=True)
        (self.frontend_dist / "index.html").write_text("<html><body>ai-builder</body></html>", encoding="utf-8")
        (self.frontend_dist / "assets" / "app.js").write_text("console.log('ai-builder')", encoding="utf-8")
        os.environ["AI_CAP_HOST_ROOT"] = str(self.host_root)
        os.environ["AI_CAP_FRONTEND_DIST"] = str(self.frontend_dist)
        reset_settings_cache()
        reset_database_cache()

    def tearDown(self) -> None:
        reset_database_cache()
        reset_settings_cache()
        os.environ.pop("AI_CAP_HOST_ROOT", None)
        os.environ.pop("AI_CAP_FRONTEND_DIST", None)
        self.temp_dir.cleanup()

    def test_frontend_root_and_assets_are_served_without_breaking_api_routes(self) -> None:
        with TestClient(create_app()) as client:
            root_response = client.get("/")
            self.assertEqual(root_response.status_code, 200)
            self.assertIn("text/html", root_response.headers["content-type"])
            self.assertIn("ai-builder", root_response.text)

            nested_response = client.get("/build/workbench")
            self.assertEqual(nested_response.status_code, 200)
            self.assertIn("ai-builder", nested_response.text)

            asset_response = client.get("/assets/app.js")
            self.assertEqual(asset_response.status_code, 200)
            self.assertIn("console.log", asset_response.text)

            health_response = client.get("/api/v1/health")
            self.assertEqual(health_response.status_code, 200)
            self.assertEqual(health_response.json()["service"], "ai-builder")
