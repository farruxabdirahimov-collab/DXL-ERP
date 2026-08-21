"""Taklif-shartnoma: teskari sanoq, sovg'a qoidalari, to'lov taqsimoti."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from app.models import ContractStatus, GiftStatus, Tariff, utcnow
from app.services import contracts as cs
from app.services.contracts import ContractError


async def _tarif(session, name="Katta-100", qty=100, price="5000", days=40,
                 gift="Nakonechnik", gift_cost="300") -> Tariff:
    tariff = Tariff(
        name=name,
        package_qty=qty,
        package_price_usd=Decimal(price),
        term_days=days,
        gift_name=gift,
        gift_cost_usd=Decimal(gift_cost),
    )
    session.add(tariff)
    await session.flush()
    return tariff


# ------------------------------------------------------------- sanoq
async def test_sanoq_imzolangan_paytdan_boshlanadi(session, base_data):
    tariff = await _tarif(session, days=15)
    hozir = utcnow()
    c = await cs.create_contract(
        session, doctor=base_data["doctor"], tariff=tariff,
        actor=base_data["agent"], signed_at=hozir,
    )
    assert c.deadline_at == hozir + timedelta(days=15)


def test_sanoq_bosqichli_korinadi():
    """Soniya faqat oxirgi 24 soatda chiqishi kerak."""
    from app.models import Contract

    hozir = utcnow()

    def yorliq(seconds: int) -> str:
        c = Contract(deadline_at=hozir + timedelta(seconds=seconds))
        return cs.countdown(c, hozir).label()

    assert yorliq(12 * 86400) == "12 kun qoldi"
    assert yorliq(3 * 86400 + 4 * 3600) == "3 kun 4 soat"
    # 24 soatdan kam — jonli soniya
    assert yorliq(5 * 3600 + 42 * 60 + 15) == "05:42:15"
    assert yorliq(-60) == "Muddat tugadi"


# ------------------------------------------------------------ sovg'a
async def test_muddatida_tolasa_sovga_qozoniladi(session, base_data):
    tariff = await _tarif(session, price="1000", days=15, gift_cost="40")
    c = await cs.create_contract(
        session, doctor=base_data["doctor"], tariff=tariff, actor=base_data["agent"]
    )

    await cs.apply_payment(session, base_data["doctor"].id, Decimal("1000"))

    assert c.status is ContractStatus.PAID
    assert c.gift_status is GiftStatus.EARNED
    assert c.remaining_usd == Decimal("0")


async def test_qisman_tolov_sovga_bermaydi(session, base_data):
    tariff = await _tarif(session, price="1000", days=15)
    c = await cs.create_contract(
        session, doctor=base_data["doctor"], tariff=tariff, actor=base_data["agent"]
    )

    await cs.apply_payment(session, base_data["doctor"].id, Decimal("950"))

    assert c.status is ContractStatus.ACTIVE, "hali yopilmaydi"
    assert c.gift_status is GiftStatus.PENDING
    assert c.remaining_usd == Decimal("50.00")
    assert round(c.paid_pct) == 95


async def test_muddat_otsa_sovga_yoqoladi(session, base_data):
    tariff = await _tarif(session, price="1000", days=15)
    c = await cs.create_contract(
        session, doctor=base_data["doctor"], tariff=tariff, actor=base_data["agent"],
        signed_at=utcnow() - timedelta(days=20),
    )

    otgan = await cs.expire_overdue(session)

    assert c in otgan
    assert c.status is ContractStatus.OVERDUE
    assert c.gift_status is GiftStatus.LOST
    # Narx o'zgarmaydi — qarz to'liq qoladi
    assert c.remaining_usd == Decimal("1000.00")


async def test_muddat_otgach_tolasa_ham_sovga_yoq(session, base_data):
    tariff = await _tarif(session, price="1000", days=15)
    c = await cs.create_contract(
        session, doctor=base_data["doctor"], tariff=tariff, actor=base_data["agent"],
        signed_at=utcnow() - timedelta(days=20),
    )

    await cs.apply_payment(session, base_data["doctor"].id, Decimal("1000"))

    assert c.status is ContractStatus.PAID
    assert c.gift_status is GiftStatus.LOST


async def test_tovar_qaytarilsa_sovga_bekor(session, base_data):
    """Kelishilgan qoida: qaytarish bo'lsa sovg'a yo'q, qarz kamayadi."""
    tariff = await _tarif(session, price="1000", days=15)
    c = await cs.create_contract(
        session, doctor=base_data["doctor"], tariff=tariff, actor=base_data["agent"]
    )

    await cs.register_return(session, c, Decimal("200"))
    assert c.gift_status is GiftStatus.LOST

    # Qolganini muddatida to'lasa ham sovg'a qaytmaydi
    await cs.apply_payment(session, base_data["doctor"].id, Decimal("1000"))
    assert c.status is ContractStatus.PAID
    assert c.gift_status is GiftStatus.LOST


# ------------------------------------------------------------ to'lov
async def _qol_bilan(session, doctor, tariff, days):
    """Ochiq shartnoma cheklovini chetlab, ikkinchi shartnoma yaratadi.

    To'lov taqsimotini sinash uchun bir vrachda ikkita ochiq shartnoma kerak.
    """
    from app.models import Contract
    from app.services.numbering import next_number

    hozir = utcnow()
    c = Contract(
        number=await next_number(session, "contract"),
        doctor_id=doctor.id,
        tariff_id=tariff.id,
        tariff_name=tariff.name,
        package_qty=tariff.package_qty,
        package_price_usd=tariff.package_price_usd,
        term_days=tariff.term_days,
        gift_name=tariff.gift_name,
        gift_cost_usd=tariff.gift_cost_usd,
        signed_at=hozir,
        deadline_at=hozir + timedelta(days=days),
    )
    session.add(c)
    await session.flush()
    return c


async def test_tolov_muddati_yaqiniga_tushadi(session, base_data):
    """FIFO emas — vrach sovg'ani yo'qotmasligi uchun shoshilinchi birinchi."""
    uzoq = await _tarif(session, name="Uzoq", price="1000", days=40)
    yaqin = await _tarif(session, name="Yaqin", price="1000", days=5)

    eski = await cs.create_contract(
        session, doctor=base_data["doctor"], tariff=uzoq, actor=base_data["agent"]
    )
    yangi = await _qol_bilan(session, base_data["doctor"], yaqin, days=5)

    await cs.apply_payment(session, base_data["doctor"].id, Decimal("1000"))

    assert yangi.status is ContractStatus.PAID, "muddati yaqin birinchi yopiladi"
    assert yangi.gift_status is GiftStatus.EARNED
    assert eski.status is ContractStatus.ACTIVE, "uzoq muddatlisi ochiq qoladi"
    assert eski.paid_usd == Decimal("0.00")


async def test_ortiqcha_tolov_keyingisiga_otadi(session, base_data):
    tariff = await _tarif(session, price="1000", days=15)
    c = await cs.create_contract(
        session, doctor=base_data["doctor"], tariff=tariff, actor=base_data["agent"]
    )

    await cs.apply_payment(session, base_data["doctor"].id, Decimal("1500"))

    assert c.paid_usd == Decimal("1000.00"), "shartnomadan ortig'i yozilmaydi"
    assert c.status is ContractStatus.PAID


# ------------------------------------------------------------ qoidalar
async def test_ochiq_shartnoma_turganda_yangisi_tuzilmaydi(session, base_data):
    """Pul oqimi qoidasi: yangi paket faqat eskisi yopilgach."""
    tariff = await _tarif(session, price="1000", days=15)
    await cs.create_contract(
        session, doctor=base_data["doctor"], tariff=tariff, actor=base_data["agent"]
    )

    with pytest.raises(ContractError, match="ochiq shartnoma"):
        await cs.create_contract(
            session, doctor=base_data["doctor"], tariff=tariff, actor=base_data["agent"]
        )


async def test_yopilgach_yangisini_tuzsa_boladi(session, base_data):
    tariff = await _tarif(session, price="1000", days=15)
    await cs.create_contract(
        session, doctor=base_data["doctor"], tariff=tariff, actor=base_data["agent"]
    )
    await cs.apply_payment(session, base_data["doctor"].id, Decimal("1000"))

    ikkinchi = await cs.create_contract(
        session, doctor=base_data["doctor"], tariff=tariff, actor=base_data["agent"]
    )
    assert ikkinchi.status is ContractStatus.ACTIVE


async def test_faol_bolmagan_tarifdan_shartnoma_tuzilmaydi(session, base_data):
    tariff = await _tarif(session)
    tariff.is_active = False
    await session.flush()

    with pytest.raises(ContractError, match="faol emas"):
        await cs.create_contract(
            session, doctor=base_data["doctor"], tariff=tariff, actor=base_data["agent"]
        )


# --------------------------------------------------------- eslatmalar
async def test_eslatma_7_3_1_kunda_bir_martadan(session, base_data):
    tariff = await _tarif(session, price="1000", days=15)
    c = await cs.create_contract(
        session, doctor=base_data["doctor"], tariff=tariff, actor=base_data["agent"],
        signed_at=utcnow() - timedelta(days=8),  # 7 kun qoldi
    )

    assert cs.reminder_due(c) == 7
    cs.mark_reminded(c, 7)
    assert cs.reminder_due(c) is None, "takror yuborilmasin"

    # 3 kun qolganda keyingisi
    c.deadline_at = utcnow() + timedelta(days=3)
    assert cs.reminder_due(c) == 3


async def test_toliq_tolangan_shartnomaga_eslatma_ketmaydi(session, base_data):
    tariff = await _tarif(session, price="1000", days=15)
    c = await cs.create_contract(
        session, doctor=base_data["doctor"], tariff=tariff, actor=base_data["agent"],
        signed_at=utcnow() - timedelta(days=14),
    )
    await cs.apply_payment(session, base_data["doctor"].id, Decimal("1000"))

    assert cs.reminder_due(c) is None


async def test_muddati_yaqinlar_royxati(session, base_data):
    tariff = await _tarif(session, price="1000", days=2)
    c = await cs.create_contract(
        session, doctor=base_data["doctor"], tariff=tariff, actor=base_data["agent"]
    )

    royxat = await cs.due_soon(session, days=3)
    assert c in royxat

    # To'liq to'langach ro'yxatdan chiqadi
    await cs.apply_payment(session, base_data["doctor"].id, Decimal("1000"))
    assert await cs.due_soon(session, days=3) == []


async def test_sovgani_faqat_qozonilganda_berish_mumkin(session, base_data):
    tariff = await _tarif(session, price="1000", days=15)
    c = await cs.create_contract(
        session, doctor=base_data["doctor"], tariff=tariff, actor=base_data["agent"]
    )

    with pytest.raises(ContractError, match="qozonilmagan"):
        await cs.issue_gift(session, c, base_data["director"])

    await cs.apply_payment(session, base_data["doctor"].id, Decimal("1000"))
    await cs.issue_gift(session, c, base_data["director"])
    assert c.gift_status is GiftStatus.ISSUED
    assert c.gift_issued_by_id == base_data["director"].id


def test_zinapoya_ulushi_hisoblanadi():
    """Direktor tarif yaratganda ulush ko'rinib turishi kerak."""
    t = Tariff(name="Katta-100", package_qty=100,
               package_price_usd=Decimal("5000"), term_days=40,
               gift_cost_usd=Decimal("300"))
    assert t.unit_price_usd == Decimal("50")
    assert t.gift_share_pct == Decimal("6")


# ------------------------------------------------ uchdan-uchgacha zanjir
async def test_haqiqiy_tolov_shartnomani_yopadi(session, base_data):
    """To'lov endpointi orqali: pul kirdi -> shartnoma yopildi -> sovg'a."""
    from app.models import PaymentMethod
    from app.services import payments as payments_service

    tariff = await _tarif(session, name="Old-20", qty=20, price="1000",
                          days=15, gift_cost="40")
    c = await cs.create_contract(
        session, doctor=base_data["doctor"], tariff=tariff, actor=base_data["agent"]
    )

    await payments_service.create_payment(
        session,
        doctor=base_data["doctor"],
        amount_uzs=Decimal("12650000"),
        fx_rate=Decimal("12650"),  # -> $1000
        method=PaymentMethod.CASH,
        actor=base_data["accountant"],
    )

    assert c.status is ContractStatus.PAID
    assert c.gift_status is GiftStatus.EARNED

    # Tabrik hali yuborilmagan — API uni topib yuboradi
    kutayotgan = await cs.unnotified_gifts(session, base_data["doctor"].id)
    assert c in kutayotgan


async def test_qaytarish_zanjiri_sovgani_bekor_qiladi(session, base_data):
    """Vrach tovar qaytarsa — sovg'a yo'qoladi, qarz kamayadi."""
    from app.models import MoveKind, OrderSource
    from app.services import inventory_ops
    from app.services import orders as orders_service, stock as stock_service
    from app.services.orders import LineInput

    tariff = await _tarif(session, name="Old-20", qty=20, price="1000", days=15)
    c = await cs.create_contract(
        session, doctor=base_data["doctor"], tariff=tariff, actor=base_data["agent"]
    )

    await stock_service.apply_move(
        session, kind=MoveKind.IN, product_id=base_data["implant"].id, qty=30,
        to_warehouse_id=base_data["warehouse"].id, doc_type="receipt", doc_id=1,
    )
    order = await orders_service.create_order(
        session, doctor=base_data["doctor"],
        lines=[LineInput(base_data["implant"].id, 5)],
        actor=base_data["agent"], source=OrderSource.AGENT,
        warehouse_id=base_data["warehouse"].id,
    )
    order.contract_id = c.id
    order.needs_director = False
    await orders_service.approve(session, order, base_data["agent"])
    await orders_service.deliver(session, order, base_data["keeper"])

    await inventory_ops.create_return(
        session, doctor=base_data["doctor"],
        warehouse_id=base_data["warehouse"].id,
        lines=[(base_data["implant"].id, 2)],
        actor=base_data["agent"], order_id=order.id, reason="Razmer mos kelmadi",
    )

    assert c.gift_status is GiftStatus.LOST
    assert c.returned_usd == Decimal("200.00")
    assert "qaytarilgani" in c.gift_note
