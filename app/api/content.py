"""Ma'rifiy kontent (maqola, video) va rassilkalar."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, require_perm
from app.db import get_session
from app.models import (
    AUDIENCE_LABELS_UZ,
    POST_LABELS_UZ,
    Audience,
    Broadcast,
    Doctor,
    DoctorCategory,
    Order,
    OrderStatus,
    Post,
    PostKind,
    Role,
    User,
    utcnow,
)
from app.permissions import (
    BROADCAST_SEND,
    CONTENT_MANAGE,
    CONTENT_VIEW,
    doctor_scope,
    user_can,
)
from app.schemas import (
    BroadcastIn,
    BroadcastOut,
    OkOut,
    PostIn,
    PostOut,
    PostUpdateIn,
)
from app.utils.audit import log_action

router = APIRouter(prefix="/content", tags=["content"])


async def _to_out(session: AsyncSession, post: Post) -> PostOut:
    out = PostOut.model_validate(post)
    out.kind_label = POST_LABELS_UZ.get(post.kind)
    if post.author_id:
        author = await session.get(User, post.author_id)
        out.author_name = author.full_name if author else None
    return out


@router.get("/posts", response_model=list[PostOut])
async def list_posts(
    kind: PostKind | None = None,
    search: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(CONTENT_VIEW)),
):
    """Materiallar ro'yxati. Vrachlar faqat e'lon qilinganlarini ko'radi."""
    stmt = select(Post).order_by(Post.published_at.desc().nullslast(), Post.id.desc())
    if not user_can(user, CONTENT_MANAGE):
        stmt = stmt.where(Post.is_published.is_(True))
    if kind is not None:
        stmt = stmt.where(Post.kind == kind)
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(Post.title.ilike(pattern))

    rows = (await session.execute(stmt.limit(limit).offset(offset))).scalars().all()
    return [await _to_out(session, post) for post in rows]


@router.get("/posts/{post_id}", response_model=PostOut)
async def get_post(
    post_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(CONTENT_VIEW)),
):
    post = await session.get(Post, post_id)
    if post is None:
        raise HTTPException(404, "Material topilmadi")
    if not post.is_published and not user_can(user, CONTENT_MANAGE):
        raise HTTPException(404, "Material topilmadi")

    post.views += 1
    await session.flush()
    return await _to_out(session, post)


@router.post("/posts", response_model=PostOut, status_code=201)
async def create_post(
    payload: PostIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(CONTENT_MANAGE)),
):
    post = Post(**payload.model_dump(), author_id=user.id)
    if post.is_published:
        post.published_at = utcnow()
    session.add(post)
    await session.flush()
    await log_action(
        session, user, "create", "post", post.id, new={"title": post.title}
    )
    return await _to_out(session, post)


@router.patch("/posts/{post_id}", response_model=PostOut)
async def update_post(
    post_id: int,
    payload: PostUpdateIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(CONTENT_MANAGE)),
):
    post = await session.get(Post, post_id)
    if post is None:
        raise HTTPException(404, "Material topilmadi")

    changes = payload.model_dump(exclude_unset=True)
    was_published = post.is_published
    for key, value in changes.items():
        setattr(post, key, value)
    if post.is_published and not was_published:
        post.published_at = utcnow()
    await session.flush()
    await log_action(session, user, "update", "post", post_id, new=changes)
    return await _to_out(session, post)


@router.delete("/posts/{post_id}", response_model=OkOut)
async def delete_post(
    post_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(CONTENT_MANAGE)),
):
    post = await session.get(Post, post_id)
    if post is None:
        raise HTTPException(404, "Material topilmadi")
    await session.delete(post)
    await log_action(session, user, "delete", "post", post_id)
    return OkOut(ok=True, message="Material o'chirildi")


# --------------------------------------------------------------- rassilka
async def _resolve_audience(
    session: AsyncSession, payload: BroadcastIn, actor: User
) -> list[User]:
    """Rassilka kimga ketishini aniqlaydi."""
    if payload.audience is Audience.STAFF:
        from app.models import STAFF_ROLES

        return list(
            (
                await session.execute(
                    select(User).where(
                        User.role.in_(list(STAFF_ROLES)), User.is_active.is_(True)
                    )
                )
            ).scalars().all()
        )

    stmt = select(Doctor).where(Doctor.is_active.is_(True), Doctor.user_id.is_not(None))

    if payload.audience is Audience.ONE_DOCTOR:
        if not payload.doctor_id:
            raise HTTPException(400, "Vrachni tanlang")
        stmt = stmt.where(Doctor.id == payload.doctor_id)
    elif payload.audience is Audience.MY_DOCTORS:
        stmt = stmt.where(Doctor.agent_id == actor.id)
    elif payload.audience is Audience.CATEGORY_A:
        stmt = stmt.where(Doctor.category == DoctorCategory.A)
    elif payload.audience is Audience.CATEGORY_B:
        stmt = stmt.where(Doctor.category == DoctorCategory.B)
    elif payload.audience is Audience.CATEGORY_C:
        stmt = stmt.where(Doctor.category == DoctorCategory.C)
    elif payload.audience is Audience.DEBTORS:
        debt = Order.total_usd - Order.paid_usd - Order.returned_usd
        debtor_ids = select(Order.doctor_id).where(
            Order.status == OrderStatus.DELIVERED, debt > Decimal("0.005")
        )
        stmt = stmt.where(Doctor.id.in_(debtor_ids))

    # Agent faqat o'z vrachlariga yubora oladi
    scope = doctor_scope(actor)
    if scope is not None:
        stmt = stmt.where(Doctor.agent_id == scope)

    doctors = (await session.execute(stmt)).scalars().all()
    users: list[User] = []
    for doctor in doctors:
        account = await session.get(User, doctor.user_id)
        if account is not None and account.is_active:
            users.append(account)
    return users


@router.post("/broadcasts", response_model=BroadcastOut, status_code=201)
async def send_broadcast(
    payload: BroadcastIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(BROADCAST_SEND)),
):
    """Xabarni tanlangan guruhga yuboradi."""
    from app.bot import notify

    if not payload.text.strip():
        raise HTTPException(400, "Xabar matni bo'sh")

    recipients = await _resolve_audience(session, payload, user)
    if not recipients:
        raise HTTPException(
            400,
            "Bu guruhda Telegram'ga ulangan foydalanuvchi yo'q. "
            "Vrachlar botga /start yozib ulanishi kerak.",
        )

    text = payload.text.strip()
    button: tuple[str, str] | None = None
    if payload.post_id:
        post = await session.get(Post, payload.post_id)
        if post is None:
            raise HTTPException(404, "Biriktirilgan material topilmadi")
        text += f"\n\n📎 <b>{post.title}</b>"
        button = ("Materialni ochish", f"/content/{post.id}")

    broadcast = Broadcast(
        text=payload.text.strip(),
        audience=payload.audience,
        doctor_id=payload.doctor_id,
        post_id=payload.post_id,
        created_by_id=user.id,
    )
    session.add(broadcast)
    await session.flush()

    sent = 0
    for recipient in recipients:
        if await notify.send_to_user(
            session,
            recipient,
            text,
            kind="broadcast",
            dedup_key=f"broadcast:{broadcast.id}:{recipient.id}",
            button=button,
        ):
            sent += 1

    broadcast.sent_count = sent
    broadcast.failed_count = len(recipients) - sent
    await session.flush()

    await log_action(
        session, user, "broadcast", "broadcast", broadcast.id,
        new={"audience": payload.audience.value, "sent": sent},
    )

    out = BroadcastOut.model_validate(broadcast)
    out.audience_label = AUDIENCE_LABELS_UZ.get(broadcast.audience)
    out.author_name = user.full_name
    return out


@router.get("/broadcasts", response_model=list[BroadcastOut])
async def list_broadcasts(
    limit: int = Query(default=50, le=200),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(BROADCAST_SEND)),
):
    stmt = select(Broadcast).order_by(Broadcast.id.desc()).limit(limit)
    if doctor_scope(user) is not None:
        stmt = stmt.where(Broadcast.created_by_id == user.id)
    rows = (await session.execute(stmt)).scalars().all()

    result = []
    for row in rows:
        out = BroadcastOut.model_validate(row)
        out.audience_label = AUDIENCE_LABELS_UZ.get(row.audience)
        if row.created_by_id:
            author = await session.get(User, row.created_by_id)
            out.author_name = author.full_name if author else None
        result.append(out)
    return result


@router.get("/audiences")
async def list_audiences(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_perm(BROADCAST_SEND)),
):
    """Guruhlar va har birida nechta odam borligi."""
    result = []
    for audience in Audience:
        if audience is Audience.ONE_DOCTOR:
            result.append(
                {"value": audience.value, "label": AUDIENCE_LABELS_UZ[audience], "count": None}
            )
            continue
        if audience is Audience.MY_DOCTORS and user.role is not Role.AGENT:
            continue
        if audience is Audience.STAFF and user.role is Role.AGENT:
            continue
        recipients = await _resolve_audience(
            session, BroadcastIn(text="x", audience=audience), user
        )
        result.append(
            {
                "value": audience.value,
                "label": AUDIENCE_LABELS_UZ[audience],
                "count": len(recipients),
            }
        )
    return result


# ------------------------------------------------------- vrach kabineti
@router.get("/my-purchases")
async def my_purchases(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Vrachning o'z xaridlari hisoboti."""
    if user.role is not Role.DOCTOR:
        raise HTTPException(403, "Faqat vrachlar uchun")

    doctor = (
        await session.execute(select(Doctor).where(Doctor.user_id == user.id))
    ).scalar_one_or_none()
    if doctor is None:
        raise HTTPException(404, "Vrach kartochkangiz topilmadi")

    from app.models import OrderItem, Product
    from app.services.fx import round_money
    from app.services.reports import month_start, today_local

    delivered = Order.status == OrderStatus.DELIVERED

    total, orders_count = (
        await session.execute(
            select(
                func.coalesce(func.sum(Order.total_usd), 0), func.count(Order.id)
            ).where(delivered, Order.doctor_id == doctor.id)
        )
    ).one()

    month_total = (
        await session.execute(
            select(func.coalesce(func.sum(Order.total_usd), 0)).where(
                delivered,
                Order.doctor_id == doctor.id,
                Order.delivered_at >= month_start(today_local()),
            )
        )
    ).scalar_one()

    units = (
        await session.execute(
            select(func.coalesce(func.sum(OrderItem.qty), 0))
            .join(Order, Order.id == OrderItem.order_id)
            .where(delivered, Order.doctor_id == doctor.id)
        )
    ).scalar_one()

    top_rows = (
        await session.execute(
            select(
                Product.name,
                Product.sku,
                func.coalesce(func.sum(OrderItem.qty), 0).label("qty"),
                func.coalesce(func.sum(OrderItem.line_total_usd), 0).label("amount"),
            )
            .join(OrderItem, OrderItem.product_id == Product.id)
            .join(Order, Order.id == OrderItem.order_id)
            .where(delivered, Order.doctor_id == doctor.id)
            .group_by(Product.name, Product.sku)
            .order_by(func.coalesce(func.sum(OrderItem.qty), 0).desc())
            .limit(10)
        )
    ).all()

    return {
        "full_name": doctor.full_name,
        "clinic_name": doctor.clinic_name,
        "category": doctor.category.value,
        "loyalty_score": doctor.loyalty_score,
        "total_usd": round_money(Decimal(total or 0)),
        "month_usd": round_money(Decimal(month_total or 0)),
        "orders": int(orders_count or 0),
        "units": int(units or 0),
        "last_order_at": doctor.last_order_at.isoformat()
        if doctor.last_order_at
        else None,
        "top_products": [
            {
                "name": r.name,
                "sku": r.sku,
                "qty": int(r.qty or 0),
                "amount_usd": round_money(Decimal(r.amount or 0)),
            }
            for r in top_rows
        ],
    }
