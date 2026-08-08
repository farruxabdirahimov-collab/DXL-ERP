"""Kunlik statistika — har kuni soat 21:00 da (Asia/Tashkent).

Har rol o'ziga kerakli kesimni oladi.
"""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import session_scope
from app.models import Doctor, Role, Task, TaskStatus, User
from app.services import plans as plans_service, reports as rp
from app.services.debt import overdue_orders, total_debt
from app.services.fx import get_rate, today_local
from app.utils.fmt import (
    bullet_list,
    fmt_date,
    money_usd,
    money_uzs,
    number,
    plan_emoji,
    progress_bar,
)

log = logging.getLogger(__name__)


async def build_management_report(session: AsyncSession, day: date) -> str:
    """Direktor, ta'sischi va super-admin uchun to'liq kunlik hisobot."""
    start, end = rp.day_bounds(day)
    month_start = rp.month_start(day)

    today = await rp.sales_summary(session, start, end)
    month = await rp.sales_summary(session, month_start, end)
    debt = await total_debt(session, day)
    rate = await get_rate(session, day)

    low = await rp.low_stock(session)
    out = [row for row in low if row["qty"] == 0]
    top = await rp.top_products(session, start, end, limit=5)
    new_doctors = await rp.new_doctors_count(session, start, end)
    agents = await plans_service.leaderboard(session, day.year, day.month)

    lines = [
        f"📊 <b>Kunlik hisobot — {fmt_date(day)}</b>",
        f"<i>Kurs: 1 USD = {number(rate)} so'm</i>",
        "",
        "<b>🛒 Bugungi sotuv</b>",
        f"  Summa: {money_usd(today['amount_usd'])} ({money_uzs(today['amount_usd'] * rate)})",
        f"  Dona: {number(today['units'])} | Buyurtma: {number(today['orders'])} | "
        f"Vrach: {number(today['doctors'])}",
        f"  Yig'ilgan pul: {money_usd(today['collected_usd'])}",
        "",
        "<b>📅 Oy boshidan</b>",
        f"  Sotuv: {money_usd(month['amount_usd'])} | {number(month['units'])} dona",
        f"  Yig'ilgan: {money_usd(month['collected_usd'])}",
        f"  Yangi vrachlar (bugun): {number(new_doctors)}",
        "",
        "<b>💳 Qarzdorlik</b>",
        f"  Jami: {money_usd(debt['total_usd'])}",
        f"  ⚠️ Muddati o'tgan: {money_usd(debt['overdue_usd'])}",
        f"  Qarzdor vrachlar: {number(debt['doctors_in_debt'])}",
    ]

    overdue = await overdue_orders(session, day)
    if overdue:
        worst = sorted(overdue, key=lambda o: o.due_date)[:5]
        items = []
        for order in worst:
            doctor = await session.get(Doctor, order.doctor_id)
            days_late = (day - order.due_date).days
            items.append(
                f"{doctor.full_name if doctor else '—'}: {money_usd(order.debt_usd)} "
                f"({days_late} kun)"
            )
        lines += ["", "<b>⏰ Eng ko'p kechikkanlar</b>", bullet_list(items, limit=5)]

    if top:
        lines += [
            "",
            "<b>🏅 Bugun eng ko'p sotilgan</b>",
            bullet_list(
                [f"{p['name']} ({p['size']}) — {p['qty']} dona" for p in top], limit=5
            ),
        ]

    if low:
        lines += [
            "",
            f"<b>📦 Omborda kam qoldi ({len(low)} ta)</b>",
            bullet_list(
                [
                    f"{r['name']} — {r['qty']} dona"
                    + (f", ~{r['days_left']} kunga yetadi" if r.get("days_left") else "")
                    for r in low
                ],
                limit=8,
            ),
        ]
    if out:
        lines += ["", f"<b>❌ Tugagan: {len(out)} ta mahsulot</b>"]

    if agents:
        rows = []
        for index, agent in enumerate(agents, start=1):
            rows.append(
                f"{index}. {agent.full_name} — {plan_emoji(agent.overall_pct)} "
                f"{agent.overall_pct:g}% ({money_usd(agent.amount.fact)})"
            )
        lines += ["", "<b>👥 Agentlar (oylik reja)</b>", "\n".join(rows[:10])]

    return "\n".join(lines)


async def build_agent_report(session: AsyncSession, agent: User, day: date) -> str:
    """Agentga: bugungi natija + oylik reja bajarilishi + ertangi vazifalar."""
    start, end = rp.day_bounds(day)
    today = await rp.sales_summary(session, start, end, agent_id=agent.id)
    progress = await plans_service.progress(session, agent, day.year, day.month)
    pace = plans_service.expected_pace_pct(progress.days_passed, progress.days_in_month)

    lines = [
        f"📊 <b>Kunlik natija — {fmt_date(day)}</b>",
        "",
        "<b>Bugun</b>",
        f"  Sotuv: {money_usd(today['amount_usd'])} | {number(today['units'])} dona",
        f"  Yig'ilgan pul: {money_usd(today['collected_usd'])}",
        "",
        f"<b>Oylik reja ({progress.days_passed}/{progress.days_in_month} kun)</b>",
    ]

    if progress.has_plan:
        for title, metric in (
            ("💵 Sotuv", progress.amount),
            ("📦 Dona", progress.units),
            ("💰 Yig'ilgan", progress.collection),
        ):
            if metric.target <= 0:
                continue
            lines.append(
                f"  {title}: {progress_bar(metric.pct)} {metric.pct:g}%\n"
                f"     {metric.fact:,.0f} / {metric.target:,.0f}".replace(",", " ")
            )
        lines.append(
            f"\n  {plan_emoji(progress.overall_pct)} <b>Umumiy: {progress.overall_pct:g}%</b> "
            f"(kutilgan temp: {pace:g}%)"
        )
        if progress.overall_pct + 5 < pace:
            lines.append("  ⚠️ Rejadan orqadasiz — ertaga jadalroq ishlash kerak.")
    else:
        lines.append("  Bu oyga reja belgilanmagan.")

    overdue = await overdue_orders(session, day, agent_id=agent.id)
    if overdue:
        items = []
        for order in sorted(overdue, key=lambda o: o.due_date)[:5]:
            doctor = await session.get(Doctor, order.doctor_id)
            items.append(
                f"{doctor.full_name if doctor else '—'} — {money_usd(order.debt_usd)} "
                f"({(day - order.due_date).days} kun kechikdi)"
            )
        lines += ["", "<b>⏰ Undirish kerak</b>", bullet_list(items, limit=5)]

    tasks = (
        await session.execute(
            select(Task).where(
                Task.user_id == agent.id,
                Task.status == TaskStatus.OPEN,
                Task.due_date <= day,
            ).order_by(Task.due_date).limit(6)
        )
    ).scalars().all()
    if tasks:
        lines += [
            "",
            "<b>📌 Ochiq vazifalar</b>",
            bullet_list([task.title for task in tasks], limit=6),
        ]

    return "\n".join(lines)


async def build_warehouse_report(session: AsyncSession, day: date) -> str:
    summary = await rp.warehouse_day_summary(session, day)
    low = await rp.low_stock(session)
    moves = summary["moves"]

    lines = [
        f"📦 <b>Ombor — {fmt_date(day)}</b>",
        "",
        f"  Kirim: {number(moves.get('in', 0))} dona",
        f"  Sotuv (chiqim): {number(moves.get('sale', 0))} dona",
        f"  Ko'chirish: {number(moves.get('transfer', 0))} dona",
        f"  Qaytarish: {number(moves.get('return', 0))} dona",
        f"  Spisaniye: {number(moves.get('writeoff', 0))} dona",
        "",
        f"  ⏳ Yig'ish kutayotgan buyurtmalar: {number(summary['waiting_orders'])}",
    ]
    if low:
        lines += [
            "",
            f"<b>🔔 Kam qolgan ({len(low)} ta)</b>",
            bullet_list(
                [f"{r['name']} — {r['qty']}/{r['min_stock']}" for r in low], limit=10
            ),
        ]
    return "\n".join(lines)


async def build_accountant_report(session: AsyncSession, day: date) -> str:
    start, end = rp.day_bounds(day)
    payments = await rp.payments_summary(session, start, end)
    debt = await total_debt(session, day)
    aging = await rp.debt_aging(session, day)

    from app.services.debt import due_soon_orders

    due_soon = await due_soon_orders(session, days=3, on_date=day)

    lines = [
        f"💰 <b>Moliya — {fmt_date(day)}</b>",
        "",
        f"  Bugungi tushum: {money_uzs(payments['total_uzs'])} "
        f"({money_usd(payments['total_usd'])})",
    ]
    for method, data in payments["by_method"].items():
        label = {"cash": "Naqd", "card": "Karta", "transfer": "O'tkazma"}.get(method, method)
        lines.append(f"    {label}: {money_uzs(data['amount_uzs'])}")

    lines += [
        "",
        f"  Umumiy qarz: {money_usd(debt['total_usd'])}",
        f"  ⚠️ Muddati o'tgan: {money_usd(debt['overdue_usd'])}",
        "",
        "<b>Qarz yoshi</b>",
    ]
    for name, value in aging.items():
        lines.append(f"  {name}: {money_usd(value)}")

    if due_soon:
        items = []
        for order in due_soon[:8]:
            doctor = await session.get(Doctor, order.doctor_id)
            items.append(
                f"{doctor.full_name if doctor else '—'} — {money_usd(order.debt_usd)} "
                f"({fmt_date(order.due_date)})"
            )
        lines += ["", "<b>📆 3 kun ichida muddati tugaydi</b>", bullet_list(items, limit=8)]

    return "\n".join(lines)


async def send_daily_reports(day: date | None = None) -> None:
    """Barcha rollarga kunlik statistikani yuboradi (21:00 jobi)."""
    from app.bot import notify

    day = day or today_local()
    async with session_scope() as session:
        dedup = f"daily:{day.isoformat()}"

        text = await build_management_report(session, day)
        await notify.send_to_roles(
            session,
            [Role.DIRECTOR, Role.FOUNDER, Role.SUPERADMIN],
            text,
            kind="daily_management",
            dedup_key=dedup,
            button=("Batafsil ko'rish", "/reports"),
        )

        wh_text = await build_warehouse_report(session, day)
        await notify.send_to_roles(
            session, [Role.WAREHOUSE], wh_text, kind="daily_warehouse",
            dedup_key=dedup, button=("Omborni ochish", "/stock"),
        )

        acc_text = await build_accountant_report(session, day)
        await notify.send_to_roles(
            session, [Role.ACCOUNTANT], acc_text, kind="daily_finance",
            dedup_key=dedup, button=("Qarzlarni ko'rish", "/debts"),
        )

        agents = (
            await session.execute(
                select(User).where(User.role == Role.AGENT, User.is_active.is_(True))
            )
        ).scalars().all()
        for agent in agents:
            agent_text = await build_agent_report(session, agent, day)
            await notify.send_to_user(
                session, agent, agent_text, kind="daily_agent",
                dedup_key=dedup, button=("Rejani ko'rish", "/plan"),
            )

    log.info("Kunlik hisobot yuborildi: %s", day)
