# Agent ekrani — taklif

Agent kuniga 10–12 marta ilovani ochadi, ko'pincha **ko'chada, bir qo'lda,
shoshib**. Shuning uchun ikkita o'lchov bor:

1. **Nechta bosishda ish bitadi** — 5 bosish 2 ga tushsa, kuniga 30 ta
   ortiqcha harakat yo'qoladi
2. **Ochgisi keladimi** — majburiyat emas, qiziqish bilan ochsin

---

## 1. Bosh ekran «statistika» emas, «bugun nima qilaman» bo'lsin

Hozir bosh ekranda to'rtta raqam turadi. Agent uchun ular **hisobot**, ish
emas. Ular direktorga kerak.

### Taklif: uch qavatli bosh ekran

```
┌──────────────────────────────────────┐
│  Salom, Aziz                         │
│                                      │
│      💵 $487.50                      │   ← 1. PUL. Eng tepada, eng katta
│      Bu oy topgan puling             │      Har amaldan keyin o'sadi
│      ▓▓▓▓▓▓▓░░░  bugun +$18          │
├──────────────────────────────────────┤
│  BUGUN                               │   ← 2. Kunlik maqsad, halqa
│   ⭕ 7/12 tashrif                     │      250/22 kun ≈ 12
│   Yana 5 ta — $3 qoladi              │
├──────────────────────────────────────┤
│  ⚡ TEZ AMALLAR                       │   ← 3. Ikki katta tugma
│  ┌────────────┐  ┌────────────┐      │
│  │ 📍 TASHRIF │  │ 🛒 BUYURTMA│      │
│  └────────────┘  └────────────┘      │
├──────────────────────────────────────┤
│  🔴 SHOSHILINCH (3)                  │   ← 4. Bugun nima qilish kerak
│  Dr. Karimov — ertaga muddat, $400   │
│  Dr. Aliyev — 2 kun, $1 200          │
│  Dr. Sobirov — 90% to'lagan, $50 qoldi│
└──────────────────────────────────────┘
```

**Nima o'zgardi:** raqam emas — **harakat**. Agent ekranni ochib darhol
biladi: bugun 5 ta tashrif kerak, uchta odamga qo'ng'iroq qilish kerak.

«$50 qoldi» qatori alohida qimmatli — bu **eng arzon pul**: bir qo'ng'iroq
bilan shartnoma yopiladi va agent bo'nus oladi.

---

## 2. Ma'lumot kiritishni qisqartirish

### Tashrif: 4 bosish → 1 bosish

Hozir: Tashriflar → vrachni qidirish → tanlash → tasdiqlash.

Taklif: bosh ekrandagi **📍 TASHRIF** tugmasi geolokatsiyani oladi va
**eng yaqin 3 ta vrachni** ko'rsatadi:

```
📍 Joylashuvingiz aniqlandi

  Dr. Karimov · Shifo klinika      45 m  →
  Dr. Aliyev  · Med Plus          220 m  →
  Dr. Sobirov · Denta             480 m  →

  🔍 Boshqa vrach
```

Odatda birinchisi to'g'ri chiqadi — **bitta bosish**. Bosgandan keyin
darhol: «✅ Tashrif qayd etildi · +$0.60».

### Buyurtma: takrorlash tugmasi

Vrachlar ko'pincha **bir xil narsani qayta oladi**. Vrach kartochkasida:

```
🔁 Oxirgi buyurtmani takrorlash
   4.0×10 mm × 5, 3.5×8 mm × 2 — $700
```

Bir bosishda savat to'ladi, agent faqat sonini o'zgartiradi.

### Razmer tanlash: ro'yxat emas, panjara

100 ta mahsulot ro'yxatidan qidirish o'rniga **diametr × uzunlik panjarasi**:

```
        8.5   10   11.5   13
 3.5 │  12  │ 8  │  3   │ 0
 4.0 │  20  │ 15 │  9   │ 4      ← katakdagi raqam = ombordagi qoldiq
 4.5 │   5  │ 11 │  6   │ 2
 5.0 │   0  │ 3  │  1   │ 0      ← kulrang = yo'q
```

Katakni bosish = savatga qo'shish. Agent razmerni **ko'rib** tanlaydi,
yozmaydi. Qoldiq ham shu yerda — «bormi?» deb so'rash kerak emas.

### Umumiy qoidalar

- **Tugmalar kamida 44 px** — ko'chada, qo'lqop bilan ham bosiladi
- **Har maydonga standart qiymat** — ombor, sana, kurs o'zi to'ladi
- **Klaviatura kamroq**: son uchun +/− tugmalar, telefon uchun oxirgi
  4 raqam bo'yicha qidiruv
- **Xato o'rniga ogohlantirish**: «Qoldiq 3 ta, siz 5 ta yozdingiz» —
  bloklamasdan, to'g'irlash imkonini berib

---

## 3. Dofamin — nega qayta-qayta ochsin

Odam **oldinga siljishni ko'rgani** uchun qaytadi. To'rtta ishlaydigan
mexanizm:

### a) Pul raqami har amaldan keyin o'ssin

Eng kuchlisi. Tashrif qayd etdi → **+$0.60**. To'lov kiritdi → **+$12**.
Post tasdiqlandi → **+$5**.

Raqam sakrab o'zgarsin (animatsiya bilan) va tepada tursin. Agent har
ochganda «bugun qancha topdim» deb qaraydi — bu odat bo'lib qoladi.

### b) Kunlik halqa (12 tashrif)

Oylik maqsad — 250. Bu juda uzoq, his qilinmaydi. Kunga bo'linsa **12** —
erishsa bo'ladigan raqam. Halqa to'lgani ko'rinib turadi.

```
   ⭕ 7/12          →      ✅ 12/12
   Yana 5 ta               Bugungi maqsad bajarildi! 🎉
```

### c) Ketma-ketlik (streak)

«**5 kun ketma-ket maqsadni bajarding 🔥**»

Uzilib qolishni istamaslik — davom etishdan kuchliroq turtki. Faqat
jazolamaslik kerak: uzilsa «yangi ketma-ketlik boshlandi» deb yozilsin.

### d) Kutilmagan tabrik

50% / 80% / 100% xabarlari allaqachon bor. Qo'shimcha:
- Oyda birinchi shartnoma yopilganda
- Shaxsiy rekord yangilanganda: «Bu oy o'z rekordingni yangilading!»
- Reytingda ko'tarilganda: «3-o'rindan 2-o'ringa chiqding»

### Nima QILMASLIK kerak

- **Sun'iy nishonlar** («10 ta tashrif uchun bronza medal») — kattalar
  buni sezadi va ishonch yo'qoladi
- **Ochilishi shart bo'lgan kunlik bonus** — o'yin mexanikasi, ish
  vositasiga tushmaydi
- **Doimiy bildirishnoma** — 2-3 kunda o'chirib qo'yiladi. Kuniga eng
  ko'pi 2 ta, faqat haqiqatan muhim bo'lsa

---

## 4. Menyu soddalashtirish

Hozir agentda pastda: Bosh · Vrachlar · Buyurtma · Reja · Yana.
«Reja» va «Oyligim» — deyarli bir xil narsa (ikkalasi ham natija).

Taklif: **Bosh · Vrachlar · Buyurtma · Pul · Yana**

«Pul» ichida: oylik, reja bajarilishi, yig'ilgan pul, postlar. Agentning
pul bilan bog'liq hamma narsasi bitta joyda — qidirmaydi.

---

## 5. Nimadan boshlash kerak

Hammasini birdan qilish shart emas. Ta'sir/mehnat nisbati bo'yicha:

| Ish | Ta'sir | Mehnat |
|---|---|---|
| Bosh ekranda pul raqami + kunlik halqa | ⭐⭐⭐ | kichik |
| «Shoshilinch» ro'yxati bosh ekranga | ⭐⭐⭐ | kichik |
| Tashrif — eng yaqin vrachlar bilan 1 bosish | ⭐⭐⭐ | o'rta |
| «Oxirgi buyurtmani takrorlash» | ⭐⭐ | kichik |
| Razmer panjarasi | ⭐⭐ | o'rta |
| Streak va rekord xabarlari | ⭐⭐ | kichik |
| Menyuni qayta guruhlash | ⭐ | kichik |

**Tavsiyam:** birinchi uchtasini qilib, bir hafta ishlatib ko'ring.
Agentlar nimadan shikoyat qilsa — o'shani keyingi qilamiz. Taxmin qilib
o'ntasini qurgandan ko'ra, ular aytganini qilish yaxshiroq.
