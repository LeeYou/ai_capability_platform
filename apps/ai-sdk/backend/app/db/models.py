from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class SdkPackageModel(Base):
    __tablename__ = "sdk_package"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    package_name: Mapped[str] = mapped_column(String(128), index=True)
    capability_name: Mapped[str] = mapped_column(String(128), index=True)
    model_version: Mapped[str] = mapped_column(String(128))
    requested_targets_json: Mapped[str] = mapped_column(Text)
    jni_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    package_root_path: Mapped[str] = mapped_column(Text, default="")
    log_path: Mapped[str] = mapped_column(Text, default="")
    manifest_path: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.current_timestamp())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    targets: Mapped[list[SdkTargetModel]] = relationship(back_populates="package")
    artifacts: Mapped[list[SdkArtifactModel]] = relationship(back_populates="package")


class SdkTargetModel(Base):
    __tablename__ = "sdk_target"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    package_id: Mapped[int] = mapped_column(ForeignKey("sdk_package.id"), index=True)
    target_name: Mapped[str] = mapped_column(String(64))
    os_name: Mapped[str] = mapped_column(String(32))
    arch_name: Mapped[str] = mapped_column(String(32))
    artifact_format: Mapped[str] = mapped_column(String(16))
    jni_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    output_dir: Mapped[str] = mapped_column(Text)
    binary_path: Mapped[str] = mapped_column(Text)
    manifest_path: Mapped[str] = mapped_column(Text)
    checksum: Mapped[str] = mapped_column(String(128))
    log_path: Mapped[str] = mapped_column(Text)
    download_archive_path: Mapped[str] = mapped_column(Text)

    package: Mapped[SdkPackageModel] = relationship(back_populates="targets")
    artifacts: Mapped[list[SdkArtifactModel]] = relationship(back_populates="target")


class SdkArtifactModel(Base):
    __tablename__ = "sdk_artifact"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    package_id: Mapped[int] = mapped_column(ForeignKey("sdk_package.id"), index=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("sdk_target.id"), index=True)
    artifact_type: Mapped[str] = mapped_column(String(32))
    relative_path: Mapped[str] = mapped_column(Text)
    absolute_path: Mapped[str] = mapped_column(Text)
    checksum: Mapped[str] = mapped_column(String(128))

    package: Mapped[SdkPackageModel] = relationship(back_populates="artifacts")
    target: Mapped[SdkTargetModel] = relationship(back_populates="artifacts")
