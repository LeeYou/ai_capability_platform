from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.config import reset_settings_cache
from app.db.database import reset_database_cache
from app.main import create_app
from app.services.runtime_service import initialize_database


class ApiRoutesTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.host_root = Path(self.temp_dir.name) / "host"
        os.environ["AI_CAP_HOST_ROOT"] = str(self.host_root)
        reset_settings_cache()
        reset_database_cache()
        initialize_database()
        self.app = create_app()

    def tearDown(self) -> None:
        reset_database_cache()
        reset_settings_cache()
        os.environ.pop("AI_CAP_HOST_ROOT", None)
        self.temp_dir.cleanup()

    def test_public_runtime_routes_are_not_exposed_by_python_shell(self) -> None:
        route_paths = {route.path for route in self.app.routes}
        self.assertNotIn("/api/v1/health", route_paths)
        self.assertNotIn("/api/v1/capabilities", route_paths)
        self.assertNotIn("/api/v1/license/status", route_paths)
        self.assertNotIn("/api/v1/admin/reload", route_paths)

    def test_internal_diagnostic_routes_remain_available(self) -> None:
        route_paths = {route.path for route in self.app.routes}
        self.assertIn("/internal/admin/revisions", route_paths)
        self.assertIn("/internal/admin/operations", route_paths)
        self.assertIn("/internal/audit-logs", route_paths)
