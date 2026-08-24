"""Ma'lumotlar zaxirasi.

Konteyner o'chsa diskdagi hamma narsa yo'qoladi, shuning uchun zaxira
**Telegram orqali** yuboriladi — direktor chatida abadiy saqlanadi va
hech qanday tashqi xizmat yoki parol kerak emas.

Format: barcha jadvallar JSON'ga yig'ilib, gzip qilinadi. `pg_dump` talab
qilinmaydi (konteynerda u yo'q) va fayl istalgan joyda ochiladi.
"""

from __future__ import annotations

import gzip
import io
import json
import logging
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Base
from app.services.fx import today_local

log = logging.getLogger(__name__)

#: Zaxiraga kirmaydigan jadvallar — qayta tiklanadigan yoki shovqinli
SKIP_TABLES = {
    "notifications",   # yuborilgan xabarlar tarixi, tiklash shart emas
    "alembic_version",
}


def _jsonable(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value


async def dump(session: AsyncSession) -> tuple[bytes, dict]:
    """Butun bazani gzip'langan JSON qilib qaytaradi.

    Qaytaradi: (fayl baytlari, qisqacha statistika).
    """
    payload: dict = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "tables": {},
    }
    stats: dict[str, int] = {}

    # Jadvallarni bog'lanish tartibida olamiz — tiklashda FK buzilmasin
    for table in Base.metadata.sorted_tables:
        if table.name in SKIP_TABLES:
            continue
        rows = (await session.execute(select(table))).mappings().all()
        payload["tables"][table.name] = [
            {key: _jsonable(value) for key, value in row.items()} for row in rows
        ]
        stats[table.name] = len(rows)

    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", compresslevel=9) as gz:
        gz.write(raw)

    data = buffer.getvalue()
    log.info(
        "Zaxira tayyor: %s jadval, %s yozuv, %.1f KB",
        len(stats), sum(stats.values()), len(data) / 1024,
    )
    return data, stats


def filename(on_date: date | None = None) -> str:
    return f"dxl-erp-zaxira-{(on_date or today_local()).isoformat()}.json.gz"


def summary_text(stats: dict[str, int], size_bytes: int) -> str:
    """Zaxira bilan birga yuboriladigan qisqa izoh."""
    muhim = ("doctors", "orders", "payments", "contracts", "products", "stock_moves")
    qatorlar = [
        f"  {nom}: {stats[nom]}" for nom in muhim if stats.get(nom)
    ]
    return (
        "💾 <b>Ma'lumotlar zaxirasi</b>\n"
        f"{today_local().isoformat()} · {size_bytes / 1024:.0f} KB\n\n"
        + "\n".join(qatorlar)
        + f"\n\nJami {sum(stats.values())} yozuv, {len(stats)} jadval.\n"
        "<i>Bu faylni saqlab qo'ying — baza yo'qolsa shundan tiklanadi.</i>"
    )


async def send_to_admins(session: AsyncSession) -> int:
    """Zaxirani direktor va super-adminlarga Telegram orqali yuboradi."""
    from aiogram.types import BufferedInputFile

    from app.bot.bot import get_bot
    from app.models import Role, User

    bot = get_bot()
    if bot is None:
        log.warning("Zaxira yuborilmadi: BOT_TOKEN sozlanmagan")
        return 0

    data, stats = await dump(session)
    izoh = summary_text(stats, len(data))
    fayl = BufferedInputFile(data, filename=filename())

    qabul = (
        await session.execute(
            select(User).where(
                User.role.in_([Role.DIRECTOR, Role.SUPERADMIN]),
                User.is_active.is_(True),
                User.telegram_id.is_not(None),
            )
        )
    ).scalars().all()

    yuborildi = 0
    for user in qabul:
        try:
            await bot.send_document(user.telegram_id, fayl, caption=izoh)
            yuborildi += 1
        except Exception as exc:  # bloklagan, chat yopiq va h.k.
            log.warning("Zaxira yuborilmadi (%s): %s", user.telegram_id, exc)

    return yuborildi
