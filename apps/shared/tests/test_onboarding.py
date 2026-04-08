"""R13 跨模块新增能力模板化接入集成测试。

验证 onboard_capability.py 生成的接入指南与各模块模板函数语义一致：
- ai-train task_contracts 标注 schema / 训练模板
- ai-builder 构建模板要求
- ai-test 回归用例模板
- ai-prod 运行时接入要求
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

# 将 shared/scripts 加入 path
SCRIPTS_ROOT = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from onboard_capability import (
    SUPPORTED_TASK_TYPES,
    build_annotation_schema,
    build_builder_template,
    build_onboarding_guide,
    build_prod_template,
    build_test_template,
    build_training_template,
    normalize_task_type,
    write_onboarding_guide,
)


class NormalizeTaskTypeTestCase(unittest.TestCase):
    def test_supported_types_accepted(self) -> None:
        for tt in SUPPORTED_TASK_TYPES:
            self.assertEqual(normalize_task_type(tt), tt)

    def test_uppercase_accepted(self) -> None:
        self.assertEqual(normalize_task_type("CLASSIFICATION"), "classification")

    def test_unsupported_type_raises(self) -> None:
        with self.assertRaises(ValueError):
            normalize_task_type("unknown_type")


class AnnotationSchemaTestCase(unittest.TestCase):
    def test_classification_has_required_label(self) -> None:
        schema = build_annotation_schema("classification")
        self.assertIn("label", schema["required_fields"])
        self.assertEqual(schema["label_type"], "single_label")

    def test_detection_has_objects(self) -> None:
        schema = build_annotation_schema("detection")
        self.assertIn("objects", schema["required_fields"])

    def test_ocr_has_text(self) -> None:
        schema = build_annotation_schema("ocr")
        self.assertIn("text", schema["required_fields"])

    def test_structured_extraction_has_fields(self) -> None:
        schema = build_annotation_schema("structured_extraction")
        self.assertIn("fields", schema["required_fields"])


class TrainingTemplateTestCase(unittest.TestCase):
    def test_template_contains_expected_outputs(self) -> None:
        tmpl = build_training_template("my_cap", "classification")
        self.assertIn("weights.bin", tmpl["expected_outputs"])
        self.assertIn("training_manifest.json", tmpl["expected_outputs"])

    def test_capability_name_propagated(self) -> None:
        tmpl = build_training_template("face_detect", "detection")
        self.assertEqual(tmpl["capability_name"], "face_detect")
        self.assertEqual(tmpl["task_type"], "detection")


class BuilderTemplateTestCase(unittest.TestCase):
    def test_plugin_entry_uses_capability_name(self) -> None:
        tmpl = build_builder_template("ocr_engine", "ocr")
        self.assertIn("ocr_engine_plugin_create", tmpl["plugin_entry"])

    def test_required_runtime_assets_present(self) -> None:
        tmpl = build_builder_template("any", "classification")
        self.assertIn("manifest.json", tmpl["required_runtime_assets"])

    def test_pre_delivery_checks_listed(self) -> None:
        tmpl = build_builder_template("any", "detection")
        self.assertIn("plugin_loadability", tmpl["pre_delivery_checks"])


class TestTemplateTestCase(unittest.TestCase):
    def test_all_task_types_have_template_cases(self) -> None:
        for tt in SUPPORTED_TASK_TYPES:
            tmpl = build_test_template("cap", tt)
            self.assertGreaterEqual(len(tmpl["template_cases"]), 1)
            self.assertEqual(tmpl["task_type"], tt)

    def test_evidence_chain_fields_listed(self) -> None:
        tmpl = build_test_template("cap", "classification")
        self.assertIn("source_train_task_id", tmpl["evidence_chain_fields"])

    def test_output_schema_has_required_keys(self) -> None:
        for tt in SUPPORTED_TASK_TYPES:
            tmpl = build_test_template("cap", tt)
            self.assertIn("required_keys", tmpl["output_schema"])
            self.assertGreaterEqual(len(tmpl["output_schema"]["required_keys"]), 1)


class ProdTemplateTestCase(unittest.TestCase):
    def test_admission_checklist_non_empty(self) -> None:
        tmpl = build_prod_template("face", "detection")
        self.assertGreaterEqual(len(tmpl["admission_checklist"]), 1)

    def test_expected_infer_output_present(self) -> None:
        for tt in SUPPORTED_TASK_TYPES:
            tmpl = build_prod_template("cap", tt)
            self.assertIsNotNone(tmpl["expected_infer_output"])


class OnboardingGuideTestCase(unittest.TestCase):
    def _guide(self, tt: str) -> dict[str, object]:
        return build_onboarding_guide("new_cap", tt)

    def test_guide_has_all_sections(self) -> None:
        guide = self._guide("classification")
        for key in (
            "annotation_schema", "training_template", "builder_template",
            "test_template", "prod_template", "onboarding_checklist",
            "modules_involved",
        ):
            self.assertIn(key, guide)

    def test_guide_task_type_propagated(self) -> None:
        for tt in SUPPORTED_TASK_TYPES:
            guide = self._guide(tt)
            self.assertEqual(guide["task_type"], tt)

    def test_checklist_has_12_steps(self) -> None:
        guide = self._guide("ocr")
        self.assertEqual(len(guide["onboarding_checklist"]), 12)

    def test_all_modules_listed(self) -> None:
        guide = self._guide("structured_extraction")
        for mod in ("ai-train", "ai-builder", "ai-test", "ai-prod", "ai-sdk"):
            self.assertIn(mod, guide["modules_involved"])

    def test_checklist_covers_all_modules(self) -> None:
        guide = self._guide("classification")
        covered_modules = {item["module"] for item in guide["onboarding_checklist"]}
        self.assertIn("ai-train", covered_modules)
        self.assertIn("ai-builder", covered_modules)
        self.assertIn("ai-test", covered_modules)
        self.assertIn("ai-prod", covered_modules)


class WriteOnboardingGuideTestCase(unittest.TestCase):
    def test_writes_valid_json(self) -> None:
        with TemporaryDirectory() as tmp:
            out = write_onboarding_guide("demo_cap", "detection", Path(tmp))
            self.assertTrue(out.is_file())
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["capability_name"], "demo_cap")
            self.assertEqual(data["task_type"], "detection")

    def test_creates_output_dir(self) -> None:
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "sub" / "guide"
            out = write_onboarding_guide("cap", "ocr", target)
            self.assertTrue(out.is_file())


if __name__ == "__main__":
    unittest.main()
