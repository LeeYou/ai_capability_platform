from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class CapabilityRegistryModel(Base):
    __tablename__ = "capability_registry"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    capability_name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(64), default="manual")
    input_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    output_schema: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.current_timestamp(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    dataset_binding: Mapped[DatasetBindingModel | None] = relationship(
        back_populates="capability",
        cascade="all, delete-orphan",
        uselist=False,
    )
    annotation_tasks: Mapped[list[AnnotationTaskModel]] = relationship(
        back_populates="capability",
        cascade="all, delete-orphan",
    )
    training_tasks: Mapped[list[TrainingTaskModel]] = relationship(
        back_populates="capability",
        cascade="all, delete-orphan",
    )


class DatasetBindingModel(Base):
    __tablename__ = "dataset_binding"
    __table_args__ = (
        UniqueConstraint("capability_id", name="uq_dataset_binding_capability_id"),
        UniqueConstraint("dataset_path", name="uq_dataset_binding_dataset_path"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    capability_id: Mapped[int] = mapped_column(ForeignKey("capability_registry.id", ondelete="CASCADE"))
    dataset_path: Mapped[str] = mapped_column(Text)
    dataset_status: Mapped[str] = mapped_column(String(64), default="ready")
    source: Mapped[str] = mapped_column(String(64), default="manual")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.current_timestamp(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    capability: Mapped[CapabilityRegistryModel] = relationship(back_populates="dataset_binding")
    annotation_tasks: Mapped[list[AnnotationTaskModel]] = relationship(back_populates="dataset_binding")
    training_tasks: Mapped[list[TrainingTaskModel]] = relationship(back_populates="dataset_binding")


class AnnotationTaskModel(Base):
    __tablename__ = "annotation_task"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    capability_id: Mapped[int] = mapped_column(ForeignKey("capability_registry.id", ondelete="CASCADE"), index=True)
    dataset_binding_id: Mapped[int] = mapped_column(ForeignKey("dataset_binding.id", ondelete="CASCADE"), index=True)
    task_name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(64), default="pending")
    sample_total: Mapped[int] = mapped_column(Integer, default=0)
    labeled_count: Mapped[int] = mapped_column(Integer, default=0)
    result_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.current_timestamp(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    capability: Mapped[CapabilityRegistryModel] = relationship(back_populates="annotation_tasks")
    dataset_binding: Mapped[DatasetBindingModel] = relationship(back_populates="annotation_tasks")
    training_tasks: Mapped[list[TrainingTaskModel]] = relationship(back_populates="annotation_task")


class TrainingTaskModel(Base):
    __tablename__ = "training_task"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    capability_id: Mapped[int] = mapped_column(ForeignKey("capability_registry.id", ondelete="CASCADE"), index=True)
    dataset_binding_id: Mapped[int] = mapped_column(ForeignKey("dataset_binding.id", ondelete="CASCADE"), index=True)
    annotation_task_id: Mapped[int | None] = mapped_column(
        ForeignKey("annotation_task.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    task_name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(64), default="pending")
    framework: Mapped[str] = mapped_column(String(64), default="pytorch")
    backend_type: Mapped[str] = mapped_column(String(64), default="cpu")
    train_params_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    log_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.current_timestamp(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    capability: Mapped[CapabilityRegistryModel] = relationship(back_populates="training_tasks")
    dataset_binding: Mapped[DatasetBindingModel] = relationship(back_populates="training_tasks")
    annotation_task: Mapped[AnnotationTaskModel | None] = relationship(back_populates="training_tasks")
