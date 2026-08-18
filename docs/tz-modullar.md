# TZ — 3 ta yangi modul

Holat: **kelishuvga tayyor**, kod yozilmagan. Har modul alohida navbatda
bajariladi: TZ tasdiqlanadi → kod → test → deploy → keyingisi.

---

## Hozirgi poydevor (nima bor, nima yo'q)

Yangi modullar shu ustiga quriladi, shuning uchun avval aniq holat:

| Kerak bo'ladigan narsa | Holati |
|---|---|
| Vrachda chegirma foizi, qarz limiti, to'lov muddati | ✅ bor (`doctors` jadvalida) |
| Nomlangan tarif rejalari (Standart/Kumush/Oltin) | ❌ yo'q |
| Shartnoma hujjati | ❌ yo'q |
| Agentga oylik reja (3 ko'rsatkich) va reyting | ✅ bor, ishlaydi |
| Kompaniya (direktor) rejasi | ❌ yo'q |
| Kirim hujjatida tannarx maydoni | ⚠️ **baza va API'da bor, lekin Mini App so'ramaydi** — hozir hammasi 0 |
| Mahsulotning joriy tannarxi | ❌ yo'q |
| Xarajatlar (ijara, oylik, transport…) | ❌ yo'q |
| Foyda-zarar hisoboti | ❌ yo'q |

**Eng muhim xulosa:** foyda-zararning to'sig'i — dasturda emas, **ma'lumotda**.
Tannarxsiz foydani hech qanday dastur hisoblab bera olmaydi.

---

# MODUL 1 — Shartnoma va tariflar

## Maqsad

Hozir har bir vrachga chegirma **qo'lda** yoziladi. 50 ta vrach bo'lsa —
50 xil shart, kim qanchaga kelishganini hech kim eslamaydi. Tarif rejasi
buni tartibga soladi: vrach tarifga biriktiriladi, shartlar tarifdan keladi.

## Nima qo'shiladi

### Baza

**`tariffs`** — tarif rejasi:
- `name` — "Standart", "Kumush", "Oltin", "Platina"
- `discount_pct` — chegirma foizi
- `debt_limit_usd` — qarz limiti
- `payment_term_days` — to'lov muddati (kun)
- `min_monthly_usd` — shu tarifga tushish uchun oylik minimal xarid
- `bonus_note` — qo'shimcha shartlar matni (masalan "har 10 implantga 1 ta bepul")
- `is_active`

**`tariff_prices`** *(ixtiyoriy, 2-bosqich)* — tarifga maxsus narx:
- `tariff_id`, `product_id` yoki `category_id`, `price_usd`
- Bo'sh bo'lsa — umumiy prays-listdan `discount_pct` ayiriladi

**`contracts`** — shartnoma:
- `number` (SHRT-2026-00001), `doctor_id`, `tariff_id`
- `signed_date`, `valid_from`, `valid_to`
- `status` — loyiha / amalda / muddati tugagan / bekor qilingan
- `note`, `created_by_id`

**`doctors`** ga qo'shiladi: `tariff_id`, `contract_id`

### Mantiq

- Buyurtma yozilganda chegirma **shartnomadagi tarifdan** olinadi.
  Vrachga alohida chegirma qo'yilgan bo'lsa — u ustun turadi (istisno),
  lekin bu audit jurnaliga "tarifdan chetlashish" deb yoziladi.
- Shartnoma muddati tugagan bo'lsa — buyurtmada ogohlantirish chiqadi,
  direktor tasdig'iga ketadi.
- **Avtomatik tarif taklifi:** oxirgi 3 oylik xarid `min_monthly_usd` dan
  yuqori bo'lsa, tizim "bu vrachni Oltin tarifiga o'tkazish mumkin" deb
  taklif qiladi. Avtomatik o'tkazmaydi — direktor tasdiqlaydi.
- Muddati tugashiga 30 kun qolganda direktorga eslatma (09:00 jobiga qo'shiladi).

### Ekranlar

- **Sozlamalar → Tariflar** — tariflar ro'yxati, yaratish/tahrirlash (direktor)
- **Vrach kartochkasi** — "Tarif va shartnoma" bloki: tarif nomi, shartnoma
  raqami, amal muddati, shartlar; "Shartnoma tuzish" tugmasi
- **Vrachlar ro'yxati** — tarif bo'yicha filtr
- **Shartnoma PDF** — `reportlab` allaqachon ulangan (hisob-faktura uchun),
  shu bilan bosma shakl chiqariladi

### Qabul mezonlari

1. Vrachni Oltin tarifiga biriktirgach, yangi buyurtmada chegirma o'zi qo'yiladi
2. Tarif chegirmasi o'zgartirilsa, **eski buyurtmalar o'zgarmaydi** (narx hujjatda qotgan)
3. Shartnoma muddati tugagan vrachga buyurtma direktor tasdig'isiz o'tmaydi
4. Shartnoma PDF telefonda ochiladi va ulashiladi
5. Tarif chegirmasidan chetlashish audit jurnalida ko'rinadi

**Baholash:** ~2 ish kuni (tariff_prices'siz), +1 kun tarifga maxsus narx bilan.

---

# MODUL 2 — Oylik rejani boyitish

## Maqsad

Bo'lim bo'sh ko'rinishining ikki sababi bor:
1. Hali birorta ham reja qo'yilmagan (ma'lumot yo'q)
2. Faqat **agentga** reja bor — kompaniya darajasida reja yo'q, direktor
   o'zi uchun hech narsa ko'rmaydi

## Nima qo'shiladi

### Kompaniya rejasi (direktor uchun)

**`company_plans`** — oylik umumiy reja:
- `year`, `month`
- `target_amount_usd`, `target_units`, `target_collection_usd`
- `target_new_doctors` — oyda nechta yangi vrach
- `target_margin_usd` — foyda maqsadi *(Modul 3 dan keyin faollashadi)*

Direktor ekranida: kompaniya rejasi vs agentlar rejalari yig'indisi.
Agar agentlar yig'indisi kompaniya rejasidan kam bo'lsa — qizil ogohlantirish
(«$12 000 reja qo'yilgan, agentlarga bo'lingani $9 500 — $2 500 egasiz»).

### Yangi ko'rsatkichlar

Hozir 3 ta: summa, dona, yig'ilgan pul. Qo'shiladi:
- **Yangi vrachlar** — oyda nechta yangi mijoz ochildi
- **Faol vrachlar** — oyda kamida bir marta buyurtma bergan vrachlar soni
- **Tashriflar** — geolokatsiyali tashriflar soni *(modul allaqachon bor)*

Har biri ixtiyoriy: 0 qo'yilsa — hisobga olinmaydi.

### Prognoz va sur'at

- «Shu sur'atda oy oxirida **$8 400** bo'ladi (reja $10 000, **84%**)»
- Kunlik kerakli sur'at: «rejani bajarish uchun kuniga $420 kerak,
  hozirgi o'rtacha $310»
- Rangli holat: yashil (sur'atda) / sariq (ortda) / qizil (jiddiy ortda)

### Tarix va tez ish

- **Oxirgi 6 oy grafigi** — har oy bajarilish foizi (agent va kompaniya)
- **«O'tgan oydan nusxa»** tugmasi — reja qo'yishni bir bosishga tushiradi
- **«Hammaga bir xil qo'yish»** — barcha agentlarga bitta raqam
- Reja o'zgartirilsa audit jurnaliga yoziladi (oy o'rtasida pasaytirilmasin)

### Xabarnomalar

- Agent 50% / 80% / 100% ga yetganda tabrik xabari
- Oy oxirigacha 5 kun qolganda 70% dan past agentga eslatma
- Oy yakunida: reja bajarilishi + reyting o'rni

### Bonus hisoblash *(ixtiyoriy, aytsangiz qo'shaman)*

Tarifga o'xshash jadval: 80% → 0%, 100% → 3%, 120% → 5% sotuv summasidan.
Tizim bonusni o'zi hisoblab, oylik yakunda ko'rsatadi.

### Qabul mezonlari

1. Direktor kompaniya rejasini qo'yadi va agentlar yig'indisi bilan solishtirishni ko'radi
2. Agent bosh ekranda: bajarilish %, prognoz, kunlik kerakli sur'at
3. «O'tgan oydan nusxa» bir bosishda barcha agentlarga reja qo'yadi
4. 6 oylik grafik ishlaydi
5. Reja bajarilishi **qaytarish ayirilgan sof raqamdan** hisoblanadi (hozir ham shunday)

**Baholash:** ~2 ish kuni (bonussiz), +0.5 kun bonus bilan.

---

# MODUL 3 — Foyda-zarar hisoboti

## Savolingizga javob: ha, ma'lumot kerak

Foydani hisoblash uchun **uchta** narsa kerak. Ikkitasi hozir yo'q:

### 1. Tannarx — sotib olish narxi ⚠️ ENG MUHIMI

Yaxshi xabar: baza tayyor. `receipt_items.cost_usd` maydoni **allaqachon bor**,
API ham qabul qiladi. Yomon xabar: **Mini App'dagi kirim oynasi buni so'ramaydi**,
shuning uchun hozirgacha kirim qilingan hamma tovarning tannarxi **0**.

Kerak bo'ladi:
- Kirim oynasiga «Tannarx (dona)» maydoni qo'shish (1 soatlik ish)
- **Sizdan:** hozirgi ombordagi tovarning tannarxi — Excel'da
  `SKU | dona | tannarx $` ko'rinishida. Men import qilaman.
- Bundan keyin har kirimda tannarx yoziladi

**Hisoblash usuli — o'rtacha harakatlanuvchi tannarx (moving average).**
Misol: 100 ta $40 dan bor edi, 50 ta $46 dan keldi →
yangi tannarx `(100×40 + 50×46) / 150 = $42`. Sotilganda shu $42 yoziladi.
FIFO ham mumkin, lekin partiya hisobi kerak bo'ladi — siz avval "partiyasiz,
faqat soni" deb tanlagansiz, shuning uchun o'rtacha usul mos.

### 2. Xarajatlar — umuman yo'q

**`expenses`** jadvali qo'shiladi:
- `date`, `category`, `amount_uzs`, `fx_rate`, `amount_usd`, `note`, `created_by_id`
- `recurring` — har oy takrorlanadigan (ijara, oylik) bir marta kiritiladi

Xarajat turlari (kelishamiz):
ijara · xodimlar oyligi · transport/yetkazib berish · bojxona va rasmiylashtirish ·
reklama va marketing · aloqa va internet · bank xizmati · soliq · boshqa

**Sizdan:** oylik doimiy xarajatlaringiz ro'yxati va taxminiy summasi.

### 3. Qaytarish, chegirma, spisaniye — ✅ bu allaqachon tayyor

O'tgan hafta qilgan ish shu yerda ishlaydi: qaytarilgan tovar sotuvdan
ayiriladi, spisaniye alohida yoziladi.

## Hisobot ko'rinishi

```
FOYDA-ZARAR · Avgust 2026

Sotuv (sof, qaytarish ayirilgan)              $24 800
Sotilgan tovar tannarxi                      − $14 900
─────────────────────────────────────────────────────
YALPI FOYDA (margin)                           $9 900   (39.9%)

Xarajatlar
  Xodimlar oyligi                             − $2 400
  Ijara                                         − $800
  Transport                                     − $350
  Reklama                                        − $200
  Boshqa                                         − $150
  Spisaniye (yaroqsiz tovar)                     − $120
─────────────────────────────────────────────────────
JAMI XARAJAT                                  − $4 020

SOF FOYDA                                      $5 880   (23.7%)

Eslatma: yig'ilgan pul $19 200 — $5 600 qarzda qoldi
```

### Qo'shimcha kesimlar

- **Mahsulot bo'yicha foyda** — qaysi razmer ko'p foyda keltiradi,
  qaysi biri zarar bilan sotilgan (chegirma tannarxdan pastga tushsa — qizil)
- **Vrach bo'yicha foyda** — qaysi mijoz haqiqatan foydali
  (ko'p oladi, lekin katta chegirma bilan → foyda kam bo'lishi mumkin)
- **Agent bo'yicha foyda** — sotuv summasi emas, **foyda** bo'yicha reyting
- **Ombordagi pul** — hozir qancha pul tovarda turibdi (tannarx bo'yicha)
- **Chegirma nazorati** — chegirma tufayli yo'qotilgan foyda

### Muhim: ikki xil "foyda"

| | Nima | Qachon kerak |
|---|---|---|
| **Hisob bo'yicha (accrual)** | Yetkazilgan tovar bo'yicha, pul kelmagan bo'lsa ham | Biznes qanday ishlayapti |
| **Pul bo'yicha (cash)** | Faqat qo'lga tekkan pul | Kassada pul yetadimi |

Ikkalasini ham beraman — dillerlikda farq katta bo'ladi (qarzga sotiladi).

### Qabul mezonlari

1. Kirim oynasida tannarx so'raladi va saqlanadi
2. Tovar sotilganda o'sha paytdagi o'rtacha tannarx hujjatga **qotib qoladi**
3. Xarajat kiritiladi (so'mda, kursi bilan) va hisobotga tushadi
4. Yalpi foyda = sof sotuv − sotilgan tovar tannarxi
5. Sof foyda = yalpi foyda − xarajatlar − spisaniye
6. Foyda-zararni faqat direktor, ta'sischi va buxgalter ko'radi (agent **ko'rmaydi**)
7. Excel'ga yuklanadi

**Baholash:** ~3 ish kuni. **Lekin ma'lumot yig'ish sizdan vaqt oladi.**

---

# Sizdan kerak bo'ladigan ma'lumotlar

Modul bo'yicha ajratdim — hammasi birdan kerak emas.

### Modul 1 uchun (hozir)
1. Nechta tarif bo'ladi va nomlari? (masalan Standart / Kumush / Oltin)
2. Har tarifda: chegirma %, qarz limiti $, to'lov muddati (kun),
   shu tarifga tushish uchun oylik minimal xarid $
3. Tarif faqat chegirma foizimi, yoki ayrim mahsulotga maxsus narx ham bo'ladimi?
4. Shartnoma odatda necha oyga tuziladi?
5. Bosma shartnomangiz bormi? Bo'lsa — matnini bering, shabloniga solaman.

### Modul 2 uchun (keyinroq)
6. Agentga oylik reja qanday qo'yiladi — hammaga bir xilmi yoki alohida?
7. Bonus tizimi bormi? Bo'lsa — foizlari qanday?
8. Kompaniyaning oylik maqsadi qancha (USD)?

### Modul 3 uchun (eng ko'p vaqt oladi — hozirdan boshlang)
9. **Hozirgi ombor qoldig'ining tannarxi** — Excel: `SKU | dona | tannarx $`
10. Oylik doimiy xarajatlar ro'yxati va summasi
11. Tovarni qanday olasiz — oldindan to'lovmi, qarzgami? Bojxona/transport
    xarajati tannarxga qo'shiladimi yoki alohida yozilsinmi?
12. Valyuta: yetkazib beruvchiga USD to'laysizmi yoki boshqa valyutada?

---

# Tavsiyalar — yana nima qo'shish kerak

Muhimlik bo'yicha tartibladim.

### 1. Konsignatsiya (berib turilgan tovar) — ⭐ eng kerakli

Implant biznesida odatiy holat: vrachga 10 ta implant **qoldiriladi**,
u ishlatganini to'laydi, qolganini qaytaradi. Hozir tizimda bunday
tushuncha yo'q — ular sotilgan deb yoziladi va qarz paydo bo'ladi.

Nima beradi: vrachda qancha tovaringiz turganini bilasiz, oy oxirida
"hisobot beriladi", ishlatilgani sotuvga, qolgani omborga qaytadi.
Foyda-zarar ham to'g'ri chiqadi.

**Buni 4-modul qilib qo'shishni tavsiya qilaman.**

### 2. Zaxira rejalash — qachon va qancha buyurtma qilish

~100 SKU va ombordagi pulni hisobga olsak, bu to'g'ridan-to'g'ri pulga ta'sir
qiladi. Sotuv tezligi + yetkazib berish muddati asosida:
«4.0×10 mm — kuniga 1.2 dona ketyapti, 18 kunga yetadi, yetkazish 45 kun →
**bugun 60 dona buyurtma qiling**».

Hozir faqat `min_stock` bor — u statik, sotuv tezligini bilmaydi.
Modul 3 dan keyin qilish mantiqiy (tannarx bilan birga).

### 3. Yetkazib beruvchi bilan hisob-kitob

Vrachlarning sizga qarzini hisoblaymiz, lekin **sizning yetkazib beruvchiga
qarzingiz** hisoblanmaydi. Pul oqimi to'liq ko'rinishi uchun kerak.
Modul 3 ning tabiiy davomi.

### 4. Kassa va pul oqimi

Pul qayerda: naqd kassa, bank hisobi, agentlar qo'lidagi yig'ilgan pul.
Hozir to'lov yoziladi, lekin "pul qayerda" degan savolga javob yo'q.

### 5. Partiya va yaroqlilik muddati — o'ylab ko'ring

Siz avval "partiyasiz, faqat soni" degansiz va kichik jamoa uchun bu to'g'ri
qaror edi. Lekin implant — tibbiy buyum. Agar bir partiyada nuqson chiqsa
yoki tekshiruv kelsa, "bu seriya qaysi vrachlarga ketgan" degan savolga
javob bera olmaysiz.

Majburiy emas, lekin **xavfni bilib turishingiz kerak**. Keyin qo'shish
mumkin, ammo o'shanda eski ma'lumotda partiya bo'lmaydi.

### 6. Ma'lumotlar zaxirasi (backup)

Hozir baza faqat Railway'da. Haftalik avtomatik zaxira nusxa (Excel yoki
SQL dump) — bir kunlik ish, lekin butun biznes ma'lumoti xavfsiz bo'ladi.
**Buni modullardan oldin ham qilish mumkin.**

---

# Navbat — tavsiya qilingan tartib

Sizning tartibingiz (1 → 2 → 3) to'g'ri, chunki:

- **Modul 1** mustaqil, hech narsani kutmaydi
- **Modul 2** ham mustaqil, tez bajariladi
- **Modul 3** sizdan ma'lumot kutadi (tannarx, xarajatlar)

Shuning uchun eng samarali yo'l:

| Bosqich | Men | Siz |
|---|---|---|
| Hozir | Modul 1 (shartnoma va tariflar) | Tannarx Excel'ini yig'ib boring |
| Keyin | Modul 2 (oylik reja) | Xarajatlar ro'yxatini tayyorlang |
| So'ng | Modul 3 (foyda-zarar) | Ma'lumot tayyor bo'ladi |
| Keyin | Konsignatsiya, zaxira rejalash | — |

Ya'ni **Modul 3 uchun ma'lumot yig'ishni bugundan boshlang** — kod tayyor
bo'lgunicha ma'lumot ham tayyor bo'ladi va bir kun ham yo'qotilmaydi.
