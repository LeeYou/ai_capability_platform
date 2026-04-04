from __future__ import annotations

import unittest

from app.services.license_service import _is_version_allowed


class LicenseServiceTestCase(unittest.TestCase):
    def test_version_constraints_support_prefix_and_numeric_range(self) -> None:
        constraints = {
            "prefix": "v1.",
            "min_version": "v1.2.0",
            "max_version": "v1.10.0",
        }

        self.assertTrue(_is_version_allowed("v1.2.0", constraints))
        self.assertTrue(_is_version_allowed("v1.10.0", constraints))
        self.assertFalse(_is_version_allowed("v2.0.0", constraints))
        self.assertFalse(_is_version_allowed("v1.11.0", constraints))

    def test_version_constraints_require_product_version_when_configured(self) -> None:
        constraints = {"allowed_versions": ["v1.0.0"]}

        self.assertFalse(_is_version_allowed(None, constraints))
        self.assertFalse(_is_version_allowed("", constraints))
        self.assertTrue(_is_version_allowed("v1.0.0", constraints))
        self.assertFalse(_is_version_allowed("v1.0.1", constraints))
