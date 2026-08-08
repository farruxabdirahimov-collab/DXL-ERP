"""Hujjat raqamlarini ketma-ket berish: BUY-2026-00042."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import DocCounter, utcnow

PREFIXES = {
    "order": "BUY",       # Buyurtma
    "receipt": "KIR",     # Kirim
    "transfer": "KCH",    # Ko'chirish
    "return": "QAY",      # Qaytarish
    "writeoff": "SPS",    # Spisaniye
    "payment": "TLV",     # To'lov
}


async def next_number(session: AsyncSession, doc_type: str) -> str:
    prefix = PREFIXES.get(doc_type, doc_type[:3].upper())
    year = utcnow().astimezone(settings.timezone).year

    stmt = select(DocCounter).where(
        DocCounter.prefix == prefix, DocCounter.year == year
    )
    if not settings.is_sqlite:
        stmt = stmt.with_for_update()

    counter = (await session.execute(stmt)).scalar_one_or_none()
    if counter is None:
        counter = DocCounter(prefix=prefix, year=year, last_number=0)
        session.add(counter)
        await session.flush()

    counter.last_number += 1
    await session.flush()
    return f"{prefix}-{year}-{counter.last_number:05d}"
