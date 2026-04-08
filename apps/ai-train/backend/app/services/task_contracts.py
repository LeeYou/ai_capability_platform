from __future__ import annotations

from collections.abc import Mapping
from typing import Any


SCHEMA_VERSION = "1.0"
DEFAULT_TASK_TYPE = "classification"
SUPPORTED_TASK_TYPES = {
    "classification",
    "detection",
    "ocr",
    "structured_extraction",
}


def normalize_task_type(task_type: str | None) -> str:
    normalized = (task_type or DEFAULT_TASK_TYPE).strip().lower()
    if normalized not in SUPPORTED_TASK_TYPES:
        supported_values = " / ".join(sorted(SUPPORTED_TASK_TYPES))
        raise ValueError(f"task_type 仅支持 {supported_values}。")
    return normalized


def default_input_type_for_task(task_type: str) -> str:
    normalized = normalize_task_type(task_type)
    if normalized == "structured_extraction":
        return "document"
    return "image"


def build_annotation_schema(task_type: str) -> dict[str, object]:
    normalized = normalize_task_type(task_type)
    schema_map: dict[str, dict[str, object]] = {
        "classification": {
            "required_fields": ["label"],
            "optional_fields": ["note", "attributes"],
            "label_type": "single_label",
            "sample_contract": {
                "label": "string",
                "note": "string?",
                "attributes": "object?",
            },
        },
        "detection": {
            "required_fields": ["objects"],
            "optional_fields": ["note"],
            "label_type": "multi_object",
            "sample_contract": {
                "objects": [
                    {
                        "label": "string",
                        "bbox": "[x1, y1, x2, y2]",
                    }
                ],
                "note": "string?",
            },
        },
        "ocr": {
            "required_fields": ["text"],
            "optional_fields": ["regions", "note"],
            "label_type": "sequence",
            "sample_contract": {
                "text": "string",
                "regions": [
                    {
                        "text": "string",
                        "bbox": "[x1, y1, x2, y2]",
                    }
                ],
                "note": "string?",
            },
        },
        "structured_extraction": {
            "required_fields": ["fields"],
            "optional_fields": ["note", "confidence"],
            "label_type": "field_map",
            "sample_contract": {
                "fields": {"field_name": "string|number|boolean"},
                "confidence": {"field_name": "number"},
                "note": "string?",
            },
        },
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "task_type": normalized,
        **schema_map[normalized],
    }


def build_template_bundle(capability_name: str, task_type: str) -> dict[str, object]:
    normalized_task_type = normalize_task_type(task_type)
    normalized_capability_name = capability_name.strip()
    return {
        "schema_version": SCHEMA_VERSION,
        "task_type": normalized_task_type,
        "training_template": {
            "capability_name": normalized_capability_name,
            "entrypoint": "python train_runner.py --config train_config.json",
            "dataset_format": f"{normalized_task_type}_dataset",
            "default_train_params": {
                "epochs": 3,
                "batch_size": 4,
                "learning_rate": 0.001,
            },
            "expected_outputs": ["weights.bin", "metrics.json", "training_manifest.json"],
        },
        "test_template": {
            "recommended_task_type": "acceptance",
            "smoke_inputs": ["sample_001"],
            "expected_report_sections": ["research", "delivery"],
            "task_type": normalized_task_type,
        },
        "inference_template": {
            "input_contract": build_annotation_schema(normalized_task_type)["sample_contract"],
            "output_contract": {
                "classification": {"label": "string", "score": "number"},
                "detection": {"objects": [{"label": "string", "bbox": "[x1,y1,x2,y2]", "score": "number"}]},
                "ocr": {"text": "string", "regions": [{"text": "string", "bbox": "[x1,y1,x2,y2]"}]},
                "structured_extraction": {"fields": {"field_name": "string"}, "confidence": {"field_name": "number"}},
            }[normalized_task_type],
        },
        "builder_template": {
            "plugin_entry": f"{normalized_capability_name}_plugin_create",
            "required_runtime_assets": ["manifest.json", "preprocess.json", "labels.json"],
            "task_type": normalized_task_type,
        },
        "manifest_template": {
            "required_fields": [
                "capability_name",
                "task_type",
                "model_version",
                "checksum",
                "runtime_contract",
                "delivery_metadata",
            ],
            "schema_path": "apps/shared/schemas/manifest_model.json",
        },
    }


def validate_annotation_payload(task_type: str, item: Mapping[str, Any], index: int) -> dict[str, Any]:
    normalized_task_type = normalize_task_type(task_type)
    sample_id = item.get("sample_id")
    if not isinstance(sample_id, str) or not sample_id.strip():
        raise ValueError(f"annotations[{index}] 缺失 sample_id。")

    normalized: dict[str, Any] = {"sample_id": sample_id.strip()}
    if normalized_task_type == "classification":
        label = item.get("label")
        if not isinstance(label, str) or not label.strip():
            raise ValueError(f"annotations[{index}] 缺失 label。")
        normalized["label"] = label.strip()
        note = item.get("note")
        if note is not None:
            if not isinstance(note, str):
                raise ValueError(f"annotations[{index}].note 必须为字符串。")
            normalized["note"] = note.strip()
        attributes = item.get("attributes")
        if attributes is not None:
            if not isinstance(attributes, dict):
                raise ValueError(f"annotations[{index}].attributes 必须为对象。")
            normalized["attributes"] = dict(attributes)
        return normalized

    if normalized_task_type == "detection":
        objects = item.get("objects")
        if not isinstance(objects, list) or not objects:
            raise ValueError(f"annotations[{index}] 缺失 objects。")
        normalized_objects: list[dict[str, Any]] = []
        for object_index, current in enumerate(objects):
            if not isinstance(current, dict):
                raise ValueError(f"annotations[{index}].objects[{object_index}] 必须为对象。")
            label = current.get("label")
            bbox = current.get("bbox")
            if not isinstance(label, str) or not label.strip():
                raise ValueError(f"annotations[{index}].objects[{object_index}] 缺失 label。")
            if not isinstance(bbox, list) or len(bbox) != 4 or any(not isinstance(value, (int, float)) for value in bbox):
                raise ValueError(f"annotations[{index}].objects[{object_index}] 缺失合法 bbox。")
            normalized_objects.append({"label": label.strip(), "bbox": bbox})
        normalized["objects"] = normalized_objects
        note = item.get("note")
        if note is not None:
            if not isinstance(note, str):
                raise ValueError(f"annotations[{index}].note 必须为字符串。")
            normalized["note"] = note.strip()
        return normalized

    if normalized_task_type == "ocr":
        text = item.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"annotations[{index}] 缺失 text。")
        normalized["text"] = text.strip()
        regions = item.get("regions")
        if regions is not None:
            if not isinstance(regions, list):
                raise ValueError(f"annotations[{index}].regions 必须为数组。")
            normalized_regions: list[dict[str, Any]] = []
            for region_index, current in enumerate(regions):
                if not isinstance(current, dict):
                    raise ValueError(f"annotations[{index}].regions[{region_index}] 必须为对象。")
                region_text = current.get("text")
                bbox = current.get("bbox")
                if not isinstance(region_text, str) or not region_text.strip():
                    raise ValueError(f"annotations[{index}].regions[{region_index}] 缺失 text。")
                if not isinstance(bbox, list) or len(bbox) != 4 or any(not isinstance(value, (int, float)) for value in bbox):
                    raise ValueError(f"annotations[{index}].regions[{region_index}] 缺失合法 bbox。")
                normalized_regions.append({"text": region_text.strip(), "bbox": bbox})
            normalized["regions"] = normalized_regions
        note = item.get("note")
        if note is not None:
            if not isinstance(note, str):
                raise ValueError(f"annotations[{index}].note 必须为字符串。")
            normalized["note"] = note.strip()
        return normalized

    fields = item.get("fields")
    if not isinstance(fields, dict) or not fields:
        raise ValueError(f"annotations[{index}] 缺失 fields。")
    if any(not isinstance(key, str) or not key.strip() for key in fields):
        raise ValueError(f"annotations[{index}].fields 包含非法字段名。")
    normalized["fields"] = dict(fields)
    confidence = item.get("confidence")
    if confidence is not None:
        if not isinstance(confidence, dict) or any(not isinstance(key, str) or not isinstance(value, (int, float)) for key, value in confidence.items()):
            raise ValueError(f"annotations[{index}].confidence 必须为数字对象。")
        normalized["confidence"] = dict(confidence)
    note = item.get("note")
    if note is not None:
        if not isinstance(note, str):
            raise ValueError(f"annotations[{index}].note 必须为字符串。")
        normalized["note"] = note.strip()
    return normalized


def build_training_input(
    capability_name: str,
    task_type: str,
    annotations: list[dict[str, Any]],
    dataset_path: str,
) -> dict[str, object]:
    normalized_task_type = normalize_task_type(task_type)
    samples: list[dict[str, object]] = []
    label_space: set[str] = set()
    for current in annotations:
        sample_id = str(current.get("sample_id", "")).strip()
        if not sample_id:
            continue
        sample_payload: dict[str, object] = {
            "sample_id": sample_id,
            "dataset_path": dataset_path,
        }
        if normalized_task_type == "classification":
            label = str(current["label"]).strip()
            label_space.add(label)
            sample_payload["label"] = label
            sample_payload["attributes"] = current.get("attributes", {})
        elif normalized_task_type == "detection":
            objects = current.get("objects", [])
            labels = [str(item["label"]).strip() for item in objects if isinstance(item, dict) and isinstance(item.get("label"), str)]
            label_space.update(labels)
            sample_payload["objects"] = objects
            sample_payload["object_count"] = len(objects) if isinstance(objects, list) else 0
        elif normalized_task_type == "ocr":
            sample_payload["text"] = current.get("text", "")
            sample_payload["regions"] = current.get("regions", [])
        else:
            sample_payload["fields"] = current.get("fields", {})
            sample_payload["confidence"] = current.get("confidence", {})
            label_space.update(str(key).strip() for key in sample_payload["fields"] if str(key).strip())
        samples.append(sample_payload)

    return {
        "schema_version": SCHEMA_VERSION,
        "capability_name": capability_name,
        "task_type": normalized_task_type,
        "dataset_path": dataset_path,
        "sample_count": len(samples),
        "label_space": sorted(label_space),
        "samples": samples,
    }


def build_adapter_summary(training_input: Mapping[str, Any]) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "task_type": training_input.get("task_type", DEFAULT_TASK_TYPE),
        "sample_count": training_input.get("sample_count", 0),
        "label_space_size": len(training_input.get("label_space", [])) if isinstance(training_input.get("label_space"), list) else 0,
        "adapter_status": "ready",
    }
