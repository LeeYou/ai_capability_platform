from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import hashlib
import importlib.util
import json
from pathlib import Path
import time

ALLOWED_BACKENDS = {"auto", "gpu", "cpu"}
ALLOWED_EXECUTION_MODES = {"real", "simulated"}


TASK_TYPE_OUTPUT_SCHEMAS: dict[str, dict[str, object]] = {
    "classification": {
        "required_keys": ["label", "score"],
        "sample_output": {"label": "positive", "score": 0.95},
    },
    "detection": {
        "required_keys": ["objects"],
        "sample_output": {"objects": [{"label": "face", "bbox": [0, 0, 100, 100], "score": 0.9}]},
    },
    "ocr": {
        "required_keys": ["text"],
        "sample_output": {"text": "sample text", "regions": [{"text": "sample", "bbox": [0, 0, 50, 20]}]},
    },
    "structured_extraction": {
        "required_keys": ["fields"],
        "sample_output": {"fields": {"key": "value"}, "confidence": {"key": 0.9}},
    },
}


def list_execution_providers() -> list[str]:
    if importlib.util.find_spec("onnxruntime") is None:
        return ["CPUExecutionProvider"]

    import onnxruntime  # type: ignore

    return list(onnxruntime.get_available_providers())


def resolve_execution_backend(requested_backend: str) -> tuple[str, str]:
    normalized_backend = requested_backend.strip().lower()
    if normalized_backend not in ALLOWED_BACKENDS:
        raise ValueError("requested_backend 仅支持 auto/gpu/cpu。")

    providers = list_execution_providers()
    if normalized_backend in {"auto", "gpu"} and "CUDAExecutionProvider" in providers:
        return ("gpu", "CUDAExecutionProvider")
    return ("cpu", "CPUExecutionProvider")


def resolve_test_execution_mode(capability_name: str) -> tuple[str, str | None]:
    from app.services.capability_adapters import get_test_adapter

    adapter = get_test_adapter(capability_name)
    if adapter is None:
        return ("simulated", "未检测到真实测试适配器，当前结果来自仿真推理。")
    return ("real", None)


def validate_expected_output(expected_output: str | None, task_type: str) -> dict[str, object]:
    if expected_output is None or expected_output.strip() == "":
        return {"status": "no_expected_output", "task_type": task_type}
    schema = TASK_TYPE_OUTPUT_SCHEMAS.get(task_type, {})
    required_keys = list(schema.get("required_keys", []))
    try:
        parsed = json.loads(expected_output)
        if isinstance(parsed, dict) and required_keys:
            missing = [key for key in required_keys if key not in parsed]
            if missing:
                return {
                    "status": "schema_mismatch",
                    "task_type": task_type,
                    "missing_keys": missing,
                    "hint": f"{task_type} 类型期望输出应包含 {required_keys}",
                }
            return {"status": "schema_match", "task_type": task_type}
    except (ValueError, TypeError):
        if task_type == "classification":
            return {"status": "label_string", "task_type": task_type}
        return {
            "status": "schema_warning",
            "task_type": task_type,
            "hint": f"{task_type} 类型建议使用 JSON 格式期望输出",
        }
    return {"status": "ok", "task_type": task_type}


def build_execution_evidence(
    *,
    execution_mode: str,
    execution_backend: str,
    provider: str,
    requested_backend: str,
    execution_risk: str | None,
) -> dict[str, object]:
    return {
        "execution_mode": execution_mode,
        "requested_backend": requested_backend,
        "execution_backend": execution_backend,
        "provider": provider,
        "risk_notice": execution_risk,
    }


def execute_case_with_timeout(
    *,
    capability_name: str,
    model_version: str,
    provider: str,
    case_name: str,
    input_path: str,
    timeout_seconds: int,
    task_type: str = "classification",
    model_artifact_path: str = "",
) -> dict[str, object]:
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            execute_case,
            capability_name=capability_name,
            model_version=model_version,
            provider=provider,
            case_name=case_name,
            input_path=input_path,
            task_type=task_type,
            model_artifact_path=model_artifact_path,
        )
        try:
            return future.result(timeout=timeout_seconds)
        except FutureTimeoutError as exc:
            raise TimeoutError("测试执行超时。") from exc


def execute_case(
    *,
    capability_name: str,
    model_version: str,
    provider: str,
    case_name: str,
    input_path: str,
    task_type: str = "classification",
    model_artifact_path: str = "",
) -> dict[str, object]:
    from app.services.capability_adapters import get_test_adapter

    adapter = get_test_adapter(capability_name)
    if adapter is not None and model_artifact_path:
        try:
            payload = adapter.infer(
                capability_name=capability_name,
                model_version=model_version,
                model_artifact_path=model_artifact_path,
                input_path=input_path,
                task_type=task_type,
            )
            raw_output = payload.get("raw_output")
            if not isinstance(raw_output, dict):
                raise ValueError("真实推理返回的 raw_output 非法。")
            actual_output = payload.get("actual_output")
            score = payload.get("score")
            duration_ms = payload.get("duration_ms")
            if not isinstance(actual_output, str):
                raise ValueError("真实推理返回的 actual_output 非法。")
            if not isinstance(score, (int, float)):
                raise ValueError("真实推理返回的 score 非法。")
            if not isinstance(duration_ms, int):
                raise ValueError("真实推理返回的 duration_ms 非法。")
            raw_output.setdefault("provider", provider)
            raw_output.setdefault("task_type", task_type)
            return {
                "actual_output": actual_output,
                "score": float(score),
                "provider": provider,
                "duration_ms": duration_ms,
                "raw_output": raw_output,
                "task_type": task_type,
                "execution_mode": "real",
                "execution_risk": None,
            }
        except Exception as exc:
            fallback = simulate_case_execution(
                capability_name=capability_name,
                model_version=model_version,
                provider=provider,
                case_name=case_name,
                input_path=input_path,
                task_type=task_type,
            )
            fallback["execution_risk"] = f"真实测试适配器执行失败，已回退仿真推理：{exc}"
            return fallback

    fallback = simulate_case_execution(
        capability_name=capability_name,
        model_version=model_version,
        provider=provider,
        case_name=case_name,
        input_path=input_path,
        task_type=task_type,
    )
    fallback["execution_risk"] = "未检测到真实测试适配器，当前结果来自仿真推理。"
    return fallback


def simulate_case_execution(
    *,
    capability_name: str,
    model_version: str,
    provider: str,
    case_name: str,
    input_path: str,
    task_type: str = "classification",
) -> dict[str, object]:
    started = time.perf_counter()
    digest = hashlib.sha256(f"{capability_name}:{model_version}:{case_name}:{input_path}".encode("utf-8")).hexdigest()
    score = round(0.5 + (int(digest[2:6], 16) / 65535) * 0.49, 4)
    duration_ms = max(1, int((time.perf_counter() - started) * 1000))

    if task_type == "detection":
        label = "person" if int(digest[:2], 16) % 2 == 0 else "face"
        x1 = int(digest[6:8], 16)
        y1 = int(digest[8:10], 16)
        x2 = x1 + int(digest[10:12], 16) + 20
        y2 = y1 + int(digest[12:14], 16) + 20
        raw_output = {
            "objects": [{"label": label, "bbox": [x1, y1, x2, y2], "score": score}],
        }
        actual_output = label
    elif task_type == "ocr":
        sample_texts = ["invoice", "contract", "report", "form"]
        text_idx = int(digest[:2], 16) % len(sample_texts)
        raw_output = {
            "text": sample_texts[text_idx],
            "regions": [{"text": sample_texts[text_idx], "bbox": [0, 0, 100, 20]}],
        }
        actual_output = sample_texts[text_idx]
    elif task_type == "structured_extraction":
        raw_output = {
            "fields": {"field_0": f"value_{digest[:4]}", "field_1": f"value_{digest[4:8]}"},
            "confidence": {"field_0": score, "field_1": round(score - 0.05, 4)},
        }
        actual_output = json.dumps(raw_output["fields"], ensure_ascii=False, sort_keys=True)
    else:
        label = "positive" if int(digest[:2], 16) % 2 == 0 else "negative"
        raw_output = {"label": label, "score": score}
        actual_output = label

    raw_output["provider"] = provider
    raw_output["task_type"] = task_type
    return {
        "actual_output": actual_output,
        "score": score,
        "provider": provider,
        "duration_ms": duration_ms,
        "raw_output": raw_output,
        "task_type": task_type,
        "execution_mode": "simulated",
        "execution_risk": None,
    }
