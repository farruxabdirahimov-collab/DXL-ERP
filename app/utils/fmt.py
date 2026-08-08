"""Matnni chiroyli ko'rsatish uchun yordamchilar (o'zbekcha)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from app.config import settings


def as_aware(value: datetime | None) -> datetime | None:
    """Vaqt zonasi yo'q sanaga zona qo'shadi (SQLite bilan sinov uchun)."""
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=settings.timezone)

MONTHS_UZ = [
    "yanvar", "fevral", "mart", "aprel", "may", "iyun",
    "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr",
]

WEEKDAYS_UZ = [
    "dushanba", "seshanba", "chorshanba", "payshanba",
    "juma", "shanba", "yakshanba",
]


def money_usd(value: Decimal | float | int | None) -> str:
    value = Decimal(str(value or 0))
    return f"${value:,.2f}".replace(",", " ")


def money_uzs(value: Decimal | float | int | None) -> str:
    value = Decimal(str(value or 0))
    return f"{value:,.0f} so'm".replace(",", " ")


def number(value: int | float | None) -> str:
    return f"{value or 0:,.0f}".replace(",", " ")


def pct(value: float | None) -> str:
    return f"{value or 0:.0f}%"


def fmt_date(value: date | datetime | None) -> str:
    if value is None:
        return "—"
    if isinstance(value, datetime):
        value = value.date()
    return f"{value.day} {MONTHS_UZ[value.month - 1]} {value.year}"


def fmt_short_date(value: date | datetime | None) -> str:
    if value is None:
        return "—"
    if isinstance(value, datetime):
        value = value.date()
    return value.strftime("%d.%m.%Y")


def progress_bar(percent: float, width: int = 10) -> str:
    """Reja bajarilishini vizual ko'rsatish: ▓▓▓▓▓░░░░░"""
    filled = max(0, min(width, round(percent / 100 * width)))
    return "▓" * filled + "░" * (width - filled)


def plan_emoji(percent: float) -> str:
    if percent >= 100:
        return "🏆"
    if percent >= 80:
        return "🟢"
    if percent >= 50:
        return "🟡"
    return "🔴"


def bullet_list(items: list[str], limit: int = 10, empty: str = "— yo'q") -> str:
    if not items:
        return empty
    shown = items[:limit]
    text = "\n".join(f"  • {item}" for item in shown)
    if len(items) > limit:
        text += f"\n  … va yana {len(items) - limit} ta"
    return text
