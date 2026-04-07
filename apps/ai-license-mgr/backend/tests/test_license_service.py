from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from app.config import get_settings, reset_settings_cache
from app.db.database import get_session_factory, reset_database_cache
from app.services.audit_service import list_audit_logs
from app.services.license_service import (
    build_hardware_fingerprint,
    create_customer,
    create_key_pair,
    create_license_policy,
    export_license_issue,
    export_license_tool_release,
    get_license_validation_contract,
    get_license_validation_vectors,
    get_license_issue,
    get_license_policy,
    get_license_tool_release,
    isolate_key_pair,
    initialize_database,
    issue_license,
    list_customers,
    list_key_pairs,
    list_license_issues,
    list_license_policies,
    list_license_tool_releases,
    rotate_key_pair,
    sync_default_license_tool_release,
    validate_license_issue,
)


class LicenseServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.host_root = Path(self.temp_dir.name)
        for directory_name in ("data", "license", "logs", "exports"):
            (self.host_root / directory_name).mkdir()
        os.environ["AI_CAP_HOST_ROOT"] = str(self.host_root)
        reset_settings_cache()
        reset_database_cache()
        initialize_database()

    def tearDown(self) -> None:
        reset_database_cache()
        reset_settings_cache()
        os.environ.pop("AI_CAP_HOST_ROOT", None)
        self.temp_dir.cleanup()

    def test_create_customer_and_key_pair(self) -> None:
        with get_session_factory()() as session:
            customer = create_customer(
                session,
                get_settings().audit_log_path,
                customer_code="cust_001",
                customer_name="客户一",
                contact_name="张三",
                contact_email="zhangsan@example.com",
            )
            key_pair = create_key_pair(
                session,
                get_settings().key_pairs_root,
                get_settings().audit_log_path,
                key_name="release-key",
            )

            self.assertEqual(len(list_customers(session)), 1)
            self.assertEqual(len(list_key_pairs(session)), 1)

        self.assertEqual(customer["customer_code"], "cust_001")
        self.assertTrue(Path(key_pair["private_key_path"]).is_file())
        self.assertTrue(Path(key_pair["public_key_path"]).is_file())

    def test_issue_validate_and_export_license(self) -> None:
        with get_session_factory()() as session:
            customer = create_customer(
                session,
                get_settings().audit_log_path,
                customer_code="cust_002",
                customer_name="客户二",
                contact_name=None,
                contact_email=None,
            )
            key_pair = create_key_pair(
                session,
                get_settings().key_pairs_root,
                get_settings().audit_log_path,
                key_name="prod-key",
            )
            hardware_fingerprint = build_hardware_fingerprint(
                {"cpu": "intel-i7", "mac": "00:11:22:33:44:55", "disk": "nvme-sn-001"}
            )
            policy = create_license_policy(
                session,
                get_settings().audit_log_path,
                policy_name="policy-prod",
                customer_id=int(customer["customer_id"]),
                key_pair_id=int(key_pair["key_pair_id"]),
                capability_scope=["ocr", "det"],
                version_constraints={"min_version": "1.0.0", "max_version": "2.0.0"},
                hardware_fingerprint=hardware_fingerprint,
                start_at_cst="2026-04-01T00:00:00+08:00",
                expire_at_cst="2027-04-01T00:00:00+08:00",
                notes="生产授权",
            )
            issue = issue_license(
                session,
                get_settings().license_root,
                get_settings().issue_records_root,
                get_settings().audit_log_path,
                policy_id=int(policy["policy_id"]),
            )
            validation = validate_license_issue(
                session,
                get_settings().audit_log_path,
                issue_record_id=int(issue["issue_record_id"]),
                hardware_fingerprint=hardware_fingerprint,
                capability_name="ocr",
                product_version="1.4.2",
            )
            exported = export_license_issue(
                session,
                get_settings().exports_root,
                get_settings().audit_log_path,
                issue_record_id=int(issue["issue_record_id"]),
                export_format="bin",
            )
            issue_detail = get_license_issue(session, int(issue["issue_record_id"]))

        self.assertEqual(len(list_license_policies(session)), 1)
        self.assertEqual(len(list_license_issues(session)), 1)
        self.assertTrue(validation["valid"])
        self.assertTrue(Path(issue["license_path"]).is_file())
        self.assertTrue((get_settings().license_root / "license.bin").is_file())
        self.assertTrue((get_settings().license_root / "pubkey.pem").is_file())
        self.assertTrue(Path(exported).is_file())
        self.assertEqual(issue_detail["payload"]["customer_code"], "cust_002")

    def test_validate_license_rejects_mismatch(self) -> None:
        with get_session_factory()() as session:
            customer = create_customer(
                session,
                get_settings().audit_log_path,
                customer_code="cust_003",
                customer_name="客户三",
                contact_name=None,
                contact_email=None,
            )
            key_pair = create_key_pair(
                session,
                get_settings().key_pairs_root,
                get_settings().audit_log_path,
                key_name="qa-key",
            )
            policy = create_license_policy(
                session,
                get_settings().audit_log_path,
                policy_name="policy-qa",
                customer_id=int(customer["customer_id"]),
                key_pair_id=int(key_pair["key_pair_id"]),
                capability_scope=["ocr"],
                version_constraints={"allowed_versions": ["1.0.0"]},
                hardware_fingerprint="fp-001",
                start_at_cst="2026-04-01T00:00:00+08:00",
                expire_at_cst="2027-04-01T00:00:00+08:00",
                notes=None,
            )
            issue = issue_license(
                session,
                get_settings().license_root,
                get_settings().issue_records_root,
                get_settings().audit_log_path,
                policy_id=int(policy["policy_id"]),
            )
            validation = validate_license_issue(
                session,
                get_settings().audit_log_path,
                issue_record_id=int(issue["issue_record_id"]),
                hardware_fingerprint="fp-bad",
                capability_name="ocr",
                product_version="1.0.1",
            )

        self.assertFalse(validation["valid"])
        self.assertIn("不匹配", validation["reason"])
        self.assertEqual(validation["code"], "hardware_fingerprint_mismatch")
        self.assertEqual(validation["stage"], "hardware_fingerprint")
        self.assertEqual(validation["details"]["expected_hardware_fingerprint"], "fp-001")

    def test_audit_logs_are_written(self) -> None:
        with get_session_factory()() as session:
            create_customer(
                session,
                get_settings().audit_log_path,
                customer_code="cust_004",
                customer_name="客户四",
                contact_name=None,
                contact_email=None,
            )

        logs = list_audit_logs(get_settings().audit_log_path, limit=20)
        self.assertGreaterEqual(len(logs), 1)
        self.assertEqual(logs[0]["entity_type"], "customer")

    def test_sync_and_export_license_tool_release(self) -> None:
        with get_session_factory()() as session:
            release = sync_default_license_tool_release(
                session,
                get_settings().license_tools_root,
                get_settings().audit_log_path,
            )
            export_path = export_license_tool_release(
                session,
                get_settings().exports_root,
                get_settings().audit_log_path,
                release_id=int(release["release_id"]),
                export_format="archive",
            )
            diagnostics_export = export_license_tool_release(
                session,
                get_settings().exports_root,
                get_settings().audit_log_path,
                release_id=int(release["release_id"]),
                export_format="diagnostics",
            )
            release_detail = get_license_tool_release(session, int(release["release_id"]))

        self.assertEqual(len(list_license_tool_releases(session)), 1)
        self.assertEqual(release_detail["tool_name"], "license_tool")
        self.assertTrue(Path(release["archive_path"]).is_file())
        self.assertTrue(Path(release["manifest_path"]).is_file())
        self.assertTrue(Path(release["readme_path"]).is_file())
        self.assertTrue(Path(export_path).is_file())
        self.assertTrue(Path(diagnostics_export).is_file())
        self.assertTrue((Path(release["manifest_path"]).parent / "LICENSE_DIAGNOSTICS.json").is_file())
        self.assertTrue((Path(release["manifest_path"]).parent / "VALIDATION_VECTORS.json").is_file())
        manifest_payload = Path(release["manifest_path"]).read_text(encoding="utf-8")
        self.assertIn('"version": "1.0.0"', manifest_payload)
        self.assertIn('"diagnostics_version": "1.0"', manifest_payload)

    def test_rotate_key_pair_migrates_active_policies(self) -> None:
        with get_session_factory()() as session:
            customer = create_customer(
                session,
                get_settings().audit_log_path,
                customer_code="cust_rotate",
                customer_name="轮转客户",
                contact_name=None,
                contact_email=None,
            )
            key_pair = create_key_pair(
                session,
                get_settings().key_pairs_root,
                get_settings().audit_log_path,
                key_name="rotate-key",
            )
            policy = create_license_policy(
                session,
                get_settings().audit_log_path,
                policy_name="policy-rotate",
                customer_id=int(customer["customer_id"]),
                key_pair_id=int(key_pair["key_pair_id"]),
                capability_scope=["ocr"],
                version_constraints={},
                hardware_fingerprint=None,
                start_at_cst="2026-04-01T00:00:00+08:00",
                expire_at_cst="2027-04-01T00:00:00+08:00",
                notes=None,
            )
            rotated = rotate_key_pair(
                session,
                get_settings().key_pairs_root,
                get_settings().audit_log_path,
                key_pair_id=int(key_pair["key_pair_id"]),
                new_key_name=None,
                reason="年度轮转",
            )
            policy_after = get_license_policy(session, int(policy["policy_id"]))
            issue = issue_license(
                session,
                get_settings().license_root,
                get_settings().issue_records_root,
                get_settings().audit_log_path,
                policy_id=int(policy["policy_id"]),
            )

        self.assertEqual(rotated["source_key_pair"]["status"], "rotated")
        self.assertEqual(rotated["new_key_pair"]["rotation_version"], 2)
        self.assertEqual(policy_after["key_pair_id"], rotated["new_key_pair"]["key_pair_id"])
        self.assertEqual(issue["key_pair_id"], rotated["new_key_pair"]["key_pair_id"])
        self.assertEqual(rotated["migrated_policy_ids"], [int(policy["policy_id"])])

    def test_isolated_key_pair_blocks_policy_and_issue(self) -> None:
        with get_session_factory()() as session:
            customer = create_customer(
                session,
                get_settings().audit_log_path,
                customer_code="cust_isolate",
                customer_name="隔离客户",
                contact_name=None,
                contact_email=None,
            )
            active_key_pair = create_key_pair(
                session,
                get_settings().key_pairs_root,
                get_settings().audit_log_path,
                key_name="active-key",
            )
            policy = create_license_policy(
                session,
                get_settings().audit_log_path,
                policy_name="policy-isolate",
                customer_id=int(customer["customer_id"]),
                key_pair_id=int(active_key_pair["key_pair_id"]),
                capability_scope=["ocr"],
                version_constraints={},
                hardware_fingerprint=None,
                start_at_cst="2026-04-01T00:00:00+08:00",
                expire_at_cst="2027-04-01T00:00:00+08:00",
                notes=None,
            )
            isolated = isolate_key_pair(
                session,
                get_settings().audit_log_path,
                key_pair_id=int(active_key_pair["key_pair_id"]),
                reason="发现风险",
            )
            with self.assertRaisesRegex(ValueError, "不可用于签发 license"):
                issue_license(
                    session,
                    get_settings().license_root,
                    get_settings().issue_records_root,
                    get_settings().audit_log_path,
                    policy_id=int(policy["policy_id"]),
                )
            with self.assertRaisesRegex(ValueError, "不可用于创建授权策略"):
                create_license_policy(
                    session,
                    get_settings().audit_log_path,
                    policy_name="policy-isolate-new",
                    customer_id=int(customer["customer_id"]),
                    key_pair_id=int(active_key_pair["key_pair_id"]),
                    capability_scope=["ocr"],
                    version_constraints={},
                    hardware_fingerprint=None,
                    start_at_cst="2026-04-01T00:00:00+08:00",
                    expire_at_cst="2027-04-01T00:00:00+08:00",
                    notes=None,
                )

        self.assertEqual(isolated["status"], "isolated")
        self.assertEqual(isolated["status_reason"], "发现风险")

    def test_isolated_key_pair_cannot_create_new_policy(self) -> None:
        with get_session_factory()() as session:
            customer = create_customer(
                session,
                get_settings().audit_log_path,
                customer_code="cust_isolate_2",
                customer_name="隔离客户二",
                contact_name=None,
                contact_email=None,
            )
            key_pair = create_key_pair(
                session,
                get_settings().key_pairs_root,
                get_settings().audit_log_path,
                key_name="isolated-new-policy-key",
            )
            isolate_key_pair(
                session,
                get_settings().audit_log_path,
                key_pair_id=int(key_pair["key_pair_id"]),
                reason="隔离测试",
            )

            with self.assertRaisesRegex(ValueError, "不可用于创建授权策略"):
                create_license_policy(
                    session,
                    get_settings().audit_log_path,
                    policy_name="policy-isolated-fail",
                    customer_id=int(customer["customer_id"]),
                    key_pair_id=int(key_pair["key_pair_id"]),
                    capability_scope=["det"],
                    version_constraints={},
                    hardware_fingerprint=None,
                    start_at_cst="2026-04-01T00:00:00+08:00",
                    expire_at_cst="2027-04-01T00:00:00+08:00",
                    notes=None,
                )

    def test_key_pair_audit_logs_include_rotate_and_isolate(self) -> None:
        with get_session_factory()() as session:
            key_pair = create_key_pair(
                session,
                get_settings().key_pairs_root,
                get_settings().audit_log_path,
                key_name="audit-key",
            )
            rotate_key_pair(
                session,
                get_settings().key_pairs_root,
                get_settings().audit_log_path,
                key_pair_id=int(key_pair["key_pair_id"]),
                new_key_name="audit-key-v2",
                reason="审计轮转",
            )
            isolate_key_pair(
                session,
                get_settings().audit_log_path,
                key_pair_id=int(key_pair["key_pair_id"]) + 1,
                reason="审计隔离",
            )

        logs = list_audit_logs(get_settings().audit_log_path, limit=20)
        actions = [item["action"] for item in logs]
        self.assertIn("rotate", actions)
        self.assertIn("isolate", actions)

    def test_validation_contract_and_vectors_are_available(self) -> None:
        contract = get_license_validation_contract()
        vectors = get_license_validation_vectors()

        self.assertEqual(contract["diagnostics_version"], "1.0")
        self.assertIn("signature_invalid", contract["code_catalog"])
        self.assertEqual(vectors["diagnostics_version"], "1.0")
        self.assertGreaterEqual(len(vectors["license_validation_vectors"]), 5)
        self.assertEqual(
            vectors["fingerprint_vectors"][0]["expected_fingerprint"],
            build_hardware_fingerprint(vectors["fingerprint_vectors"][0]["features"]),
        )

    def test_cross_module_validation_matches_ai_prod_python(self) -> None:
        features = {"cpu": "intel-i7", "disk": "nvme-sn-001", "mac": "00:11:22:33:44:55"}
        with get_session_factory()() as session:
            customer = create_customer(
                session,
                get_settings().audit_log_path,
                customer_code="cust_cross",
                customer_name="跨模块客户",
                contact_name=None,
                contact_email=None,
            )
            key_pair = create_key_pair(
                session,
                get_settings().key_pairs_root,
                get_settings().audit_log_path,
                key_name="cross-key",
            )
            hardware_fingerprint = build_hardware_fingerprint(features)
            policy = create_license_policy(
                session,
                get_settings().audit_log_path,
                policy_name="policy-cross",
                customer_id=int(customer["customer_id"]),
                key_pair_id=int(key_pair["key_pair_id"]),
                capability_scope=["ocr"],
                version_constraints={"min_version": "1.0.0", "max_version": "2.0.0"},
                hardware_fingerprint=hardware_fingerprint,
                start_at_cst="2026-04-01T00:00:00+08:00",
                expire_at_cst="2027-04-01T00:00:00+08:00",
                notes=None,
            )
            issue = issue_license(
                session,
                get_settings().license_root,
                get_settings().issue_records_root,
                get_settings().audit_log_path,
                policy_id=int(policy["policy_id"]),
            )
            mgr_validation = validate_license_issue(
                session,
                get_settings().audit_log_path,
                issue_record_id=int(issue["issue_record_id"]),
                hardware_fingerprint=hardware_fingerprint,
                capability_name="ocr",
                product_version="1.2.0",
            )

        ai_prod_backend_root = Path("/home/runner/work/ai_capability_platform/ai_capability_platform/apps/ai-prod/backend")
        inline_code = "\n".join(
            [
                "import json",
                "import sys",
                "from pathlib import Path",
                "sys.path.insert(0, sys.argv[1])",
                "from app.services.license_service import validate_license_bundle",
                "payload = validate_license_bundle(Path(sys.argv[2]), hardware_features=json.loads(sys.argv[3]), capability_name=sys.argv[4], product_version=sys.argv[5])",
                "print(json.dumps(payload, ensure_ascii=False))",
            ]
        )
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                inline_code,
                str(ai_prod_backend_root),
                str(get_settings().license_root),
                json.dumps(features, ensure_ascii=False),
                "ocr",
                "1.2.0",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        prod_validation = json.loads(result.stdout)

        self.assertTrue(mgr_validation["valid"])
        self.assertEqual(mgr_validation["code"], "license_valid")
        self.assertTrue(prod_validation["valid"])
        self.assertEqual(prod_validation["reason"], mgr_validation["reason"])
