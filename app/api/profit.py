"""Foyda-zarar, tannarx va xarajatlar."""

from __future__ import annotations

from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_perm
from app.db import get_session
from app.models import (
    EXPENSE_LABELS_UZ,
    Expense,
    ExpenseCategory,
    Product,
    ProductCategory,
    User,
)
from app.permissions import PRODUCTS_EDIT, REPORTS_FINANCE
from app.schemas import BulkCostIn, ExpenseIn, OkOut
from app.services import profit as profit_service
from app.services.fx import today_local
from app.utils.audit import log_action

router = APIRouter(prefix="/profit", tags=["profit"])


# ----------------------------------------------------------------- hisobot
@router.get("")
async def profit_report(
    year: int | None = None,
    month: int | None = None,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_perm(REPORTS_FINANCE)),
):
    """Oylik foyda-zarar. Agent bu bo'limni ko'rmaydi."""
    today = today_local()
    return await profit_service.monthly_report(
        session, year or today.year, month or today.month
    )


# ----------------------------------------------------------------- tannarx
@router.get("/cost-status")
async def cost_status(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_perm(PRODUCTS_EDIT)),
):
    """Qaysi kategoriyada tannarx to'ldirilgan — to'ldirish ekrani uchun."""
    rows = (
        await session.execute(
            select(ProductCategory).order_by(ProductCategory.sort_order)
        )
    ).scalars().all()

    natija = []
    for category in rows:
        mahsulotlar = (
            await session.execute(
                select(Product).where(
                    Product.category_id == category.id, Product.is_active.is_(True)
                )
            )
        ).scalars().all()
        if not mahsulotlar:
            continue
        tannarxlar = {c for c in (p.cost_usd for p in mahsulotlar)}
        natija.append(
            {
                "category_id": category.id,
                "code": category.code,
                "name": category.name_uz,
                "products": len(mahsulotlar),
                "missing": sum(1 for p in mahsulotlar if p.cost_usd <= 0),
                # Hammasi bir xil bo'lsa — bitta raqam ko'rsatiladi
                "same_cost": tannarxlar.pop() if len(tannarxlar) == 1 else None,
            }
        )
    return {
        "categories": natija,
        "missing_total": await profit_service.products_without_cost(session),
    }


@router.post("/bulk-cost", response_model=OkOut)
async def bulk_cost(
    payload: BulkCostIn,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_perm(PRODUCTS_EDIT)),
):
    """Bitta raqam bilan butun kategoriyaga tannarx qo'yadi.

    Implantlarning narxi razmeridan qat'i nazar bir xil bo'lgani uchun
    Excel kerak emas — kategoriya tanlanadi va bitta raqam kiritiladi.
    """
    stmt = update(Product).where(Product.is_active.is_(True))
    if payload.category_id is not None:
        category = await session.get(ProductCategory, payload.category_id)
        if category is None:
            raise HTTPException(404, "Kategoriya topilmadi")
        stmt = stmt.where(Product.category_id == payload.category_id)
        nom = category.name_uz
    else:
        nom = "barcha mahsulotlar"

    if not payload.overwrite:
        # Faqat bo'shlarini to'ldiramiz — qo'lda kiritilganlar buzilmasin
        stmt = stmt.where(Product.cost_usd <= 0)

    result = await session.execute(stmt.values(cost_usd=payload.cost_usd))
    count = result.rowcount or 0

    await log_action(
        session, actor, "bulk_cost", "product", payload.category_id,
        new={"tannarx": str(payload.cost_usd), "soni": count, "kategoriya": nom},
    )
    return OkOut(
        ok=True,
        message=(
            f"{nom}: {count} ta mahsulotga ${payload.cost_usd} tannarx qo'yildi"
            if count
            else "O'zgarish bo'lmadi (hammasida tannarx bor — «qayta yozish»ni yoqing)"
        ),
    )


# -------------------------------------------------------------- xarajatlar
@router.get("/expenses")
async def list_expenses(
    limit: int = Query(default=100, le=300),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_perm(REPORTS_FINANCE)),
):
    rows = (
        await session.execute(
            select(Expense).order_by(Expense.is_monthly.desc(), Expense.spent_on.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [
        {
            "id": e.id,
            "category": e.category.value,
            "label": EXPENSE_LABELS_UZ[e.category],
            "spent_on": e.spent_on.isoformat(),
            "amount_usd": e.amount_usd,
            "is_monthly": e.is_monthly,
            "ended_on": e.ended_on.isoformat() if e.ended_on else None,
            "note": e.note,
        }
        for e in rows
    ]


@router.get("/expenses/categories")
async def expense_categories(
    _: User = Depends(require_perm(REPORTS_FINANCE)),
):
    return [
        {"value": c.value, "label": EXPENSE_LABELS_UZ[c]} for c in ExpenseCategory
    ]


@router.post("/expenses", response_model=OkOut, status_code=201)
async def create_expense(
    payload: ExpenseIn,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_perm(REPORTS_FINANCE)),
):
    try:
        category = ExpenseCategory(payload.category)
    except ValueError:
        raise HTTPException(400, f"Noma'lum xarajat turi: {payload.category}") from None

    expense = Expense(
        category=category,
        spent_on=payload.spent_on,
        amount_usd=payload.amount_usd,
        is_monthly=payload.is_monthly,
        ended_on=payload.ended_on,
        note=payload.note,
        created_by_id=actor.id,
    )
    session.add(expense)
    await session.flush()
    await log_action(
        session, actor, "create", "expense", expense.id,
        new=payload.model_dump(mode="json"),
    )
    return OkOut(
        ok=True,
        message=(
            f"{EXPENSE_LABELS_UZ[category]}: ${payload.amount_usd}"
            + (" (har oy)" if payload.is_monthly else "")
        ),
    )


@router.delete("/expenses/{expense_id}", response_model=OkOut)
async def delete_expense(
    expense_id: int,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_perm(REPORTS_FINANCE)),
):
    expense = await session.get(Expense, expense_id)
    if expense is None:
        raise HTTPException(404, "Xarajat topilmadi")
    await session.delete(expense)
    await log_action(session, actor, "delete", "expense", expense_id)
    return OkOut(ok=True, message="Xarajat o'chirildi")
