# DXL Dental Implant — Dillerlik ERP

Telegram Mini App ko'rinishidagi to'liq boshqaruv tizimi: ombor, mahsulot katalogi,
vrach-mijozlar, buyurtma, qarz nazorati, oylik reja va avtomatik hisobotlar.

O'zbek tilida, mobil qurilma uchun mo'ljallangan. Backend — FastAPI + PostgreSQL,
bot — aiogram 3, ilova — React + TypeScript. Hammasi bitta servisda ishlaydi.

---

## Nima qila oladi

**Rollar va ularning imkoniyatlari**

| Rol | Nima qiladi |
|---|---|
| **Super-admin** | Hammasi + xodimlar, rollar, tizim sozlamalari, audit jurnali |
| **Direktor** | Hammasi + tasdiqlash, reja qo'yish, xodim qo'shish |
| **Ta'sischi** | Faqat ko'radi — hamma hisobot ochiq, hech narsani o'zgartira olmaydi |
| **Buxgalter** | To'lov qabul qilish, qarz yuritish, valyuta kursi, moliyaviy hisobot |
| **Omborchi** | Kirim, ko'chirish, inventarizatsiya, spisaniye, buyurtma yig'ish va yetkazish |
| **Sotuv agenti** | O'z vrachlari, buyurtma yozish, naqd pul yig'ish, tashrif, oylik reja |
| **Vrach (mijoz)** | Katalog va ombor qoldig'i, buyurtma berish, o'z qarzi va muddatlari |

**Asosiy modullar**

- **Katalog** — implantlar diametr × uzunlik × tur kesimida; Excel orqali import/eksport
- **Ombor** — markaziy ombor + har agentga alohida qo'l ombori (sozlanadigan).
  Qoldiq hech qachon manfiy bo'lmaydi; tasdiqlangan buyurtma tovarni band qiladi
- **Vrachlar (CRM)** — manzil, tug'ilgan kun, biriktirilgan agent, qarz limiti va
  to'lov muddati, xarid darajasi (A/B/C) va sodiqlik ko'rsatkichi (0–100)
- **Buyurtma** — vrach beradi → agent tasdiqlaydi → chegirma yoki qarz limitidan
  oshsa direktorga tushadi → omborchi yig'adi va yetkazadi
- **Qarz** — USD'da yuritiladi, so'mda to'lanadi. Yoshlanish 0-30 / 31-60 / 61-90 / 90+ kun.
  To'lov eng eski qarzdan boshlab avtomatik taqsimlanadi
- **Hisobotlar** — eng talabgir razmerlar, eng ko'p/kam sotilgan, omborda kam qolgan
  («necha kunga yetadi» bilan), o'lik zaxira, agentlar reytingi; hammasi Excel'ga chiqadi
- **Reja** — har agentga 3 ko'rsatkich: sotuv summasi, sotilgan dona, yig'ilgan pul
- **Avtomatika** — pastda «Jadval» bo'limiga qarang

---

## Jadval (avtomatik xabarlar, Asia/Tashkent)

| Vaqt | Nima bo'ladi |
|---|---|
| **21:00** | Kunlik statistika. Direktor/ta'sischiga — to'liq manzara; agentga — shaxsiy natija va reja %; omborchiga — kirim/chiqim va kam qolganlar; buxgalterga — tushum va qarz yoshi |
| **09:00** | Tug'ilgan kun eslatmalari, muddati o'tgan qarzlar, dushanba kunlari «uxlab qolgan mijozlar» |
| **09:05** | Bugungi valyuta kursi kiritilmagan bo'lsa eslatma |
| **02:00** | Vrach toifalari (A/B/C) va sodiqlik ko'rsatkichini qayta hisoblash |
| **Har oy 1-sana 09:00** | O'tgan oy yakuni va agentlar reytingi |
| **Darhol** | Yangi buyurtma → agentga; tasdiq kerak → direktorga; tasdiqlandi → omborchiga; yetkazildi → buxgalterga; qoldiq minimumdan pastga tushdi → omborchi va direktorga |

---

## Ishga tushirish (Railway)

### 1. Telegram bot yarating

1. [@BotFather](https://t.me/BotFather) ga `/newbot` yozing va **yangi** bot yarating
   (mavjud botlaringizning tokenidan foydalanmang — bu alohida bot bo'lishi kerak)
2. Tokenni saqlab qo'ying — `BOT_TOKEN`
3. O'z Telegram ID raqamingizni biling: [@userinfobot](https://t.me/userinfobot) ga yozing

### 2. Railway'da servis yarating

1. Yangi **PostgreSQL** bazasi qo'shing — Railway `DATABASE_URL` ni o'zi beradi
2. Shu repodan yangi **service** qo'shing (Railway `Dockerfile` ni o'zi topadi)
3. **Settings → Networking → Generate Domain** — chiqqan manzilni `WEBAPP_URL` ga yozing

### 3. Muhit o'zgaruvchilari

```
BOT_TOKEN=<BotFather bergan token>
DATABASE_URL=<Railway Postgres ulanishi>
WEBAPP_URL=https://<sizning-domeningiz>.up.railway.app
WEBHOOK_SECRET=<istalgan tasodifiy satr>
SUPERADMIN_TELEGRAM_ID=<sizning Telegram ID raqamingiz>
TZ=Asia/Tashkent
DEFAULT_USD_UZS=12500
DAILY_REPORT_TIME=21:00
MORNING_REMINDER_TIME=09:00
```

To'liq ro'yxat: [`.env.example`](.env.example)

### 4. Mini App tugmasini sozlang

BotFather'da: `/mybots` → botingiz → **Bot Settings → Menu Button → Configure menu button**
→ URL sifatida `WEBAPP_URL` ni kiriting, nom: «DXL ERP».

### 5. Birinchi kirish

Botga `/start` yuboring. `SUPERADMIN_TELEGRAM_ID` sizga tegishli bo'lgani uchun
avtomatik super-admin bo'lasiz va Mini App ochiladi.

---

## Xodimlarni qo'shish

1. Mini App → **Yana → Xodimlar va rollar → + Taklif**
2. Ism va rolni tanlang (agent bo'lsa «qo'l ombori» kerakligini belgilang)
3. Chiqqan havolani xodimga yuboring — u bosgach avtomatik ro'yxatdan o'tadi

## Vrachlarni qo'shish

Agent yoki direktor **Vrachlar → + Yangi** orqali qo'shadi. Vrach botga
`/start` yuborib **telefon raqamini ulashsa**, tizim uni kartochkasiga bog'laydi
va u o'z buyurtmalari hamda qarzini ko'ra boshlaydi.

## Katalogni o'z prays-listingiz bilan almashtirish

Boshlang'ich katalogda 103 ta namunaviy SKU bor (tipik implant o'lchamlari).
O'zingiznikiga almashtirish:

1. **Katalog → ⬇️ Excel'ga yuklash** — shakl yuklab olinadi
2. Excel'da o'z mahsulotlaringizni to'ldiring (SKU, nomi, kategoriya, diametr,
   uzunlik, turi, narx, minimal qoldiq)
3. **Katalog → ⬆️ Excel'dan yuklash** — SKU bo'yicha yangilanadi yoki yangisi qo'shiladi

---

## Lokal ishlab chiqish

```bash
# Backend
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
export DATABASE_URL="sqlite+aiosqlite:///./local.db"   # yoki Postgres
.venv/bin/alembic upgrade head
.venv/bin/python -m seed.load        # faqat katalog
.venv/bin/python -m seed.demo        # katalog + demo sotuv tarixi
.venv/bin/uvicorn app.main:app --reload

# Frontend (boshqa terminalda)
cd web && npm install && npm run dev
```

`BOT_TOKEN` bo'sh bo'lsa ilova **ishlab chiqish rejimida** ishlaydi: brauzerda
`http://localhost:5173/?debug_tg=<telegram_id>` manzili bilan oching — imzo
o'rniga shu ID ishlatiladi. **Ishlab chiqarishda `BOT_TOKEN` majburiy**, aks holda
har so'rov rad etiladi.

### Testlar

```bash
.venv/bin/python -m pytest -q
```

Qamrov: ombor matematikasi (rezerv, manfiy qoldiq, ko'chirish), buyurtmaning to'liq
yo'li, qarz hisobi va yoshlanishi, to'lovni taqsimlash, valyuta kursi qotib qolishi,
sodiqlik/A-B-C formulasi, reja foizi, Telegram imzo tekshiruvi va rol huquqlari matritsasi.

---

## Loyiha tuzilishi

```
.
├── app/
│   ├── main.py          FastAPI: /api/*, /tg/webhook, Mini App static
│   ├── auth.py          Telegram initData tekshiruvi, require_perm()
│   ├── permissions.py   Rol × ruxsat matritsasi (backend ham, frontend ham shundan)
│   ├── models/          SQLAlchemy modellari (29 jadval)
│   ├── api/             12 ta router
│   ├── services/        Biznes mantiq (ombor, buyurtma, qarz, valyuta, sodiqlik, reja)
│   ├── bot/             aiogram: /start, taklifnoma, vrachni telefon orqali ulash
│   ├── jobs/            APScheduler: 21:00 statistika, eslatmalar, oylik yakun
│   └── utils/           Excel, PDF, audit, geo, formatlash
├── web/                 React + TS + Tailwind Mini App (19 sahifa)
├── migrations/          Alembic
├── seed/                Katalog (103 SKU) va demo ma'lumot
└── tests/               pytest
```

---

## Muhim texnik qarorlar

- **Qoldiq faqat `stock_moves` orqali o'zgaradi** — har harakat yozib boriladi,
  qoldiq manfiy bo'lolmaydi, band qilingan tovarni boshqa hujjat yechib ketolmaydi
- **Hujjat o'z kursini saqlaydi** — kurs keyin o'zgarsa eski hisob-fakturalar buzilmaydi
- **Audit jurnali o'chirilmaydi** — narx, qoldiq, qarz, rol o'zgarishlari qayd etiladi
- **Har so'rovda `initData` qayta tekshiriladi** — sessiya yoki token saqlanmaydi
- **Ruxsatlar bitta manbadan** — `app/permissions.py`; backend endpointni himoyalaydi,
  frontend menyuni shunga qarab chizadi
- **Qaytarilgan tovar hech qayerda sotilgan bo'lib qolmaydi** — qaytarish ombor,
  qarz, sotuv hisoboti, agent rejasi va vrachning xarid darajasini bir vaqtda
  to'g'rilaydi ([qo'llanma](docs/qaytarish.md))
