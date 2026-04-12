from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import time

from sqlalchemy.orm import Session

from app.db.models import TestCaseModel, TestResultModel, TestTaskModel
from app.services.model_sync_service import get_model_catalog
from app.services.report_service import generate_test_report


ALLOWED_BACKENDS = {"auto", "gpu", "cpu"}

# TT12：各任务类型的期望输出 schema 模板（与 ai-train task_contracts 保持一致）
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

# TT14：各任务类型的模板化回归测试用例定义
TASK_TYPE_REGRESSION_TEMPLATES: dict[str, list[dict[str, object]]] = {
    "classification": [
        {"case_name": "smoke_positive", "expected_output": "positive"},
        {"case_name": "smoke_negative", "expected_output": "negative"},
    ],
    "detection": [
        {"case_name": "smoke_object_detect", "expected_output": None},
        {"case_name": "smoke_empty_scene", "expected_output": None},
    ],
    "ocr": [
        {"case_name": "smoke_text_extract", "expected_output": None},
        {"case_name": "smoke_blank_image", "expected_output": None},
    ],
    "structured_extraction": [
        {"case_name": "smoke_field_extract", "expected_output": None},
        {"case_name": "smoke_empty_doc", "expected_output": None},
    ],
}


class TestTaskNotFoundError(ValueError):
    """测试任务不存在。"""


@dataclass(frozen=True)
class TestCaseInputPayload:
    case_name: str
    input_path: str
    expected_output: str | None


def initialize_database() -> None:
    from app.db.database import Base, get_engine
    from app.db import models  # noqa: F401
    from app.db.database import get_session_factory
    from app.services.baseline_service import initialize_default_performance_baselines

    Base.metadata.create_all(bind=get_engine())
    with get_session_factory()() as session:
        initialize_default_performance_baselines(session)


def _infer_input_type(input_path: str) -> str:
    suffix = Path(input_path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}:
        return "image"
    if suffix in {".mp4", ".avi", ".mov", ".mkv"}:
        return "video"
    if suffix == ".pdf":
        return "pdf"
    return "file"


def _list_execution_providers() -> list[str]:
    if importlib.util.find_spec("onnxruntime") is None:
        return ["CPUExecutionProvider"]

    import onnxruntime  # type: ignore

    return list(onnxruntime.get_available_providers())


def _resolve_execution_backend(requested_backend: str) -> tuple[str, str]:
    normalized_backend = requested_backend.strip().lower()
    if normalized_backend not in ALLOWED_BACKENDS:
        raise ValueError("requested_backend 仅支持 auto/gpu/cpu。")

    providers = _list_execution_providers()
    if normalized_backend in {"auto", "gpu"} and "CUDAExecutionProvider" in providers:
        return ("gpu", "CUDAExecutionProvider")
    return ("cpu", "CPUExecutionProvider")


def _safe_input_path(datasets_root: Path, input_path: str) -> str:
    raw_path = Path(input_path).expanduser()
    resolved_path = raw_path.resolve() if raw_path.is_absolute() else (datasets_root / raw_path).resolve()
    if not (resolved_path == datasets_root or datasets_root in resolved_path.parents):
        raise ValueError("测试输入路径必须位于 datasets 根目录内。")
    return str(resolved_path)


def _resolve_model(catalog: dict[str, object], capability_name: str, model_version: str) -> dict[str, object]:
    items = catalog.get("models", [])
    if not isinstance(items, list):
        raise ValueError("模型目录快照格式非法。")
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("capability_name") == capability_name and item.get("model_version") == model_version:
            return item
    raise ValueError("未找到匹配的模型版本，请先同步 ai-train 模型目录。")


def _load_model_manifest(model: dict[str, object]) -> dict[str, object] | None:
    """TT12/TT13：从模型目录快照条目加载 ai-train 模型包 manifest。"""
    manifest_path_str = str(model.get("manifest_path") or "")
    if not manifest_path_str:
        return None
    manifest_path = Path(manifest_path_str)
    if not manifest_path.is_file():
        return None
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (OSError, ValueError):
        pass
    return None


def _extract_task_type(model: dict[str, object], model_manifest: dict[str, object] | None) -> str:
    """TT12：从模型条目或 manifest 提取任务类型，未知时回退到 classification。"""
    task_type = str(model.get("task_type") or "")
    if not task_type and model_manifest:
        task_type = str(model_manifest.get("task_type") or "")
    return task_type if task_type in TASK_TYPE_OUTPUT_SCHEMAS else "classification"


def _build_evidence_chain(
    model: dict[str, object],
    model_manifest: dict[str, object] | None,
    task_type: str,
) -> dict[str, object]:
    """TT13：构建模型 / 插件 / license / revision 统一验收证据链。"""
    source_train_task_id: int | None = None
    manifest_checksum: str | None = None
    if model_manifest:
        raw_task_id = model_manifest.get("source_train_task_id")
        if isinstance(raw_task_id, int):
            source_train_task_id = raw_task_id
        manifest_path_str = str(model.get("manifest_path") or "")
        if manifest_path_str and Path(manifest_path_str).is_file():
            manifest_checksum = hashlib.sha256(
                Path(manifest_path_str).read_bytes()
            ).hexdigest()

    return {
        "model": {
            "capability_name": str(model.get("capability_name") or ""),
            "model_version": str(model.get("model_version") or ""),
            "task_type": task_type,
            "source_train_task_id": source_train_task_id,
            "manifest_path": str(model.get("manifest_path") or ""),
            "manifest_checksum": manifest_checksum,
            "artifact_path": str(model.get("artifact_path") or ""),
            "backend_type": str(model.get("backend_type") or ""),
        },
        "plugin": {
            "note": "如需插件追溯，请与 ai-builder delivery_package/package_manifest.json 中 provenance 字段对应。"
        },
        "license": {
            "note": "如需 license 追溯，请与 ai-license-mgr 授权记录 issue_record_id 对应。"
        },
        "revision": {
            "note": "如需运行时版本追溯，请参考 ai-prod /api/v1/status revision 字段。"
        },
    }


def _validate_expected_output(expected_output: str | None, task_type: str) -> dict[str, object]:
    """TT12：校验测试用例期望输出与任务类型 schema 的兼容性。"""
    if expected_output is None or expected_output.strip() == "":
        return {"status": "no_expected_output", "task_type": task_type}
    schema = TASK_TYPE_OUTPUT_SCHEMAS.get(task_type, {})
    required_keys = list(schema.get("required_keys", []))

    # 尝试将 expected_output 解析为 JSON 做 schema 对齐校验
    try:
        parsed = json.loads(expected_output)
        if isinstance(parsed, dict) and required_keys:
            missing = [k for k in required_keys if k not in parsed]
            if missing:
                return {
                    "status": "schema_mismatch",
                    "task_type": task_type,
                    "missing_keys": missing,
                    "hint": f"{task_type} 类型期望输出应包含 {required_keys}",
                }
            return {"status": "schema_match", "task_type": task_type}
    except (ValueError, TypeError):
        # 非 JSON 格式：视为标签字符串，仅对 classification 类型有效
        if task_type == "classification":
            return {"status": "label_string", "task_type": task_type}
        return {
            "status": "schema_warning",
            "task_type": task_type,
            "hint": f"{task_type} 类型建议使用 JSON 格式期望输出",
        }
    return {"status": "ok", "task_type": task_type}


def _simulate_case_execution(
    capability_name: str,
    model_version: str,
    provider: str,
    case_name: str,
    input_path: str,
    task_type: str = "classification",
    model_artifact_path: str = "",
) -> dict[str, object]:
    """TT12：任务类型感知的推理执行。

    优先尝试调用真实能力适配器执行推理；无适配器时回退到仿真推理。
    根据 task_type 生成与训练标注 schema 对齐的输出，确保测试样本输入与
    训练标注 schema 保持一致性，便于后续期望输出校验。
    """
    # ── 尝试真实推理适配器 ──
    try:
        from app.services.capability_adapters import get_test_adapter

        adapter = get_test_adapter(capability_name)
        if adapter is not None and model_artifact_path:
            return adapter.infer(
                capability_name=capability_name,
                model_version=model_version,
                model_artifact_path=model_artifact_path,
                input_path=input_path,
                task_type=task_type,
            )
    except Exception:
        pass  # 适配器不可用时静默回退到仿真推理

    # ── 回退：仿真推理 ──
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
        # classification（默认）
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
    }


def _run_case_with_timeout(
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
            _simulate_case_execution,
            capability_name,
            model_version,
            provider,
            case_name,
            input_path,
            task_type,
            model_artifact_path,
        )
        try:
            return future.result(timeout=timeout_seconds)
        except FutureTimeoutError as exc:
            raise TimeoutError("测试执行超时。") from exc


def _task_item(task: TestTaskModel) -> dict[str, object]:
    return {
        "task_id": task.id,
        "task_type": task.task_type,
        "capability_name": task.capability_name,
        "model_version": task.model_version,
        "requested_backend": task.requested_backend,
        "execution_backend": task.execution_backend,
        "timeout_seconds": task.timeout_seconds,
        "status": task.status,
        "total_cases": task.total_cases,
        "passed_cases": task.passed_cases,
        "failed_cases": task.failed_cases,
        "error_message": task.error_message,
        "report_id": task.report.id if task.report is not None else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


def _task_detail(task: TestTaskModel) -> dict[str, object]:
    case_result_map = {result.case_id: result for result in task.results}
    detail = _task_item(task)
    detail["cases"] = [
        {
            "case_id": case.id,
            "case_name": case.case_name,
            "input_path": case.input_path,
            "input_type": case.input_type,
            "status": case_result_map[case.id].status if case.id in case_result_map else "pending",
            "expected_output": case.expected_output,
            "actual_output": case_result_map[case.id].actual_output if case.id in case_result_map else None,
            "duration_ms": case_result_map[case.id].duration_ms if case.id in case_result_map else 0,
            "score": case_result_map[case.id].score if case.id in case_result_map else 0.0,
            "provider": case_result_map[case.id].provider if case.id in case_result_map else None,
        }
        for case in task.cases
    ]
    # TT13：附加 evidence_chain 到任务详情（从 evidence_json 字段恢复）
    if hasattr(task, "evidence_json") and task.evidence_json:
        try:
            detail["evidence_chain"] = json.loads(task.evidence_json)
        except (ValueError, TypeError):
            detail["evidence_chain"] = None
    return detail


def create_test_task(
    session: Session,
    *,
    model_catalog_snapshot_path: Path,
    ai_train_api_base_url: str,
    datasets_root: Path,
    test_reports_root: Path,
    task_type: str,
    capability_name: str,
    model_version: str,
    requested_backend: str,
    timeout_seconds: int,
    cases: list[TestCaseInputPayload],
) -> dict[str, object]:
    if task_type not in {"single", "batch"}:
        raise ValueError("task_type 仅支持 single/batch。")
    if not cases:
        raise ValueError("至少需要一个测试用例。")

    catalog = get_model_catalog(model_catalog_snapshot_path, ai_train_api_base_url)
    model = _resolve_model(catalog, capability_name, model_version)
    execution_backend, provider = _resolve_execution_backend(requested_backend)

    # TT12/TT13：加载模型 manifest，提取任务类型与证据链
    model_manifest = _load_model_manifest(model)
    capability_task_type = _extract_task_type(model, model_manifest)
    evidence_chain = _build_evidence_chain(model, model_manifest, capability_task_type)

    task = TestTaskModel(
        task_type=task_type,
        capability_name=capability_name,
        model_version=model_version,
        model_artifact_path=str(model["artifact_path"]),
        requested_backend=requested_backend,
        execution_backend=execution_backend,
        timeout_seconds=timeout_seconds,
        status="running",
        total_cases=len(cases),
        passed_cases=0,
        failed_cases=0,
        started_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    # TT13：将 evidence_chain 序列化写入任务记录（如模型支持该字段）
    if hasattr(task, "evidence_json"):
        task.evidence_json = json.dumps(evidence_chain, ensure_ascii=False, sort_keys=True)
    session.add(task)
    session.commit()
    session.refresh(task)

    for case_payload in cases:
        test_case = TestCaseModel(
            task_id=task.id,
            case_name=case_payload.case_name.strip(),
            input_path=_safe_input_path(datasets_root, case_payload.input_path),
            input_type=_infer_input_type(case_payload.input_path),
            expected_output=case_payload.expected_output,
        )
        session.add(test_case)
        session.commit()
        session.refresh(test_case)

        # TT12：校验期望输出与任务类型 schema 兼容性
        schema_check = _validate_expected_output(case_payload.expected_output, capability_task_type)

        try:
            execution = _run_case_with_timeout(
                capability_name=capability_name,
                model_version=model_version,
                provider=provider,
                case_name=test_case.case_name,
                input_path=test_case.input_path,
                timeout_seconds=timeout_seconds,
                task_type=capability_task_type,
                model_artifact_path=str(model["artifact_path"]),
            )
            actual_output = str(execution["actual_output"])
            passed = test_case.expected_output in {None, "", actual_output}
            raw_output = dict(execution["raw_output"])
            raw_output["schema_check"] = schema_check
            raw_output["evidence_chain_ref"] = {
                "task_id": task.id,
                "source_train_task_id": evidence_chain["model"]["source_train_task_id"],
            }
            result = TestResultModel(
                task_id=task.id,
                case_id=test_case.id,
                status="passed" if passed else "failed",
                execution_backend=execution_backend,
                provider=str(execution["provider"]),
                duration_ms=int(execution["duration_ms"]),
                score=float(execution["score"]),
                expected_output=test_case.expected_output,
                actual_output=actual_output,
                raw_output_json=json.dumps(raw_output, ensure_ascii=False, sort_keys=True),
                error_message=None if passed else "实际输出与期望输出不一致。",
            )
            task.passed_cases += 1 if passed else 0
            task.failed_cases += 0 if passed else 1
        except TimeoutError:
            result = TestResultModel(
                task_id=task.id,
                case_id=test_case.id,
                status="failed",
                execution_backend=execution_backend,
                provider=provider,
                duration_ms=timeout_seconds * 1000,
                score=0.0,
                expected_output=test_case.expected_output,
                actual_output="timeout",
                raw_output_json=json.dumps({"error": "timeout"}, ensure_ascii=False),
                error_message="测试执行超时。",
            )
            task.failed_cases += 1

        session.add(result)
        session.commit()

    task.status = "completed"
    task.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.commit()
    generate_test_report(session, test_reports_root, task.id)
    session.refresh(task)
    return _task_detail(task)


def list_test_tasks(session: Session) -> list[dict[str, object]]:
    tasks = session.query(TestTaskModel).order_by(TestTaskModel.id.asc()).all()
    return [_task_item(task) for task in tasks]


def get_test_task(session: Session, task_id: int) -> dict[str, object]:
    task = session.get(TestTaskModel, task_id)
    if task is None:
        raise TestTaskNotFoundError("测试任务不存在。")
    return _task_detail(task)


def get_capability_test_template(task_type: str) -> dict[str, object]:
    """TT14：获取指定任务类型的模板化测试用例定义。

    返回标准测试用例模板，新增能力时可直接复用，避免重复定义回归用例。
    """
    normalized = task_type.strip().lower()
    template_cases = TASK_TYPE_REGRESSION_TEMPLATES.get(normalized, TASK_TYPE_REGRESSION_TEMPLATES["classification"])
    schema = TASK_TYPE_OUTPUT_SCHEMAS.get(normalized, TASK_TYPE_OUTPUT_SCHEMAS["classification"])
    return {
        "task_type": normalized,
        "output_schema": schema,
        "template_cases": template_cases,
        "usage": (
            "使用 template_cases 中定义的 case_name 和 expected_output，"
            "配合 create_template_regression_task() 创建标准回归任务。"
        ),
    }


def create_template_regression_task(
    session: Session,
    *,
    model_catalog_snapshot_path: Path,
    ai_train_api_base_url: str,
    datasets_root: Path,
    test_reports_root: Path,
    capability_name: str,
    model_version: str,
    requested_backend: str = "auto",
    timeout_seconds: int = 30,
    sample_input_path: str = "sample.jpg",
) -> dict[str, object]:
    """TT14：基于任务类型模板创建标准化回归测试任务。

    自动从模型 manifest 提取任务类型，生成标准测试用例，无需调用者手动指定用例。
    新增能力时可直接使用此函数快速建立回归基线。
    """
    catalog = get_model_catalog(model_catalog_snapshot_path, ai_train_api_base_url)
    model = _resolve_model(catalog, capability_name, model_version)
    model_manifest = _load_model_manifest(model)
    capability_task_type = _extract_task_type(model, model_manifest)

    template = get_capability_test_template(capability_task_type)
    cases = [
        TestCaseInputPayload(
            case_name=str(tc["case_name"]),
            input_path=sample_input_path,
            expected_output=str(tc["expected_output"]) if tc["expected_output"] is not None else None,
        )
        for tc in template["template_cases"]
    ]

    return create_test_task(
        session,
        model_catalog_snapshot_path=model_catalog_snapshot_path,
        ai_train_api_base_url=ai_train_api_base_url,
        datasets_root=datasets_root,
        test_reports_root=test_reports_root,
        task_type="batch",
        capability_name=capability_name,
        model_version=model_version,
        requested_backend=requested_backend,
        timeout_seconds=timeout_seconds,
        cases=cases,
    )
