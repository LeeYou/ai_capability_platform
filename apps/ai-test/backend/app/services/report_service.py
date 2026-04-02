from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import shutil

from sqlalchemy.orm import Session

from app.db.models import TestReportModel, TestResultModel, TestTaskModel


class TestReportNotFoundError(ValueError):
    """测试报告不存在。"""


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
        "exported_at": report.exported_at.isoformat() if report.exported_at else None,
        "summary": summary,
    }


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
    summary = {
        "task_id": task.id,
        "task_type": task.task_type,
        "capability_name": task.capability_name,
        "model_version": task.model_version,
        "execution_backend": task.execution_backend,
        "total_cases": task.total_cases,
        "passed_cases": task.passed_cases,
        "failed_cases": task.failed_cases,
        "results": [
            {
                "case_id": result.case_id,
                "status": result.status,
                "provider": result.provider,
                "duration_ms": result.duration_ms,
                "score": result.score,
                "expected_output": result.expected_output,
                "actual_output": result.actual_output,
            }
            for result in results
        ],
    }

    json_report_path = report_dir / "report.json"
    html_report_path = report_dir / "report.html"
    pdf_report_path = report_dir / "report.pdf"
    json_report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    html_report_path.write_text(
        "\n".join(
            [
                "<html><head><meta charset='utf-8'><title>ai-test 报告</title></head><body>",
                f"<h1>测试报告 #{task.id}</h1>",
                f"<p>能力：{task.capability_name}</p>",
                f"<p>模型版本：{task.model_version}</p>",
                f"<p>通过：{task.passed_cases} / 失败：{task.failed_cases}</p>",
                "<table border='1' cellspacing='0' cellpadding='6'><tr><th>Case</th><th>Status</th><th>Score</th><th>Output</th></tr>",
                *[
                    f"<tr><td>{result.case.case_name}</td><td>{result.status}</td><td>{result.score:.3f}</td><td>{result.actual_output}</td></tr>"
                    for result in results
                ],
                "</table></body></html>",
            ]
        ),
        encoding="utf-8",
    )
    pdf_report_path.write_bytes(_minimal_pdf_bytes(f"ai-test 报告 #{task.id} {task.capability_name} {task.model_version}"))

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


def get_test_report(session: Session, report_id: int) -> dict[str, object]:
    report = session.get(TestReportModel, report_id)
    if report is None:
        raise TestReportNotFoundError("测试报告不存在。")
    return _report_item(report.task, report)


def export_test_report(
    session: Session,
    exports_root: Path,
    report_id: int,
    export_format: str,
) -> Path:
    report = session.get(TestReportModel, report_id)
    if report is None:
        raise TestReportNotFoundError("测试报告不存在。")

    source_map = {
        "json": Path(report.json_report_path),
        "html": Path(report.html_report_path),
        "pdf": Path(report.pdf_report_path),
    }
    if export_format not in source_map:
        raise ValueError("仅支持导出 json/html/pdf。")

    export_dir = (exports_root / "ai-test").resolve()
    if not (export_dir == exports_root or exports_root in export_dir.parents):
        raise ValueError("导出目录非法。")
    export_dir.mkdir(parents=True, exist_ok=True)

    destination = export_dir / f"test_report_{report.id}.{export_format}"
    shutil.copyfile(source_map[export_format], destination)
    report.exported_at = datetime.now(UTC).replace(tzinfo=None)
    session.commit()
    return destination.resolve()
