"""Botning kirish oqimi: /start, taklifnoma, vrachni telefon orqali ulash."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from sqlalchemy import select

from app.bot.notify import webapp_button
from app.db import session_scope
from app.models import (
    ROLE_LABELS_UZ,
    Doctor,
    DoctorRequest,
    Invite,
    RequestStatus,
    Role,
    User,
    utcnow,
)

log = logging.getLogger(__name__)
router = Router()


class DoctorSignup(StatesGroup):
    """Vrach o'zi ro'yxatdan o'tayotganda klinika nomini so'raymiz."""

    clinic = State()

CONTACT_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📱 Telefon raqamimni yuborish", request_contact=True)]
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)


def _normalize_phone(raw: str | None) -> str:
    if not raw:
        return ""
    digits = "".join(ch for ch in raw if ch.isdigit())
    return f"+{digits}" if digits else ""


def _phone_tail(phone: str, length: int = 9) -> str:
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    return digits[-length:] if len(digits) >= length else digits


async def _open_app_message(message: Message, user: User) -> None:
    await message.answer(
        f"👋 Assalomu alaykum, <b>{user.full_name}</b>!\n"
        f"Rolingiz: <b>{ROLE_LABELS_UZ[user.role]}</b>\n\n"
        "Ishni boshlash uchun quyidagi tugmani bosing 👇",
        reply_markup=webapp_button("🦷 DXL ERP ni ochish"),
    )


async def _redeem_invite(message: Message, token: str) -> bool:
    """Taklif havolasi bo'yicha xodimni ro'yxatga olish."""
    async with session_scope() as session:
        invite = (
            await session.execute(select(Invite).where(Invite.token == token))
        ).scalar_one_or_none()

        if invite is None:
            await message.answer("❌ Taklif havolasi topilmadi yoki bekor qilingan.")
            return True
        if invite.used_at is not None:
            await message.answer("❌ Bu taklif havolasi allaqachon ishlatilgan.")
            return True
        if invite.expires_at < utcnow():
            await message.answer("❌ Taklif havolasining muddati o'tgan. Yangisini so'rang.")
            return True

        tg_id = message.from_user.id
        existing = (
            await session.execute(select(User).where(User.telegram_id == tg_id))
        ).scalar_one_or_none()
        if existing is not None:
            await message.answer("Siz allaqachon tizimdasiz.")
            await _open_app_message(message, existing)
            return True

        user = User(
            telegram_id=tg_id,
            telegram_username=message.from_user.username,
            phone=invite.phone,
            full_name=invite.full_name,
            role=invite.role,
            has_own_stock=invite.has_own_stock,
            is_active=True,
            created_by_id=invite.created_by_id,
        )
        session.add(user)
        await session.flush()

        invite.used_at = utcnow()
        invite.used_by_id = user.id

        if user.role is Role.AGENT and user.has_own_stock:
            from app.services import stock as stock_service

            await stock_service.ensure_agent_warehouse(session, user)

        await message.answer("✅ Ro'yxatdan o'tdingiz!")
        await _open_app_message(message, user)
        return True


@router.message(CommandStart(deep_link=True))
async def start_with_payload(message: Message, command: CommandObject) -> None:
    payload = (command.args or "").strip()
    if payload.startswith("inv_"):
        await _redeem_invite(message, payload[4:])
        return
    await start(message)


@router.message(CommandStart())
async def start(message: Message) -> None:
    tg_id = message.from_user.id
    async with session_scope() as session:
        user = (
            await session.execute(select(User).where(User.telegram_id == tg_id))
        ).scalar_one_or_none()

        if user is not None:
            if not user.is_active:
                await message.answer(
                    "⛔️ Hisobingiz vaqtincha faolsizlantirilgan. Rahbaringizga murojaat qiling."
                )
                return
            await _open_app_message(message, user)
            return

    await message.answer(
        "🦷 <b>DXL Dental Implant — ERP</b>\n\n"
        "Sizni tanimadim. Agar siz <b>vrach</b> bo'lsangiz, telefon raqamingizni yuboring — "
        "tizimdagi kartochkangizga ulanasiz.\n\n"
        "Agar <b>xodim</b> bo'lsangiz, rahbaringizdan taklif havolasini so'rang.",
        reply_markup=CONTACT_KB,
    )


@router.message(F.contact)
async def link_doctor_by_contact(message: Message, state: FSMContext) -> None:
    """Vrach o'z telefon raqamini yuboradi — kartochkasiga ulanadi."""
    contact = message.contact
    if contact.user_id and contact.user_id != message.from_user.id:
        await message.answer(
            "❌ Iltimos, o'zingizning raqamingizni yuboring (boshqa kishinikini emas).",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    phone = _normalize_phone(contact.phone_number)
    tail = _phone_tail(phone)
    tg_id = message.from_user.id

    async with session_scope() as session:
        existing = (
            await session.execute(select(User).where(User.telegram_id == tg_id))
        ).scalar_one_or_none()
        if existing is not None:
            await _open_app_message(message, existing)
            return

        doctors = (await session.execute(select(Doctor))).scalars().all()
        doctor = next(
            (d for d in doctors if tail and _phone_tail(d.phone) == tail), None
        )

        if doctor is None:
            await _create_signup_request(message, phone, state)
            return

        if doctor.user_id:
            await message.answer(
                "❌ Bu kartochka boshqa Telegram hisobiga ulangan. Agentingizga murojaat qiling.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        user = User(
            telegram_id=tg_id,
            telegram_username=message.from_user.username,
            phone=doctor.phone,
            full_name=doctor.full_name,
            role=Role.DOCTOR,
            is_active=True,
        )
        session.add(user)
        await session.flush()

        doctor.user_id = user.id
        doctor.telegram_id = tg_id
        await session.flush()

        await message.answer(
            "✅ Kartochkangiz topildi va ulandi!", reply_markup=ReplyKeyboardRemove()
        )
        await _open_app_message(message, user)


async def _create_signup_request(
    message: Message, phone: str, state: FSMContext
) -> None:
    """Vrach topilmadi — ro'yxatdan o'tish arizasini boshlaymiz."""
    tg_id = message.from_user.id
    full_name = " ".join(
        p for p in (message.from_user.first_name, message.from_user.last_name) if p
    ) or f"Vrach {tg_id}"

    async with session_scope() as session:
        existing = (
            await session.execute(
                select(DoctorRequest).where(DoctorRequest.telegram_id == tg_id)
            )
        ).scalar_one_or_none()

        if existing is not None and existing.status is RequestStatus.PENDING:
            await message.answer(
                "⏳ Arizangiz allaqachon yuborilgan va ko'rib chiqilmoqda.\n"
                "Tasdiqlangach sizga xabar keladi.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        if existing is not None:
            existing.status = RequestStatus.PENDING
            existing.phone = phone
            existing.full_name = full_name
            existing.reject_reason = None
            request = existing
        else:
            request = DoctorRequest(
                telegram_id=tg_id,
                telegram_username=message.from_user.username,
                full_name=full_name,
                phone=phone,
                status=RequestStatus.PENDING,
            )
            session.add(request)
        await session.flush()

    await state.set_state(DoctorSignup.clinic)
    await message.answer(
        "📝 <b>Ro'yxatdan o'tish</b>\n\n"
        "Ishlaydigan <b>klinikangiz nomini</b> va shahringizni yozing.\n"
        "Masalan: <i>«Smile» klinikasi, Toshkent</i>",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(DoctorSignup.clinic, F.text)
async def signup_clinic(message: Message, state: FSMContext) -> None:
    """Klinika nomini saqlaymiz va arizani xodimlarga yuboramiz."""
    clinic = (message.text or "").strip()[:200]
    tg_id = message.from_user.id

    async with session_scope() as session:
        request = (
            await session.execute(
                select(DoctorRequest).where(DoctorRequest.telegram_id == tg_id)
            )
        ).scalar_one_or_none()
        if request is None:
            await state.clear()
            await message.answer("Arizangiz topilmadi. /start bosib qaytadan boshlang.")
            return

        request.clinic_name = clinic
        await session.flush()

        from app.services import notifications

        await notifications.doctor_request_created(session, request)

    await state.clear()
    await message.answer(
        "✅ <b>Arizangiz yuborildi!</b>\n\n"
        f"Ism: {message.from_user.first_name or '—'}\n"
        f"Klinika: {clinic}\n\n"
        "Xodimlarimiz tez orada ko'rib chiqadi. Tasdiqlangach sizga xabar keladi "
        "va ilovadan foydalana boshlaysiz."
    )


@router.message(Command("id"))
async def whoami(message: Message) -> None:
    """Telegram ID ni ko'rsatadi — birinchi admin sozlashda kerak bo'ladi."""
    await message.answer(
        f"Sizning Telegram ID: <code>{message.from_user.id}</code>"
    )


@router.message(Command("yordam", "help"))
async def help_command(message: Message) -> None:
    await message.answer(
        "🦷 <b>DXL ERP yordam</b>\n\n"
        "/start — ilovani ochish\n"
        "/id — Telegram ID ni bilish\n\n"
        "Barcha ish ilova ichida bajariladi. Ilovani ochish uchun /start bosing.",
        reply_markup=webapp_button("🦷 DXL ERP ni ochish"),
    )
