"""Audit jurnaliga yozish."""

from __future__ import annotations

from decimal import Decimal
from datetime import date, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, User, utcnow


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if hasattr(value, "value"):  # Enum
        return value.value
    return value


async def log_action(
    session: AsyncSession,
    user: User | None,
    action: str,
    entity: str,
    entity_id: Any = None,
    *,
    old: dict | None = None,
    new: dict | None = None,
    comment: str | None = None,
) -> None:
    """Har qanday muhim o'zgarishni jurnalga yozadi (o'chirilmaydi)."""
    session.add(
        AuditLog(
            created_at=utcnow(),
            user_id=user.id if user else None,
            user_name=user.full_name if user else None,
            action=action,
            entity=entity,
            entity_id=str(entity_id) if entity_id is not None else None,
            old_value=_jsonable(old) if old else None,
            new_value=_jsonable(new) if new else None,
            comment=comment,
        )
    )
