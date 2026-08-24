"""Ma'lumotlar zaxirasi: to'liq, ochiladigan va tiklashga yaroqli."""

from __future__ import annotations

import gzip
import json
from decimal import Decimal

from app.models import MoveKind, OrderSource
from app.services import backup
from app.services import orders as orders_service, stock as stock_service
from app.services.orders import LineInput


async def _malumot(session, base_data):
    await stock_service.apply_move(
        session, kind=MoveKind.IN, product_id=base_data["implant"].id, qty=20,
        to_warehouse_id=base_data["warehouse"].id, doc_type="receipt", doc_id=1,
    )
    order = await orders_service.create_order(
        session, doctor=base_data["doctor"],
        lines=[LineInput(base_data["implant"].id, 3)],
        actor=base_data["agent"], source=OrderSource.AGENT,
        warehouse_id=base_data["warehouse"].id,
    )
    order.needs_director = False
    await orders_service.approve(session, order, base_data["agent"])
    await orders_service.deliver(session, order, base_data["keeper"])
    return order


async def test_zaxira_ochiladi_va_toliq(session, base_data):
    order = await _malumot(session, base_data)
    data, stats = await backup.dump(session)

    # Haqiqiy gzip va o'qiladigan JSON
    ochilgan = json.loads(gzip.decompress(data).decode("utf-8"))
    assert "created_at" in ochilgan
    jadvallar = ochilgan["tables"]

    # Asosiy ma'lumotlar joyida
    assert len(jadvallar["doctors"]) == 1
    assert len(jadvallar["orders"]) == 1
    assert len(jadvallar["order_items"]) == 1
    assert jadvallar["orders"][0]["number"] == order.number
    assert stats["doctors"] == 1


async def test_pul_va_sana_matn_sifatida_saqlanadi(session, base_data):
    """Decimal va datetime JSON'da yo'qolmasin."""
    await _malumot(session, base_data)
    data, _ = await backup.dump(session)
    ochilgan = json.loads(gzip.decompress(data).decode("utf-8"))

    buyurtma = ochilgan["tables"]["orders"][0]
    assert isinstance(buyurtma["total_usd"], str)
    assert Decimal(buyurtma["total_usd"]) == Decimal("300.00")
    assert isinstance(buyurtma["created_at"], str)
    assert "T" in buyurtma["created_at"], "ISO sana bo'lishi kerak"


async def test_jadvallar_boglanish_tartibida(session, base_data):
    """Tiklashda FK buzilmasligi uchun ota jadval oldin turishi kerak."""
    await _malumot(session, base_data)
    data, _ = await backup.dump(session)
    tartib = list(json.loads(gzip.decompress(data).decode("utf-8"))["tables"])

    assert tartib.index("doctors") < tartib.index("orders")
    assert tartib.index("orders") < tartib.index("order_items")
    assert tartib.index("products") < tartib.index("order_items")


async def test_shovqinli_jadvallar_kirmaydi(session, base_data):
    data, stats = await backup.dump(session)
    assert "notifications" not in stats
    assert "alembic_version" not in stats


async def test_bosh_bazada_ham_yiqilmaydi(session):
    """Biznes ma'lumoti yo'q bo'lsa ham zaxira yasaladi."""
    data, stats = await backup.dump(session)
    ochilgan = json.loads(gzip.decompress(data).decode("utf-8"))

    assert ochilgan["tables"] != {}, "jadval tuzilmasi baribir yoziladi"
    assert stats["orders"] == 0
    assert stats["doctors"] == 0


async def test_izoh_matni_asosiy_raqamlarni_korsatadi(session, base_data):
    await _malumot(session, base_data)
    _, stats = await backup.dump(session)
    matn = backup.summary_text(stats, 4096)

    assert "doctors: 1" in matn
    assert "orders: 1" in matn
    assert "Jami" in matn


async def test_botsiz_yuborish_yiqilmaydi(session, base_data):
    """Bot sozlanmagan bo'lsa job xato bermasin, 0 qaytarsin."""
    assert await backup.send_to_admins(session) == 0
