from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import Base, get_engine
from app.db.models import CapabilityRegistryModel, DatasetBindingModel
from app.services.dataset_service import normalize_dataset_path, scan_dataset_bindings


_CAPABILITY_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


@dataclass(frozen=True)
class CapabilitySummary:
    capability_name: str
    display_name: str
    dataset_path: str
    dataset_status: str
    source: str


@dataclass(frozen=True)
class DatasetSummary:
    capability_name: str
    dataset_path: str
    dataset_status: str
    source: str


def initialize_database() -> None:
    Base.metadata.create_all(bind=get_engine())


def normalize_capability_name(capability_name: str) -> str:
    normalized_name = capability_name.strip()
    if not normalized_name:
        raise ValueError("capability_name 不能为空。")
    if not _CAPABILITY_NAME_PATTERN.match(normalized_name):
        raise ValueError("capability_name 仅支持字母、数字、下划线和中划线，且必须以字母或数字开头。")
    return normalized_name


def _default_display_name(capability_name: str) -> str:
    words = capability_name.replace("-", "_").split("_")
    return " ".join(part.capitalize() for part in words if part)


def register_capability(
    session: Session,
    capability_name: str,
    display_name: str | None = None,
    source: str = "manual",
) -> CapabilitySummary:
    normalized_name = normalize_capability_name(capability_name)
    normalized_display_name = display_name.strip() if display_name else _default_display_name(normalized_name)

    capability = session.scalar(
        select(CapabilityRegistryModel).where(CapabilityRegistryModel.capability_name == normalized_name)
    )
    if capability is None:
        capability = CapabilityRegistryModel(
            capability_name=normalized_name,
            display_name=normalized_display_name,
            source=source,
        )
        session.add(capability)
        session.commit()
        session.refresh(capability)
    else:
        changed = False
        if normalized_display_name and capability.display_name != normalized_display_name:
            capability.display_name = normalized_display_name
            changed = True
        if source and capability.source != source:
            capability.source = source
            changed = True
        if changed:
            session.commit()
            session.refresh(capability)

    binding = capability.dataset_binding
    return CapabilitySummary(
        capability_name=capability.capability_name,
        display_name=capability.display_name,
        dataset_path=binding.dataset_path if binding is not None else "",
        dataset_status=binding.dataset_status if binding is not None else "unbound",
        source=binding.source if binding is not None else capability.source,
    )


def bind_dataset_to_capability(
    session: Session,
    datasets_root: Path,
    capability_name: str,
    dataset_path: str,
    dataset_status: str = "ready",
    source: str = "manual",
) -> DatasetSummary:
    normalized_name = normalize_capability_name(capability_name)
    normalized_path = normalize_dataset_path(datasets_root, dataset_path)
    if not normalized_path.exists() or not normalized_path.is_dir():
        raise ValueError("dataset_path 对应目录不存在。")

    capability = session.scalar(
        select(CapabilityRegistryModel).where(CapabilityRegistryModel.capability_name == normalized_name)
    )
    if capability is None:
        raise ValueError("能力尚未注册，无法绑定数据集。")

    conflict_binding = session.scalar(
        select(DatasetBindingModel).where(
            DatasetBindingModel.dataset_path == str(normalized_path),
            DatasetBindingModel.capability_id != capability.id,
        )
    )
    if conflict_binding is not None:
        raise ValueError("该数据集目录已绑定到其他能力。")

    binding = capability.dataset_binding
    if binding is None:
        binding = DatasetBindingModel(
            capability_id=capability.id,
            dataset_path=str(normalized_path),
            dataset_status=dataset_status,
            source=source,
        )
        session.add(binding)
    else:
        binding.dataset_path = str(normalized_path)
        binding.dataset_status = dataset_status
        binding.source = source

    session.commit()
    session.refresh(binding)
    return DatasetSummary(
        capability_name=capability.capability_name,
        dataset_path=binding.dataset_path,
        dataset_status=binding.dataset_status,
        source=binding.source,
    )


def sync_dataset_bindings_from_filesystem(session: Session, datasets_root: Path) -> None:
    scanned_items = scan_dataset_bindings(datasets_root)
    scanned_paths = {item.dataset_path for item in scanned_items}
    has_changes = False

    for item in scanned_items:
        capability = session.scalar(
            select(CapabilityRegistryModel).where(CapabilityRegistryModel.capability_name == item.capability_name)
        )
        if capability is None:
            capability = CapabilityRegistryModel(
                capability_name=item.capability_name,
                display_name=item.display_name,
                source=item.source,
            )
            session.add(capability)
            session.flush()
            has_changes = True

        binding = capability.dataset_binding
        if binding is None:
            session.add(
                DatasetBindingModel(
                    capability_id=capability.id,
                    dataset_path=item.dataset_path,
                    dataset_status=item.dataset_status,
                    source=item.source,
                )
            )
            has_changes = True
            continue

        if binding.dataset_path != item.dataset_path or binding.dataset_status != item.dataset_status:
            binding.dataset_path = item.dataset_path
            binding.dataset_status = item.dataset_status
            binding.source = item.source
            has_changes = True

    existing_bindings = session.scalars(select(DatasetBindingModel)).all()
    for binding in existing_bindings:
        dataset_exists = Path(binding.dataset_path).is_dir()
        if not dataset_exists and binding.dataset_status != "missing":
            binding.dataset_status = "missing"
            has_changes = True
        if dataset_exists and binding.source == "datasets_root" and binding.dataset_path in scanned_paths and binding.dataset_status != "ready":
            binding.dataset_status = "ready"
            has_changes = True

    if has_changes:
        session.commit()


def list_capabilities(session: Session) -> list[CapabilitySummary]:
    capabilities = session.scalars(
        select(CapabilityRegistryModel).order_by(CapabilityRegistryModel.capability_name.asc())
    ).all()
    return [
        CapabilitySummary(
            capability_name=item.capability_name,
            display_name=item.display_name,
            dataset_path=item.dataset_binding.dataset_path if item.dataset_binding is not None else "",
            dataset_status=item.dataset_binding.dataset_status if item.dataset_binding is not None else "unbound",
            source=item.dataset_binding.source if item.dataset_binding is not None else item.source,
        )
        for item in capabilities
    ]


def list_dataset_bindings(session: Session) -> list[DatasetSummary]:
    bindings = session.scalars(
        select(DatasetBindingModel).join(DatasetBindingModel.capability).order_by(CapabilityRegistryModel.capability_name.asc())
    ).all()
    return [
        DatasetSummary(
            capability_name=item.capability.capability_name,
            dataset_path=item.dataset_path,
            dataset_status=item.dataset_status,
            source=item.source,
        )
        for item in bindings
    ]
