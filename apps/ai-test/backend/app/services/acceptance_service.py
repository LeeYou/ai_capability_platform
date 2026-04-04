from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import subprocess
import sys
import traceback
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.db.models import AcceptanceTaskModel, TestCaseModel, TestResultModel, TestTaskModel
from app.services.report_service import generate_test_report


class AcceptanceTaskNotFoundError(ValueError):
    """验收任务不存在。"""


@dataclass(frozen=True)
class AcceptanceTaskCreatePayload:
    image_uri: str
    target_base_url: str
    capability_name: str | None
    input_type: str
    infer_payload: str
    prefer_device: str
    acceptance_timeout_seconds: int
    run_admin_checks: bool
    pressure_requests: int
    pressure_concurrency: int
    pressure_timeout_seconds: int
    pressure_min_success_rate: float
    pressure_max_p95_ms: int


def _repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / ".git").exists() or (parent / "docs" / "06_开发计划" / "总体开发计划.md").is_file():
            return parent
    raise ValueError("无法定位仓库根目录。")


def _script_path(script_name: str) -> Path:
    script_path = (_repo_root() / "apps" / "ai-prod" / "scripts" / script_name).resolve()
    if not script_path.is_file():
        raise ValueError(f"验收脚本不存在：{script_path}")
    return script_path


def _validate_base_url(raw_value: str) -> str:
    base_url = raw_value.strip()
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("target_base_url 必须是合法的 http/https 地址。")
    return base_url.rstrip("/")


def _task_item(task: TestTaskModel, acceptance_task: AcceptanceTaskModel) -> dict[str, object]:
    return {
        "acceptance_task_id": acceptance_task.id,
        "task_id": task.id,
        "image_uri": acceptance_task.image_uri,
        "target_base_url": acceptance_task.target_base_url,
        "capability_name": acceptance_task.capability_name,
        "input_type": acceptance_task.input_type,
        "prefer_device": acceptance_task.prefer_device,
        "status": task.status,
        "total_cases": task.total_cases,
        "passed_cases": task.passed_cases,
        "failed_cases": task.failed_cases,
        "report_id": task.report.id if task.report is not None else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


def _task_detail(task: TestTaskModel, acceptance_task: AcceptanceTaskModel) -> dict[str, object]:
    payload = _task_item(task, acceptance_task)
    payload["script_results"] = [
        {
            "case_name": case.case_name,
            "status": result.status,
            "duration_ms": result.duration_ms,
            "passed": result.status == "passed",
            "detail": json.loads(result.raw_output_json),
        }
        for case in task.cases
        for result in case.results
    ]
    return payload


def _run_json_script(command: list[str], timeout_seconds: int) -> dict[str, object]:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout_seconds,
    )
    stdout = completed.stdout.strip()
    if not stdout:
        raise ValueError(f"验收脚本未输出 JSON：{' '.join(command)}")
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"验收脚本输出不是合法 JSON：{stdout}") from exc
    if not isinstance(payload, dict):
        raise ValueError("验收脚本输出必须是 JSON 对象。")
    payload["exit_code"] = completed.returncode
    if completed.stderr.strip():
        payload["stderr"] = completed.stderr.strip()
    return payload


def _create_script_case(session: Session, task_id: int, case_name: str) -> TestCaseModel:
    case = TestCaseModel(
        task_id=task_id,
        case_name=case_name,
        input_path=case_name,
        input_type="api",
        expected_output="passed",
    )
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


def _store_script_result(
    session: Session,
    *,
    task: TestTaskModel,
    case: TestCaseModel,
    status: str,
    duration_ms: int,
    actual_output: str,
    raw_output: dict[str, object],
    error_message: str | None,
) -> None:
    result = TestResultModel(
        task_id=task.id,
        case_id=case.id,
        status=status,
        execution_backend="api",
        provider="subprocess",
        duration_ms=duration_ms,
        score=1.0 if status == "passed" else 0.0,
        expected_output="passed",
        actual_output=actual_output,
        raw_output_json=json.dumps(raw_output, ensure_ascii=False, sort_keys=True),
        error_message=error_message,
    )
    session.add(result)
    if status == "passed":
        task.passed_cases += 1
    else:
        task.failed_cases += 1
    session.commit()


def create_acceptance_task(
    session: Session,
    *,
    test_reports_root: Path,
    payload: AcceptanceTaskCreatePayload,
) -> dict[str, object]:
    target_base_url = _validate_base_url(payload.target_base_url)
    task = TestTaskModel(
        task_type="acceptance",
        capability_name=payload.capability_name or "ai-prod-delivery",
        model_version=payload.image_uri,
        model_artifact_path=target_base_url,
        requested_backend="api",
        execution_backend="api",
        timeout_seconds=max(payload.acceptance_timeout_seconds, payload.pressure_timeout_seconds),
        status="running",
        total_cases=2,
        passed_cases=0,
        failed_cases=0,
        started_at=datetime.now(UTC).replace(tzinfo=None),
    )
    session.add(task)
    session.commit()
    session.refresh(task)

    acceptance_task = AcceptanceTaskModel(
        task_id=task.id,
        image_uri=payload.image_uri,
        target_base_url=target_base_url,
        capability_name=payload.capability_name,
        input_type=payload.input_type,
        infer_payload=payload.infer_payload,
        prefer_device=payload.prefer_device,
        acceptance_timeout_seconds=payload.acceptance_timeout_seconds,
        run_admin_checks=payload.run_admin_checks,
        pressure_requests=payload.pressure_requests,
        pressure_concurrency=payload.pressure_concurrency,
        pressure_timeout_seconds=payload.pressure_timeout_seconds,
        pressure_min_success_rate=payload.pressure_min_success_rate,
        pressure_max_p95_ms=payload.pressure_max_p95_ms,
    )
    session.add(acceptance_task)
    session.commit()
    session.refresh(acceptance_task)

    acceptance_case = _create_script_case(session, task.id, "acceptance_check")
    pressure_case = _create_script_case(session, task.id, "pressure_smoke")

    acceptance_command = [
        sys.executable,
        str(_script_path("acceptance_check.py")),
        "--base-url",
        target_base_url,
        "--timeout",
        str(payload.acceptance_timeout_seconds),
        "--input-type",
        payload.input_type,
        "--infer-payload",
        payload.infer_payload,
        "--prefer-device",
        payload.prefer_device,
    ]
    if payload.capability_name:
        acceptance_command.extend(["--capability", payload.capability_name])
    if payload.run_admin_checks:
        acceptance_command.append("--run-admin-checks")

    try:
        acceptance_output = _run_json_script(acceptance_command, payload.acceptance_timeout_seconds)
        acceptance_results = acceptance_output.get("results", [])
        acceptance_passed = isinstance(acceptance_results, list) and all(
            isinstance(item, dict) and item.get("passed") is True for item in acceptance_results
        )
        acceptance_duration_ms = sum(
            int(item.get("latency_ms", 0)) for item in acceptance_results if isinstance(item, dict)
        )
        _store_script_result(
            session,
            task=task,
            case=acceptance_case,
            status="passed" if acceptance_passed else "failed",
            duration_ms=acceptance_duration_ms,
            actual_output="passed" if acceptance_passed else "failed",
            raw_output=acceptance_output,
            error_message=None if acceptance_passed else "acceptance_check 验收失败。",
        )
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, ValueError) as exc:
        _store_script_result(
            session,
            task=task,
            case=acceptance_case,
            status="failed",
            duration_ms=0,
            actual_output="failed",
            raw_output={"error": str(exc), "traceback": traceback.format_exc(), "script": "acceptance_check"},
            error_message=str(exc),
        )

    pressure_command = [
        sys.executable,
        str(_script_path("pressure_smoke.py")),
        "--base-url",
        target_base_url,
        "--requests",
        str(payload.pressure_requests),
        "--concurrency",
        str(payload.pressure_concurrency),
        "--timeout",
        str(payload.pressure_timeout_seconds),
        "--min-success-rate",
        str(payload.pressure_min_success_rate),
        "--max-p95-ms",
        str(payload.pressure_max_p95_ms),
    ]
    if payload.capability_name:
        pressure_command.extend(
            [
                "--path",
                f"/api/v1/infer/{payload.capability_name}",
                "--method",
                "POST",
                "--body-json",
                json.dumps(
                    {
                        "input_type": payload.input_type,
                        "payload": payload.infer_payload,
                        "prefer_device": payload.prefer_device,
                        "options": {},
                    },
                    ensure_ascii=False,
                ),
                "--include-metrics",
            ]
        )

    try:
        pressure_output = _run_json_script(pressure_command, payload.pressure_timeout_seconds)
        pressure_p95 = 0
        if isinstance(pressure_output.get("latency_ms"), dict):
            pressure_p95 = int(pressure_output["latency_ms"].get("p95", 0))
        pressure_passed = (
            float(pressure_output.get("success_rate", 0.0)) >= payload.pressure_min_success_rate
            and pressure_p95 <= payload.pressure_max_p95_ms
            and int(pressure_output.get("exit_code", 1)) == 0
        )
        _store_script_result(
            session,
            task=task,
            case=pressure_case,
            status="passed" if pressure_passed else "failed",
            duration_ms=pressure_p95,
            actual_output="passed" if pressure_passed else "failed",
            raw_output=pressure_output,
            error_message=None if pressure_passed else "pressure_smoke 验收失败。",
        )
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, ValueError) as exc:
        _store_script_result(
            session,
            task=task,
            case=pressure_case,
            status="failed",
            duration_ms=0,
            actual_output="failed",
            raw_output={"error": str(exc), "traceback": traceback.format_exc(), "script": "pressure_smoke"},
            error_message=str(exc),
        )

    task.status = "completed" if task.failed_cases == 0 else "failed"
    task.completed_at = datetime.now(UTC).replace(tzinfo=None)
    session.commit()
    generate_test_report(session, test_reports_root, task.id)
    session.refresh(task)
    session.refresh(acceptance_task)
    return _task_detail(task, acceptance_task)


def list_acceptance_tasks(session: Session) -> list[dict[str, object]]:
    tasks = (
        session.query(AcceptanceTaskModel)
        .join(TestTaskModel, AcceptanceTaskModel.task_id == TestTaskModel.id)
        .order_by(AcceptanceTaskModel.id.asc())
        .all()
    )
    return [_task_item(task.task, task) for task in tasks]


def get_acceptance_task(session: Session, acceptance_task_id: int) -> dict[str, object]:
    acceptance_task = session.get(AcceptanceTaskModel, acceptance_task_id)
    if acceptance_task is None:
        raise AcceptanceTaskNotFoundError("验收任务不存在。")
    return _task_detail(acceptance_task.task, acceptance_task)
