from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class TestTaskModel(Base):
    __tablename__ = "test_task"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_type: Mapped[str] = mapped_column(String(32))
    capability_name: Mapped[str] = mapped_column(String(128), index=True)
    model_version: Mapped[str] = mapped_column(String(128))
    model_artifact_path: Mapped[str] = mapped_column(Text)
    requested_backend: Mapped[str] = mapped_column(String(32), default="auto")
    execution_backend: Mapped[str | None] = mapped_column(String(32), nullable=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    total_cases: Mapped[int] = mapped_column(Integer, default=0)
    passed_cases: Mapped[int] = mapped_column(Integer, default=0)
    failed_cases: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    cases: Mapped[list[TestCaseModel]] = relationship(back_populates="task", cascade="all, delete-orphan")
    results: Mapped[list[TestResultModel]] = relationship(back_populates="task", cascade="all, delete-orphan")
    report: Mapped[TestReportModel | None] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        uselist=False,
    )
    acceptance_task: Mapped[AcceptanceTaskModel | None] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        uselist=False,
    )


class TestCaseModel(Base):
    __tablename__ = "test_case"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("test_task.id", ondelete="CASCADE"), index=True)
    case_name: Mapped[str] = mapped_column(String(255))
    input_path: Mapped[str] = mapped_column(Text)
    input_type: Mapped[str] = mapped_column(String(64))
    expected_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.current_timestamp())

    task: Mapped[TestTaskModel] = relationship(back_populates="cases")
    results: Mapped[list[TestResultModel]] = relationship(back_populates="case", cascade="all, delete-orphan")


class TestResultModel(Base):
    __tablename__ = "test_result"
    __table_args__ = (
        UniqueConstraint("case_id", name="uq_test_result_case_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("test_task.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("test_case.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(32))
    execution_backend: Mapped[str] = mapped_column(String(32))
    provider: Mapped[str] = mapped_column(String(128))
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    expected_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    actual_output: Mapped[str] = mapped_column(Text)
    raw_output_json: Mapped[str] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.current_timestamp())

    task: Mapped[TestTaskModel] = relationship(back_populates="results")
    case: Mapped[TestCaseModel] = relationship(back_populates="results")


class TestReportModel(Base):
    __tablename__ = "test_report"
    __table_args__ = (
        UniqueConstraint("task_id", name="uq_test_report_task_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("test_task.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="ready")
    summary_json: Mapped[str] = mapped_column(Text)
    json_report_path: Mapped[str] = mapped_column(Text)
    html_report_path: Mapped[str] = mapped_column(Text)
    pdf_report_path: Mapped[str] = mapped_column(Text)
    exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    task: Mapped[TestTaskModel] = relationship(back_populates="report")


class AcceptanceTaskModel(Base):
    __tablename__ = "acceptance_task"
    __table_args__ = (
        UniqueConstraint("task_id", name="uq_acceptance_task_task_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("test_task.id", ondelete="CASCADE"), index=True)
    image_uri: Mapped[str] = mapped_column(Text)
    target_base_url: Mapped[str] = mapped_column(Text)
    capability_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    input_type: Mapped[str] = mapped_column(String(32), default="json")
    infer_payload: Mapped[str] = mapped_column(Text)
    prefer_device: Mapped[str] = mapped_column(String(32), default="auto")
    acceptance_timeout_seconds: Mapped[int] = mapped_column(Integer, default=10)
    run_admin_checks: Mapped[bool] = mapped_column(Boolean, default=False)
    pressure_requests: Mapped[int] = mapped_column(Integer, default=32)
    pressure_concurrency: Mapped[int] = mapped_column(Integer, default=8)
    pressure_timeout_seconds: Mapped[int] = mapped_column(Integer, default=10)
    pressure_min_success_rate: Mapped[float] = mapped_column(Float, default=1.0)
    pressure_max_p95_ms: Mapped[int] = mapped_column(Integer, default=5000)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    task: Mapped[TestTaskModel] = relationship(back_populates="acceptance_task")


class PerformanceBaselineModel(Base):
    __tablename__ = "performance_baseline"
    __table_args__ = (
        UniqueConstraint("capability_name", "scenario_name", name="uq_performance_baseline_capability_scenario"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    capability_name: Mapped[str] = mapped_column(String(128), index=True)
    scenario_name: Mapped[str] = mapped_column(String(64))
    latency_max_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    throughput_min_rps: Mapped[float | None] = mapped_column(Float, nullable=True)
    p95_max_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    p99_max_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    success_rate_min: Mapped[float] = mapped_column(Float, default=1.0)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
