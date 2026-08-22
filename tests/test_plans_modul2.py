"""Modul 2 — kengaytirilgan oylik reja: prognoz, kompaniya rejasi, tarix."""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models import MoveKind, OrderSource, Role, User
from app.services import plans as ps
from app.services import orders as orders_service, stock as stock_service
from app.services.fx import today_local
from app.services.orders import LineInput


async def _sotuv(session, base_data, qty=5):
    await stock_service.apply_move(
        session, kind=MoveKind.IN, product_id=base_data["implant"].id, qty=qty + 10,
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


# ---------------------------------------------------------------- prognoz
def test_prognoz_surat_asosida_hisoblanadi():
    """10 kunda $1000 qilgan bo'lsa, 30 kunda $3000 bo'ladi."""
    f = ps.forecast(fact_usd=1000, target_usd=3000, days_passed=10, days_in_month=30)
    assert f.projected_usd == 3000.0
    assert f.projected_pct == 100.0
    assert f.daily_so_far_usd == 100.0
    assert f.daily_needed_usd == 100.0
    assert f.on_track


def test_prognoz_ortda_qolganini_korsatadi():
    f = ps.forecast(fact_usd=500, target_usd=3000, days_passed=15, days_in_month=30)
    assert f.projected_usd == 1000.0
    assert f.projected_pct == pytest.approx(33.3, abs=0.1)
    # Qolgan 15 kunda $2500 kerak -> kuniga $166.67
    assert f.daily_needed_usd == pytest.approx(166.67, abs=0.01)
    assert not f.on_track, "sur'at yetarli emas"


def test_prognoz_oy_boshida_yiqilmaydi():
    """Nolga bo'lish bo'lmasin."""
    f = ps.forecast(fact_usd=0, target_usd=3000, days_passed=0, days_in_month=30)
    assert f.projected_usd == 0.0
    assert f.daily_needed_usd == 100.0

    # Rejasiz ham yiqilmaydi
    f2 = ps.forecast(fact_usd=500, target_usd=0, days_passed=10, days_in_month=30)
    assert f2.projected_pct == 0.0
    assert f2.on_track


# ------------------------------------------------- qo'shimcha ko'rsatkichlar
async def test_yangi_korsatkichlar_hisoblanadi(session, base_data):
    from app.models import Doctor, Visit, utcnow

    bugun = today_local()
    await _sotuv(session, base_data, qty=3)

    # Agentga yangi vrach biriktiramiz
    yangi = Doctor(full_name="Yangi vrach", phone="+998901110022",
                   agent_id=base_data["agent"].id)
    session.add(yangi)
    session.add(
        Visit(
            created_at=utcnow(),
            agent_id=base_data["agent"].id,
            doctor_id=base_data["doctor"].id,
        )
    )
    await session.flush()

    start, end = ps.month_bounds(bugun.year, bugun.month)
    yangi_v, faol_v, tashrif = await ps.agent_extra_facts(
        session, base_data["agent"].id, start, end
    )
    assert yangi_v >= 1
    assert faol_v == 1, "bitta vrachga sotilgan"
    assert tashrif == 1


async def test_qoyilmagan_maqsad_foizga_kirmaydi(session, base_data):
    """0 qo'yilgan ko'rsatkich umumiy bajarilishni pasaytirmasligi kerak."""
    bugun = today_local()
    await _sotuv(session, base_data, qty=5)  # $500

    await ps.upsert_plan(
        session, user_id=base_data["agent"].id, year=bugun.year, month=bugun.month,
        target_amount_usd=Decimal("500"), target_units=0,
        target_collection_usd=Decimal("0"),
        target_new_doctors=0, target_active_doctors=0, target_visits=0,
    )

    p = await ps.progress(session, base_data["agent"], bugun.year, bugun.month)
    assert p.amount.pct == 100.0
    assert p.overall_pct == 100.0, "faqat summa hisobga olinsin"
    assert p.units.target == 0
    assert p.visits.target == 0


# ------------------------------------------------------- kompaniya rejasi
async def test_kompaniya_rejasi_taqsimotni_nazorat_qiladi(session, base_data):
    """Agentlar yig'indisi kompaniya rejasidan kam bo'lsa — farq ko'rinsin."""
    bugun = today_local()

    await ps.upsert_company_plan(
        session, year=bugun.year, month=bugun.month, actor=base_data["director"],
        target_amount_usd=Decimal("12000"),
    )
    await ps.upsert_plan(
        session, user_id=base_data["agent"].id, year=bugun.year, month=bugun.month,
        target_amount_usd=Decimal("9500"), target_units=0,
        target_collection_usd=Decimal("0"),
    )

    c = await ps.company_progress(session, bugun.year, bugun.month)
    assert c["has_plan"]
    assert c["amount"]["target"] == 12000.0
    assert c["assigned_usd"] == 9500.0
    assert c["unassigned_usd"] == 2500.0, "egasiz reja ko'rinishi kerak"
    assert c["agents_with_plan"] == 1


async def test_kompaniya_rejasi_haqiqatni_yigadi(session, base_data):
    bugun = today_local()
    await _sotuv(session, base_data, qty=4)  # $400

    await ps.upsert_company_plan(
        session, year=bugun.year, month=bugun.month, actor=base_data["director"],
        target_amount_usd=Decimal("1000"),
    )
    c = await ps.company_progress(session, bugun.year, bugun.month)
    assert c["amount"]["fact"] == 400.0
    assert c["amount"]["pct"] == 40.0
    assert c["forecast"]["projected_usd"] > 0


async def test_kompaniya_rejasisiz_ham_yiqilmaydi(session, base_data):
    bugun = today_local()
    c = await ps.company_progress(session, bugun.year, bugun.month)
    assert c["has_plan"] is False
    assert c["amount"]["target"] == 0.0
    assert c["unassigned_usd"] == 0.0


# --------------------------------------------------------- ommaviy amallar
async def test_otgan_oydan_nusxa(session, base_data):
    bugun = today_local()
    o_yil, o_oy = ps.previous_month(bugun.year, bugun.month)

    await ps.upsert_plan(
        session, user_id=base_data["agent"].id, year=o_yil, month=o_oy,
        target_amount_usd=Decimal("3000"), target_units=60,
        target_collection_usd=Decimal("2500"), target_visits=20,
    )

    count = await ps.copy_from_previous(
        session, year=bugun.year, month=bugun.month, actor=base_data["director"]
    )
    assert count == 1

    yangi = await ps.get_plan(session, base_data["agent"].id, bugun.year, bugun.month)
    assert yangi.target_amount_usd == Decimal("3000.00")
    assert yangi.target_visits == 20

    # Ikkinchi marta bosilsa mavjudini buzmaydi
    assert await ps.copy_from_previous(
        session, year=bugun.year, month=bugun.month, actor=base_data["director"]
    ) == 0


async def test_hammaga_bir_xil_reja(session, base_data):
    bugun = today_local()
    ikkinchi = User(full_name="Ikkinchi agent", role=Role.AGENT, telegram_id=881001)
    session.add(ikkinchi)
    await session.flush()

    count = await ps.apply_to_all_agents(
        session, year=bugun.year, month=bugun.month, actor=base_data["director"],
        target_amount_usd=Decimal("2000"), target_units=40,
        target_collection_usd=Decimal("1800"),
    )
    assert count == 2
    for uid in (base_data["agent"].id, ikkinchi.id):
        plan = await ps.get_plan(session, uid, bugun.year, bugun.month)
        assert plan.target_amount_usd == Decimal("2000.00")


# ----------------------------------------------------------------- tarix
async def test_tarix_oxirgi_oylarni_qaytaradi(session, base_data):
    rows = await ps.history(session, base_data["agent"], months=6)
    assert len(rows) == 6
    # Eskisidan yangisiga tartiblangan
    kalitlar = [(r["year"], r["month"]) for r in rows]
    assert kalitlar == sorted(kalitlar)
    bugun = today_local()
    assert kalitlar[-1] == (bugun.year, bugun.month)


async def test_agent_ozganing_tarixini_kormaydi(session, base_data):
    from app.api.plans import plan_history

    ozga = User(full_name="Boshqa agent", role=Role.AGENT, telegram_id=881002)
    session.add(ozga)
    await session.flush()

    with pytest.raises(HTTPException) as exc:
        await plan_history(ozga.id, 6, session, base_data["agent"])
    assert exc.value.status_code == 403

    # Direktor ko'radi
    rows = await plan_history(ozga.id, 6, session, base_data["director"])
    assert len(rows) == 6


# ------------------------------------------------------------ xabarnomalar
async def test_faqat_eng_yuqori_bosqich_yuboriladi(session, base_data):
    """100% ga yetgan agentga 50 va 80 emas, faqat 100 xabari ketsin."""
    from sqlalchemy import select

    from app.jobs.reminders import plan_milestones
    from app.models import Notification

    bugun = today_local()
    await _sotuv(session, base_data, qty=5)  # $500
    await ps.upsert_plan(
        session, user_id=base_data["agent"].id, year=bugun.year, month=bugun.month,
        target_amount_usd=Decimal("500"), target_units=0,
        target_collection_usd=Decimal("0"),
    )

    assert await plan_milestones(session, bugun) == 1

    turlar = {
        n.kind
        for n in (
            await session.execute(
                select(Notification).where(Notification.user_id == base_data["agent"].id)
            )
        ).scalars().all()
    }
    assert "plan_100" in turlar
    assert "plan_50" not in turlar and "plan_80" not in turlar


async def test_bosqich_xabari_dedup_kalitini_oladi(session, base_data):
    """Takrorlanmaslik `dedup_key` bilan ta'minlanadi (yetkazilgach ishlaydi)."""
    from sqlalchemy import select

    from app.jobs.reminders import plan_milestones
    from app.models import Notification

    bugun = today_local()
    await _sotuv(session, base_data, qty=5)
    await ps.upsert_plan(
        session, user_id=base_data["agent"].id, year=bugun.year, month=bugun.month,
        target_amount_usd=Decimal("500"), target_units=0,
        target_collection_usd=Decimal("0"),
    )
    await plan_milestones(session, bugun)

    xabar = (
        await session.execute(
            select(Notification).where(Notification.kind == "plan_100")
        )
    ).scalars().first()
    kutilgan = f"plan-{base_data['agent'].id}-{bugun.year}-{bugun.month:02d}-100"
    assert xabar.dedup_key == kutilgan


async def test_rejasiz_agentga_xabar_ketmaydi(session, base_data):
    from app.jobs.reminders import plan_milestones

    bugun = today_local()
    await _sotuv(session, base_data, qty=5)
    assert await plan_milestones(session, bugun) == 0
