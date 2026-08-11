"""Bitta xodim bir necha vazifani bajarishi (agent + omborchi)."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.models import MoveKind, OrderSource, Role, User
from app.permissions import (
    DOCTORS_ALL,
    ORDERS_FULFILL,
    STOCK_EDIT,
    agent_scope,
    doctor_scope,
    effective_permissions,
    user_can,
)


def _combo(**kwargs) -> User:
    base = {"full_name": "Aziz", "role": Role.AGENT, "extra_roles": ["warehouse"]}
    base.update(kwargs)
    user = User(**base)
    user.id = 7
    return user


def test_ruxsatlar_birlashadi():
    combo = _combo()
    # Agentdan
    assert user_can(combo, "doctors.edit")
    assert user_can(combo, "orders.create")
    # Omborchidan
    assert user_can(combo, STOCK_EDIT)
    assert user_can(combo, ORDERS_FULFILL)
    # Ikkalasida ham yo'q
    assert not user_can(combo, "users.manage")
    assert not user_can(combo, "settings.manage")


def test_qoshimcha_rol_yoq_bolsa_ozgarish_yoq():
    plain = _combo(extra_roles=[])
    assert effective_permissions(plain) == effective_permissions(
        _combo(extra_roles=None)
    )
    assert not user_can(plain, STOCK_EDIT)


def test_notogri_rol_nomi_yiqitmaydi():
    """Bazada eskirgan yoki noma'lum rol qolsa ham ilova ishlashda davom etadi."""
    broken = _combo(extra_roles=["warehouse", "yoq-bunday-rol"])
    assert user_can(broken, STOCK_EDIT)


def test_ombor_vazifasi_buyurtma_korinishini_kengaytiradi():
    """Omborchilik qo'shilsa, u boshqalarning buyurtmasini ham ko'rishi kerak."""
    plain_agent = _combo(extra_roles=[])
    assert agent_scope(plain_agent) == 7  # faqat o'ziniki

    combo = _combo()
    assert agent_scope(combo) is None  # hammasini ko'radi — yig'ishi kerak


def test_vrachlar_baribir_ozinikiligicha_qoladi():
    """Ombor vazifasi mijozlar bazasini ochib yubormasligi kerak."""
    combo = _combo()
    assert doctor_scope(combo) == 7
    assert not user_can(combo, DOCTORS_ALL)


def test_direktor_qoshilsa_hamma_vrach_korinadi():
    boss = _combo(extra_roles=["director"])
    assert user_can(boss, DOCTORS_ALL)
    assert doctor_scope(boss) is None


async def test_agent_omborchi_toliq_zanjirni_bajaradi(session, base_data):
    """Bitta xodim: buyurtma yozadi, tasdiqlaydi, o'zi yig'ib yetkazadi."""
    from app.api.orders import deliver_order, list_orders
    from app.services import orders as orders_service, stock as stock_service
    from app.services.orders import LineInput

    combo = User(
        full_name="Aziz (agent + omborchi)",
        role=Role.AGENT,
        extra_roles=["warehouse"],
        telegram_id=880001,
    )
    session.add(combo)
    await session.flush()

    doctor = base_data["doctor"]
    doctor.agent_id = combo.id
    await session.flush()

    await stock_service.apply_move(
        session,
        kind=MoveKind.IN,
        product_id=base_data["implant"].id,
        qty=10,
        to_warehouse_id=base_data["warehouse"].id,
        doc_type="receipt",
        doc_id=1,
    )

    order = await orders_service.create_order(
        session,
        doctor=doctor,
        lines=[LineInput(base_data["implant"].id, 2)],
        actor=combo,
        source=OrderSource.AGENT,
        warehouse_id=base_data["warehouse"].id,
    )
    await orders_service.approve(session, order, combo)

    # Omborchi sifatida o'zi yetkazadi
    delivered = await deliver_order(order.id, session, combo)
    assert delivered.status.value == "delivered"
    assert await stock_service.get_qty(
        session, base_data["warehouse"].id, base_data["implant"].id
    ) == 8

    # Ro'yxatda ko'radi
    rows = await list_orders(None, None, None, False, 50, 0, session, combo)
    assert any(o.id == order.id for o in rows)


async def test_uch_rolli_xodim_chegirmani_ozi_tasdiqlaydi(session, base_data):
    """Agent + direktor + omborchi: buyurtma direktor tasdig'ida osilib qolmasin."""
    from decimal import Decimal

    from sqlalchemy import select

    from app.api.orders import approve_order
    from app.models import AuditLog, OrderStatus
    from app.services import orders as orders_service, stock as stock_service
    from app.services.orders import LineInput

    combo = User(
        full_name="Aziz (agent + direktor + omborchi)",
        role=Role.AGENT,
        extra_roles=["director", "warehouse"],
        telegram_id=880002,
    )
    session.add(combo)
    await session.flush()

    doctor = base_data["doctor"]
    doctor.agent_id = combo.id
    await session.flush()

    await stock_service.apply_move(
        session,
        kind=MoveKind.IN,
        product_id=base_data["implant"].id,
        qty=10,
        to_warehouse_id=base_data["warehouse"].id,
        doc_type="receipt",
        doc_id=1,
    )

    # Katta chegirma — odatda direktor tasdig'iga ketadi
    order = await orders_service.create_order(
        session,
        doctor=doctor,
        lines=[LineInput(base_data["implant"].id, 2, Decimal("40"))],
        actor=combo,
        source=OrderSource.AGENT,
        warehouse_id=base_data["warehouse"].id,
    )
    assert order.needs_director, "chegirma direktor tasdig'ini talab qilishi kerak"

    # Direktorlik qo'shimcha roldan kelgani uchun bir bosishda tasdiqlanadi
    result = await approve_order(order.id, session, combo)
    assert result.status is OrderStatus.APPROVED

    # ...lekin bu audit jurnalida belgilanadi
    rows = (
        await session.execute(
            select(AuditLog).where(
                AuditLog.entity == "order", AuditLog.action == "approve"
            )
        )
    ).scalars().all()
    assert any((r.new_value or {}).get("ozini_ozi_tasdiqladi") for r in rows)


async def test_oddiy_agent_yetkazish_himoyasiga_urilmaydi(base_data):
    """Endpointni himoyalovchi tekshiruv qo'shimcha rolsiz agentni o'tkazmaydi."""
    from app.auth import require_perm

    guard = require_perm(ORDERS_FULFILL)

    # Oddiy agent — ruxsat yo'q
    with pytest.raises(HTTPException) as exc:
        await guard(base_data["agent"])
    assert exc.value.status_code == 403

    # Omborchilik qo'shilgan agent — o'tadi
    base_data["agent"].extra_roles = ["warehouse"]
    passed = await guard(base_data["agent"])
    assert passed is base_data["agent"]

    # Ombor xodimi ham o'tadi
    assert await guard(base_data["keeper"]) is base_data["keeper"]


async def test_ombor_himoyasi_qoshimcha_rol_bilan_ochiladi(base_data):
    from app.auth import require_perm

    guard = require_perm(STOCK_EDIT)

    with pytest.raises(HTTPException):
        await guard(base_data["agent"])

    base_data["agent"].extra_roles = ["warehouse"]
    assert await guard(base_data["agent"]) is base_data["agent"]
