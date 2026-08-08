"""Mahsulot katalogi: kategoriyalar, mahsulotlar, Excel import/eksport."""

from __future__ import annotations

import io
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, require_perm
from app.db import get_session
from app.models import Product, ProductCategory, Stock, User
from app.permissions import PRODUCTS_EDIT, PRODUCTS_VIEW
from app.schemas import CategoryOut, OkOut, ProductIn, ProductOut, ProductUpdateIn
from app.utils.audit import log_action
from app.utils.excel import build_products_workbook, parse_products_workbook

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_perm(PRODUCTS_VIEW)),
):
    rows = (
        await session.execute(
            select(ProductCategory)
            .where(ProductCategory.is_active.is_(True))
            .order_by(ProductCategory.sort_order, ProductCategory.name_uz)
        )
    ).scalars().all()
    return rows


async def _product_rows(
    session: AsyncSession,
    *,
    search: str | None,
    category_id: int | None,
    implant_type: str | None,
    only_active: bool,
    in_stock: bool | None,
    limit: int,
    offset: int,
) -> list[ProductOut]:
    qty_sum = func.coalesce(func.sum(Stock.qty), 0).label("qty")
    reserved_sum = func.coalesce(func.sum(Stock.reserved_qty), 0).label("reserved")

    stmt = (
        select(Product, ProductCategory.name_uz, qty_sum, reserved_sum)
        .join(ProductCategory, ProductCategory.id == Product.category_id)
        .outerjoin(Stock, Stock.product_id == Product.id)
        .group_by(Product.id, ProductCategory.name_uz)
        .order_by(Product.name)
        .limit(limit)
        .offset(offset)
    )
    if only_active:
        stmt = stmt.where(Product.is_active.is_(True))
    if category_id:
        stmt = stmt.where(Product.category_id == category_id)
    if implant_type:
        stmt = stmt.where(Product.implant_type == implant_type)
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(or_(Product.name.ilike(pattern), Product.sku.ilike(pattern)))
    if in_stock is True:
        stmt = stmt.having(qty_sum > 0)
    elif in_stock is False:
        stmt = stmt.having(qty_sum <= 0)

    rows = (await session.execute(stmt)).all()
    result = []
    for product, category_name, qty, reserved in rows:
        out = ProductOut.model_validate(product)
        out.category_name = category_name
        out.qty = int(qty or 0)
        out.reserved = int(reserved or 0)
        out.available = out.qty - out.reserved
        result.append(out)
    return result


@router.get("/products", response_model=list[ProductOut])
async def list_products(
    search: str | None = None,
    category_id: int | None = None,
    implant_type: str | None = None,
    only_active: bool = True,
    in_stock: bool | None = None,
    limit: int = Query(default=200, le=1000),
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_perm(PRODUCTS_VIEW)),
):
    return await _product_rows(
        session,
        search=search,
        category_id=category_id,
        implant_type=implant_type,
        only_active=only_active,
        in_stock=in_stock,
        limit=limit,
        offset=offset,
    )


@router.get("/products/filters")
async def product_filters(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_perm(PRODUCTS_VIEW)),
):
    """Filtr uchun mavjud qiymatlar: turlar, diametrlar, uzunliklar."""
    types = (
        await session.execute(
            select(func.distinct(Product.implant_type))
            .where(Product.implant_type.is_not(None), Product.is_active.is_(True))
            .order_by(Product.implant_type)
        )
    ).scalars().all()
    diameters = (
        await session.execute(
            select(func.distinct(Product.diameter_mm))
            .where(Product.diameter_mm.is_not(None), Product.is_active.is_(True))
            .order_by(Product.diameter_mm)
        )
    ).scalars().all()
    lengths = (
        await session.execute(
            select(func.distinct(Product.length_mm))
            .where(Product.length_mm.is_not(None), Product.is_active.is_(True))
            .order_by(Product.length_mm)
        )
    ).scalars().all()
    return {
        "implant_types": [t for t in types if t],
        "diameters": [float(d) for d in diameters if d is not None],
        "lengths": [float(x) for x in lengths if x is not None],
    }


@router.get("/products/{product_id}", response_model=ProductOut)
async def get_product(
    product_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_perm(PRODUCTS_VIEW)),
):
    product = await session.get(Product, product_id)
    if product is None:
        raise HTTPException(404, "Mahsulot topilmadi")
    category = await session.get(ProductCategory, product.category_id)
    qty, reserved = (
        await session.execute(
            select(
                func.coalesce(func.sum(Stock.qty), 0),
                func.coalesce(func.sum(Stock.reserved_qty), 0),
            ).where(Stock.product_id == product_id)
        )
    ).one()
    out = ProductOut.model_validate(product)
    out.category_name = category.name_uz if category else None
    out.qty = int(qty or 0)
    out.reserved = int(reserved or 0)
    out.available = out.qty - out.reserved
    return out


@router.post("/products", response_model=ProductOut, status_code=201)
async def create_product(
    payload: ProductIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(PRODUCTS_EDIT)),
):
    exists = (
        await session.execute(select(Product).where(Product.sku == payload.sku))
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(409, f"Bu SKU allaqachon mavjud: {payload.sku}")

    product = Product(**payload.model_dump())
    session.add(product)
    await session.flush()
    await log_action(session, user, "create", "product", product.id, new=payload.model_dump())
    return await get_product(product.id, session, user)


@router.patch("/products/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: int,
    payload: ProductUpdateIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(PRODUCTS_EDIT)),
):
    product = await session.get(Product, product_id)
    if product is None:
        raise HTTPException(404, "Mahsulot topilmadi")

    changes = payload.model_dump(exclude_unset=True)
    old = {key: getattr(product, key) for key in changes}
    for key, value in changes.items():
        setattr(product, key, value)
    await session.flush()
    await log_action(session, user, "update", "product", product_id, old=old, new=changes)
    return await get_product(product_id, session, user)


@router.get("/products.xlsx")
async def export_products(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_perm(PRODUCTS_VIEW)),
):
    """Katalogni Excel'ga yuklab olish (import uchun ham shu format)."""
    rows = await _product_rows(
        session,
        search=None,
        category_id=None,
        implant_type=None,
        only_active=False,
        in_stock=None,
        limit=10_000,
        offset=0,
    )
    categories = (await session.execute(select(ProductCategory))).scalars().all()
    stream = build_products_workbook(rows, categories)
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="dxl-katalog.xlsx"'},
    )


@router.post("/products/import", response_model=OkOut)
async def import_products(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(PRODUCTS_EDIT)),
):
    """Excel'dan katalogni yuklash. SKU bo'yicha yangilaydi yoki yangi qo'shadi."""
    content = await file.read()
    try:
        parsed = parse_products_workbook(io.BytesIO(content))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    categories = {
        c.name_uz.strip().lower(): c
        for c in (await session.execute(select(ProductCategory))).scalars().all()
    }
    codes = {c.code: c for c in categories.values()}

    created = updated = 0
    for row in parsed:
        category = categories.get((row.get("category") or "").strip().lower()) or codes.get(
            (row.get("category") or "").strip()
        )
        if category is None:
            raise HTTPException(
                400, f"Kategoriya topilmadi: «{row.get('category')}» (SKU {row.get('sku')})"
            )

        product = (
            await session.execute(select(Product).where(Product.sku == row["sku"]))
        ).scalar_one_or_none()
        values = {
            "name": row["name"],
            "category_id": category.id,
            "diameter_mm": row.get("diameter_mm"),
            "length_mm": row.get("length_mm"),
            "implant_type": row.get("implant_type"),
            "connection_type": row.get("connection_type"),
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
    await log_action(
        session, user, "import", "product", None,
        new={"created": created, "updated": updated},
    )
    return OkOut(
        ok=True, message=f"{created} ta yangi qo'shildi, {updated} tasi yangilandi"
    )
