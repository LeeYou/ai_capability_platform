from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import PerformanceBaselineModel


@dataclass(frozen=True)
class DefaultPerformanceBaseline:
    capability_name: str
    scenario_name: str
    latency_max_ms: int | None
    throughput_min_rps: float | None
    p95_max_ms: int | None
    p99_max_ms: int | None
    success_rate_min: float
    description: str


DEFAULT_BASELINES = [
    DefaultPerformanceBaseline("all", "health", 1000, None, None, None, 1.0, "health 接口基础验收阈值"),
    DefaultPerformanceBaseline("all", "capabilities", 1000, None, None, None, 1.0, "capabilities 接口基础验收阈值"),
    DefaultPerformanceBaseline("all", "license_status", 1000, None, None, None, 1.0, "license 状态接口基础验收阈值"),
    DefaultPerformanceBaseline("all", "catalog", 1000, None, None, None, 1.0, "catalog 接口基础验收阈值"),
    DefaultPerformanceBaseline("all", "metrics", 1000, None, None, None, 1.0, "metrics 接口基础验收阈值"),
    DefaultPerformanceBaseline("all", "infer_default", 5000, None, None, None, 1.0, "infer 单请求基础验收阈值"),
    DefaultPerformanceBaseline("all", "pressure_default", None, None, 5000, None, 1.0, "默认压测场景 P95 阈值"),
    DefaultPerformanceBaseline("all", "pressure_sustained", None, 1.0, 3000, 5000, 0.99, "持续压测场景成功率与时延阈值"),
]


def initialize_default_performance_baselines(session: Session) -> None:
    for item in DEFAULT_BASELINES:
        existing = (
            session.query(PerformanceBaselineModel)
            .filter(
                PerformanceBaselineModel.capability_name == item.capability_name,
                PerformanceBaselineModel.scenario_name == item.scenario_name,
            )
            .first()
        )
        if existing is not None:
            continue
        session.add(
            PerformanceBaselineModel(
                capability_name=item.capability_name,
                scenario_name=item.scenario_name,
                latency_max_ms=item.latency_max_ms,
                throughput_min_rps=item.throughput_min_rps,
                p95_max_ms=item.p95_max_ms,
                p99_max_ms=item.p99_max_ms,
                success_rate_min=item.success_rate_min,
                description=item.description,
            )
        )
    session.commit()


def _baseline_item(model: PerformanceBaselineModel) -> dict[str, object]:
    return {
        "baseline_id": model.id,
        "capability_name": model.capability_name,
        "scenario_name": model.scenario_name,
        "latency_max_ms": model.latency_max_ms,
        "throughput_min_rps": model.throughput_min_rps,
        "p95_max_ms": model.p95_max_ms,
        "p99_max_ms": model.p99_max_ms,
        "success_rate_min": model.success_rate_min,
        "description": model.description,
        "created_at": model.created_at.isoformat() if model.created_at else None,
        "updated_at": model.updated_at.isoformat() if model.updated_at else None,
    }


def list_performance_baselines(session: Session) -> list[dict[str, object]]:
    items = session.query(PerformanceBaselineModel).order_by(
        PerformanceBaselineModel.capability_name.asc(),
        PerformanceBaselineModel.scenario_name.asc(),
    )
    return [_baseline_item(item) for item in items]


def upsert_performance_baseline(
    session: Session,
    *,
    capability_name: str,
    scenario_name: str,
    latency_max_ms: int | None,
    throughput_min_rps: float | None,
    p95_max_ms: int | None,
    p99_max_ms: int | None,
    success_rate_min: float,
    description: str | None,
) -> dict[str, object]:
    normalized_capability_name = capability_name.strip()
    normalized_scenario_name = scenario_name.strip()
    if not normalized_capability_name or not normalized_scenario_name:
        raise ValueError("capability_name 和 scenario_name 不能为空。")
    item = (
        session.query(PerformanceBaselineModel)
        .filter(
            PerformanceBaselineModel.capability_name == normalized_capability_name,
            PerformanceBaselineModel.scenario_name == normalized_scenario_name,
        )
        .first()
    )
    if item is None:
        item = PerformanceBaselineModel(
            capability_name=normalized_capability_name,
            scenario_name=normalized_scenario_name,
        )
        session.add(item)
    item.latency_max_ms = latency_max_ms
    item.throughput_min_rps = throughput_min_rps
    item.p95_max_ms = p95_max_ms
    item.p99_max_ms = p99_max_ms
    item.success_rate_min = success_rate_min
    item.description = description
    session.commit()
    session.refresh(item)
    return _baseline_item(item)


def get_performance_baseline(session: Session, capability_name: str, scenario_name: str) -> dict[str, object] | None:
    item = (
        session.query(PerformanceBaselineModel)
        .filter(
            PerformanceBaselineModel.capability_name == capability_name,
            PerformanceBaselineModel.scenario_name == scenario_name,
        )
        .first()
    )
    if item is None and capability_name != "all":
        item = (
            session.query(PerformanceBaselineModel)
            .filter(
                PerformanceBaselineModel.capability_name == "all",
                PerformanceBaselineModel.scenario_name == scenario_name,
            )
            .first()
        )
    return None if item is None else _baseline_item(item)
