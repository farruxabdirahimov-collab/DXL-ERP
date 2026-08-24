"""Agent bosh ekrani: pul, kunlik maqsad va shoshilinch ro'yxat."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from app.models import Doctor, PaymentMethod, Tariff, Visit, utcnow
from app.services import agent_home as home
from app.services import contracts as cs
from app.services import kpi
from app.services.fx import today_local


async def _tashrif(session, agent, soni, kun_oldin=0):
    vaqt = utcnow() - timedelta(days=kun_oldin)
    for _ in range(soni):
        session.add(Visit(created_at=vaqt, agent_id=agent.id, doctor_id=1))
    await session.flush()


# ------------------------------------------------------------------ pul
async def test_bosh_ekran_pulni_korsatadi(session, base_data):
    r = await home.build(session, base_data["agent"])
    assert r["month_earned_usd"] == Decimal("200.00"), "fiksa"
    assert r["today_earned_usd"] == Decimal("0")
    assert r["first_name"] == base_data["agent"].full_name.split(" ")[0]


async def test_bugungi_tashrif_pulga_qoshiladi(session, base_data):
    await _tashrif(session, base_data["agent"], 5)
    r = await home.build(session, base_data["agent"])
    # 5 x $0.60 = $3.00
    assert r["today_earned_usd"] == Decimal("3.00")
    assert r["per_visit_usd"] == Decimal("0.60")


async def test_kechagi_tashrif_bugungi_pulga_kirmaydi(session, base_data):
    await _tashrif(session, base_data["agent"], 4, kun_oldin=1)
    await _tashrif(session, base_data["agent"], 2)
    r = await home.build(session, base_data["agent"])
    assert r["today_earned_usd"] == Decimal("1.20"), "faqat bugungi 2 ta"
    assert r["visits_today"] == 2
    assert r["visits_month"] >= 6


async def test_tolov_bugungi_pulga_qoshiladi(session, base_data):
    from app.services import payments as payments_service

    await payments_service.create_payment(
        session, doctor=base_data["doctor"],
        amount_uzs=Decimal("12650000"), fx_rate=Decimal("12650"),  # $1000
        method=PaymentMethod.CASH, actor=base_data["accountant"],
    )
    r = await home.build(session, base_data["agent"])
    # $1000 x 2.5% = $25
    assert r["today_earned_usd"] == Decimal("25.00")


# ------------------------------------------------------- kunlik maqsad
def test_kunlik_maqsad_qolganiga_qarab_hisoblanadi():
    """Ortda qolsa maqsad ko'tariladi, oldinda bo'lsa tushadi."""
    oy_boshi = date(2026, 3, 1)   # mart — 31 kun
    # Hech narsa qilinmagan: 250 / 31 kun
    assert home._daily_target(0, oy_boshi) == 9

    o_rta = date(2026, 3, 16)     # 16 kun qoldi
    assert home._daily_target(100, o_rta) == 10, "ortda -> ko'tariladi"
    assert home._daily_target(200, o_rta) == 4, "oldinda -> tushadi"


def test_maqsad_bajarilgach_nol_boladi():
    assert home._daily_target(250, date(2026, 3, 20)) == 0
    assert home._daily_target(300, date(2026, 3, 20)) == 0


def test_oxirgi_kunda_hammasi_talab_qilinmaydi():
    """Nolga bo'lish bo'lmasin."""
    oxirgi = date(2026, 3, 31)
    assert home._daily_target(240, oxirgi) == 10


# --------------------------------------------------------- shoshilinch
async def _shartnoma(session, base_data, days, price="1000", paid=None, doctor=None):
    """Bitta vrachda bitta ochiq shartnoma bo'ladi — kerak bo'lsa vrach beriladi."""
    tariff = Tariff(
        name=f"T{days}-{price}-{paid}", package_qty=20,
        package_price_usd=Decimal(price), term_days=days,
        gift_name="Nakonechnik", gift_cost_usd=Decimal("40"),
    )
    session.add(tariff)
    await session.flush()
    c = await cs.create_contract(
        session,
        doctor=doctor or base_data["doctor"],
        tariff=tariff,
        actor=base_data["agent"],
    )
    if paid:
        c.paid_usd = Decimal(paid)
        await session.flush()
    return c


async def _vrach(session, base_data, ism="Ikkinchi vrach", tel="+998901112233"):
    d = Doctor(full_name=ism, phone=tel, agent_id=base_data["agent"].id)
    session.add(d)
    await session.flush()
    return d


async def test_muddati_yaqin_shartnoma_royxatga_tushadi(session, base_data):
    c = await _shartnoma(session, base_data, days=2)
    r = await home.build(session, base_data["agent"])

    assert len(r["urgent"]) == 1
    qator = r["urgent"][0]
    assert qator["contract_id"] == c.id
    assert qator["reason"] == "Muddat tugayapti"
    assert qator["remaining_usd"] == Decimal("1000.00")


async def test_deyarli_tolangan_tepada_turadi(session, base_data):
    """Eng arzon pul — bir qo'ng'iroq bilan yopiladigan shartnoma."""
    await _shartnoma(session, base_data, days=2)          # muddati yaqin
    ikkinchi = await _vrach(session, base_data)
    c2 = await _shartnoma(                                 # 90% to'lagan
        session, base_data, days=30, paid="900", doctor=ikkinchi
    )

    r = await home.build(session, base_data["agent"])
    assert len(r["urgent"]) == 2
    birinchi = r["urgent"][0]
    assert birinchi["contract_id"] == c2.id, "deyarli to'langani tepada"
    assert birinchi["almost_done"] is True
    assert "bir qo'ng'iroq" in birinchi["reason"]
    assert birinchi["remaining_usd"] == Decimal("100.00")


async def test_tinch_shartnoma_royxatga_tushmaydi(session, base_data):
    """Muddati uzoq va kam to'langan — bugun shoshilish shart emas."""
    await _shartnoma(session, base_data, days=30, paid="100")
    r = await home.build(session, base_data["agent"])
    assert r["urgent"] == []


async def test_toliq_tolangan_royxatdan_chiqadi(session, base_data):
    await _shartnoma(session, base_data, days=2)
    await cs.apply_payment(session, base_data["doctor"].id, Decimal("1000"))
    r = await home.build(session, base_data["agent"])
    assert r["urgent"] == []


# ------------------------------------------------------- yaqin vrachlar
async def test_eng_yaqin_vrachlar_tartiblanadi(session, base_data):
    """Tashkent markazidan turli masofadagi uch vrach."""
    lat, lon = 41.3111, 69.2797

    uzoq = Doctor(full_name="Uzoq vrach", phone="+998901110001",
                  agent_id=base_data["agent"].id, lat=41.35, lon=69.32)
    yaqin = Doctor(full_name="Yaqin vrach", phone="+998901110002",
                   agent_id=base_data["agent"].id, lat=41.3113, lon=69.2799)
    orta = Doctor(full_name="O'rta vrach", phone="+998901110003",
                  agent_id=base_data["agent"].id, lat=41.3200, lon=69.2850)
    session.add_all([uzoq, yaqin, orta])
    await session.flush()

    rows = await home.nearby_doctors(session, base_data["agent"], lat, lon)
    ismlar = [r["full_name"] for r in rows]
    assert ismlar[0] == "Yaqin vrach"
    assert ismlar.index("O'rta vrach") < ismlar.index("Uzoq vrach")
    assert rows[0]["distance_m"] < 50


async def test_koordinatasiz_vrach_royxatga_kirmaydi(session, base_data):
    """base_data dagi vrachda koordinata yo'q."""
    rows = await home.nearby_doctors(
        session, base_data["agent"], 41.3111, 69.2797
    )
    assert all(r["id"] != base_data["doctor"].id for r in rows)


async def test_agent_faqat_oz_vrachlarini_koradi(session, base_data):
    from app.models import Role, User

    ozga = User(full_name="Boshqa agent", role=Role.AGENT, telegram_id=883001)
    session.add(ozga)
    await session.flush()

    session.add(
        Doctor(full_name="Begona vrach", phone="+998901110009",
               agent_id=ozga.id, lat=41.3111, lon=69.2797)
    )
    await session.flush()

    rows = await home.nearby_doctors(
        session, base_data["agent"], 41.3111, 69.2797
    )
    assert all(r["full_name"] != "Begona vrach" for r in rows)
