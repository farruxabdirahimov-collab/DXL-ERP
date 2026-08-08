"""Test muhiti: har test uchun toza SQLite bazasi."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# DIQQAT: app modullari import qilinishidan OLDIN sozlanishi shart
_TMP_DIR = Path(tempfile.mkdtemp(prefix="dxl-test-"))
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_TMP_DIR}/test.db")
os.environ.setdefault("BOT_TOKEN", "")
os.environ.setdefault("AUTO_MIGRATE", "0")
os.environ.setdefault("TZ", "Asia/Tashkent")
os.environ.setdefault("DEFAULT_USD_UZS", "12500")

from app.db import SessionLocal, engine  # noqa: E402
from app.models import (  # noqa: E402
    Base,
    Doctor,
    Product,
    ProductCategory,
    Role,
    User,
    Warehouse,
    WarehouseKind,
)
from app.services.settings_service import ensure_defaults  # noqa: E402


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def session():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:
        await ensure_defaults(session)
        await session.commit()
        yield session
        await session.rollback()


@pytest.fixture
async def base_data(session):
    """Minimal ma'lumot: ombor, kategoriya, 2 mahsulot, agent, vrach."""
    warehouse = Warehouse(name="Markaziy ombor", kind=WarehouseKind.MAIN, is_active=True)
    category = ProductCategory(code="implant", name_uz="Implantlar", sort_order=10)
    session.add_all([warehouse, category])
    await session.flush()

    implant = Product(
        sku="DXL-BL-40x10",
        name="DXL Bone Level 4.0x10",
        category_id=category.id,
        diameter_mm=4,
        length_mm=10,
        implant_type="Bone Level",
        price_usd=100,
        min_stock=5,
    )
    cap = Product(
        sku="DXL-HC-40",
        name="DXL healing cap 4.0",
        category_id=category.id,
        price_usd=15,
        min_stock=10,
    )
    session.add_all([implant, cap])

    director = User(full_name="Direktor", role=Role.DIRECTOR, telegram_id=1001)
    agent = User(full_name="Agent", role=Role.AGENT, telegram_id=1002)
    keeper = User(full_name="Omborchi", role=Role.WAREHOUSE, telegram_id=1003)
    accountant = User(full_name="Buxgalter", role=Role.ACCOUNTANT, telegram_id=1004)
    session.add_all([director, agent, keeper, accountant])
    await session.flush()

    doctor = Doctor(
        full_name="Vrach Aziz",
        phone="+998901234567",
        agent_id=agent.id,
        debt_limit_usd=1000,
        payment_term_days=30,
    )
    session.add(doctor)
    await session.flush()
    await session.commit()

    return {
        "warehouse": warehouse,
        "implant": implant,
        "cap": cap,
        "director": director,
        "agent": agent,
        "keeper": keeper,
        "accountant": accountant,
        "doctor": doctor,
    }
