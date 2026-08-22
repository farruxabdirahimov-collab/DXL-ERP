"""Taklif-shartnoma: teskari sanoq, sovg'a qoidalari va to'lov taqsimoti.

Qoidalar (kelishilgan):
  * Sanoq **shartnoma imzolangan paytdan** boshlanadi, soat-daqiqagacha.
  * Paket narxi qat'iy — qaysi razmer olinishidan qat'i nazar.
  * Muddat ichida to'liq to'lansa — sovg'a qozoniladi.
  * Muddat o'tsa — sovg'a yo'qoladi, narx o'zgarmaydi, qarz qoladi.
  * Tovar qaytarilsa — sovg'a bekor bo'ladi, qarz odatdagidek kamayadi.
  * To'lov **muddati eng yaqin** shartnomaga tushadi (FIFO emas) — shunda
    vrachning sovg'a olish imkoni maksimal bo'ladi.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Contract,
    ContractStatus,
    Doctor,
    GiftStatus,
    Tariff,
    User,
    utcnow,
)
from app.services.fx import round_money
from app.services.numbering import next_number

ZERO = Decimal("0")

#: Qaysi kunlarda eslatma yuboriladi
REMINDER_DAYS = (7, 3, 1)


class ContractError(Exception):
    """Shartnoma qoidasi buzilganda."""


# ---------------------------------------------------------------- sanoq
@dataclass
class Countdown:
    """Teskari sanoqning bir lahzadagi holati."""

    deadline_at: datetime
    server_now: datetime
    total_seconds: int
    expired: bool

    @property
    def days(self) -> int:
        return max(0, self.total_seconds) // 86400

    @property
    def hours(self) -> int:
        return (max(0, self.total_seconds) % 86400) // 3600

    def label(self) -> str:
        """Bosqichli ko'rinish: soniya faqat oxirgi 24 soatda kerak bo'ladi."""
        if self.expired:
            return "Muddat tugadi"
        if self.total_seconds >= 7 * 86400:
            return f"{self.days} kun qoldi"
        if self.total_seconds >= 86400:
            return f"{self.days} kun {self.hours} soat"
        soat, qoldiq = divmod(self.total_seconds, 3600)
        daqiqa, soniya = divmod(qoldiq, 60)
        return f"{soat:02d}:{daqiqa:02d}:{soniya:02d}"


def countdown(contract: Contract, now: datetime | None = None) -> Countdown:
    now = now or utcnow()
    deadline = contract.deadline_at
    if deadline.tzinfo is None:  # SQLite naiv vaqt qaytaradi
        deadline = deadline.replace(tzinfo=now.tzinfo)
    qolgan = int((deadline - now).total_seconds())
    return Countdown(
        deadline_at=deadline,
        server_now=now,
        total_seconds=qolgan,
        expired=qolgan <= 0,
    )


# ------------------------------------------------------------ yaratish
async def create_contract(
    session: AsyncSession,
    *,
    doctor: Doctor,
    tariff: Tariff,
    actor: User,
    signed_at: datetime | None = None,
    note: str | None = None,
) -> Contract:
    """Vrach bilan shartnoma tuzadi va teskari sanoqni boshlaydi."""
    if not tariff.is_active:
        raise ContractError(f"«{tariff.name}» tarifi faol emas")

    # Ochiq shartnoma turganda yangisi tuzilmaydi — qarz to'planmasin
    ochiq = await open_contract(session, doctor.id)
    if ochiq is not None:
        raise ContractError(
            f"Vrachda ochiq shartnoma bor: {ochiq.number} "
            f"(${ochiq.remaining_usd} to'lanmagan). Avval uni yoping."
        )

    signed_at = signed_at or utcnow()
    contract = Contract(
        number=await next_number(session, "contract"),
        doctor_id=doctor.id,
        tariff_id=tariff.id,
        agent_id=doctor.agent_id,
        # Shartlar nusxasi — tarif keyin o'zgarsa shartnoma buzilmaydi
        tariff_name=tariff.name,
        package_qty=tariff.package_qty,
        package_price_usd=tariff.package_price_usd,
        term_days=tariff.term_days,
        gift_name=tariff.gift_name,
        gift_cost_usd=tariff.gift_cost_usd,
        signed_at=signed_at,
        deadline_at=signed_at + timedelta(days=tariff.term_days),
        status=ContractStatus.ACTIVE,
        gift_status=GiftStatus.PENDING,
        note=note,
        created_by_id=actor.id,
    )
    session.add(contract)
    await session.flush()
    return contract


async def open_contract(session: AsyncSession, doctor_id: int) -> Contract | None:
    """Vrachning ochiq (amaldagi) shartnomasi — bo'lmasa None."""
    return (
        await session.execute(
            select(Contract)
            .where(
                Contract.doctor_id == doctor_id,
                Contract.status == ContractStatus.ACTIVE,
            )
            .order_by(Contract.deadline_at)
        )
    ).scalars().first()


async def active_contracts_all(session: AsyncSession) -> list[Contract]:
    """Barcha amaldagi shartnomalar — kunlik job uchun."""
    return list(
        (
            await session.execute(
                select(Contract)
                .where(Contract.status == ContractStatus.ACTIVE)
                .order_by(Contract.deadline_at)
            )
        ).scalars().all()
    )


async def active_contracts(
    session: AsyncSession, doctor_id: int
) -> list[Contract]:
    """Muddati eng yaqinidan boshlab — to'lov shu tartibda taqsimlanadi."""
    return list(
        (
            await session.execute(
                select(Contract)
                .where(
                    Contract.doctor_id == doctor_id,
                    Contract.status == ContractStatus.ACTIVE,
                )
                .order_by(Contract.deadline_at)
            )
        ).scalars().all()
    )


# -------------------------------------------------------------- to'lov
async def apply_payment(
    session: AsyncSession, doctor_id: int, amount_usd: Decimal
) -> list[Contract]:
    """To'lovni shartnomalarga taqsimlaydi — muddati eng yaqinidan boshlab.

    Odatdagi FIFO emas: vrach sovg'ani yo'qotmasligi uchun avval muddati
    tugayotgan shartnoma yopiladi. Qaytaradi: holati o'zgargan shartnomalar.
    """
    qoldiq = Decimal(amount_usd)
    ozgargan: list[Contract] = []

    for contract in await active_contracts(session, doctor_id):
        if qoldiq <= 0:
            break
        kerak = contract.remaining_usd
        if kerak <= 0:
            continue
        tushdi = min(kerak, qoldiq)
        contract.paid_usd = round_money(Decimal(contract.paid_usd) + tushdi)
        qoldiq -= tushdi
        if await _settle(session, contract):
            ozgargan.append(contract)

    await session.flush()
    return ozgargan


async def _settle(session: AsyncSession, contract: Contract) -> bool:
    """To'liq to'langan bo'lsa yopadi va sovg'a taqdirini hal qiladi."""
    if contract.remaining_usd > 0:
        return False

    contract.status = ContractStatus.PAID
    contract.closed_at = utcnow()

    if Decimal(contract.returned_usd) > 0:
        # Qaytarish bo'lgan — sovg'a allaqachon bekor qilingan
        contract.gift_status = GiftStatus.LOST
    elif countdown(contract).expired:
        contract.gift_status = GiftStatus.LOST
        contract.gift_note = "Muddat o'tgandan keyin to'langan"
    else:
        contract.gift_status = GiftStatus.EARNED
        contract.gift_note = "Muddat ichida to'liq to'landi"
    return True


async def unnotified_gifts(session: AsyncSession, doctor_id: int) -> list[Contract]:
    """Sovg'a qozonilgan, lekin tabrik yuborilmagan shartnomalar."""
    return list(
        (
            await session.execute(
                select(Contract).where(
                    Contract.doctor_id == doctor_id,
                    Contract.gift_status == GiftStatus.EARNED,
                    Contract.gift_notified.is_(False),
                )
            )
        ).scalars().all()
    )


# ---------------------------------------------------------- qaytarish
async def register_return(
    session: AsyncSession, contract: Contract, amount_usd: Decimal
) -> None:
    """Shartnoma bo'yicha tovar qaytarilsa — sovg'a bekor bo'ladi.

    Qarz odatdagidek kamayadi, paket narxi esa o'zgarmaydi: vrach qolgan
    summani to'laydi, lekin sovg'a olmaydi.
    """
    contract.returned_usd = round_money(Decimal(contract.returned_usd) + amount_usd)
    if contract.gift_status in (GiftStatus.PENDING, GiftStatus.EARNED):
        contract.gift_status = GiftStatus.LOST
        contract.gift_note = "Tovar qaytarilgani uchun sovg'a bekor qilindi"
    await session.flush()


# ----------------------------------------------------------- muddat
async def expire_overdue(
    session: AsyncSession, now: datetime | None = None
) -> list[Contract]:
    """Muddati o'tgan shartnomalarni yopadi. Kunlik jobdan chaqiriladi."""
    now = now or utcnow()
    otgan: list[Contract] = []

    for contract in (
        await session.execute(
            select(Contract).where(Contract.status == ContractStatus.ACTIVE)
        )
    ).scalars().all():
        if not countdown(contract, now).expired:
            continue
        contract.status = ContractStatus.OVERDUE
        if contract.gift_status is GiftStatus.PENDING:
            contract.gift_status = GiftStatus.LOST
            contract.gift_note = "Muddat ichida to'liq to'lanmadi"
        otgan.append(contract)

    await session.flush()
    return otgan


async def due_soon(
    session: AsyncSession, days: int = 3, now: datetime | None = None
) -> list[Contract]:
    """Muddati yaqin va to'lanmagan shartnomalar — shoshilinchi birinchi."""
    now = now or utcnow()
    chegara = now + timedelta(days=days)
    rows = (
        await session.execute(
            select(Contract)
            .where(
                Contract.status == ContractStatus.ACTIVE,
                Contract.deadline_at <= chegara,
            )
            .order_by(Contract.deadline_at)
        )
    ).scalars().all()
    return [c for c in rows if c.remaining_usd > 0]


def reminder_due(contract: Contract, now: datetime | None = None) -> int | None:
    """Bugun qaysi eslatma yuborilishi kerak (7/3/1) — kerak bo'lmasa None."""
    if contract.status is not ContractStatus.ACTIVE or contract.remaining_usd <= 0:
        return None

    cd = countdown(contract, now)
    if cd.expired:
        return None

    yuborilgan = {int(x) for x in (contract.reminders_sent or "").split(",") if x}
    # Qolgan to'liq kunlar: 6 kun 5 soat bo'lsa — 7 kunlik eslatma o'tib ketgan
    qolgan_kun = -(-cd.total_seconds // 86400)  # yuqoriga yaxlitlash
    for bosqich in REMINDER_DAYS:
        if qolgan_kun <= bosqich and bosqich not in yuborilgan:
            return bosqich
    return None


def mark_reminded(contract: Contract, stage: int) -> None:
    yuborilgan = {x for x in (contract.reminders_sent or "").split(",") if x}
    yuborilgan.add(str(stage))
    contract.reminders_sent = ",".join(sorted(yuborilgan, key=int, reverse=True))


# ------------------------------------------------------------- sovg'a
async def issue_gift(
    session: AsyncSession,
    contract: Contract,
    actor: User,
    *,
    warehouse_id: int | None = None,
) -> None:
    """Sovg'ani berilgan deb belgilaydi va ombordan chiqaradi.

    Sovg'a katalogdagi mahsulot bo'lsa (`tariffs.gift_product_id`), qoldiq
    kamayadi. Harakat `MoveKind.GIFT` bilan yoziladi — sotuv ham, spisaniye
    ham emas, shuning uchun hisobotlar chalkashmaydi.
    """
    if contract.gift_status is not GiftStatus.EARNED:
        raise ContractError("Bu shartnomada sovg'a qozonilmagan")

    from app.models import MoveKind, Tariff
    from app.services import stock as stock_service

    product_id = None
    if contract.tariff_id:
        tariff = await session.get(Tariff, contract.tariff_id)
        product_id = tariff.gift_product_id if tariff else None

    if product_id:
        if warehouse_id is None:
            warehouse_id = (await stock_service.main_warehouse(session)).id
        await stock_service.apply_move(
            session,
            kind=MoveKind.GIFT,
            product_id=product_id,
            qty=1,
            from_warehouse_id=warehouse_id,
            doc_type="contract_gift",
            doc_id=contract.id,
            user=actor,
            note=f"{contract.number} sovg'asi: {contract.gift_name or ''}".strip(),
        )

    contract.gift_status = GiftStatus.ISSUED
    contract.gift_issued_at = utcnow()
    contract.gift_issued_by_id = actor.id
    await session.flush()


async def pending_gifts(session: AsyncSession) -> list[Contract]:
    """Qozonilgan, lekin hali berilmagan sovg'alar — ombor tayyor tursin."""
    return list(
        (
            await session.execute(
                select(Contract)
                .where(Contract.gift_status == GiftStatus.EARNED)
                .order_by(Contract.closed_at)
            )
        ).scalars().all()
    )
