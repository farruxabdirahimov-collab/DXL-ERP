# Modul 1 — Taklif-shartnoma va teskari sanoq

Foydalanuvchi bergan tarif jadvali asosida. Holat: **kelishuvga tayyor**.

---

## 1. Jadvalning tekshiruvi

Arifmetika **to'liq to'g'ri** — uch tarifda ham raqamlar mos keladi.

| Tarif | dona | 1 dona sotuv | 1 dona tannarx | Marja | Sovg'a ulushi | Sovg'ali marja |
|---|---|---|---|---|---|---|
| Old-20 | 20 | $50 | $33 | 34.0% | 6.0% | **28.0%** |
| Standart-50 | 50 | $50 | $33 | 34.0% | 4.0% | **30.0%** |
| Katta-100 | 100 | $50 | $33 | 34.0% | 3.0% | **31.0%** |

### Ikkita e'tiborga loyiq jihat

**a) Dona narxi uch tarifda ham bir xil — $50.** Ya'ni hajm uchun chegirma
yo'q. Katta paket faqat **uzoqroq muddat** va **kattaroq sovg'a** beradi.
Bu ataylab shundaymi yoki katta paketga chegirma ham qo'shiladimi?

**b) Sovg'a foizi paket kattalashgani sayin kamayadi** (6% → 4% → 3%).
Natijada:

```
5 × Old-20   = $5000  →  sovg'a jami $300
1 × Katta-100 = $5000  →  sovg'a       $150
```

Ya'ni hisob-kitobni biladigan vrach uchun **Old-20 ni takroran olish ikki
barobar foydali**. Katta-100 kamdan-kam tanlanadi.

**Lekin bu kamchilik bo'lmasligi ham mumkin.** Maqsadingiz — pul aylanishini
tezlashtirish. Old-20 = 15 kunlik aylanma, eng tezi. Ya'ni siz eng tez
aylanadigan paketni eng ko'p rag'batlantiryapsiz — bu **maqsadga mos**.
Faqat bilib turing: Katta-100 amalda kam ishlatiladi.

Agar Katta-100 ham jozibali bo'lishini istasangiz, ikki yo'l bor:
- sovg'ani oshirish ($150 → $250, marja 31% → 29% ga tushadi), yoki
- dona narxini pasaytirish ($50 → $48, ya'ni haqiqiy hajm chegirmasi)

---

## 2. Teskari sanoq — ha, qilinadi

### Soniyagacha ko'rsatish mumkinmi?

**Texnik jihatdan — ha, oson.** Lekin **har doim soniya ko'rsatish tavsiya
etilmaydi**: 15 kun qolganda soniya sanashning ma'nosi yo'q, ekran
bezovta qiladi va arzon marketing taassurotini beradi.

**Tavsiyam — bosqichli ko'rinish:**

| Qolgan vaqt | Ko'rinishi | Rang |
|---|---|---|
| 7 kundan ko'p | `12 kun qoldi` | ko'k |
| 1–7 kun | `3 kun 4 soat` | sariq |
| 24 soatdan kam | `18:42:15` — **jonli, soniyagacha** | qizil, pulsatsiya |
| Muddat o'tgan | `Muddat tugadi · sovg'a berilmaydi` | kulrang |

Shunda soniya **haqiqatan ahamiyatli bo'lgan paytda** paydo bo'ladi va
kuchli ta'sir qiladi.

### Texnik yechim

- Server `deadline_at` (aniq vaqt) va `server_now` ni birga qaytaradi
- Telefon ikkalasining farqini bir marta hisoblab, **o'zi sanaydi**
  (serverga har soniya so'rov ketmaydi)
- Telefon soati o'zgartirilsa ham sanoq buzilmaydi — server vaqti asos
- Vaqt mintaqasi: Asia/Tashkent (tizimda allaqachon shunday)

### Faqat vaqt emas, pul ham

Teskari sanoqning yonida **qolgan summa** ham turishi kerak — vrach uchun
asosiy harakat shu:

```
┌────────────────────────────────────┐
│  Standart-50 · SHRT-2026-00042     │
│                                    │
│        ⏳  8 kun 3 soat            │
│                                    │
│  To'langan    $2 100 / $2 500      │
│  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░  84%         │
│                                    │
│  Sovg'ani olish uchun: $400        │
│  🎁 Nakonechnik ($100)             │
└────────────────────────────────────┘
```

---

## 3. Kim nima ko'radi

| Rol | Ko'rinishi |
|---|---|
| **Vrach** | Bosh ekranda katta teskari sanoq + qolgan summa + sovg'a nomi |
| **Agent** | O'z vrachlarining shartnomalari, muddati yaqinlashgani tepada |
| **Direktor** | Barcha shartnomalar, muddati o'tish xavfi bor summasi jami |
| **Buxgalter** | To'lov kiritganda qaysi shartnomaga tushayotgani ko'rinadi |
| **Ta'sischi** | Faqat ko'radi |

Agent va direktor uchun alohida ro'yxat: **«Muddati yaqin shartnomalar»** —
3 kundan kam qolgan va to'lanmagan summasi bor shartnomalar, eng shoshilinchi
tepada. Agent ertalab shuni ochib, kimga qo'ng'iroq qilishni biladi.

---

## 4. Xabarnomalar

| Qachon | Kimga | Matn mazmuni |
|---|---|---|
| 7 kun qolganda | vrach + agent | «$400 qoldi, 7 kun ichida yopsangiz $100 lik nakonechnik sovg'a» |
| 3 kun qolganda | vrach + agent | shoshilinch ohang |
| 1 kun qolganda | vrach + agent + direktor | «Ertaga muddat tugaydi» |
| To'liq to'langanda | vrach + agent | «🎁 Tabriklaymiz! Sovg'angiz tayyor» |
| Muddat o'tganda | agent + direktor | «Sovg'a berilmadi, qarz $400 qoldi» |
| Har kuni 21:00 | direktor | 3 kundan kam qolgan shartnomalar ro'yxati |

Vaqt: ertalab 09:00 (eslatmalar jobi allaqachon shu vaqtda ishlaydi).

---

## 5. Baza tuzilmasi

**`tariffs`** — taklif shabloni:
- `name` — "Old-20"
- `package_qty` — 20
- `package_price_usd` — 1000
- `package_cost_usd` — 660 *(reja qilingan tannarx; haqiqiysi kirimdan olinadi)*
- `term_days` — 15
- `gift_name` — "Nakonechnik"
- `gift_value_usd` — 60
- `gift_product_id` — sovg'a katalogdagi mahsulot bo'lsa (ombordan chiqadi)
- `is_active`

**`contracts`** — tuzilgan shartnoma:
- `number` — SHRT-2026-00042
- `doctor_id`, `tariff_id`, `agent_id`
- `starts_at` — **teskari sanoq boshlanish vaqti (aniq soat-daqiqa)**
- `deadline_at` — `starts_at + term_days`
- `package_qty`, `package_price_usd` — tarifdan **nusxa** olinadi
  *(tarif keyin o'zgarsa, tuzilgan shartnoma o'zgarmaydi)*
- `gift_name`, `gift_value_usd` — shu ham nusxa
- `delivered_qty`, `paid_usd`, `returned_usd`
- `status` — amalda / to'liq to'langan / muddati o'tgan / bekor qilingan
- `gift_status` — kutilmoqda / **qozonildi** / berildi / yo'qotildi
- `gift_issued_at`, `gift_issued_by_id`
- `closed_at`

**`orders`** ga: `contract_id` — buyurtma qaysi shartnoma hisobidan

---

## 6. Mantiq

### Teskari sanoq qachon boshlanadi

Ikki variant bor, kelishish kerak (savol #2 pastda):
- **A:** shartnoma imzolangan payt — siz shunday degansiz
- **B:** tovar vrachga yetkazilgan payt

**Tavsiyam — B (yetkazilgan payt).** Sabab: shartnoma imzolanib, tovar
3 kun keyin yetsa, vrach 15 kunning 3 tasini yo'qotadi va bu adolatsizlik
his qildiradi. Yetkazishdan boshlansa — nizo bo'lmaydi.
Agar A ni tanlasangiz ham qilinadi, faqat shartnoma va yetkazish orasidagi
farqni qisqa ushlash kerak bo'ladi.

### To'lov qaysi shartnomaga tushadi

Hozir to'lov **eng eski qarzdan** yopiladi (FIFO). Shartnomalar kelgach bu
muammo tug'diradi: vrachda ikkita shartnoma bo'lsa, to'lov noto'g'ri
joyga tushib, sovg'a yo'qolishi mumkin.

**Tavsiyam:** to'lov kiritilganda **muddati eng yaqin shartnoma** birinchi
yopiladi (FIFO emas, «deadline bo'yicha»). Buxgalter xohlasa qo'lda
boshqa shartnomani tanlashi mumkin. Bu vrachning sovg'a olish imkonini
maksimal qiladi va sizning maqsadingizga — tez to'lovga — xizmat qiladi.

### Sovg'a qachon beriladi

Siz «muddat oxirida» degansiz. Lekin vrach 5-kuni to'liq to'lasa,
10 kun kutishning ma'nosi yo'q — aksincha, darrov berilsa taassurot kuchli
bo'ladi va u keyingi paketni oladi.

**Tavsiyam:** to'liq to'langan **zahoti** «sovg'a qozonildi» holati qo'yiladi
va vrachga xabar boradi. Jismonan berish — keyingi tashrifda yoki
buyurtma bilan birga. Ombordan chiqishi hujjat bilan yoziladi.

### Qaytarish bilan bog'lanishi ⚠️ muhim

Vrach 20 tadan 5 tasini qaytarsa, shartnoma summasi $1000 dan $750 ga
tushadimi? Agar shunday bo'lsa, **teshik paydo bo'ladi**:

> Vrach 19 ta implantni qaytaradi, $50 to'laydi va $60 lik sovg'ani oladi
> — sovg'a to'lovdan qimmat.

**Tavsiyam:** sovg'a shartida **minimal chegara** bo'lsin — masalan
paket qiymatining **80% i** haqiqatan olib qolinib to'langan bo'lsa.
Undan kam bo'lsa: qarz kamayadi, lekin sovg'a berilmaydi.

### Muddat o'tsa

- Sovg'a berilmaydi (`gift_status = yo'qotilgan`)
- Narx o'zgarmaydi, qarz qoladi va odatdagi qarz nazoratiga o'tadi
- Shartnoma «muddati o'tgan» holatiga tushadi
- Vrachning to'lov intizomi ko'rsatkichiga yoziladi (sodiqlik ballida
  allaqachon `avg_payment_delay_days` bor)

---

## 7. Savollar — javob kerak

### Blokirovka qiluvchi (bularsiz boshlay olmayman)

1. **Paket narxi qat'iymi?** Jadvalda implant $50 dan. Katalogda esa har
   razmerning narxi har xil ($95–110 atrofida, bu men yaratgan namunaviy
   narxlar). Ya'ni:
   - **A:** paket qat'iy — qaysi razmer olinishidan qat'i nazar 20 ta = $1000
   - **B:** dona narxi $50, katalog narxlari shunga moslanadi
   - **C:** katalog narxlari haqiqiy, tarif esa chegirma foizi beradi

2. **Teskari sanoq qachondan?** Shartnoma imzolangandanmi yoki tovar
   yetkazilgandanmi? *(tavsiyam — yetkazilgandan)*

3. **Sovg'adagi $60 — sotuv narximi yoki tannarxmi?** Agar nakonechnikning
   sotuv narxi $60, tannarxi $40 bo'lsa, haqiqiy sof foyda $280 emas,
   **$300**. Jadvalingiz bu holda ehtiyotkor hisoblangan bo'ladi.

4. **Qaytarish shartnoma summasini kamaytiradimi?** Va yuqoridagi
   80% li minimal chegara qabul qilinadimi?

### Muhim, lekin keyin ham javob berish mumkin

5. Bitta vrachda bir vaqtda **nechta shartnoma** bo'la oladi?
   *(Tavsiyam: bir nechta bo'lsin, lekin jami qarz limitidan oshmasin)*

6. To'lov **qisman** bo'lsa — masalan 15-kunda $950 to'langan, $50 qolgan.
   Sovg'a beriladimi? *(Tavsiyam: yo'q — «to'liq to'lov» sharti buzilmasin,
   aks holda chegara suzuvchi bo'lib qoladi)*

7. Muddat o'tgach vrach yana shartnoma tuza oladimi yoki eski qarz
   yopilmaguncha bloklanadimi? *(Tavsiyam: bloklansin, direktor ochishi mumkin)*

8. Sovg'a ombordan chiqadimi (nakonechnik — katalogdagi mahsulot) yoki
   alohida hisoblanadimi?

9. Shartnomani kim tuza oladi — agentmi yoki faqat direktormi?
   *(Tavsiyam: agent tuzadi, direktor tasdiqlaydi — chegirma nazorati kabi)*

10. Agentning oylik rejasida shartnoma ko'rsatkichi bo'lsinmi?
    Masalan «oyda 5 ta shartnoma, 4 tasi muddatida yopilgan».
    *(Modul 2 bilan bog'lanadi)*

---

## 8. Qo'shimcha takliflar

**1. «Sovg'a yo'qotilgan» hisoboti.** Oy oxirida: nechta shartnoma sovg'a
bilan, nechtasi sovg'asiz yopilgan. Bu tarif ishlayaptimi yoki yo'qmi —
shundan bilinadi. Agar 90% vrach sovg'ani ololmasa, muddat juda qisqa.

**2. Vrachga «hisob-kitob» tugmasi.** Teskari sanoq yonida «Qolgan $400 ni
to'lash» tugmasi — agentga darhol xabar boradi, u borib pulni oladi.
Vrach o'ylab turgan paytda harakatga o'tkazish kerak.

**3. Tarifni sinash rejimi.** Yangi tarif kiritishdan oldin: «shu tarif
o'tgan 3 oyga qo'llanganda foyda qancha bo'lardi» — hisoblab ko'rsatadi.
Modul 3 (foyda-zarar) dan keyin qilinadi.

**4. Sovg'a zaxirasi.** Agar 10 ta shartnoma bir vaqtda yopilsa, 10 ta
nakonechnik kerak bo'ladi. Tizim «kutilayotgan sovg'alar» sonini ko'rsatib
tursin, ombor tayyor bo'lsin.

**5. Muddat o'tishiga oz qolgan pul jamlanmasi.** Direktor uchun bitta
raqam: «3 kun ichida $4 200 kelishi kerak, kelmasa $260 lik sovg'a
yo'qoladi». Pul oqimini oldindan ko'rish imkonini beradi.
