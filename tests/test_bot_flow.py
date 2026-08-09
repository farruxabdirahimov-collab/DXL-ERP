"""Botga kelgan xabar handlergacha yetib borishini tekshiradi.

Telegram bilan haqiqiy aloqa qilinmaydi — sessiya o'rniga soxta obyekt qo'yiladi
va bot nima javob yuborganini yozib boradi.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.methods import SendMessage
from aiogram.types import Chat, Contact, Message, Update, User as TgUser

from app.models import Doctor, DoctorRequest, RequestStatus, Role, User

FAKE_TOKEN = "123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"


class RecordingSession(BaseSession):
    """Telegram'ga chiqmaydi — yuborilgan xabarlarni ro'yxatga yozadi."""

    def __init__(self) -> None:
        super().__init__()
        self.sent: list = []

    async def close(self) -> None:  # pragma: no cover
        return None

    async def make_request(self, bot, method, timeout=None):  # type: ignore[override]
        self.sent.append(method)
        if isinstance(method, SendMessage):
            return Message(
                message_id=1,
                date=datetime.now(tz=timezone.utc),
                chat=Chat(id=method.chat_id, type="private"),
                text=method.text,
            )
        return True

    async def stream_content(self, *args, **kwargs):  # pragma: no cover
        yield b""


def _message(text: str | None = None, *, user_id: int = 900001, contact=None) -> Update:
    tg_user = TgUser(id=user_id, is_bot=False, first_name="Farrukh", username="farrukh")
    return Update(
        update_id=1,
        message=Message(
            message_id=10,
            date=datetime.now(tz=timezone.utc),
            chat=Chat(id=user_id, type="private"),
            from_user=tg_user,
            text=text,
            contact=contact,
        ),
    )


@pytest.fixture
async def bot_pair(session):
    """Soxta sessiyali bot + dispatcher.

    Handlerlar `session_scope()` orqali ishlaydi — u testdagi bilan bir xil
    bazaga ulanadi, shuning uchun qo'shimcha sozlash kerak emas.
    """
    from app.bot import bot as bot_module

    # Dispatcher bir marta yig'iladi (routerni qayta ulab bo'lmaydi).
    # Har test o'z Telegram ID sidan foydalanadi, shuning uchun FSM holatlari
    # bir-biriga aralashmaydi.
    recording = RecordingSession()
    bot = Bot(token=FAKE_TOKEN, session=recording)
    dispatcher = bot_module.get_dispatcher()
    yield bot, dispatcher, recording
    await bot.session.close()


async def test_notanish_foydalanuvchiga_telefon_soraladi(bot_pair):
    # `bot_pair` sessiyaga bog'liq — jadvallar yaratilgan bo'ladi
    bot, dispatcher, recording = bot_pair

    await dispatcher.feed_update(bot, _message("/start"))

    assert recording.sent, "Bot umuman javob bermadi"
    text = recording.sent[-1].text
    assert "telefon raqamingizni yuboring" in text.lower()


async def test_royxatdagi_xodim_ilova_tugmasini_oladi(bot_pair, session):
    bot, dispatcher, recording = bot_pair
    session.add(
        User(
            telegram_id=900002,
            full_name="Direktor Test",
            role=Role.DIRECTOR,
            is_active=True,
        )
    )
    await session.commit()

    await dispatcher.feed_update(bot, _message("/start", user_id=900002))

    assert recording.sent, "Bot umuman javob bermadi"
    assert "Direktor Test" in recording.sent[-1].text


async def test_mavjud_vrach_telefon_orqali_boglanadi(bot_pair, session, base_data):
    bot, dispatcher, recording = bot_pair
    doctor = base_data["doctor"]
    await session.commit()

    contact = Contact(phone_number=doctor.phone, first_name="Vrach", user_id=900003)
    await dispatcher.feed_update(bot, _message(contact=contact, user_id=900003))

    texts = " ".join(m.text for m in recording.sent if hasattr(m, "text"))
    assert "topildi" in texts.lower()

    await session.refresh(doctor)
    assert doctor.telegram_id == 900003


async def test_notanish_telefon_ariza_boshlaydi(bot_pair, session, base_data):
    bot, dispatcher, recording = bot_pair
    await session.commit()

    contact = Contact(phone_number="+998907776655", first_name="Yangi", user_id=900004)
    await dispatcher.feed_update(bot, _message(contact=contact, user_id=900004))

    texts = " ".join(m.text for m in recording.sent if hasattr(m, "text"))
    assert "klinika" in texts.lower(), f"Kutilmagan javob: {texts}"

    # Klinika nomini yuboramiz — ariza yakunlanadi
    await dispatcher.feed_update(
        bot, _message("«Smile» klinikasi, Toshkent", user_id=900004)
    )

    texts = " ".join(m.text for m in recording.sent if hasattr(m, "text"))
    assert "yuborildi" in texts.lower(), f"Kutilmagan javob: {texts}"

    request = (await session.execute(_select_request())).scalar_one()
    assert request.status is RequestStatus.PENDING
    assert request.clinic_name == "«Smile» klinikasi, Toshkent"
    assert request.phone == "+998907776655"


def _select_request():
    from sqlalchemy import select

    return select(DoctorRequest).where(DoctorRequest.telegram_id == 900004)


async def test_handlerdagi_xato_foydalanuvchiga_aytiladi(
    bot_pair, session, monkeypatch
):
    """Xato bo'lsa ham bot jim qolmasligi kerak."""
    bot, dispatcher, recording = bot_pair
    session.add(
        User(
            telegram_id=900005,
            full_name="Xodim",
            role=Role.DIRECTOR,
            is_active=True,
        )
    )
    await session.commit()

    from app.bot.handlers import start as start_handlers

    async def boom(*args, **kwargs):
        raise RuntimeError("sinov uchun xato")

    monkeypatch.setattr(start_handlers, "_open_app_message", boom)

    await dispatcher.feed_update(bot, _message("/start", user_id=900005))

    texts = " ".join(m.text for m in recording.sent if hasattr(m, "text"))
    assert "nosozlik" in texts.lower(), f"Bot xato haqida aytmadi: {texts}"
