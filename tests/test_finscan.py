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


# ---------------------------------------------------------------- ariza
import base64  # noqa: E402

from sqlalchemy import select  # noqa: E402

from app.models import Notification  # noqa: E402
from app.services import finscan as svc  # noqa: E402


def test_paket_hisobi_sahifa_bilan_bir_xil():
    # Sahifadagi standart: 300 ta × $48, $18 000 boshlang'ich, 12 oy
    p = svc.paket(300, 48, 18_000, 12)
    assert p.total == 54_400
    assert p.mon == 3_034  # ceil(36 400 / 12)
    assert p.last == 36_400 - 3_034 * 11
    assert p.mon * (p.term - 1) + p.last + p.down == p.total


@pytest.mark.parametrize(
    ("n", "price", "down", "term"),
    [
        (99, 49, 18_000, 12),  # implant kam
        (2_001, 45, 18_000, 12),
        (300, 48, 18_000, 5),  # muddat qisqa
        (300, 48, 18_000, 15),
        (300, 45, 18_000, 12),  # 300 ta uchun $45 emas, kamida $48
        (199, 48, 18_000, 12),  # 199 ta uchun kamida $49
        (300, 50, 18_000, 12),  # ro'yxatda yo'q narx
        (300, 48, 9_999, 12),  # boshlang'ich kam
        (300, 48, 54_400 - 11, 12),  # har oyga $1 ham qolmaydi
    ],
)
def test_paket_chegaradan_tashqari_rad_etiladi(n, price, down, term):
    with pytest.raises(svc.PaketXato):
        svc.paket(n, price, down, term)


@pytest.mark.parametrize(
    ("n", "price"), [(100, 49), (199, 49), (200, 48), (300, 48), (301, 45), (2_000, 45), (301, 49)]
)
def test_paket_chegaraviy_qiymatlar_qabul_qilinadi(n, price):
    p = svc.paket(n, price, 10_000, 6)
    assert p.total == 40_000 + n * price
    # boshlang'ich eng ko'p: har oyga roppa-rosa $1
    top = svc.paket(n, price, p.total - 14, 14)
    assert top.mon == 1 and top.last == 1


def _ariza(**kw):
    data = {
        "name": "Smile <b>Dent</b>", "phone": "+998901234567", "head": "", "addr": "",
        "n": 300, "price": 48, "down": 18_000, "term": 12, "roi": "oyiga $4 400",
    }
    data.update(kw)
    return data


@pytest.fixture
def ariza_client(client, monkeypatch):
    finscan._ariza_log.clear()
    sent_pdfs: list = []

    async def fake_send_pdf(chat_ids, pdf, name):
        sent_pdfs.append((set(chat_ids), pdf, name))

    monkeypatch.setattr(finscan, "_send_pdf", fake_send_pdf)
    client.sent_pdfs = sent_pdfs
    yield client
    finscan._ariza_log.clear()


async def _xabarlar(session):
    rows = (await session.execute(select(Notification).where(Notification.kind == "finscan_ariza"))).scalars().all()
    return {n.user_id: n.text for n in rows}


async def test_ariza_agent_va_direktorga_boradi(ariza_client, session, base_data):
    agent, director = base_data["agent"], base_data["director"]
    await session.commit()
    pdf = base64.b64encode(b"%PDF-1.3 test").decode()

    r = await ariza_client.post("/finscan/ariza", json=_ariza(agent=agent.id, pdf=pdf))
    assert r.status_code == 200, r.text
    assert r.json()["agent"] == agent.full_name

    msgs = await _xabarlar(session)
    assert set(msgs) == {agent.id, director.id}
    text = msgs[agent.id]
    assert "$54 400" in text and "$3 034 × 12 oy" in text and "+998901234567" in text
    assert f"Agent: {agent.full_name}" in text
    # Vrach yozgan HTML Telegram'da teg bo'lib ishlamasligi kerak
    assert "Smile &lt;b&gt;Dent&lt;/b&gt;" in text

    (chat_ids, body, name), = ariza_client.sent_pdfs
    assert chat_ids == {agent.telegram_id, director.telegram_id}
    assert body == b"%PDF-1.3 test" and name.endswith(".pdf")


async def test_ariza_agentsiz_faqat_direktorga(ariza_client, session, base_data):
    await session.commit()
    r = await ariza_client.post("/finscan/ariza", json=_ariza())
    assert r.status_code == 200
    msgs = await _xabarlar(session)
    assert set(msgs) == {base_data["director"].id}
    assert "havolada yo'q" in msgs[base_data["director"].id]
    assert ariza_client.sent_pdfs == []  # PDF berilmagan


async def test_ariza_havolada_vrach_raqami_bolsa_agent_hisoblanmaydi(ariza_client, session, base_data):
    from app.models import Role, User

    doctor_user = User(full_name="Vrach", role=Role.DOCTOR, telegram_id=5005, is_active=True)
    session.add(doctor_user)
    await session.commit()
    r = await ariza_client.post("/finscan/ariza", json=_ariza(agent=doctor_user.id))
    assert r.status_code == 200 and r.json()["agent"] is None
    assert doctor_user.id not in await _xabarlar(session)


async def test_ariza_notogri_paket_400(ariza_client, session, base_data):
    await session.commit()
    r = await ariza_client.post("/finscan/ariza", json=_ariza(price=45))
    assert r.status_code == 400
    assert "kamida $48" in r.json()["detail"]
    assert await _xabarlar(session) == {}


async def test_ariza_pdf_bolmasa_ham_matn_ketadi(ariza_client, session, base_data):
    await session.commit()
    bad = base64.b64encode(b"<html>").decode()
    r = await ariza_client.post("/finscan/ariza", json=_ariza(pdf=bad))
    assert r.status_code == 200
    assert ariza_client.sent_pdfs == []
    assert await _xabarlar(session)


async def test_ariza_spamdan_himoya(ariza_client, session, base_data):
    await session.commit()
    for _ in range(finscan.ARIZA_PER_IP):
        assert (await ariza_client.post("/finscan/ariza", json=_ariza())).status_code == 200
    r = await ariza_client.post("/finscan/ariza", json=_ariza())
    assert r.status_code == 429
    assert len(await _xabarlar(session)) == 1  # faqat direktor, 5 marta
    # boshqa IP bloklanmaydi
    r = await ariza_client.post("/finscan/ariza", json=_ariza(), headers={"X-Forwarded-For": "10.0.0.9"})
    assert r.status_code == 200


async def test_bot_finscan_xodim_havolasiga_belgi_qoshadi(bot_pair, session, base_data):  # noqa: F811
    bot, dispatcher, recording = bot_pair
    agent = base_data["agent"]
    await session.commit()
    await dispatcher.feed_update(bot, _message("/finscan", user_id=agent.telegram_id))
    buttons = [b for row in recording.sent[-1].reply_markup.inline_keyboard for b in row]
    assert buttons[0].url == finscan.public_url(agent.id)
    assert buttons[0].url.endswith(f"/finscan?a={agent.id}")
