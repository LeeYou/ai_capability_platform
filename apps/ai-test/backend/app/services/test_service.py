from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import TestCaseModel, TestResultModel, TestTaskModel
from app.services.model_sync_service import get_model_catalog
from app.services.report_service import generate_test_report
from app.services.test_execution_service import (
    TASK_TYPE_OUTPUT_SCHEMAS,
    build_execution_evidence,
    execute_case_with_timeout,
    resolve_execution_backend,
    resolve_test_execution_mode,
    simulate_case_execution,
    validate_expected_output,
)


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
    execution_metadata: dict[str, object],
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
        "execution": execution_metadata,
    }


def _validate_expected_output(expected_output: str | None, task_type: str) -> dict[str, object]:
    return validate_expected_output(expected_output, task_type)


def _simulate_case_execution(
    capability_name: str,
    model_version: str,
    provider: str,
    case_name: str,
    input_path: str,
    task_type: str = "classification",
    model_artifact_path: str = "",
) -> dict[str, object]:
    return simulate_case_execution(
        capability_name=capability_name,
        model_version=model_version,
        provider=provider,
        case_name=case_name,
        input_path=input_path,
        task_type=task_type,
    )


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
    return execute_case_with_timeout(
        capability_name=capability_name,
        model_version=model_version,
        provider=provider,
        case_name=case_name,
        input_path=input_path,
        timeout_seconds=timeout_seconds,
        task_type=task_type,
        model_artifact_path=model_artifact_path,
    )


def _task_execution_metadata(task: TestTaskModel) -> tuple[str, str | None, dict[str, object] | None]:
    if task.evidence_json:
        try:
            evidence_chain = json.loads(task.evidence_json)
            if isinstance(evidence_chain, dict):
                execution = evidence_chain.get("execution")
                if isinstance(execution, dict):
                    execution_mode = execution.get("execution_mode")
                    execution_risk = execution.get("risk_notice")
                    if isinstance(execution_mode, str):
                        return (
                            execution_mode,
                            execution_risk if isinstance(execution_risk, str) and execution_risk else None,
                            evidence_chain,
                        )
                return ("simulated", None, evidence_chain)
        except (ValueError, TypeError):
            pass
    return ("simulated", None, None)


def _task_item(task: TestTaskModel) -> dict[str, object]:
    execution_mode, execution_risk, _ = _task_execution_metadata(task)
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
        "execution_mode": execution_mode,
        "execution_risk": execution_risk,
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
    _, _, evidence_chain = _task_execution_metadata(task)
    detail["evidence_chain"] = evidence_chain
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
    execution_mode, execution_risk = resolve_test_execution_mode(capability_name)

    model_manifest = _load_model_manifest(model)
    capability_task_type = _extract_task_type(model, model_manifest)
    evidence_chain = _build_evidence_chain(
        model,
        model_manifest,
        capability_task_type,
        build_execution_evidence(
            execution_mode=execution_mode,
            execution_backend=execution_backend,
            provider=provider,
            requested_backend=requested_backend,
            execution_risk=execution_risk,
        ),
    )

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
    if hasattr(task, "evidence_json"):
        task.evidence_json = json.dumps(evidence_chain, ensure_ascii=False, sort_keys=True)
    session.add(task)
    session.flush()

    persisted_cases: list[TestCaseModel] = []
    for case_payload in cases:
        test_case = TestCaseModel(
            task_id=task.id,
            case_name=case_payload.case_name.strip(),
            input_path=_safe_input_path(datasets_root, case_payload.input_path),
            input_type=_infer_input_type(case_payload.input_path),
            expected_output=case_payload.expected_output,
        )
        session.add(test_case)
        persisted_cases.append(test_case)
    session.flush()

    persisted_results: list[TestResultModel] = []
    final_execution_mode = execution_mode
    final_execution_risk = execution_risk
    for test_case, case_payload in zip(persisted_cases, cases, strict=False):
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
            case_execution_mode = str(execution.get("execution_mode") or "simulated")
            case_execution_risk = execution.get("execution_risk")
            if case_execution_mode == "simulated":
                final_execution_mode = "simulated"
            if isinstance(case_execution_risk, str) and case_execution_risk:
                final_execution_risk = case_execution_risk
            raw_output["schema_check"] = schema_check
            raw_output["execution_mode"] = case_execution_mode
            raw_output["execution_risk"] = case_execution_risk
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
            if final_execution_risk is None:
                final_execution_risk = "测试任务发生超时，请结合真实/仿真执行模式复核结果。"

        session.add(result)
        persisted_results.append(result)

    evidence_chain["execution"] = build_execution_evidence(
        execution_mode=final_execution_mode,
        execution_backend=execution_backend,
        provider=provider,
        requested_backend=requested_backend,
        execution_risk=final_execution_risk,
    )
    task.evidence_json = json.dumps(evidence_chain, ensure_ascii=False, sort_keys=True)
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
