"""Tizim sozlamalari — kalit/qiymat, standart qiymatlar bilan."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Setting

#: kalit -> (standart qiymat, o'zbekcha izoh)
DEFAULT_SETTINGS: dict[str, tuple[Any, str]] = {
    "max_discount_pct_agent": (
        10,
        "Agent mustaqil bera oladigan eng katta chegirma (%). Undan oshsa direktor tasdiqlaydi.",
    ),
    "default_payment_term_days": (
        30,
        "Yangi vrach uchun standart to'lov muddati (kun).",
    ),
    "default_debt_limit_usd": (
        0,
        "Yangi vrach uchun standart qarz limiti (USD). 0 = qarzga bermaslik.",
    ),
    "sleeping_client_days": (
        60,
        "Shuncha kun xarid qilmagan vrach 'uxlab qolgan mijoz' hisoblanadi.",
    ),
    "dead_stock_days": (
        90,
        "Shuncha kun sotilmagan mahsulot 'o'lik zaxira' hisoblanadi.",
    ),
    "birthday_notice_days": (
        3,
        "Tug'ilgan kundan necha kun oldin eslatma yuborilsin.",
    ),
    "low_stock_alerts": (
        True,
        "Qoldiq minimumdan pastga tushganda ogohlantirish yuborilsinmi.",
    ),
    "block_on_debt_limit": (
        True,
        "Qarz limiti oshganda yangi buyurtma direktor tasdig'iga yuborilsinmi.",
    ),
    "block_on_overdue": (
        True,
        "Muddati o'tgan qarzi bor vrachning buyurtmasi direktor tasdig'iga yuborilsinmi.",
    ),
    "visit_max_distance_m": (
        300,
        "Tashrif klinikadan shuncha metr ichida bo'lsa 'joyida' hisoblanadi.",
    ),
    "loyalty_weights": (
        {"recency": 25, "frequency": 25, "monetary": 25, "discipline": 25},
        "Sodiqlik ko'rsatkichi og'irliklari (jami 100 ball).",
    ),
    "abc_thresholds": (
        {"a_pct": 20, "b_pct": 50},
        "A toifa — yuqori 20%, B toifa — keyingi 30% (jami 50% gacha).",
    ),
    "company_name": ("DXL Dental Implant", "Hujjatlarda chiqadigan tashkilot nomi."),
    "company_phone": ("", "Hujjatlarda chiqadigan telefon raqam."),
}


async def get_setting(session: AsyncSession, key: str) -> Any:
    row = await session.get(Setting, key)
    if row is not None:
        return row.value.get("v") if isinstance(row.value, dict) and "v" in row.value else row.value
    default, _ = DEFAULT_SETTINGS.get(key, (None, ""))
    return default


async def get_settings_map(session: AsyncSession) -> dict[str, Any]:
    result = {key: default for key, (default, _) in DEFAULT_SETTINGS.items()}
    rows = (await session.execute(select(Setting))).scalars().all()
    for row in rows:
        value = row.value
        if isinstance(value, dict) and "v" in value:
            value = value["v"]
        result[row.key] = value
    return result


async def set_setting(session: AsyncSession, key: str, value: Any) -> None:
    row = await session.get(Setting, key)
    label = DEFAULT_SETTINGS.get(key, (None, ""))[1]
    if row is None:
        session.add(Setting(key=key, value={"v": value}, label_uz=label))
    else:
        row.value = {"v": value}
        if label:
            row.label_uz = label


async def ensure_defaults(session: AsyncSession) -> None:
    """Yetishmayotgan sozlamalarni standart qiymat bilan yaratadi."""
    existing = set(
        (await session.execute(select(Setting.key))).scalars().all()
    )
    for key, (default, label) in DEFAULT_SETTINGS.items():
        if key not in existing:
            session.add(Setting(key=key, value={"v": default}, label_uz=label))
