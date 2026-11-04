"""FinScan 360 paketi — vrachga ochiq (loginsiz) sahifa.

Agent havolani vrachga Telegram'da yuboradi, vrach uni oddiy brauzerda ochadi:
Mini App'ga kirish, rol yoki initData talab qilinmaydi. Shuning uchun sahifada
faqat vrachga ko'rinadigan raqamlar bor — tannarx va ichki foyda yo'q.
"""

from __future__ import annotations

import base64
import binascii
import logging
import re
import secrets
import time
from collections import OrderedDict, deque
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import settings

log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent / "static" / "finscan"

#: Agent ham, bot ham shu yo'lni ulashadi
PATH = "/finscan"

#: PDF zaxira nusxasi: Telegram ichidagi brauzer blob faylni yuklay olmaydi,
#: shuning uchun PDF qisqa muddat serverda turadi va oddiy havola bilan beriladi.
#: Ochiq endpoint — xotira to'lib qolmasligi uchun hajm va soni cheklangan.
PDF_MAX_BYTES = 2 * 1024 * 1024
PDF_MAX_COUNT = 50
PDF_TTL_SECONDS = 30 * 60

_pdfs: OrderedDict[str, tuple[float, str, bytes]] = OrderedDict()

router = APIRouter()


def public_url(agent_id: int | None = None) -> str:
    """Vrachga yuboriladigan to'liq havola.

    `?a=` — kim ulashgani: vrach ariza yuborsa, xabar aynan o'sha agentga boradi.
    """
    url = f"{settings.webapp_url}{PATH}"
    return f"{url}?a={agent_id}" if agent_id else url


@lru_cache
def _template() -> str:
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@router.get(PATH, response_class=HTMLResponse, include_in_schema=False)
@router.get(PATH + "/", response_class=HTMLResponse, include_in_schema=False)
async def finscan_page() -> HTMLResponse:
    # Telegram havola kartochkasi (og:image) to'liq manzil talab qiladi
    html = _template().replace("{{BASE_URL}}", settings.webapp_url)
    return HTMLResponse(html, headers={"Cache-Control": "public, max-age=300"})


def _cleanup(now: float) -> None:
    for key in [k for k, (ts, _, _) in _pdfs.items() if now - ts > PDF_TTL_SECONDS]:
        _pdfs.pop(key, None)
    while len(_pdfs) > PDF_MAX_COUNT:
        _pdfs.popitem(last=False)


def _safe_name(raw: str | None) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]", "_", raw or "")[:120].strip("._")
    if not name.lower().endswith(".pdf"):
        name = (name or "Shartnoma") + ".pdf"
    return name


@router.post(PATH + "/pdf", include_in_schema=False)
async def upload_pdf(request: Request, name: str | None = None) -> dict:
    body = await request.body()
    if len(body) > PDF_MAX_BYTES:
        raise HTTPException(status_code=413, detail="PDF juda katta")
    if not body.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="Bu PDF fayl emas")
    now = time.time()
    key = secrets.token_urlsafe(16)
    _pdfs[key] = (now, _safe_name(name), body)
    _cleanup(now)
    return {"url": f"{PATH}/pdf/{key}"}


@router.get(PATH + "/pdf/{key}", include_in_schema=False)
async def download_pdf(key: str) -> Response:
    _cleanup(time.time())
    item = _pdfs.get(key)
    if item is None:
        raise HTTPException(
            status_code=404,
            detail="PDF muddati o'tgan. Sahifada tugmani qayta bosing.",
        )
    _, name, body = item
    return Response(
        body,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


# ------------------------------------------------------------------ ariza
#: Ochiq endpoint direktorga Telegram xabar yuboradi — spamdan himoya
ARIZA_PER_IP = 5
ARIZA_WINDOW_SECONDS = 10 * 60
_ariza_log: dict[str, deque] = {}


class ArizaIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    head: str = Field(default="", max_length=200)
    phone: str = Field(min_length=5, max_length=40)
    addr: str = Field(default="", max_length=300)
    n: int
    price: int
    down: int
    term: int
    agent: int | None = None
    roi: str = Field(default="", max_length=600)
    #: PDF base64 ko'rinishida — agent vrachga aynan shu faylni olib boradi
    pdf: str | None = Field(default=None, max_length=PDF_MAX_BYTES * 4 // 3 + 8)


def _client_ip(request: Request) -> str:
    # Railway proxy ortida — haqiqiy manzil X-Forwarded-For ning birinchisida
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or (request.client.host if request.client else "?")


def _rate_limited(ip: str, now: float) -> bool:
    q = _ariza_log.setdefault(ip, deque())
    while q and now - q[0] > ARIZA_WINDOW_SECONDS:
        q.popleft()
    if len(q) >= ARIZA_PER_IP:
        return True
    q.append(now)
    return False


async def _send_pdf(chat_ids: set[int], pdf: bytes, name: str) -> None:
    """PDF — qo'shimcha. Yuborilmasa ham ariza matni allaqachon yetgan."""
    from aiogram.types import BufferedInputFile

    from app.bot.bot import get_bot

    bot = get_bot()
    if bot is None:
        return
    for chat_id in chat_ids:
        try:
            await bot.send_document(chat_id, BufferedInputFile(pdf, filename=name))
        except Exception as exc:  # bloklagan va h.k. — boshqalarga yuboraveramiz
            log.warning("FinScan PDF yuborilmadi (%s): %s", chat_id, exc)


@router.post(PATH + "/ariza", include_in_schema=False)
async def ariza(data: ArizaIn, request: Request) -> dict:
    from sqlalchemy import select

    from app.bot import notify
    from app.db import session_scope
    from app.models import Role, User
    from app.services import finscan as svc

    try:
        p = svc.paket(data.n, data.price, data.down, data.term)
    except svc.PaketXato as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    pdf: bytes | None = None
    if data.pdf:
        try:
            pdf = base64.b64decode(data.pdf, validate=True)
        except (binascii.Error, ValueError):
            pdf = None
        if pdf is not None and not pdf.startswith(b"%PDF"):
            pdf = None

    if _rate_limited(_client_ip(request), time.time()):
        raise HTTPException(
            status_code=429,
            detail="Ariza yuborilgan. Agentimiz tez orada bog'lanadi.",
        )

    async with session_scope() as session:
        agent = await session.get(User, data.agent) if data.agent else None
        # Havoladagi raqamni o'zgartirib vrachga yoki o'chirilgan xodimga yozib bo'lmasin
        if agent is not None and (not agent.is_active or agent.role is Role.DOCTOR):
            agent = None
        text = svc.ariza_text(
            p,
            name=data.name.strip(),
            head=data.head.strip(),
            phone=data.phone.strip(),
            addr=data.addr.strip(),
            agent_name=agent.full_name if agent else None,
            roi=data.roi.strip(),
        )
        bosses = (
            await session.execute(
                select(User).where(
                    User.role.in_([Role.DIRECTOR, Role.SUPERADMIN]),
                    User.is_active.is_(True),
                )
            )
        ).scalars().all()
        recipients = {u.id: u for u in bosses}
        if agent is not None:
            recipients[agent.id] = agent
        delivered = 0
        for user in recipients.values():
            if await notify.send_to_user(session, user, text, kind="finscan_ariza"):
                delivered += 1

    if pdf is not None:
        chat_ids = {u.telegram_id for u in recipients.values() if u.telegram_id}
        await _send_pdf(chat_ids, pdf, _safe_name(f"Shartnoma_{data.name}"))

    log.info("FinScan ariza: %s, agent=%s, yetkazildi=%s", data.name, data.agent, delivered)
    return {"ok": True, "agent": agent.full_name if agent else None}


def mount(app) -> None:
    """SPA catch-all yo'lidan OLDIN chaqirilishi shart — aks holda index.html qaytadi."""
    app.include_router(router)
    app.mount(
        PATH + "/f",
        StaticFiles(directory=STATIC_DIR),
        name="finscan-static",
    )
