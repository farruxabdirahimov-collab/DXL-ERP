"""FinScan 360 paketi: vrachga ochiq sahifa, PDF zaxira havolasi va bot buyrug'i."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app import finscan
from app.main import app
from tests.test_bot_flow import _message, bot_pair  # noqa: F401  (fixture)


@pytest.fixture
async def client():
    finscan._pdfs.clear()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    finscan._pdfs.clear()


async def test_sahifa_loginsiz_ochiladi(client):
    for path in ("/finscan", "/finscan/"):
        r = await client.get(path)
        assert r.status_code == 200, path
        assert "FinScan 360" in r.text
        assert "O'zingizga mos shartni va raqamlarni kiriting yoki tanlang" in r.text


async def test_sahifada_ichki_raqamlar_yoq(client):
    # Havola vrachga ketadi — tannarx va Baxtiyor to'lovlari ko'rinmasligi shart
    html = (await client.get("/finscan")).text
    for ichki in ("Baxtiyor", "tannarx", "p-cbct-cost", "p-impl-cost", "35000", 'id="pr"', 'id="c-cbct"'):
        assert ichki not in html, ichki


async def test_havola_kartochkasi_toliq_manzil_bilan(client):
    html = (await client.get("/finscan")).text
    assert "{{BASE_URL}}" not in html
    assert f'content="{finscan.settings.webapp_url}/finscan/f/finscan360.jpg"' in html


async def test_rasm_va_pdf_kutubxonasi_beriladi(client):
    img = await client.get("/finscan/f/finscan360.jpg")
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"
    lib = await client.get("/finscan/f/jspdf.umd.min.js")
    assert lib.status_code == 200 and "jsPDF" in lib.text


async def test_pdf_yuklanib_havola_orqali_olinadi(client):
    pdf = b"%PDF-1.3\n...test..."
    r = await client.post("/finscan/pdf?name=Shartnoma_Smile Dent.pdf", content=pdf)
    assert r.status_code == 200
    url = r.json()["url"]

    got = await client.get(url)
    assert got.status_code == 200
    assert got.content == pdf
    assert got.headers["content-type"] == "application/pdf"
    assert 'filename="Shartnoma_Smile_Dent.pdf"' in got.headers["content-disposition"]


async def test_pdf_bolmagan_fayl_qabul_qilinmaydi(client):
    r = await client.post("/finscan/pdf", content=b"<html>salom</html>")
    assert r.status_code == 400


async def test_pdf_chegaradan_katta_bolsa_rad_etiladi(client):
    ok = b"%PDF" + b"0" * (finscan.PDF_MAX_BYTES - 4)
    assert (await client.post("/finscan/pdf", content=ok)).status_code == 200
    big = ok + b"0"
    assert (await client.post("/finscan/pdf", content=big)).status_code == 413


async def test_pdf_muddati_otsa_yoqoladi(client, monkeypatch):
    url = (await client.post("/finscan/pdf", content=b"%PDF-1.3")).json()["url"]
    now = finscan.time.time()
    monkeypatch.setattr(finscan.time, "time", lambda: now + finscan.PDF_TTL_SECONDS + 1)
    r = await client.get(url)
    assert r.status_code == 404
    assert "qayta bosing" in r.json()["detail"]


async def test_pdf_soni_cheklangan_eskisi_ochadi(client):
    urls = []
    for _ in range(finscan.PDF_MAX_COUNT + 1):
        urls.append((await client.post("/finscan/pdf", content=b"%PDF-1.3")).json()["url"])
    assert len(finscan._pdfs) == finscan.PDF_MAX_COUNT
    assert (await client.get(urls[0])).status_code == 404
    assert (await client.get(urls[-1])).status_code == 200


async def test_bot_finscan_ochish_va_ulashish_tugmasi(bot_pair):  # noqa: F811
    bot, dispatcher, recording = bot_pair
    await dispatcher.feed_update(bot, _message("/finscan", user_id=900050))

    sent = recording.sent[-1]
    assert "grafigini ko'ring" in sent.text
    buttons = [b for row in sent.reply_markup.inline_keyboard for b in row]
    page_url = finscan.public_url()
    assert buttons[0].url == page_url

    share = urlparse(buttons[1].url)
    assert share.netloc == "t.me" and share.path == "/share/url"
    q = parse_qs(share.query)
    assert q["url"] == [page_url]
    assert "O'zingizga mos shartni" in q["text"][0]
