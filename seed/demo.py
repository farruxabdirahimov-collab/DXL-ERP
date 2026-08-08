"""Sinov uchun namunaviy ma'lumot: `python -m seed.demo`.

Ishlab chiqarish bazasida ISHLATMANG — faqat tizimni sinab ko'rish uchun.
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import session_scope
from app.models import (
    Doctor,
    OrderSource,
    PaymentMethod,
    Product,
    Role,
    User,
    utcnow,
)
from app.services import (
    fx as fx_service,
    loyalty,
    orders as orders_service,
    payments as payments_service,
    plans as plans_service,
    stock as stock_service,
)
from app.services.settings_service import ensure_defaults
from seed.load import seed_products

log = logging.getLogger(__name__)

REGIONS = ["Toshkent", "Samarqand", "Farg'ona", "Andijon", "Namangan", "Buxoro"]

DEMO_STAFF = [
    ("Direktor Demo", Role.DIRECTOR, "+998901110001", False),
    ("Ta'sischi Demo", Role.FOUNDER, "+998901110002", False),
    ("Buxgalter Demo", Role.ACCOUNTANT, "+998901110003", False),
    ("Omborchi Demo", Role.WAREHOUSE, "+998901110004", False),
    ("Agent Aziz", Role.AGENT, "+998901110005", True),
    ("Agent Dilnoza", Role.AGENT, "+998901110006", False),
    ("Agent Sardor", Role.AGENT, "+998901110007", False),
]

DEMO_DOCTORS = [
    "Karimov Aziz", "Yusupova Malika", "Rahimov Bekzod", "Toshmatova Nilufar",
    "Ergashev Jasur", "Sobirova Zulfiya", "Nazarov Otabek", "Qodirova Dildora",
    "Umarov Sherzod", "Islomova Kamola", "Xolmatov Rustam", "Ahmedova Sevara",
    "Yo'ldoshev Farrux", "Mirzayeva Gulnora", "Sattorov Ulug'bek",
]


async def _get_or_create_user(
    session: AsyncSession, name: str, role: Role, phone: str, own_stock: bool
) -> User:
    user = (
        await session.execute(select(User).where(User.phone == phone))
    ).scalar_one_or_none()
    if user is not None:
        return user
    user = User(
        full_name=name, role=role, phone=phone, is_active=True, has_own_stock=own_stock
    )
    session.add(user)
    await session.flush()
    if role is Role.AGENT and own_stock:
        await stock_service.ensure_agent_warehouse(session, user)
    return user


async def seed_demo_data() -> None:
    random.seed(42)
    async with session_scope() as session:
        await ensure_defaults(session)
        await seed_products(session)

        warehouse = await stock_service.main_warehouse(session)
        await fx_service.set_rate(session, Decimal(str(settings.default_usd_uzs)))

        staff = [
            await _get_or_create_user(session, *row) for row in DEMO_STAFF
        ]
        agents = [u for u in staff if u.role is Role.AGENT]
        director = next(u for u in staff if u.role is Role.DIRECTOR)
        warehouse_user = next(u for u in staff if u.role is Role.WAREHOUSE)
        accountant = next(u for u in staff if u.role is Role.ACCOUNTANT)

        products = (
            await session.execute(select(Product).where(Product.is_active.is_(True)))
        ).scalars().all()

        # --- Kirim: har mahsulotdan omborga tovar kiritamiz ---
        existing_moves = (
            await session.execute(select(func.count()).select_from(Product))
        ).scalar_one()
        receipt_lines = [
            (p.id, random.randint(150, 600), Decimal(p.price_usd) * Decimal("0.55"))
            for p in products
        ]
        await orders_service.receive_stock(
            session,
            warehouse_id=warehouse.id,
            lines=receipt_lines,
            actor=warehouse_user,
            supplier="DXL Korea",
            invoice_no="DEMO-0001",
            note="Namunaviy boshlang'ich kirim",
        )
        log.info("Kirim qilindi: %s ta pozitsiya", existing_moves)

        # --- Vrachlar ---
        doctors: list[Doctor] = []
        for index, name in enumerate(DEMO_DOCTORS):
            phone = f"+9989{random.randint(10_000_000, 99_999_999)}"
            doctor = (
                await session.execute(select(Doctor).where(Doctor.full_name == name))
            ).scalar_one_or_none()
            if doctor is None:
                doctor = Doctor(
                    full_name=name,
                    phone=phone,
                    clinic_name=f"«{random.choice(['Smile', 'Dental Plus', 'Med Line', 'Implant Pro'])}» klinikasi",
                    region=random.choice(REGIONS),
                    address=f"{random.randint(1, 90)}-uy, {random.choice(REGIONS)} sh.",
                    lat=41.31 + random.uniform(-0.4, 0.4),
                    lon=69.24 + random.uniform(-0.4, 0.4),
                    birth_date=date(
                        random.randint(1968, 1995),
                        random.randint(1, 12),
                        random.randint(1, 28),
                    ),
                    specialty=random.choice(
                        ["Implantolog", "Jarroh-stomatolog", "Ortoped", "Terapevt"]
                    ),
                    agent_id=agents[index % len(agents)].id,
                    debt_limit_usd=Decimal(random.choice([500, 1000, 2000, 3000])),
                    payment_term_days=random.choice([14, 21, 30, 45]),
                    created_by_id=director.id,
                )
                session.add(doctor)
                await session.flush()
            doctors.append(doctor)

        # --- Oxirgi 120 kunlik sotuv tarixi ---
        implant_products = [p for p in products if p.implant_type not in (None, "Asbob")]
        today = fx_service.today_local()

        for day_offset in range(120, 0, -1):
            day = today - timedelta(days=day_offset)
            if day.weekday() == 6:  # yakshanba dam
                continue
            for _ in range(random.randint(0, 3)):
                doctor = random.choice(doctors)
                actor = next(
                    (a for a in agents if a.id == doctor.agent_id), agents[0]
                )
                lines = [
                    orders_service.LineInput(
                        product_id=random.choice(implant_products).id,
                        qty=random.randint(1, 6),
                    )
                    for _ in range(random.randint(1, 3))
                ]
                try:
                    order = await orders_service.create_order(
                        session,
                        doctor=doctor,
                        lines=lines,
                        actor=actor,
                        source=random.choice([OrderSource.AGENT, OrderSource.DOCTOR]),
                        warehouse_id=warehouse.id,
                        discount_pct=Decimal(random.choice([0, 0, 0, 5])),
                    )
                    order.needs_director = False
                    order = await orders_service.approve(session, order, director)
                    order = await orders_service.deliver(session, order, warehouse_user)
                    # Sanalarni orqaga suramiz
                    delivered = utcnow() - timedelta(days=day_offset)
                    order.created_at = delivered
                    order.delivered_at = delivered
                    order.due_date = day + timedelta(days=doctor.payment_term_days)

                    # Buyurtmalarning ~65 foizi to'langan
                    if random.random() < 0.65:
                        await payments_service.create_payment(
                            session,
                            doctor=doctor,
                            amount_uzs=(
                                Decimal(order.total_usd) * Decimal(order.fx_rate)
                            ),
                            method=random.choice(list(PaymentMethod)),
                            actor=accountant,
                            order_id=order.id,
                            paid_at=delivered + timedelta(days=random.randint(1, 40)),
                        )
                except Exception as exc:  # qoldiq tugagan bo'lishi mumkin
                    log.debug("Demo buyurtma o'tkazilmadi: %s", exc)

        # --- Oylik rejalar ---
        for agent in agents:
            await plans_service.upsert_plan(
                session,
                user_id=agent.id,
                year=today.year,
                month=today.month,
                target_amount_usd=Decimal(random.choice([6000, 8000, 12000])),
                target_units=random.choice([80, 120, 150]),
                target_collection_usd=Decimal(random.choice([5000, 7000, 10000])),
                actor=director,
            )

        await loyalty.recalculate(session, today)

    print("✅ Demo ma'lumot yuklandi")
    print("   Xodimlar telefon raqamlari: +99890111000X (1..7)")
    print("   Ular Telegram'ga ulanishi uchun /admin/users bo'limidan telegram_id qo'ying.")


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    asyncio.run(seed_demo_data())
