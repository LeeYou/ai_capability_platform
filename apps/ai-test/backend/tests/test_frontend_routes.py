from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import app.main as main_module
from app.config import reset_settings_cache
from app.db.database import reset_database_cache
from app.main import create_app


class FrontendRoutesTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.host_root = Path(self.temp_dir.name) / "host"
        self.frontend_dist = Path(self.temp_dir.name) / "frontend-dist"
        (self.frontend_dist / "assets").mkdir(parents=True)
        (self.frontend_dist / "index.html").write_text("<html><body>ai-test</body></html>", encoding="utf-8")
        (self.frontend_dist / "assets" / "app.js").write_text("console.log('ai-test')", encoding="utf-8")
        os.environ["AI_CAP_HOST_ROOT"] = str(self.host_root)
        self.original_get_frontend_dist = main_module._get_frontend_dist
        main_module._get_frontend_dist = lambda: self.frontend_dist
        reset_settings_cache()
        reset_database_cache()

    def tearDown(self) -> None:
        reset_database_cache()
        reset_settings_cache()
        os.environ.pop("AI_CAP_HOST_ROOT", None)
        main_module._get_frontend_dist = self.original_get_frontend_dist
        self.temp_dir.cleanup()

    def test_frontend_routes_are_registered_without_breaking_api_routes(self) -> None:
        app = create_app()
        route_paths = {route.path for route in app.routes}
        self.assertIn("/", route_paths)
        self.assertIn("/{frontend_path:path}", route_paths)
        self.assertIn("/api/v1/health", route_paths)
        self.assertIn("/assets", route_paths)

        root_route = next(route for route in app.routes if route.path == "/" and getattr(route, "endpoint", None) is not None)
        root_response = root_route.endpoint()
        self.assertEqual(Path(root_response.path).read_text(encoding="utf-8"), "<html><body>ai-test</body></html>")

        frontend_route = next(route for route in app.routes if route.path == "/{frontend_path:path}")
        nested_response = frontend_route.endpoint("acceptance/workbench")
        self.assertEqual(Path(nested_response.path).read_text(encoding="utf-8"), "<html><body>ai-test</body></html>")
