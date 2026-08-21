"""Tariflar va taklif-shartnomalar."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_perm
from app.db import get_session
from app.models import (
    CONTRACT_STATUS_UZ,
    GIFT_STATUS_UZ,
    Contract,
    ContractStatus,
    Doctor,
    GiftStatus,
    Role,
    Tariff,
    User,
    utcnow,
)
from app.permissions import (
    CONTRACTS_CREATE,
    CONTRACTS_VIEW,
    GIFTS_ISSUE,
    REPORTS_FINANCE,
    TARIFFS_MANAGE,
    doctor_scope,
    user_can,
)
from app.schemas import ContractIn, OkOut, TariffIn
from app.services import contracts as cs
from app.services.fx import round_money
from app.utils.audit import log_action

router = APIRouter(prefix="/contracts", tags=["contracts"])


def _sees_money(user: User) -> bool:
    """Sovg'a tannarxi va foyda — faqat rahbariyat va buxgalteriya uchun."""
    return user_can(user, REPORTS_FINANCE)


def _tariff_out(tariff: Tariff, user: User) -> dict:
    data = {
        "id": tariff.id,
        "name": tariff.name,
        "package_qty": tariff.package_qty,
        "package_price_usd": tariff.package_price_usd,
        "unit_price_usd": round_money(tariff.unit_price_usd),
        "term_days": tariff.term_days,
        "gift_name": tariff.gift_name,
        "is_active": tariff.is_active,
        "sort_order": tariff.sort_order,
        "note": tariff.note,
    }
    if _sees_money(user):
        # Zinapoya to'g'rimi — direktor tarif yaratayotganda ko'rib tursin
        data |= {
            "gift_cost_usd": tariff.gift_cost_usd,
            "gift_product_id": tariff.gift_product_id,
            "gift_share_pct": round(float(tariff.gift_share_pct), 1),
            "daily_turnover_usd": round_money(
                Decimal(tariff.package_price_usd) / max(tariff.term_days, 1)
            ),
        }
    return data


def _contract_out(contract: Contract, user: User, doctor_name: str | None = None) -> dict:
    cd = cs.countdown(contract)
    data = {
        "id": contract.id,
        "number": contract.number,
        "doctor_id": contract.doctor_id,
        "doctor_name": doctor_name,
        "agent_id": contract.agent_id,
        "tariff_name": contract.tariff_name,
        "package_qty": contract.package_qty,
        "package_price_usd": contract.package_price_usd,
        "term_days": contract.term_days,
        "gift_name": contract.gift_name,
        "signed_at": contract.signed_at.isoformat(),
        "deadline_at": cd.deadline_at.isoformat(),
        # Telefon shu ikkisining farqini olib o'zi sanaydi — soat
        # o'zgartirilsa ham sanoq buzilmaydi
        "server_now": cd.server_now.isoformat(),
        "remaining_seconds": cd.total_seconds,
        "expired": cd.expired,
        "countdown_label": cd.label(),
        "delivered_qty": contract.delivered_qty,
        "paid_usd": contract.paid_usd,
        "remaining_usd": contract.remaining_usd,
        "paid_pct": round(contract.paid_pct, 1),
        "returned_usd": contract.returned_usd,
        "status": contract.status.value,
        "status_label": CONTRACT_STATUS_UZ[contract.status],
        "gift_status": contract.gift_status.value,
        "gift_status_label": GIFT_STATUS_UZ[contract.gift_status],
        "gift_note": contract.gift_note,
        "note": contract.note,
    }
    if _sees_money(user):
        data |= {"gift_cost_usd": contract.gift_cost_usd, "cost_usd": contract.cost_usd}
    return data


# ------------------------------------------------------------- tariflar
@router.get("/tariffs")
async def list_tariffs(
    only_active: bool = True,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(CONTRACTS_VIEW)),
):
    stmt = select(Tariff).order_by(Tariff.sort_order, Tariff.package_qty)
    if only_active:
        stmt = stmt.where(Tariff.is_active.is_(True))
    rows = (await session.execute(stmt)).scalars().all()
    return [_tariff_out(t, user) for t in rows]


@router.post("/tariffs", status_code=201)
async def create_tariff(
    payload: TariffIn,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_perm(TARIFFS_MANAGE)),
):
    exists = (
        await session.execute(select(Tariff).where(Tariff.name == payload.name))
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(409, f"«{payload.name}» nomli tarif allaqachon bor")

    tariff = Tariff(**payload.model_dump())
    session.add(tariff)
    await session.flush()
    await log_action(
        session, actor, "create", "tariff", tariff.id, new=payload.model_dump(mode="json")
    )
    return _tariff_out(tariff, actor)


@router.patch("/tariffs/{tariff_id}")
async def update_tariff(
    tariff_id: int,
    payload: TariffIn,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_perm(TARIFFS_MANAGE)),
):
    """Tarif o'zgartiriladi. Tuzilgan shartnomalar tegilmaydi — ularda nusxa bor."""
    tariff = await session.get(Tariff, tariff_id)
    if tariff is None:
        raise HTTPException(404, "Tarif topilmadi")

    changes = payload.model_dump()
    old = {key: getattr(tariff, key) for key in changes}
    for key, value in changes.items():
        setattr(tariff, key, value)
    await session.flush()
    await log_action(
        session, actor, "update", "tariff", tariff_id,
        old={k: str(v) for k, v in old.items()},
        new=payload.model_dump(mode="json"),
    )
    return _tariff_out(tariff, actor)


@router.get("/tariffs/ladder")
async def tariff_ladder(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(TARIFFS_MANAGE)),
):
    """Zinapoya tekshiruvi: sovg'a ulushi paket kattalashgani sayin oshishi kerak.

    Aks holda vrach kichik paketni takrorlashni foydali deb topadi va katta
    paket hech qachon tanlanmaydi.
    """
    rows = (
        await session.execute(
            select(Tariff)
            .where(Tariff.is_active.is_(True))
            .order_by(Tariff.package_price_usd)
        )
    ).scalars().all()

    natija = []
    ogohlantirish: list[str] = []
    oldingi_ulush: Decimal | None = None

    for tariff in rows:
        ulush = tariff.gift_share_pct
        buzilgan = oldingi_ulush is not None and ulush < oldingi_ulush
        if buzilgan:
            ogohlantirish.append(
                f"«{tariff.name}» ulushi {float(ulush):.1f}% — undan kichik "
                f"paketda {float(oldingi_ulush):.1f}%. Vrach uchun kichik paketni "
                "takrorlash foydaliroq bo'lib qoladi."
            )
        natija.append(
            _tariff_out(tariff, user) | {"ladder_ok": not buzilgan}
        )
        oldingi_ulush = ulush

    return {"tariffs": natija, "warnings": ogohlantirish, "ok": not ogohlantirish}


# --------------------------------------------------------- shartnomalar
@router.get("")
async def list_contracts(
    doctor_id: int | None = None,
    status: ContractStatus | None = None,
    due_days: int | None = Query(default=None, description="Muddati shuncha kun ichida"),
    limit: int = Query(default=50, le=200),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(CONTRACTS_VIEW)),
):
    """Shartnomalar — muddati eng yaqinidan boshlab."""
    stmt = (
        select(Contract, Doctor.full_name)
        .join(Doctor, Doctor.id == Contract.doctor_id)
        .order_by(Contract.deadline_at)
        .limit(limit)
    )
    if doctor_id is not None:
        stmt = stmt.where(Contract.doctor_id == doctor_id)
    if status is not None:
        stmt = stmt.where(Contract.status == status)

    # Vrach faqat o'zinikini, agent faqat o'z vrachlariniki
    if user.role is Role.DOCTOR:
        own = (
            await session.execute(select(Doctor).where(Doctor.user_id == user.id))
        ).scalar_one_or_none()
        if own is None:
            return []
        stmt = stmt.where(Contract.doctor_id == own.id)
    elif doctor_scope(user) is not None:
        stmt = stmt.where(Contract.agent_id == user.id)

    rows = (await session.execute(stmt)).all()
    natija = [_contract_out(c, user, name) for c, name in rows]

    if due_days is not None:
        natija = [
            r for r in natija
            if not r["expired"] and r["remaining_seconds"] <= due_days * 86400
            and Decimal(str(r["remaining_usd"])) > 0
        ]
    return natija


@router.get("/at-risk")
async def at_risk(
    days: int = Query(default=3, ge=1, le=30),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(CONTRACTS_VIEW)),
):
    """Xavf ostidagi pul: muddati yaqin va to'lanmagan shartnomalar.

    Agent ertalab shuni ochib, kimga qo'ng'iroq qilishni biladi.
    """
    rows = await cs.due_soon(session, days=days)
    if doctor_scope(user) is not None:
        rows = [c for c in rows if c.agent_id == user.id]

    ismlar = {
        d.id: d.full_name
        for d in (
            await session.execute(
                select(Doctor).where(Doctor.id.in_([c.doctor_id for c in rows] or [0]))
            )
        ).scalars().all()
    }

    return {
        "days": days,
        "total_usd": round_money(sum((c.remaining_usd for c in rows), Decimal("0"))),
        "gift_at_risk_usd": (
            round_money(sum((Decimal(c.gift_cost_usd) for c in rows), Decimal("0")))
            if _sees_money(user)
            else None
        ),
        "contracts": [_contract_out(c, user, ismlar.get(c.doctor_id)) for c in rows],
    }


@router.post("", status_code=201)
async def create_contract(
    payload: ContractIn,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_perm(CONTRACTS_CREATE)),
):
    doctor = await session.get(Doctor, payload.doctor_id)
    if doctor is None:
        raise HTTPException(404, "Vrach topilmadi")
    if doctor_scope(actor) is not None and doctor.agent_id != actor.id:
        raise HTTPException(403, "Bu vrach sizga biriktirilmagan")

    tariff = await session.get(Tariff, payload.tariff_id)
    if tariff is None:
        raise HTTPException(404, "Tarif topilmadi")

    try:
        contract = await cs.create_contract(
            session, doctor=doctor, tariff=tariff, actor=actor, note=payload.note
        )
    except cs.ContractError as exc:
        raise HTTPException(400, str(exc)) from exc

    await log_action(
        session, actor, "create", "contract", contract.id,
        new={"number": contract.number, "tariff": tariff.name,
             "deadline": contract.deadline_at.isoformat()},
    )
    return _contract_out(contract, actor, doctor.full_name)


@router.post("/{contract_id}/gift", response_model=OkOut)
async def issue_gift(
    contract_id: int,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_perm(GIFTS_ISSUE)),
):
    """Qozonilgan sovg'ani berilgan deb belgilaydi."""
    contract = await session.get(Contract, contract_id)
    if contract is None:
        raise HTTPException(404, "Shartnoma topilmadi")

    try:
        await cs.issue_gift(session, contract, actor)
    except cs.ContractError as exc:
        raise HTTPException(400, str(exc)) from exc

    await log_action(
        session, actor, "gift", "contract", contract_id,
        new={"gift": contract.gift_name, "number": contract.number},
    )
    return OkOut(ok=True, message=f"Sovg'a berildi: {contract.gift_name}")


@router.post("/{contract_id}/cancel", response_model=OkOut)
async def cancel_contract(
    contract_id: int,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_perm(TARIFFS_MANAGE)),
):
    contract = await session.get(Contract, contract_id)
    if contract is None:
        raise HTTPException(404, "Shartnoma topilmadi")
    if contract.status is not ContractStatus.ACTIVE:
        raise HTTPException(400, "Faqat amaldagi shartnomani bekor qilish mumkin")

    contract.status = ContractStatus.CANCELLED
    contract.gift_status = GiftStatus.LOST
    contract.closed_at = utcnow()
    await session.flush()
    await log_action(session, actor, "cancel", "contract", contract_id)
    return OkOut(ok=True, message=f"{contract.number} bekor qilindi")
