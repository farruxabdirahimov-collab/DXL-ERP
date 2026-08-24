# Ma'lumotlar zaxirasi (backup)

## Nima uchun Telegram

Ilova Railway'da ishlaydi va konteyner o'chsa **diskdagi hamma narsa
yo'qoladi**. Shuning uchun zaxira faylga emas, **Telegramga** yuboriladi:
direktor chatida abadiy saqlanadi, hech qanday tashqi xizmat, parol yoki
to'lov kerak emas.

## Qanday ishlaydi

**Avtomatik:** har **yakshanba 03:00** da direktor va super-adminlarga
Telegram orqali fayl keladi. Ish vaqtiga xalaqit bermaydi.

**Qo'lda:** Sozlamalar → «Ma'lumotlar zaxirasi»
- **💾 Telegramga yuborish** — darhol yuboradi
- **⬇️ Yuklab olish** — telefonga/kompyuterga saqlaydi

Fayl bilan birga qisqa izoh keladi:

```
💾 Ma'lumotlar zaxirasi
2026-08-24 · 340 KB

  doctors: 52
  orders: 418
  payments: 390
  contracts: 61
  products: 103
  stock_moves: 1 240

Jami 2 264 yozuv, 35 jadval.
```

## Fayl ichida nima bor

`dxl-erp-zaxira-2026-08-24.json.gz` — gzip qilingan JSON. Barcha jadvallar:
vrachlar, buyurtmalar, to'lovlar, shartnomalar, ombor harakatlari, tariflar,
xarajatlar, KPI yozuvlari, audit jurnali.

Kirmaydi: yuborilgan Telegram xabarlari tarixi (tiklash shart emas).

Jadvallar **bog'lanish tartibida** yoziladi — tiklashda vrach buyurtmadan
oldin, mahsulot buyurtma qatoridan oldin keladi.

## Faylni ochish

Gzip'langan oddiy JSON — istalgan joyda ochiladi:

```bash
gunzip -c dxl-erp-zaxira-2026-08-24.json.gz > zaxira.json
```

Telefonda ham ko'rish mumkin, lekin fayl katta bo'lsa kompyuter qulayroq.

## Tiklash

Tiklash kamdan-kam va ehtiyotkorlik talab qiladigan ish — tugma qilib
qo'yilmagan (bir noto'g'ri bosish butun bazani almashtirib yuborishi
mumkin). Kerak bo'lsa faylni menga bering, birga tiklaymiz.

## Muhim: fayl maxfiy

Zaxirada vrachlarning telefon raqami, manzili va moliyaviy ma'lumot bor.
Faylni begonaga yubormang. Telegram chatingizda tursa xavfsiz.

## Hajm

Bir yillik ishda ham fayl bir necha yuz kilobayt atrofida bo'ladi —
Telegramning 50 MB chegarasidan ancha kichik.
