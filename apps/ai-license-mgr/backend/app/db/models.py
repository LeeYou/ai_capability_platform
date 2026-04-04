from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class CustomerModel(Base):
    __tablename__ = "customer"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_code: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    customer_name: Mapped[str] = mapped_column(String(255))
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    policies: Mapped[list[LicensePolicyModel]] = relationship(back_populates="customer")
    issues: Mapped[list[LicenseIssueRecordModel]] = relationship(back_populates="customer")


class KeyPairModel(Base):
    __tablename__ = "key_pair"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key_name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    algorithm: Mapped[str] = mapped_column(String(64), default="ed25519")
    private_key_path: Mapped[str] = mapped_column(Text)
    public_key_path: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    policies: Mapped[list[LicensePolicyModel]] = relationship(back_populates="key_pair")
    issues: Mapped[list[LicenseIssueRecordModel]] = relationship(back_populates="key_pair")


class LicensePolicyModel(Base):
    __tablename__ = "license_policy"
    __table_args__ = (UniqueConstraint("policy_name", name="uq_license_policy_policy_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    policy_name: Mapped[str] = mapped_column(String(128), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.id"))
    key_pair_id: Mapped[int] = mapped_column(ForeignKey("key_pair.id"))
    capability_scope_json: Mapped[str] = mapped_column(Text)
    version_constraints_json: Mapped[str] = mapped_column(Text)
    hardware_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    start_at_cst: Mapped[str] = mapped_column(String(64))
    expire_at_cst: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    customer: Mapped[CustomerModel] = relationship(back_populates="policies")
    key_pair: Mapped[KeyPairModel] = relationship(back_populates="policies")
    issues: Mapped[list[LicenseIssueRecordModel]] = relationship(back_populates="policy")


class LicenseIssueRecordModel(Base):
    __tablename__ = "license_issue_record"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("license_policy.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.id"), index=True)
    key_pair_id: Mapped[int] = mapped_column(ForeignKey("key_pair.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="issued")
    payload_json: Mapped[str] = mapped_column(Text)
    signature_base64: Mapped[str] = mapped_column(Text)
    license_path: Mapped[str] = mapped_column(Text)
    public_key_export_path: Mapped[str] = mapped_column(Text)
    hardware_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    capability_scope_json: Mapped[str] = mapped_column(Text)
    version_constraints_json: Mapped[str] = mapped_column(Text)
    issued_at_cst: Mapped[str] = mapped_column(String(64))
    last_validation_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_validation_result: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    policy: Mapped[LicensePolicyModel] = relationship(back_populates="issues")
    customer: Mapped[CustomerModel] = relationship(back_populates="issues")
    key_pair: Mapped[KeyPairModel] = relationship(back_populates="issues")


class LicenseToolReleaseModel(Base):
    __tablename__ = "license_tool_release"
    __table_args__ = (UniqueConstraint("tool_name", "version", name="uq_license_tool_release_name_version"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tool_name: Mapped[str] = mapped_column(String(128), index=True, default="license_tool")
    version: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    archive_path: Mapped[str] = mapped_column(Text)
    manifest_path: Mapped[str] = mapped_column(Text)
    readme_path: Mapped[str] = mapped_column(Text)
    checksum_sha256: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
