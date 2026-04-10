from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import TestReportModel, TestResultModel, TestTaskModel
from app.services.baseline_service import get_performance_baseline


class TestReportNotFoundError(ValueError):
    """测试报告不存在。"""


REPORT_TEMPLATE_TYPES = ("research", "delivery")


def _report_dir(test_reports_root: Path, task_id: int) -> Path:
    report_dir = (test_reports_root / f"task_{task_id}").resolve()
    if not (report_dir == test_reports_root or test_reports_root in report_dir.parents):
        raise ValueError("报告目录非法。")
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir


def _minimal_pdf_bytes(text: str) -> bytes:
    sanitized = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 36 760 Td ({sanitized}) Tj ET"
    objects = [
        "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
        "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj",
        f"4 0 obj << /Length {len(stream.encode('utf-8'))} >> stream\n{stream}\nendstream endobj",
        "5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
    ]
    pdf = "%PDF-1.4\n"
    offsets: list[int] = []
    for obj in objects:
        offsets.append(len(pdf.encode("utf-8")))
        pdf += obj + "\n"
    xref_offset = len(pdf.encode("utf-8"))
    pdf += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    for offset in offsets:
        pdf += f"{offset:010d} 00000 n \n"
    pdf += (
        f"trailer << /Root 1 0 R /Size {len(objects) + 1} >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    )
    return pdf.encode("utf-8")


def _report_item(task: TestTaskModel, report: TestReportModel) -> dict[str, object]:
    summary = json.loads(report.summary_json)
    return {
        "report_id": report.id,
        "task_id": task.id,
        "capability_name": task.capability_name,
        "model_version": task.model_version,
        "status": report.status,
        "passed_cases": summary["passed_cases"],
        "failed_cases": summary["failed_cases"],
        "json_report_path": report.json_report_path,
        "html_report_path": report.html_report_path,
        "pdf_report_path": report.pdf_report_path,
        "available_template_types": summary.get("available_template_types", list(REPORT_TEMPLATE_TYPES)),
        "active_template_type": "research",
        "exported_at": report.exported_at.isoformat() if report.exported_at else None,
        "summary": summary,
    }


def _result_baseline_summary(session: Session, task: TestTaskModel, result: TestResultModel) -> dict[str, object] | None:
    if task.task_type != "acceptance":
        return None
    detail = json.loads(result.raw_output_json)
    if result.case.case_name == "acceptance_check":
        checks = detail.get("results", [])
        if not isinstance(checks, list):
            return None
        check_items: list[dict[str, object]] = []
        for item in checks:
            if not isinstance(item, dict):
                continue
            scenario_name = str(item.get("name", ""))
            baseline = get_performance_baseline(session, task.capability_name, scenario_name)
            check_items.append(
                {
                    "scenario_name": scenario_name,
                    "latency_max_ms": None if baseline is None else baseline.get("latency_max_ms"),
                    "actual_latency_ms": int(item.get("latency_ms", 0)),
                    "passed": bool(item.get("passed", False)),
                }
            )
        return {
            "scenario_name": "acceptance_check",
            "checks": check_items,
        }
    if result.case.case_name != "pressure_smoke":
        return None
    baseline = get_performance_baseline(session, task.capability_name, "pressure_default")
    latency = detail.get("latency_ms", {}) if isinstance(detail.get("latency_ms"), dict) else {}
    return {
        "scenario_name": "pressure_default",
        "p95_max_ms": None if baseline is None else baseline.get("p95_max_ms"),
        "p99_max_ms": None if baseline is None else baseline.get("p99_max_ms"),
        "success_rate_min": None if baseline is None else baseline.get("success_rate_min"),
        "throughput_min_rps": None if baseline is None else baseline.get("throughput_min_rps"),
        "actual_p95_ms": latency.get("p95"),
        "actual_p99_ms": latency.get("p99"),
        "actual_success_rate": detail.get("success_rate"),
        "actual_throughput_rps": detail.get("throughput_rps"),
    }


def _research_template_summary(task: TestTaskModel, results: list[TestResultModel]) -> dict[str, object]:
    return {
        "title": "研发验收报告",
        "focus": "侧重技术执行细节、性能基线与问题定位。",
        "case_breakdown": [
            {
                "case_name": result.case.case_name,
                "status": result.status,
                "provider": result.provider,
                "duration_ms": result.duration_ms,
                "actual_output": result.actual_output,
            }
            for result in results
        ],
        "technical_findings": [
            f"{result.case.case_name}: status={result.status}, duration_ms={result.duration_ms}, provider={result.provider}"
            for result in results
        ],
    }


def _delivery_template_summary(task: TestTaskModel, results: list[TestResultModel]) -> dict[str, object]:
    checklist: list[dict[str, object]] = []
    for result in results:
        raw_detail = json.loads(result.raw_output_json)
        if task.task_type == "acceptance" and result.case.case_name == "acceptance_check":
            checks = raw_detail.get("results", [])
            if isinstance(checks, list):
                for item in checks:
                    if not isinstance(item, dict):
                        continue
                    checklist.append(
                        {
                            "item_name": f"接口验收/{item.get('name', 'unknown')}",
                            "status": "passed" if item.get("passed") else "failed",
                            "evidence": f"status_code={item.get('status_code')} latency_ms={item.get('latency_ms')}",
                        }
                    )
                continue
        if task.task_type == "acceptance" and result.case.case_name == "pressure_smoke":
            latency = raw_detail.get("latency_ms", {}) if isinstance(raw_detail.get("latency_ms"), dict) else {}
            checklist.append(
                {
                    "item_name": "稳定性压测",
                    "status": result.status,
                    "evidence": (
                        f"success_rate={raw_detail.get('success_rate')} "
                        f"p95_ms={latency.get('p95')} p99_ms={latency.get('p99')}"
                    ),
                }
            )
            continue
        checklist.append(
            {
                "item_name": f"测试用例/{result.case.case_name}",
                "status": result.status,
                "evidence": f"actual_output={result.actual_output}",
            }
        )
    checklist.append(
        {
            "item_name": "报告归档",
            "status": "passed",
            "evidence": f"task_id={task.id} 已生成 json/html/pdf 报告",
        }
    )
    return {
        "title": "交付验收报告",
        "focus": "侧重客户交付可核对项、验收结论与留档证据。",
        "checklist": checklist,
        "delivery_conclusion": "passed" if task.failed_cases == 0 else "failed",
    }


def _compose_summary(session: Session, task: TestTaskModel, results: list[TestResultModel]) -> dict[str, object]:
    import json as _json

    # TT13：从任务记录中恢复证据链
    evidence_chain: dict[str, object] | None = None
    if hasattr(task, "evidence_json") and task.evidence_json:
        try:
            evidence_chain = _json.loads(task.evidence_json)
        except (ValueError, TypeError):
            evidence_chain = None

    return {
        "task_id": task.id,
        "task_type": task.task_type,
        "capability_name": task.capability_name,
        "model_version": task.model_version,
        "execution_backend": task.execution_backend,
        "total_cases": task.total_cases,
        "passed_cases": task.passed_cases,
        "failed_cases": task.failed_cases,
        "evidence_chain": evidence_chain,
        "available_template_types": list(REPORT_TEMPLATE_TYPES),
        "results": [
            {
                "case_id": result.case_id,
                "case_name": result.case.case_name,
                "status": result.status,
                "provider": result.provider,
                "duration_ms": result.duration_ms,
                "score": result.score,
                "expected_output": result.expected_output,
                "actual_output": result.actual_output,
                "baseline_comparison": _result_baseline_summary(session, task, result),
            }
            for result in results
        ],
        "report_templates": {
            "research": _research_template_summary(task, results),
            "delivery": _delivery_template_summary(task, results),
        },
    }


def _project_summary(summary: dict[str, object], template_type: str) -> dict[str, object]:
    if template_type not in REPORT_TEMPLATE_TYPES:
        raise ValueError("仅支持 research/delivery 报告模板。")
    projected = dict(summary)
    report_templates = dict(summary.get("report_templates", {}))
    projected["active_template_type"] = template_type
    projected["template_summary"] = report_templates.get(template_type, {})
    return projected


def _render_html_report(summary: dict[str, object]) -> str:
    template_type = str(summary.get("active_template_type", "research"))
    template_summary = summary.get("template_summary", {})
    title = escape(str(template_summary.get("title", "ai-test 报告")))
    focus = escape(str(template_summary.get("focus", "")))
    body_lines = [
        "<html><head><meta charset='utf-8'><title>ai-test 报告</title></head><body>",
        f"<h1>{title}</h1>",
        f"<p>报告视角：{escape(template_type)}</p>",
        f"<p>能力：{escape(str(summary.get('capability_name', '')))}</p>",
        f"<p>模型版本：{escape(str(summary.get('model_version', '')))}</p>",
        f"<p>通过：{escape(str(summary.get('passed_cases', 0)))} / 失败：{escape(str(summary.get('failed_cases', 0)))}</p>",
        f"<p>{focus}</p>",
    ]
    if template_type == "delivery":
        checklist = template_summary.get("checklist", [])
        body_lines.extend(
            [
                "<table border='1' cellspacing='0' cellpadding='6'><tr><th>检查项</th><th>状态</th><th>证据</th></tr>",
                *[
                    f"<tr><td>{escape(str(item.get('item_name', '')))}</td><td>{escape(str(item.get('status', '')))}</td><td>{escape(str(item.get('evidence', '')))}</td></tr>"
                    for item in checklist
                    if isinstance(item, dict)
                ],
                "</table>",
            ]
        )
    else:
        body_lines.extend(
            [
                "<table border='1' cellspacing='0' cellpadding='6'><tr><th>Case</th><th>Status</th><th>Provider</th><th>Duration(ms)</th><th>Output</th></tr>",
                *[
                    f"<tr><td>{escape(str(item.get('case_name', '')))}</td><td>{escape(str(item.get('status', '')))}</td><td>{escape(str(item.get('provider', '')))}</td><td>{escape(str(item.get('duration_ms', '')))}</td><td>{escape(str(item.get('actual_output', '')))}</td></tr>"
                    for item in template_summary.get("case_breakdown", [])
                    if isinstance(item, dict)
                ],
                "</table>",
            ]
        )
    body_lines.append("</body></html>")
    return "\n".join(body_lines)


def generate_test_report(session: Session, test_reports_root: Path, task_id: int) -> dict[str, object]:
    task = session.get(TestTaskModel, task_id)
    if task is None:
        raise TestReportNotFoundError("测试任务不存在，无法生成报告。")

    results = (
        session.query(TestResultModel)
        .filter(TestResultModel.task_id == task.id)
        .order_by(TestResultModel.case_id.asc())
        .all()
    )
    report_dir = _report_dir(test_reports_root, task.id)
    summary = _compose_summary(session, task, results)
    default_summary = _project_summary(summary, "research")

    json_report_path = report_dir / "report.json"
    html_report_path = report_dir / "report.html"
    pdf_report_path = report_dir / "report.pdf"
    json_report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    html_report_path.write_text(_render_html_report(default_summary), encoding="utf-8")
    pdf_report_path.write_bytes(
        _minimal_pdf_bytes(
            f"{default_summary['template_summary'].get('title', 'ai-test 报告')} #{task.id} {task.capability_name} {task.model_version}"
        )
    )

    report = task.report
    if report is None:
        report = TestReportModel(
            task_id=task.id,
            summary_json=json.dumps(summary, ensure_ascii=False, sort_keys=True),
            json_report_path=str(json_report_path.resolve()),
            html_report_path=str(html_report_path.resolve()),
            pdf_report_path=str(pdf_report_path.resolve()),
            status="ready",
        )
        session.add(report)
    else:
        report.summary_json = json.dumps(summary, ensure_ascii=False, sort_keys=True)
        report.json_report_path = str(json_report_path.resolve())
        report.html_report_path = str(html_report_path.resolve())
        report.pdf_report_path = str(pdf_report_path.resolve())
        report.status = "ready"
    session.commit()
    session.refresh(report)
    return _report_item(task, report)


def list_test_reports(session: Session) -> list[dict[str, object]]:
    reports = session.query(TestReportModel).order_by(TestReportModel.id.asc()).all()
    return [_report_item(report.task, report) for report in reports]


def get_test_report(session: Session, report_id: int, *, template_type: str = "research") -> dict[str, object]:
    report = session.get(TestReportModel, report_id)
    if report is None:
        raise TestReportNotFoundError("测试报告不存在。")
    payload = _report_item(report.task, report)
    payload["active_template_type"] = template_type
    payload["summary"] = _project_summary(payload["summary"], template_type)
    return payload


def export_test_report(
    session: Session,
    exports_root: Path,
    report_id: int,
    export_format: str,
    *,
    template_type: str = "research",
) -> Path:
    report = session.get(TestReportModel, report_id)
    if report is None:
        raise TestReportNotFoundError("测试报告不存在。")

    if export_format not in {"json", "html", "pdf"}:
        raise ValueError("仅支持导出 json/html/pdf。")

    export_dir = (exports_root / "ai-test").resolve()
    if not (export_dir == exports_root or exports_root in export_dir.parents):
        raise ValueError("导出目录非法。")
    export_dir.mkdir(parents=True, exist_ok=True)

    summary = _project_summary(json.loads(report.summary_json), template_type)
    destination = export_dir / f"test_report_{report.id}_{template_type}.{export_format}"
    if export_format == "json":
        destination.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    elif export_format == "html":
        destination.write_text(_render_html_report(summary), encoding="utf-8")
    else:
        destination.write_bytes(
            _minimal_pdf_bytes(
                f"{summary['template_summary'].get('title', 'ai-test 报告')} #{report.id} {summary.get('capability_name')} {summary.get('model_version')}"
            )
        )
    report.exported_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.commit()
    return destination.resolve()
