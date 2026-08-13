"""Hisobotlar va mahsulot tahlili."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_perm
from app.config import settings
from app.db import get_session
from app.models import Role, User
from app.permissions import REPORTS_FINANCE, REPORTS_VIEW, doctor_scope
from app.services import reports as rp
from app.utils.excel import build_workbook

router = APIRouter(prefix="/reports", tags=["reports"])


def _range(date_from: date | None, date_to: date | None) -> tuple[datetime, datetime]:
    """Standart oraliq — joriy oy boshidan bugungacha."""
    today = rp.today_local()
    date_to = date_to or today
    date_from = date_from or today.replace(day=1)
    if date_from > date_to:
        raise HTTPException(400, "Boshlanish sanasi tugash sanasidan katta")
    tz = settings.timezone
    return (
        datetime.combine(date_from, time.min, tzinfo=tz),
        datetime.combine(date_to, time.max, tzinfo=tz),
    )


@router.get("/dashboard")
async def dashboard(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(REPORTS_VIEW)),
):
    data = await rp.dashboard(session)
    if doctor_scope(user) is not None:
        start, end = _range(None, None)
        data["my_month"] = await rp.sales_summary(session, start, end, agent_id=user.id)
    return data


@router.get("/sales")
async def sales(
    date_from: date | None = None,
    date_to: date | None = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(REPORTS_VIEW)),
):
    start, end = _range(date_from, date_to)
    agent_id = doctor_scope(user)
    return {
        "summary": await rp.sales_summary(session, start, end, agent_id=agent_id),
        "by_category": await rp.category_breakdown(session, start, end),
        "by_type": await rp.sales_by_type(session, start, end),
    }


@router.get("/trend")
async def trend(
    days: int = Query(default=30, ge=7, le=180),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_perm(REPORTS_VIEW)),
):
    return await rp.sales_trend(session, days)


# ------------------------------------------------------- mahsulot tahlili
@router.get("/products/top")
async def top_products(
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=20, le=100),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_perm(REPORTS_VIEW)),
):
    """Eng ko'p sotilgan mahsulotlar."""
    start, end = _range(date_from, date_to)
    return await rp.top_products(session, start, end, limit=limit)


@router.get("/products/least")
async def least_products(
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=20, le=100),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_perm(REPORTS_VIEW)),
):
    """Eng kam sotilgan (lekin sotilgan) mahsulotlar."""
    start, end = _range(date_from, date_to)
    return await rp.top_products(session, start, end, limit=limit, ascending=True)


@router.get("/products/sizes")
async def size_demand(
    date_from: date | None = None,
    date_to: date | None = None,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_perm(REPORTS_VIEW)),
):
    """Eng talabgir implant razmerlari (diametr x uzunlik).

    `sold` — sof talab (qaytarilgani ayirilgan), `returned` — qaysi razmerlar
    qaytarib berilgani. Ikkalasi yonma-yon ko'rinsin uchun birga qaytariladi.
    """
    start, end = _range(date_from, date_to)
    return {
        "sold": await rp.size_demand(session, start, end),
        "returned": await rp.returned_sizes(session, start, end),
    }


@router.get("/products/types")
async def by_type(
    date_from: date | None = None,
    date_to: date | None = None,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_perm(REPORTS_VIEW)),
):
    start, end = _range(date_from, date_to)
    return await rp.sales_by_type(session, start, end)


@router.get("/products/dead")
async def dead_stock(
    days: int | None = None,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_perm(REPORTS_VIEW)),
):
    """O'lik zaxira — uzoq vaqt sotilmagan, lekin omborda turgan tovar."""
    return await rp.dead_stock(session, days)


@router.get("/products/low")
async def low_stock(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_perm(REPORTS_VIEW)),
):
    return await rp.low_stock(session)


@router.get("/products/out")
async def out_of_stock(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_perm(REPORTS_VIEW)),
):
    return await rp.out_of_stock(session)


# --------------------------------------------------------- vrach / agent
@router.get("/doctors")
async def doctors_report(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(REPORTS_VIEW)),
):
    agent_id = doctor_scope(user)
    return await rp.doctor_rows(session, agent_id=agent_id)


@router.get("/agents")
async def agents_report(
    date_from: date | None = None,
    date_to: date | None = None,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_perm(REPORTS_FINANCE)),
):
    start, end = _range(date_from, date_to)
    return await rp.agent_rows(session, start, end)


@router.get("/payments")
async def payments_report(
    date_from: date | None = None,
    date_to: date | None = None,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_perm(REPORTS_FINANCE)),
):
    start, end = _range(date_from, date_to)
    return await rp.payments_summary(session, start, end)


# ------------------------------------------------------------- eksport
_EXPORT_COLUMNS = {
    "top": [
        ("sku", "SKU"), ("name", "Nomi"), ("size", "Razmer"),
        ("implant_type", "Turi"), ("qty", "Sotilgan (dona)"), ("amount_usd", "Summa (USD)"),
    ],
    "sizes": [
        ("size", "Razmer"), ("diameter_mm", "Diametr"), ("length_mm", "Uzunlik"),
        ("qty", "Sotilgan (dona)"), ("amount_usd", "Summa (USD)"),
    ],
    "low": [
        ("sku", "SKU"), ("name", "Nomi"), ("size", "Razmer"), ("qty", "Qoldiq"),
        ("min_stock", "Minimum"), ("shortage", "Yetishmaydi"),
        ("avg_daily", "Kunlik sarf"), ("days_left", "Necha kunga yetadi"),
    ],
    "dead": [
        ("sku", "SKU"), ("name", "Nomi"), ("size", "Razmer"), ("qty", "Qoldiq"),
        ("value_usd", "Qotib qolgan pul (USD)"), ("days_idle", "Necha kun sotilmagan"),
    ],
    "stock": [
        ("sku", "SKU"), ("name", "Nomi"), ("category", "Kategoriya"), ("size", "Razmer"),
        ("qty", "Qoldiq"), ("reserved", "Band"), ("available", "Bo'sh"),
        ("min_stock", "Minimum"), ("value_usd", "Qiymati (USD)"),
    ],
    "debts": [
        ("full_name", "Vrach"), ("clinic_name", "Klinika"), ("phone", "Telefon"),
        ("category", "Toifa"), ("debt_usd", "Qarz (USD)"),
        ("overdue_usd", "Muddati o'tgan (USD)"), ("oldest_due_date", "Eng eski muddat"),
        ("overdue_days", "Kechikish (kun)"), ("debt_limit_usd", "Limit (USD)"),
    ],
    "doctors": [
        ("full_name", "Vrach"), ("clinic_name", "Klinika"), ("phone", "Telefon"),
        ("region", "Hudud"), ("birth_date", "Tug'ilgan kun"), ("category", "Toifa"),
        ("loyalty_score", "Sodiqlik"), ("purchased_12m_usd", "12 oylik xarid (USD)"),
        ("orders_12m", "Buyurtmalar"), ("last_order_at", "Oxirgi xarid"),
        ("debt_usd", "Qarz (USD)"), ("overdue_usd", "Muddati o'tgan (USD)"),
    ],
    "agents": [
        ("full_name", "Agent"), ("doctors", "Vrachlar"), ("amount_usd", "Sotuv (USD)"),
        ("units", "Dona"), ("orders", "Buyurtmalar"), ("collected_usd", "Yig'ilgan (USD)"),
    ],
}


@router.get("/export.xlsx")
async def export_report(
    kind: str = Query(..., description="top | sizes | low | dead | stock | debts | doctors | agents"),
    date_from: date | None = None,
    date_to: date | None = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(REPORTS_VIEW)),
):
    """Hisobotni Excel'ga yuklab olish."""
    if kind not in _EXPORT_COLUMNS:
        raise HTTPException(400, f"Noma'lum hisobot turi: {kind}")

    start, end = _range(date_from, date_to)
    agent_id = doctor_scope(user)

    if kind == "top":
        rows = await rp.top_products(session, start, end, limit=200)
        title = "Eng ko'p sotilgan"
    elif kind == "sizes":
        rows = await rp.size_demand(session, start, end, limit=200)
        title = "Talabgir razmerlar"
    elif kind == "low":
        rows = await rp.low_stock(session)
        title = "Kam qolganlar"
    elif kind == "dead":
        rows = await rp.dead_stock(session)
        title = "O'lik zaxira"
    elif kind == "stock":
        rows = await rp.stock_by_product(session)
        title = "Ombor qoldig'i"
    elif kind == "debts":
        rows = await rp.doctor_debt_rows(session, agent_id=agent_id)
        title = "Qarzlar"
    elif kind == "doctors":
        rows = await rp.doctor_rows(session, agent_id=agent_id)
        title = "Vrachlar"
    else:
        rows = await rp.agent_rows(session, start, end)
        title = "Agentlar"

    stream = build_workbook({title: (_EXPORT_COLUMNS[kind], rows)})
    filename = f"dxl-{kind}-{rp.today_local().isoformat()}.xlsx"
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/daily-preview")
async def daily_preview(
    on_date: date | None = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(REPORTS_VIEW)),
):
    """21:00 da yuboriladigan kunlik statistikani oldindan ko'rish."""
    from app.jobs.daily_report import build_management_report

    day = on_date or rp.today_local()
    text = await build_management_report(session, day)
    return {"date": day.isoformat(), "text": text}


@router.get("/warehouse-day")
async def warehouse_day(
    on_date: date | None = None,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_perm(REPORTS_VIEW)),
):
    return await rp.warehouse_day_summary(session, on_date or rp.today_local())
