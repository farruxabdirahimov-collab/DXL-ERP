# DXL Dental Implant — dillerlik ERP

Telegram Mini App. Hamma xodim **faqat telefondan** ishlaydi. Til: **o'zbek
(lotin)**. Narx va qarz **USD**, to'lov **so'mda** (kurs hujjatga qotib qoladi).

Asosiy foydalanuvchi — **sotuv agenti**. Interfeys birinchi navbatda unga
qulay bo'lishi kerak.

## Buyruqlar

```bash
.venv/bin/python -m pytest -q          # testlar (hozir 253 ta)
cd web && npm run typecheck && npm run build
.venv/bin/python -m alembic upgrade head
```

Migratsiyani toza bazada sinash:
```bash
DATABASE_URL="sqlite+aiosqlite:///tmp/x.db" .venv/bin/python -m alembic upgrade head
```

## Stek va tuzilma

FastAPI · SQLAlchemy 2.0 async · Alembic · PostgreSQL · aiogram 3 (webhook)
· APScheduler (Asia/Tashkent) · React 18 + TS + Vite + Tailwind v4 +
TanStack Query. Bitta Railway servisi API, bot webhook va SPA'ni birga beradi.

```
app/models/      SQLAlchemy modellari
app/services/    biznes mantiq — hisob-kitob shu yerda
app/api/         endpointlar — mantiq emas, faqat ruxsat va shakl
app/jobs/        21:00 statistika, 09:00 eslatmalar, yakshanba zaxira
app/bot/         /start, taklifnoma, vrachni telefon orqali ulash
web/src/pages/   ekranlar
docs/            foydalanuvchi qo'llanmalari (o'zbekcha)
```

## Qat'iy qoidalar

**1. Ruxsatlar bitta manbadan.** `app/permissions.py` — rol × ruxsat
matritsasi. Backend `require_perm()` bilan himoyalaydi, frontend `can()`
bilan menyu chizadi. Yangi ruxsat qo'shsangiz ikkalasi ham shundan oladi.

Bitta xodimda bir necha rol bo'lishi mumkin (`User.extra_roles`) —
ruxsatlar **birlashadi**. Shuning uchun biznes qoidalarida `user.role ==`
emas, **`user_can(user, RUXSAT)`** ishlating. (Bir marta shu xato tufayli
agent+direktor buyurtmani tasdiqlay olmay qolgan edi.)

**2. Qoldiq faqat `stock_moves` orqali.** To'g'ridan-to'g'ri `Stock.qty`
o'zgartirilmaydi. `stock.apply_move()` chaqiriladi. Manfiy qoldiq va band
qilingan tovarni yechish bloklanadi.

**3. Hujjat o'z qiymatlarini saqlaydi.** Narx, kurs va **tannarx** hujjatga
yozilib qotib qoladi. Keyin katalog o'zgarsa eski hisobotlar buzilmaydi.

**4. Qaytarish hech qayerda "sotilgan" bo'lib qolmaydi.** Yangi hisobot
yozganda qaytarishni ayirishni unutmang: sotuv summasi, dona, mahsulot
tahlili, razmer talabi, agent rejasi, vrach xarid darajasi, tannarx.

**5. Direktor tasdig'i faqat CHEGIRMA uchun.** Ikki xil nazorat bor va
ular ataylab bir xil emas:

| Sabab | Oqibat | Maydon |
|---|---|---|
| Chegirma limitdan oshdi | Buyurtma **to'xtaydi** → `director_review` | `needs_director` + `director_reason` |
| Qarz limitidan oshdi | Buyurtma **o'tadi**, faqat belgilanadi | `over_limit_reason` |

Sabab: real holatda har vrachga qarzga beriladi va direktor bu so'rovlarni
hech qachon rad etmagan — ya'ni tasdiq nazorat emas, kechikish edi.
Chegirma esa kamdan-kam bo'ladi va pul darhol foydadan ketadi, shuning
uchun u haqiqiy qaror.

Limitdan oshgan buyurtma bo'yicha direktorga **xabar** boradi
(`notifications.order_over_limit` — "so'rov emas"), u Buyurtmalar →
**«Nazorat»** tabida (`GET /orders?over_limit=true`) va 21:00 hisobotida
ko'rinadi. Nazorat yo'qolmadi, faqat OLDINDAN emas, KEYIN bo'ladi.

**6. Hisobotlar chalkashmasin.** Har harakat o'z turi bilan yoziladi:
`SALE` / `RETURN` / `WRITEOFF` / **`GIFT`** (shartnoma sovg'asi — sotuv
ham, spisaniye ham emas).

## Migratsiya — ikki tuzoq

**a) `0001_initial` `Base.metadata.create_all` ishlatadi.** Toza bazada u
JORIY modellardan hamma jadvalni yaratadi, keyingi migratsiyalar esa
o'tkazib yuboriladi. Shuning uchun har migratsiya **mavjudlikni
tekshirishi shart**:

```python
if "tariffs" not in set(sa.inspect(op.get_bind()).get_table_names()):
    op.create_table(...)
```

**b) `TimestampMixin` qiymatni bazadan kutadi.** `created_at`/`updated_at`
ni migratsiyada **`server_default=sa.text("now()")`** siz yaratsangiz,
INSERT paytida NULL tushib 500 chiqadi. Toza bazada bu ko'rinmaydi
(`create_all` default'ni o'zi qo'yadi) — faqat eski bazada.

`tests/test_migratsiya_sxema.py` buni AST orqali tekshiradi.

SQLite `ALTER COLUMN` ni qo'llab-quvvatlamaydi — dialektni tekshiring.

## Muhim biznes qoidalari

**Taklif-shartnoma** (`services/contracts.py`)
- Teskari sanoq **imzolangan paytdan**, soat-daqiqagacha
- Paket **qat'iy narxda** — razmerdan qat'i nazar
- Muddatida to'liq to'lansa sovg'a; kechiksa yo'qoladi, narx o'zgarmaydi
- **Tovar qaytarilsa sovg'a bekor bo'ladi**
- To'lov **muddati eng YAQIN** shartnomaga tushadi (FIFO emas) — vrach
  sovg'ani yo'qotmasligi uchun
- Ochiq shartnoma turganda yangisi tuzilmaydi

**Menejer KPI** (`services/kpi.py`) — barcha summalar fayl boshida:
fiksa $200 · tashrif 250=$150 nisbatan, oshmaydi · yig'im $4000 gacha 2.5%,
undan butun summaga 3% · post va otziv 4 tagacha $0, 5–12 har biri $5,
12 dan keyin oshmaydi. Post/otziv **direktor tasdiqlagach** hisobga kiradi.

**Foyda-zarar** (`services/profit.py`)
Implantlar razmeridan qat'i nazar bir xil narxda → tannarx **kategoriya
bo'yicha bitta raqam** bilan qo'yiladi, Excel kerak emas.

**Oylik reja** (`services/plans.py`)
Maqsad 0 bo'lsa umumiy bajarilish foiziga **kirmaydi**.

## Yozuv uslubi

- Izohlar va foydalanuvchi matnlari **o'zbekcha**. Test nomlari ham.
- Izoh **nima uchun** ekanini yozadi, nima qilayotganini emas.
- Frontend: flex/grid + `gap`, inline style emas class. `.input` kabi
  komponent uslublari `@layer components` ichida — Tailwind klasslari
  ustun turishi uchun (aks holda `w-20` ishlamaydi).
- Har xususiyatga test. Pul hisobi bo'lsa — chegara qiymatlarda ham.

## Deploy

Railway. `DATABASE_URL`, `BOT_TOKEN`, `WEBAPP_URL` (https bilan),
`SUPERADMIN_TELEGRAM_ID`. Ishga tushish **fonda** bajariladi —
`/api/health` har doim 200 qaytaradi, aks holda healthcheck konteynerni
o'ldiradi. Muammo `/api/diagnostics` da ko'rinadi (`migratsiya` holati va
`songgi_xatolar`).

Kutilmagan xato bo'sh 500 emas, **o'zbekcha sabab** qaytaradi
(`app/main.py` dagi `kutilmagan_xato`).

## Agent bosh ekrani

`web/src/components/AgentHome.tsx` — agentga statistika emas, «bugun nima
qilaman» ko'rsatiladi: topgan puli (har amaldan keyin o'sadi), kunlik
tashrif halqasi, ikki katta tugma, shoshilinch ro'yxat.

Butun ekran **bitta so'rov** oladi (`/kpi/home`) — agent kuniga 10-12
marta, ko'pincha sekin internetda ochadi.

Kunlik maqsad qat'iy emas: qolgan tashrif ÷ qolgan kun. Ortda qolsa
ertangi raqam ko'tariladi, oldinda bo'lsa tushadi.

Tashrif qayd etilgach `agent-home` va `kpi` so'rovlari bekor qilinadi —
pul raqami darhol o'sishi kerak, dofamin shunda.

## FinScan 360 paketi — vrachga ochiq sahifa

`/finscan` — loginsiz ochiladi (`app/finscan.py`, fayllar
`app/static/finscan/`). Agent botda `/finscan` yoki Mini App → Yana →
«Vrachga yuborish» orqali ulashadi. Sahifa kodi ham vrachga ochiq, shuning
uchun unga **tannarx va ichki foyda hech qachon qo'yilmaydi** (testda
tekshiriladi). Ichki hisob versiyasi repoda yo'q.

Havolada `?a=<user.id>` — kim ulashgani. Vrach «Ariza yuborish»ni bossa
(`POST /finscan/ariza`) xabar + PDF o'sha xodimga va direktorga botda
keladi. Paket raqamlari serverda **qayta hisoblanadi**
(`services/finscan.py` — sahifadagi JS bilan bir xil qoidalar, birini
o'zgartirsangiz ikkinchisini ham). IP bo'yicha 10 daqiqada 5 ta ariza.

PDF Telegram ichki brauzerida blob sifatida yuklanmaydi — shuning uchun
`POST /finscan/pdf` 30 daqiqaga xotirada saqlab, oddiy havola beradi.

## Qilinmagan (ataylab)

- Zaxirani **tiklash** tugmasi — bir noto'g'ri bosish bazani almashtiradi
- Konsignatsiya (vrachga qoldirilgan tovar) — taklif qilingan, kutmoqda
- Online to'lov (Click/Payme) — pul oqimiga eng katta ta'sir qiladi
- Partiya/seriya hisobi — foydalanuvchi "kerak emas" degan

## Foydalanuvchi haqida

Tez, aniq javob kutadi. Ortiqcha murakkablikni yoqtirmaydi —
"juda murakkab bo'lsa tizim ishlamay qoladi" degan. Yangi funksiya
qo'shishdan oldin **haqiqatan kerakmi** deb o'ylang.
