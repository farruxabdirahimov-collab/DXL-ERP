"""FinScan 360 paketi — vrachga ochiq (loginsiz) sahifa.

Agent havolani vrachga Telegram'da yuboradi, vrach uni oddiy brauzerda ochadi:
Mini App'ga kirish, rol yoki initData talab qilinmaydi. Shuning uchun sahifada
faqat vrachga ko'rinadigan raqamlar bor — tannarx va ichki foyda yo'q.
"""

from __future__ import annotations

import re
import secrets
import time
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from app.config import settings

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


def public_url() -> str:
    """Vrachga yuboriladigan to'liq havola."""
    return f"{settings.webapp_url}{PATH}"


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


def mount(app) -> None:
    """SPA catch-all yo'lidan OLDIN chaqirilishi shart — aks holda index.html qaytadi."""
    app.include_router(router)
    app.mount(
        PATH + "/f",
        StaticFiles(directory=STATIC_DIR),
        name="finscan-static",
    )
