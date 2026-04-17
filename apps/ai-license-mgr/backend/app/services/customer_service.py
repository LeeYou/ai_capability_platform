from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import CustomerModel
from app.services.audit_service import append_audit_log
from app.services.license_errors import CustomerNotFoundError


def list_customers(session: Session) -> list[dict[str, object]]:
    return [
        {
            "customer_id": item.id,
            "customer_code": item.customer_code,
            "customer_name": item.customer_name,
            "contact_name": item.contact_name,
            "contact_email": item.contact_email,
            "status": item.status,
        }
        for item in session.query(CustomerModel).order_by(CustomerModel.id.asc()).all()
    ]


def get_customer(session: Session, customer_id: int) -> dict[str, object]:
    customer = session.get(CustomerModel, customer_id)
    if customer is None:
        raise CustomerNotFoundError("客户不存在。")
    return {
        "customer_id": customer.id,
        "customer_code": customer.customer_code,
        "customer_name": customer.customer_name,
        "contact_name": customer.contact_name,
        "contact_email": customer.contact_email,
        "status": customer.status,
    }


def create_customer(
    session: Session,
    audit_log_path: Path,
    *,
    customer_code: str,
    customer_name: str,
    contact_name: str | None,
    contact_email: str | None,
) -> dict[str, object]:
    normalized_code = customer_code.strip()
    if not normalized_code:
        raise ValueError("客户编码不能为空。")
    if session.query(CustomerModel).filter(CustomerModel.customer_code == normalized_code).first() is not None:
        raise ValueError("客户编码已存在。")

    normalized_name = customer_name.strip()
    if not normalized_name:
        raise ValueError("客户名称不能为空。")

    customer = CustomerModel(
        customer_code=normalized_code,
        customer_name=normalized_name,
        contact_name=contact_name.strip() if contact_name else None,
        contact_email=contact_email.strip() if contact_email else None,
        status="active",
    )
    session.add(customer)
    session.commit()
    session.refresh(customer)
    append_audit_log(
        audit_log_path,
        action="create",
        entity_type="customer",
        entity_id=str(customer.id),
        detail={"customer_code": customer.customer_code},
    )
    return {
        "customer_id": customer.id,
        "customer_code": customer.customer_code,
        "customer_name": customer.customer_name,
        "contact_name": customer.contact_name,
        "contact_email": customer.contact_email,
        "status": customer.status,
    }
