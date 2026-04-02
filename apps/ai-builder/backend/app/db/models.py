from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class BuildTaskModel(Base):
    __tablename__ = "build_task"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_name: Mapped[str] = mapped_column(String(255))
    capability_name: Mapped[str] = mapped_column(String(128), index=True)
    model_version: Mapped[str] = mapped_column(String(128))
    issue_record_id: Mapped[int] = mapped_column(Integer, index=True)
    requested_targets_json: Mapped[str] = mapped_column(Text)
    jni_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    build_root_path: Mapped[str] = mapped_column(Text)
    log_path: Mapped[str] = mapped_column(Text)
    manifest_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    targets: Mapped[list[BuildTargetModel]] = relationship(back_populates="task")
    artifacts: Mapped[list[BuildArtifactModel]] = relationship(back_populates="task")
    manifest: Mapped[BuildManifestModel | None] = relationship(back_populates="task", uselist=False)


class BuildTargetModel(Base):
    __tablename__ = "build_target"
    __table_args__ = (UniqueConstraint("task_id", "target_name", name="uq_build_target_task_target"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("build_task.id"), index=True)
    target_name: Mapped[str] = mapped_column(String(64), index=True)
    os_name: Mapped[str] = mapped_column(String(32))
    arch_name: Mapped[str] = mapped_column(String(32))
    artifact_format: Mapped[str] = mapped_column(String(16))
    build_mode: Mapped[str] = mapped_column(String(32))
    toolchain_name: Mapped[str] = mapped_column(String(128))
    jni_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    output_dir: Mapped[str] = mapped_column(Text)
    binary_path: Mapped[str] = mapped_column(Text)
    header_dir: Mapped[str] = mapped_column(Text)
    manifest_path: Mapped[str] = mapped_column(Text)
    checksum: Mapped[str] = mapped_column(String(128))
    log_path: Mapped[str] = mapped_column(Text)
    download_archive_path: Mapped[str] = mapped_column(Text)

    task: Mapped[BuildTaskModel] = relationship(back_populates="targets")
    artifacts: Mapped[list[BuildArtifactModel]] = relationship(back_populates="target")


class BuildArtifactModel(Base):
    __tablename__ = "build_artifact"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("build_task.id"), index=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("build_target.id"), index=True)
    artifact_type: Mapped[str] = mapped_column(String(32))
    relative_path: Mapped[str] = mapped_column(Text)
    absolute_path: Mapped[str] = mapped_column(Text)
    checksum: Mapped[str] = mapped_column(String(128))

    task: Mapped[BuildTaskModel] = relationship(back_populates="artifacts")
    target: Mapped[BuildTargetModel] = relationship(back_populates="artifacts")


class BuildManifestModel(Base):
    __tablename__ = "build_manifest"
    __table_args__ = (UniqueConstraint("task_id", name="uq_build_manifest_task_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("build_task.id"), index=True)
    manifest_version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    manifest_path: Mapped[str] = mapped_column(Text)
    manifest_json: Mapped[str] = mapped_column(Text)
    dependency_summary_json: Mapped[str] = mapped_column(Text)

    task: Mapped[BuildTaskModel] = relationship(back_populates="manifest")
