"""Materiallar (maqola/video) va rassilka."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import (
    Audience,
    Broadcast,
    Doctor,
    DoctorCategory,
    Post,
    PostKind,
    Role,
    User,
)
from app.permissions import BROADCAST_SEND, CONTENT_MANAGE, CONTENT_VIEW, can
from app.schemas import BroadcastIn, PostIn, PostUpdateIn


async def _doctor_with_account(session, name, phone, tg_id, agent_id, category=None):
    account = User(
        telegram_id=tg_id, full_name=name, role=Role.DOCTOR, is_active=True, phone=phone
    )
    session.add(account)
    await session.flush()
    doctor = Doctor(
        full_name=name,
        phone=phone,
        agent_id=agent_id,
        user_id=account.id,
        telegram_id=tg_id,
        category=category or DoctorCategory.NEW,
    )
    session.add(doctor)
    await session.flush()
    return doctor


# ------------------------------------------------------------- ruxsatlar
def test_kim_material_joylay_oladi():
    assert can(Role.DIRECTOR, CONTENT_MANAGE)
    assert can(Role.AGENT, CONTENT_MANAGE)
    assert not can(Role.DOCTOR, CONTENT_MANAGE)
    assert not can(Role.FOUNDER, CONTENT_MANAGE)
    assert not can(Role.WAREHOUSE, CONTENT_MANAGE)


def test_hamma_material_kora_oladi():
    for role in Role:
        assert can(role, CONTENT_VIEW), role


def test_rassilkani_kim_yubora_oladi():
    assert can(Role.DIRECTOR, BROADCAST_SEND)
    assert can(Role.AGENT, BROADCAST_SEND)
    assert not can(Role.DOCTOR, BROADCAST_SEND)
    assert not can(Role.ACCOUNTANT, BROADCAST_SEND)


# --------------------------------------------------------------- materiallar
async def test_material_yaratiladi_va_chop_etiladi(session, base_data):
    from app.api.content import create_post

    out = await create_post(
        PostIn(
            kind=PostKind.VIDEO,
            title="DXL implantni o'rnatish texnikasi",
            summary="Bosqichma-bosqich video dars",
            media_url="https://youtube.com/watch?v=abc",
        ),
        session,
        base_data["director"],
    )
    assert out.title == "DXL implantni o'rnatish texnikasi"
    assert out.kind is PostKind.VIDEO
    assert out.kind_label == "Video"
    assert out.is_published is True
    assert out.published_at is not None
    assert out.author_name == "Direktor"


async def test_chop_etilmagan_material_vrachga_korinmaydi(session, base_data):
    from app.api.content import create_post, get_post, list_posts

    doctor_account = User(
        telegram_id=970001, full_name="Vrach", role=Role.DOCTOR, is_active=True
    )
    session.add(doctor_account)
    await session.flush()

    draft = await create_post(
        PostIn(title="Qoralama maqola", is_published=False),
        session,
        base_data["director"],
    )

    # Vrach ro'yxatda ko'rmaydi
    visible = await list_posts(None, None, 50, 0, session, doctor_account)
    assert all(p.id != draft.id for p in visible)

    # To'g'ridan-to'g'ri ochsa ham topilmaydi
    with pytest.raises(HTTPException) as exc:
        await get_post(draft.id, session, doctor_account)
    assert exc.value.status_code == 404

    # Direktor esa ko'radi
    staff_visible = await list_posts(None, None, 50, 0, session, base_data["director"])
    assert any(p.id == draft.id for p in staff_visible)


async def test_material_ochilganda_korishlar_ortadi(session, base_data):
    from app.api.content import create_post, get_post

    post = await create_post(
        PostIn(title="Implant parvarishi"), session, base_data["director"]
    )
    assert post.views == 0

    await get_post(post.id, session, base_data["director"])
    reopened = await get_post(post.id, session, base_data["director"])
    assert reopened.views == 2


async def test_qoralama_chop_etilganda_sana_qoyiladi(session, base_data):
    from app.api.content import create_post, update_post

    draft = await create_post(
        PostIn(title="Keyinroq", is_published=False), session, base_data["director"]
    )
    assert draft.published_at is None

    published = await update_post(
        draft.id, PostUpdateIn(is_published=True), session, base_data["director"]
    )
    assert published.published_at is not None


# ----------------------------------------------------------------- rassilka
async def test_barcha_vrachlarga_rassilka(session, base_data):
    from app.api.content import send_broadcast

    await _doctor_with_account(session, "Vrach A", "+998900000001", 970101, base_data["agent"].id)
    await _doctor_with_account(session, "Vrach B", "+998900000002", 970102, base_data["agent"].id)

    out = await send_broadcast(
        BroadcastIn(text="Yangi partiya keldi!", audience=Audience.ALL_DOCTORS),
        session,
        base_data["director"],
    )
    assert out.sent_count + out.failed_count == 2
    assert out.audience_label == "Barcha vrachlar"

    saved = (await session.execute(select(Broadcast))).scalars().all()
    assert len(saved) == 1
    assert saved[0].text == "Yangi partiya keldi!"


async def test_agent_faqat_oz_vrachlariga_yuboradi(session, base_data):
    from app.api.content import send_broadcast

    other_agent = User(full_name="Boshqa agent", role=Role.AGENT, telegram_id=1099)
    session.add(other_agent)
    await session.flush()

    await _doctor_with_account(session, "Meniki", "+998900000003", 970103, base_data["agent"].id)
    await _doctor_with_account(session, "Begona", "+998900000004", 970104, other_agent.id)

    out = await send_broadcast(
        BroadcastIn(text="Salom", audience=Audience.ALL_DOCTORS),
        session,
        base_data["agent"],
    )
    # Agent "barcha vrachlar" tanlasa ham faqat o'zinikilar oladi
    assert out.sent_count + out.failed_count == 1


async def test_toifa_boyicha_rassilka(session, base_data):
    from app.api.content import send_broadcast

    await _doctor_with_account(
        session, "Yirik", "+998900000005", 970105, base_data["agent"].id,
        category=DoctorCategory.A,
    )
    await _doctor_with_account(
        session, "Kichik", "+998900000006", 970106, base_data["agent"].id,
        category=DoctorCategory.C,
    )

    out = await send_broadcast(
        BroadcastIn(text="A toifa uchun taklif", audience=Audience.CATEGORY_A),
        session,
        base_data["director"],
    )
    assert out.sent_count + out.failed_count == 1


async def test_bosh_guruhga_yuborilmaydi(session, base_data):
    from app.api.content import send_broadcast

    with pytest.raises(HTTPException) as exc:
        await send_broadcast(
            BroadcastIn(text="Salom", audience=Audience.ALL_DOCTORS),
            session,
            base_data["director"],
        )
    assert exc.value.status_code == 400
    assert "yo'q" in exc.value.detail.lower()


async def test_shaxsiy_xabar_vrach_tanlanishi_shart(session, base_data):
    from app.api.content import send_broadcast

    with pytest.raises(HTTPException) as exc:
        await send_broadcast(
            BroadcastIn(text="Shaxsiy", audience=Audience.ONE_DOCTOR),
            session,
            base_data["director"],
        )
    assert exc.value.status_code == 400


# ------------------------------------------------------- vrach kabineti
async def test_vrach_oz_xaridlarini_koradi(session, base_data):
    from app.api.content import my_purchases
    from app.models import MoveKind, OrderSource
    from app.services import orders as orders_service, stock as stock_service
    from app.services.orders import LineInput

    doctor = base_data["doctor"]
    account = User(
        telegram_id=970201, full_name=doctor.full_name, role=Role.DOCTOR, is_active=True
    )
    session.add(account)
    await session.flush()
    doctor.user_id = account.id
    await session.flush()

    await stock_service.apply_move(
        session,
        kind=MoveKind.IN,
        product_id=base_data["implant"].id,
        qty=20,
        to_warehouse_id=base_data["warehouse"].id,
        doc_type="receipt",
        doc_id=1,
    )
    order = await orders_service.create_order(
        session,
        doctor=doctor,
        lines=[LineInput(base_data["implant"].id, 3)],
        actor=base_data["agent"],
        source=OrderSource.AGENT,
        warehouse_id=base_data["warehouse"].id,
    )
    await orders_service.approve(session, order, base_data["agent"])
    await orders_service.deliver(session, order, base_data["keeper"])

    report = await my_purchases(session, account)
    assert report["orders"] == 1
    assert report["units"] == 3
    assert str(report["total_usd"]) == "300.00"
    assert report["top_products"][0]["qty"] == 3


async def test_xodim_vrach_kabinetiga_kira_olmaydi(session, base_data):
    from app.api.content import my_purchases

    with pytest.raises(HTTPException) as exc:
        await my_purchases(session, base_data["agent"])
    assert exc.value.status_code == 403
