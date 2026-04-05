from __future__ import annotations

import json
from pathlib import Path
import unittest


REPO_ROOT = Path("/home/runner/work/ai_capability_platform/ai_capability_platform")
SHARED_ROOT = REPO_ROOT / "apps" / "shared"
SCHEMAS_ROOT = SHARED_ROOT / "schemas"
EXAMPLES_ROOT = SHARED_ROOT / "examples"


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_matches_schema(test_case: unittest.TestCase, schema: dict[str, object], payload: object, *, path: str = "$") -> None:
    schema_type = schema.get("type")
    if schema_type == "object":
        test_case.assertIsInstance(payload, dict, f"{path} 必须为对象")
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        assert isinstance(payload, dict)
        for key in required:
            test_case.assertIn(key, payload, f"{path} 缺少字段 {key}")
        for key, property_schema in properties.items():
            if key in payload and isinstance(property_schema, dict):
                _assert_matches_schema(test_case, property_schema, payload[key], path=f"{path}.{key}")
        return

    if schema_type == "array":
        test_case.assertIsInstance(payload, list, f"{path} 必须为数组")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(payload):
                _assert_matches_schema(test_case, item_schema, item, path=f"{path}[{index}]")
        return

    if schema_type == "string":
        test_case.assertIsInstance(payload, str, f"{path} 必须为字符串")
        return

    if schema_type == "integer":
        test_case.assertIsInstance(payload, int, f"{path} 必须为整数")
        return

    if schema_type == "boolean":
        test_case.assertIsInstance(payload, bool, f"{path} 必须为布尔值")
        return


class SharedSchemaAssetsTestCase(unittest.TestCase):
    def test_all_schema_files_are_valid_json(self) -> None:
        schema_paths = sorted(SCHEMAS_ROOT.glob("*.json"))
        self.assertGreaterEqual(len(schema_paths), 7)
        for path in schema_paths:
            payload = _load_json(path)
            self.assertIn("$schema", payload)
            self.assertIn("title", payload)
            self.assertIn("type", payload)

    def test_examples_match_schemas(self) -> None:
        example_to_schema = {
            "error_codes.example.json": "error_codes.json",
            "api_response_success.example.json": "api_response.json",
            "manifest_model.example.json": "manifest_model.json",
            "manifest_build.example.json": "manifest_build.json",
            "manifest_sdk.example.json": "manifest_sdk.json",
            "license.example.json": "license.json",
            "capability_metadata.example.json": "capability_metadata.json",
            "checksum_entry.example.json": "checksum_entry.json",
            "acceptance_checklist.example.json": "acceptance_checklist.json",
            "version_manifest.example.json": "version_manifest.json",
            "delivery_summary.example.json": "delivery_summary.json",
            "mount_template.example.json": "mount_template.json",
            "tools_bundle.example.json": "tools_bundle.json",
            "docs_bundle.example.json": "docs_bundle.json",
        }
        for example_name, schema_name in example_to_schema.items():
            schema = _load_json(SCHEMAS_ROOT / schema_name)
            payload = _load_json(EXAMPLES_ROOT / example_name)
            _assert_matches_schema(self, schema, payload)
