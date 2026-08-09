"""Vrachning o'zi ro'yxatdan o'tishi va tasdiqlash oqimi."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Doctor, DoctorRequest, RequestStatus, Role, User, utcnow


async def _make_request(session, telegram_id=555001, phone="+998901112233") -> DoctorRequest:
    request = DoctorRequest(
        telegram_id=telegram_id,
        telegram_username="vrach",
        full_name="Yangi Vrach",
        phone=phone,
        clinic_name="«Smile» klinikasi, Toshkent",
        status=RequestStatus.PENDING,
    )
    session.add(request)
    await session.flush()
    return request


async def test_ariza_yaratiladi_va_kutish_holatida(session, base_data):
    request = await _make_request(session)
    assert request.status is RequestStatus.PENDING
    assert request.doctor_id is None

    # Ariza tasdiqlanmaguncha vrach kartochkasi yaratilmaydi
    doctors = (await session.execute(select(Doctor))).scalars().all()
    assert all(d.telegram_id != request.telegram_id for d in doctors)


async def test_tasdiqlangach_vrach_va_hisob_yaratiladi(session, base_data):
    """Tasdiqlash: kartochka + foydalanuvchi hisobi + Telegram bog'lanishi."""
    from app.api.doctors import approve_request
    from app.schemas import ApproveRequestIn

    request = await _make_request(session)
    agent = base_data["agent"]
    director = base_data["director"]

    out = await approve_request(
        request.id,
        ApproveRequestIn(
            agent_id=agent.id,
            debt_limit_usd=Decimal("1500"),
            payment_term_days=21,
        ),
        session,
        director,
    )

    assert out.full_name == "Yangi Vrach"
    assert out.agent_id == agent.id
    assert out.debt_limit_usd == Decimal("1500.00")
    assert out.payment_term_days == 21

    await session.refresh(request)
    assert request.status is RequestStatus.APPROVED
    assert request.doctor_id == out.id
    assert request.reviewed_by_id == director.id

    # Vrach uchun foydalanuvchi hisobi ochildi va kartochkaga bog'landi
    account = (
        await session.execute(
            select(User).where(User.telegram_id == request.telegram_id)
        )
    ).scalar_one()
    assert account.role is Role.DOCTOR

    doctor = await session.get(Doctor, out.id)
    assert doctor.user_id == account.id
    assert doctor.telegram_id == request.telegram_id


async def test_agent_tasdiqlasa_ozini_biriktiradi(session, base_data):
    from app.api.doctors import approve_request
    from app.schemas import ApproveRequestIn

    request = await _make_request(session, telegram_id=555002, phone="+998901112244")
    agent = base_data["agent"]

    # Agent boshqa agentni ko'rsatsa ham, o'ziga biriktiriladi
    out = await approve_request(
        request.id, ApproveRequestIn(agent_id=999), session, agent
    )
    assert out.agent_id == agent.id


async def test_takroriy_telefon_rad_etiladi(session, base_data):
    from fastapi import HTTPException

    from app.api.doctors import approve_request
    from app.schemas import ApproveRequestIn

    # base_data dagi vrachning telefoni bilan ariza
    request = await _make_request(
        session, telegram_id=555003, phone=base_data["doctor"].phone
    )
    with pytest.raises(HTTPException) as exc:
        await approve_request(
            request.id,
            ApproveRequestIn(agent_id=base_data["agent"].id),
            session,
            base_data["director"],
        )
    assert exc.value.status_code == 409


async def test_rad_etilgan_ariza_qayta_korilmaydi(session, base_data):
    from fastapi import HTTPException

    from app.api.doctors import approve_request, reject_request
    from app.schemas import ApproveRequestIn, RejectRequestIn

    request = await _make_request(session, telegram_id=555004, phone="+998901112255")
    result = await reject_request(
        request.id, RejectRequestIn(reason="Bizning hududimiz emas"), session,
        base_data["director"],
    )
    assert result.ok is True

    await session.refresh(request)
    assert request.status is RequestStatus.REJECTED
    assert request.reject_reason == "Bizning hududimiz emas"

    with pytest.raises(HTTPException) as exc:
        await approve_request(
            request.id,
            ApproveRequestIn(agent_id=base_data["agent"].id),
            session,
            base_data["director"],
        )
    assert exc.value.status_code == 400


async def test_standart_shartlar_qollaniladi(session, base_data):
    """Limit va muddat ko'rsatilmasa sozlamalardagi standart qiymat olinadi."""
    from app.api.doctors import approve_request
    from app.schemas import ApproveRequestIn
    from app.services.settings_service import set_setting

    await set_setting(session, "default_payment_term_days", 45)
    await set_setting(session, "default_debt_limit_usd", 700)

    request = await _make_request(session, telegram_id=555005, phone="+998901112266")
    out = await approve_request(
        request.id,
        ApproveRequestIn(agent_id=base_data["agent"].id),
        session,
        base_data["director"],
    )
    assert out.payment_term_days == 45
    assert out.debt_limit_usd == Decimal("700.00")
