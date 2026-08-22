"""Foyda-zarar: tannarx, xarajatlar va yakuniy hisob."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from app.models import (
    Expense,
    ExpenseCategory,
    MoveKind,
    OrderSource,
    PaymentMethod,
)
from app.services import inventory_ops, profit
from app.services import orders as orders_service, stock as stock_service
from app.services.fx import today_local
from app.services.orders import LineInput


async def _tannarx(session, base_data, cost="33"):
    """Implantga tannarx qo'yamiz — sotuv narxi $100."""
    base_data["implant"].cost_usd = Decimal(cost)
    await session.flush()


async def _sotuv(session, base_data, qty=5):
    await stock_service.apply_move(
        session, kind=MoveKind.IN, product_id=base_data["implant"].id, qty=qty + 20,
        to_warehouse_id=base_data["warehouse"].id, doc_type="receipt", doc_id=1,
    )
    order = await orders_service.create_order(
        session, doctor=base_data["doctor"],
        lines=[LineInput(base_data["implant"].id, qty)],
        actor=base_data["agent"], source=OrderSource.AGENT,
        warehouse_id=base_data["warehouse"].id,
    )
    order.needs_director = False
    await orders_service.approve(session, order, base_data["agent"])
    await orders_service.deliver(session, order, base_data["keeper"])
    return order


# ------------------------------------------------------------------ tannarx
async def test_tannarx_hujjatga_qotib_qoladi(session, base_data):
    """Keyin prays o'zgarsa ham eski buyurtmaning foydasi o'zgarmaydi."""
    await _tannarx(session, base_data, "33")
    order = await _sotuv(session, base_data, qty=4)
    assert all(Decimal(i.cost_usd) == Decimal("33") for i in order.items)

    # Tannarx oshdi — eski hujjat tegilmaydi
    base_data["implant"].cost_usd = Decimal("40")
    await session.flush()
    await session.refresh(order)
    assert all(Decimal(i.cost_usd) == Decimal("33") for i in order.items)


async def test_yalpi_foyda_hisoblanadi(session, base_data):
    bugun = today_local()
    await _tannarx(session, base_data, "33")
    await _sotuv(session, base_data, qty=5)  # 5 x $100 = $500, tannarx 5 x $33

    r = await profit.monthly_report(session, bugun.year, bugun.month)
    assert r["revenue_usd"] == Decimal("500.00")
    assert r["cogs_usd"] == Decimal("165.00")
    assert r["gross_profit_usd"] == Decimal("335.00")
    assert r["gross_margin_pct"] == 67.0


async def test_qaytarish_tannarxdan_ham_ayiriladi(session, base_data):
    """Qaytgan tovar na sotuvda, na tannarxda qolmasin."""
    bugun = today_local()
    await _tannarx(session, base_data, "33")
    order = await _sotuv(session, base_data, qty=5)

    await inventory_ops.create_return(
        session, doctor=base_data["doctor"],
        warehouse_id=base_data["warehouse"].id,
        lines=[(base_data["implant"].id, 2)],
        actor=base_data["agent"], order_id=order.id, reason="Qaytdi",
    )

    r = await profit.monthly_report(session, bugun.year, bugun.month)
    assert r["revenue_usd"] == Decimal("300.00"), "3 dona qoldi"
    assert r["cogs_usd"] == Decimal("99.00"), "3 x 33"
    assert r["gross_profit_usd"] == Decimal("201.00")


async def test_tannarxsiz_hisobot_ogohlantiradi(session, base_data):
    """Tannarx kiritilmagan bo'lsa foyda soxta yuqori chiqadi — belgilaymiz."""
    bugun = today_local()
    await _sotuv(session, base_data, qty=3)  # tannarx qo'yilmagan

    r = await profit.monthly_report(session, bugun.year, bugun.month)
    assert r["cogs_usd"] == Decimal("0.00")
    assert r["cost_missing"] is True


# --------------------------------------------------------------- xarajatlar
async def test_takrorlanadigan_xarajat_har_oy_hisoblanadi(session, base_data):
    """Ijara bir marta kiritiladi, har oy hisobga olinadi."""
    bugun = today_local()
    uch_oy_oldin = date(bugun.year, bugun.month, 1) - timedelta(days=70)

    session.add(
        Expense(
            category=ExpenseCategory.RENT,
            spent_on=uch_oy_oldin,
            amount_usd=Decimal("800"),
            is_monthly=True,
        )
    )
    session.add(
        Expense(
            category=ExpenseCategory.MARKETING,
            spent_on=bugun,
            amount_usd=Decimal("200"),
            is_monthly=False,
        )
    )
    await session.flush()

    rows = await profit.expenses_for_month(session, bugun.year, bugun.month)
    turlar = {r["category"]: r["amount_usd"] for r in rows}
    assert turlar["rent"] == Decimal("800.00"), "ijara har oy"
    assert turlar["marketing"] == Decimal("200.00")

    # O'tgan oyda reklama yo'q edi, ijara bor
    o_oy = (
        (bugun.year, bugun.month - 1) if bugun.month > 1 else (bugun.year - 1, 12)
    )
    eski = {r["category"] for r in await profit.expenses_for_month(session, *o_oy)}
    assert "rent" in eski and "marketing" not in eski


async def test_sof_foyda_xarajatlarni_ayiradi(session, base_data):
    bugun = today_local()
    await _tannarx(session, base_data, "33")
    await _sotuv(session, base_data, qty=10)  # $1000, tannarx $330

    session.add(
        Expense(
            category=ExpenseCategory.RENT,
            spent_on=bugun,
            amount_usd=Decimal("200"),
            is_monthly=True,
        )
    )
    await session.flush()

    r = await profit.monthly_report(session, bugun.year, bugun.month)
    assert r["gross_profit_usd"] == Decimal("670.00")
    assert r["expenses_total_usd"] == Decimal("200.00")
    assert r["net_profit_usd"] == Decimal("470.00")
    assert r["net_margin_pct"] == 47.0


async def test_spisaniye_zarar_sifatida_ayiriladi(session, base_data):
    bugun = today_local()
    await _tannarx(session, base_data, "33")
    await _sotuv(session, base_data, qty=5)

    await inventory_ops.create_writeoff(
        session,
        warehouse_id=base_data["warehouse"].id,
        lines=[(base_data["implant"].id, 3)],
        actor=base_data["keeper"],
        reason="Yaroqsiz",
    )

    r = await profit.monthly_report(session, bugun.year, bugun.month)
    assert r["writeoff_usd"] == Decimal("99.00"), "3 x 33 tannarx"
    assert r["net_profit_usd"] == Decimal("236.00"), "335 - 99"


async def test_pul_bolib_kelmagani_korinadi(session, base_data):
    """Hisobda foyda bor, lekin pul qo'lga tekkanmi — alohida ko'rsatiladi."""
    from app.services import payments as payments_service

    bugun = today_local()
    await _tannarx(session, base_data, "33")
    await _sotuv(session, base_data, qty=5)  # $500

    await payments_service.create_payment(
        session, doctor=base_data["doctor"],
        amount_uzs=Decimal("2530000"), fx_rate=Decimal("12650"),  # $200
        method=PaymentMethod.CASH, actor=base_data["accountant"],
    )

    r = await profit.monthly_report(session, bugun.year, bugun.month)
    assert r["collected_usd"] == Decimal("200.00")
    assert r["uncollected_usd"] == Decimal("300.00")


# ------------------------------------------------------ ommaviy tannarx
async def test_kategoriya_boyicha_tannarx_bir_klikda(session, base_data):
    """Implantlar bir xil narxda — Excel kerak emas."""
    from app.api.profit import bulk_cost, cost_status
    from app.schemas import BulkCostIn

    holat = await cost_status(session, base_data["director"])
    assert holat["missing_total"] > 0

    kategoriya = base_data["implant"].category_id
    r = await bulk_cost(
        BulkCostIn(category_id=kategoriya, cost_usd=Decimal("33")),
        session,
        base_data["director"],
    )
    assert r.ok
    await session.refresh(base_data["implant"])
    assert base_data["implant"].cost_usd == Decimal("33.00")


async def test_qayta_yozish_ochirilgan_bolsa_qol_kiritilgani_saqlanadi(session, base_data):
    from app.api.profit import bulk_cost
    from app.schemas import BulkCostIn

    base_data["implant"].cost_usd = Decimal("45")  # qo'lda kiritilgan istisno
    await session.flush()

    await bulk_cost(
        BulkCostIn(category_id=base_data["implant"].category_id, cost_usd=Decimal("33")),
        session,
        base_data["director"],
    )
    await session.refresh(base_data["implant"])
    assert base_data["implant"].cost_usd == Decimal("45.00"), "qo'lda kiritilgani buzilmasin"

    # «Qayta yozish» yoqilsa — almashtiriladi
    await bulk_cost(
        BulkCostIn(
            category_id=base_data["implant"].category_id,
            cost_usd=Decimal("33"),
            overwrite=True,
        ),
        session,
        base_data["director"],
    )
    await session.refresh(base_data["implant"])
    assert base_data["implant"].cost_usd == Decimal("33.00")
