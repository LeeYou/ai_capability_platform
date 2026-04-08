from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from datetime import UTC, datetime
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


def _simulate_case_execution(
    capability_name: str,
    model_version: str,
    provider: str,
    case_name: str,
    input_path: str,
) -> dict[str, object]:
    started = time.perf_counter()
    digest = hashlib.sha256(f"{capability_name}:{model_version}:{case_name}:{input_path}".encode("utf-8")).hexdigest()
    label = "positive" if int(digest[:2], 16) % 2 == 0 else "negative"
    score = round(0.5 + (int(digest[2:6], 16) / 65535) * 0.49, 4)
    duration_ms = max(1, int((time.perf_counter() - started) * 1000))
    return {
        "label": label,
        "score": score,
        "provider": provider,
        "duration_ms": duration_ms,
        "raw_output": {"label": label, "score": score, "provider": provider},
    }


def _run_case_with_timeout(
    capability_name: str,
    model_version: str,
    provider: str,
    case_name: str,
    input_path: str,
    timeout_seconds: int,
) -> dict[str, object]:
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            _simulate_case_execution,
            capability_name,
            model_version,
            provider,
            case_name,
            input_path,
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
        started_at=datetime.now(UTC).replace(tzinfo=None),
    )
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

        try:
            execution = _run_case_with_timeout(
                capability_name=capability_name,
                model_version=model_version,
                provider=provider,
                case_name=test_case.case_name,
                input_path=test_case.input_path,
                timeout_seconds=timeout_seconds,
            )
            actual_output = str(execution["label"])
            passed = test_case.expected_output in {None, "", actual_output}
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
                raw_output_json=json.dumps(execution["raw_output"], ensure_ascii=False, sort_keys=True),
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
    task.completed_at = datetime.now(UTC).replace(tzinfo=None)
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
