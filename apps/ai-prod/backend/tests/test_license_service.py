from __future__ import annotations

import unittest

from app.services.license_service import _is_version_allowed, validate_license_bundle


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

    def test_validate_license_bundle_returns_stable_diagnostics(self) -> None:
        from base64 import b64encode
        import json
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from datetime import datetime, timedelta, timezone

        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519

        cst = timezone(timedelta(hours=8))
        with TemporaryDirectory() as temp_dir:
            license_root = Path(temp_dir)
            private_key = ed25519.Ed25519PrivateKey.generate()
            public_key = private_key.public_key()
            payload = {
                "customer_code": "cust_prod",
                "application_name": "ai-prod",
                "operating_system": "linux",
                "min_operating_system_version": "5.4.0",
                "system_architecture": "x86_64",
                "capability_scope": ["ocr"],
                "hardware_fingerprint": None,
                "start_at_cst": (datetime.now(cst) - timedelta(days=1)).isoformat(),
                "expire_at_cst": (datetime.now(cst) + timedelta(days=1)).isoformat(),
                "version_constraints": {"allowed_versions": ["1.0.0"]},
            }
            signature = private_key.sign(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8"))
            (license_root / "license.bin").write_text(
                json.dumps({"algorithm": "ed25519", "payload": payload, "signature": b64encode(signature).decode("ascii")}, ensure_ascii=False),
                encoding="utf-8",
            )
            (license_root / "pubkey.pem").write_bytes(
                public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo,
                )
            )

            result = validate_license_bundle(
                license_root,
                hardware_features={},
                capability_name="face_detect",
                product_version="1.2.0",
                operating_system="linux",
                operating_system_version="5.15.0",
                system_architecture="x86_64",
            )

        self.assertFalse(result["valid"])
        self.assertEqual(result["result"], "failed")
        self.assertEqual(result["code"], "capability_scope_denied")
        self.assertEqual(result["stage"], "capability_scope")
        self.assertEqual(result["diagnostics_version"], "1.0")
        self.assertEqual(result["details"]["requested_capability"], "face_detect")

    def test_validate_license_bundle_rejects_operating_system_mismatch(self) -> None:
        from base64 import b64encode
        import json
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from datetime import datetime, timedelta, timezone

        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519

        cst = timezone(timedelta(hours=8))
        with TemporaryDirectory() as temp_dir:
            license_root = Path(temp_dir)
            private_key = ed25519.Ed25519PrivateKey.generate()
            public_key = private_key.public_key()
            payload = {
                "customer_code": "cust_prod",
                "application_name": "ai-prod",
                "operating_system": "windows",
                "min_operating_system_version": None,
                "system_architecture": None,
                "capability_scope": ["ocr"],
                "hardware_fingerprint": None,
                "start_at_cst": (datetime.now(cst) - timedelta(days=1)).isoformat(),
                "expire_at_cst": (datetime.now(cst) + timedelta(days=1)).isoformat(),
                "version_constraints": {},
            }
            signature = private_key.sign(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8"))
            (license_root / "license.bin").write_text(
                json.dumps({"algorithm": "ed25519", "payload": payload, "signature": b64encode(signature).decode("ascii")}, ensure_ascii=False),
                encoding="utf-8",
            )
            (license_root / "pubkey.pem").write_bytes(
                public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo,
                )
            )

            result = validate_license_bundle(
                license_root,
                hardware_features={},
                capability_name="ocr",
                product_version="1.0.0",
                operating_system="linux",
                operating_system_version="5.15.0",
                system_architecture="x86_64",
            )

        self.assertFalse(result["valid"])
        self.assertEqual(result["code"], "operating_system_denied")
        self.assertEqual(result["stage"], "operating_system")
