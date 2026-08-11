# Qaytarish (vozvrat) — qo'llanma

Vrach olgan tovarni qaytarganda, uni tizimga **qaytarish hujjati** bilan
rasmiylashtiriladi. Faqat shunda ombor qoldig'i, vrachning qarzi va barcha
hisobotlar bir vaqtda to'g'rilanadi.

> ❗ Qaytarilgan tovarni qo'lda "spisaniye" qilish yoki buyurtmani o'chirish
> **mumkin emas** — u holda qarz va hisobotlar chalkashadi.

---

## Kim qaytara oladi

| Rol | Qaytarish |
|---|---|
| Sotuv agenti | ✅ o'ziga biriktirilgan vrachlar bo'yicha |
| Omborchi | ✅ hamma bo'yicha |
| Buxgalter | ✅ hamma bo'yicha |
| Direktor / Super-admin | ✅ hamma bo'yicha |
| Vrach | ❌ (agentga aytadi) |
| Ta'sischi | ❌ (faqat ko'radi) |

---

## Qayerda turadi

Ikki joyda:

- **Yana → ↩️ Qaytarishlar** — barcha qaytarishlar tarixi va qisqa yo'riqnoma
- **Buyurtma ichida** — qaytarish shu yerdan yoziladi (pastdagi tugma)

Tugma buyurtma ichida turishining sababi: qaysi buyurtmadan qaytayotgani
ma'lum bo'lsa, tizim narxni ham, agentni ham o'zi to'g'ri oladi.

## Qadamlar (telefonda)

1. **Buyurtmalar** → yuqoridagi bo'limlardan **«Yetkazilgan»** ni tanlang
   (bo'limlar qatorini chapga suring) → kerakli buyurtmani oching.
2. Buyurtma holati **«Yetkazildi»** bo'lsa, pastda
   **«↩️ Tovarni qaytarish (vozvrat)»** tugmasi chiqadi.
3. Ochilgan oynada buyurtmadagi mahsulotlar ro'yxati ko'rinadi —
   **qaytayotgan donasini** yozing (qolganini 0 qoldiring).
4. **Sababni yozing** (majburiy): masalan «Qadoq shikastlangan»,
   «Razmer mos kelmadi», «Ortiqcha olingan».
5. **«Qaytarishni rasmiylashtirish»** tugmasini bosing.

Tayyor. Ekranda hujjat raqami chiqadi (masalan `QAY-2026-00014`).

---

## Bosgandan keyin nima o'zgaradi

Bitta amal bilan **beshta joy** birdaniga to'g'rilanadi:

| Nima | Qanday |
|---|---|
| 📦 Ombor | tovar buyurtma ketgan omborga qaytadi, qoldiq oshadi |
| 💳 Vrach qarzi | qaytarish summasi qarzdan ayiriladi |
| 🛒 Sotuv hisoboti | summa va dona **sof** bo'lib qoladi |
| 📈 Agent rejasi | bajarilish foizi shishib qolmaydi |
| ⭐ Vrachning xarid darajasi | sodiqlik/ABC toifasi sof xariddan hisoblanadi |

Buyurtma sahifasida «Qaytarilgan» qatori paydo bo'ladi, qarz esa
`Summa − To'langan − Qaytarilgan` formulasi bo'yicha qayta hisoblanadi.

---

## Qoidalar (tizim o'zi tekshiradi)

- **Sotilganidan ko'p qaytarib bo'lmaydi.** 3 dona sotilgan bo'lsa,
  5 donani qabul qilmaydi.
- **Buyurtmada yo'q mahsulot qaytarilmaydi.**
- **Narx sotilgan narxda hisoblanadi.** Chegirma bilan sotilgan bo'lsa
  ($100 → 25% chegirma → $75), qaytarish ham $75 dan hisoblanadi —
  chegirma "yo'qolmaydi".
- **Bo'sh ro'yxat va sababsiz hujjat** yozilmaydi.
- Har bir qaytarish **audit jurnaliga** tushadi: kim, qachon, qaysi vrachga,
  qancha summaga.

---

## Hisobotlarda qanday ko'rinadi

Asosiy raqamlar hamma joyda **sof** (qaytarish ayirilgan). Chalkashmaslik
uchun qaytarish bo'lgan davrda uning o'zi ham alohida ko'rsatiladi:

**Hisobotlar → Sotuv** bo'limida:

```
Jami sotildi      12 dona      $1 200
Qaytarildi         2 dona      − $200
Sof sotuv         10 dona      $1 000
```

**21:00 kunlik xabarida** (qaytarish bo'lgan kunda):

```
🛒 Bugungi sotuv
  Summa: $1 000
  Dona: 10 | Buyurtma: 4 | Vrach: 3
  ↩️ Qaytarildi: $200 (2 dona, 1 ta hujjat)
  Sotuv summasi — qaytarish ayirilgan sof raqam (jami $1 200)
```

Agentga ketadigan xabarda ham shu qator chiqadi va **«reja hisobidan
ayirildi»** deb yoziladi.

Qaytarish bo'lmagan kunda bu qatorlar umuman chiqmaydi — hisobot toza qoladi.

---

## Ko'p uchraydigan savollar

**Tugma ko'rinmayapti.**
Buyurtma hali «Yetkazildi» holatiga o'tmagan. Yetkazilmagan buyurtmani
qaytarish shart emas — uni bekor qilish kifoya (rezerv o'zi bo'shaydi).

**Vrach pul to'lab bo'lgan, keyin qaytardi.**
Qaytarish summasi baribir qarzdan ayiriladi. Agar qarz manfiy chiqsa,
bu vrachning **oldindan to'lovi** — keyingi buyurtmasida hisobga olinadi.

**Buyurtmasiz qaytarish (juda eski tovar, buyurtma topilmasa).**
Mini App'da qaytarish har doim buyurtma orqali yoziladi — shunda narx va
agent aniq bo'ladi. Buyurtmasi topilmagan holat uchun tizimda imkoniyat bor
(narx amaldagi prays-list bo'yicha olinadi, summa vrachning umumiy qarzidan
ayiriladi), lekin alohida tugma sifatida chiqarilmagan. Kerak bo'lsa ayting —
qo'shib beraman.

**Xato qaytarish yozib yubordim.**
Hujjat o'chirilmaydi (audit buzilmasligi uchun). Direktorga ayting — teskari
tuzatish kirim hujjati bilan rasmiylashtiriladi va sababda izoh qoldiriladi.
