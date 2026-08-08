"""Katalogni bazaga yuklash: `python -m seed.load`."""

from __future__ import annotations

import asyncio
import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import session_scope
from app.models import Product, ProductCategory
from app.services.settings_service import ensure_defaults
from app.services.stock import main_warehouse
from seed.catalog import CATEGORIES, read_csv

log = logging.getLogger(__name__)


def _decimal_or_none(value) -> Decimal | None:
    if value in (None, "", "None"):
        return None
    return Decimal(str(value).replace(",", "."))


async def seed_categories(session: AsyncSession) -> dict[str, ProductCategory]:
    existing = {
        c.code: c
        for c in (await session.execute(select(ProductCategory))).scalars().all()
    }
    for code, name_uz, sort_order in CATEGORIES:
        if code in existing:
            continue
        category = ProductCategory(code=code, name_uz=name_uz, sort_order=sort_order)
        session.add(category)
        existing[code] = category
    await session.flush()
    return existing


async def seed_products(session: AsyncSession) -> tuple[int, int]:
    categories = await seed_categories(session)
    rows = read_csv()

    created = updated = 0
    for row in rows:
        category = categories.get(row["category"])
        if category is None:
            log.warning("Kategoriya topilmadi: %s", row["category"])
            continue

        product = (
            await session.execute(select(Product).where(Product.sku == row["sku"]))
        ).scalar_one_or_none()
        values = {
            "name": row["name"],
            "category_id": category.id,
            "diameter_mm": _decimal_or_none(row.get("diameter_mm")),
            "length_mm": _decimal_or_none(row.get("length_mm")),
            "implant_type": row.get("implant_type") or None,
            "connection_type": row.get("connection_type") or None,
            "price_usd": Decimal(str(row.get("price_usd") or 0)),
            "min_stock": int(row.get("min_stock") or 0),
        }
        if product is None:
            session.add(Product(sku=row["sku"], **values))
            created += 1
        else:
            for key, value in values.items():
                setattr(product, key, value)
            updated += 1

    await session.flush()
    return created, updated


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    async with session_scope() as session:
        await ensure_defaults(session)
        await main_warehouse(session)
        created, updated = await seed_products(session)
    print(f"Katalog yuklandi: {created} ta yangi, {updated} tasi yangilandi")


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
