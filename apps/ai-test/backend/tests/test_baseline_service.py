from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.api.routes import create_or_update_performance_baseline, get_performance_baselines
from app.config import reset_settings_cache
from app.db.database import get_session_factory, reset_database_cache
from app.models import UpsertPerformanceBaselineRequest
from app.services.baseline_service import get_performance_baseline
from app.services.test_service import initialize_database


class BaselineServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.host_root = Path(self.temp_dir.name)
        (self.host_root / "data").mkdir()
        os.environ["AI_CAP_HOST_ROOT"] = str(self.host_root)
        reset_settings_cache()
        reset_database_cache()
        initialize_database()

    def tearDown(self) -> None:
        reset_database_cache()
        reset_settings_cache()
        os.environ.pop("AI_CAP_HOST_ROOT", None)
        self.temp_dir.cleanup()

    def test_initialize_database_creates_default_baselines(self) -> None:
        with get_session_factory()() as session:
            baselines = get_performance_baselines(session=session)
            infer_default = get_performance_baseline(session, capability_name="ocr_review", scenario_name="infer_default")
        self.assertGreaterEqual(len(baselines.items), 1)
        self.assertIsNotNone(infer_default)
        self.assertEqual(infer_default["latency_max_ms"], 5000)

    def test_create_or_update_performance_baseline(self) -> None:
        with get_session_factory()() as session:
            payload = create_or_update_performance_baseline(
                UpsertPerformanceBaselineRequest(
                    capability_name="ocr_review",
                    scenario_name="pressure_default",
                    p95_max_ms=1800,
                    p99_max_ms=2500,
                    success_rate_min=0.98,
                    throughput_min_rps=5.5,
                    description="ocr_review 压测阈值",
                ),
                session=session,
            )
            stored = get_performance_baseline(session, capability_name="ocr_review", scenario_name="pressure_default")
        self.assertEqual(payload.capability_name, "ocr_review")
        self.assertIsNotNone(stored)
        self.assertEqual(stored["p95_max_ms"], 1800)
        self.assertEqual(stored["throughput_min_rps"], 5.5)
