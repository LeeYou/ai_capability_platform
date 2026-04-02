from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class RuntimeRevisionModel(Base):
    __tablename__ = "runtime_revision"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    revision_token: Mapped[str] = mapped_column(String(128), index=True)
    action: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="active")
    source_summary_json: Mapped[str] = mapped_column(Text)
    capabilities_json: Mapped[str] = mapped_column(Text)
    license_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    detail_json: Mapped[str] = mapped_column(Text)
    rollback_of_revision_id: Mapped[int | None] = mapped_column(ForeignKey("runtime_revision.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.current_timestamp())

    operations: Mapped[list[RuntimeOperationModel]] = relationship(back_populates="revision")


class RuntimeOperationModel(Base):
    __tablename__ = "runtime_operation"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))
    detail_json: Mapped[str] = mapped_column(Text)
    revision_id: Mapped[int | None] = mapped_column(ForeignKey("runtime_revision.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.current_timestamp())

    revision: Mapped[RuntimeRevisionModel | None] = relationship(back_populates="operations")
