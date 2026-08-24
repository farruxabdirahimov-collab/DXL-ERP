# Menejer oyligi — KPI bo'yicha avtomatik hisob

Menejer **Yana → 💵 Oyligim** bo'limida oy davomida kutilayotgan oyligini
ko'rib turadi. Raqamlar kun sayin o'zi yangilanadi.

## Tarkibi

| Qism | Qoida |
|---|---|
| **Fiksa** | $200 — doimiy |
| **Klinika tashriflari** | 250 ta = $150. Kam bo'lsa nisbatan (200 ta → $120). Ko'p bo'lsa $150 da to'xtaydi |
| **Yig'ilgan pul** | $4000 gacha **2.5%**, $4000 dan boshlab **butun summaga 3%** |
| **Post / video** | 4 tagacha $0 · 5–12 ta har biri $5 · 12 tadan keyin oshmaydi ($60) |
| **Shifokor otzivi** | xuddi shunday |

**Eng ko'pi:** 200 + 150 + 3% + 60 + 60.

## Chegara nima uchun muhim

$3999 yig'ilsa — $99.98. $4000 yig'ilsa — **$120**. Bir dollar farq $20 dan
ko'p bo'nus keltiradi. Menejer oy oxirida chegarani kesib o'tishga harakat
qiladi, bu esa pulni tezroq yig'ishga majbur qiladi.

## Post va otziv qanday hisobga olinadi

1. Menejer: **Oyligim → «Postlarim» → «+ Havola yuborish»**
   Turi (post yoki otziv) va havolani kiritadi
2. Direktor: **Oyligim → «Tasdiqlash»** — havolani ochib ko'radi va
   ✅ tasdiqlaydi yoki ❌ rad etadi
3. Tasdiqlangani **darhol** oylikka qo'shiladi, menejerga xabar boradi

Faqat tasdiqlangani pulga kiradi — shuning uchun son o'z-o'zidan
shishib ketmaydi.

**Oy hisobi:** havola *joylangan* sana bo'yicha. Direktor keyingi oyda
tasdiqlasa ham o'sha oyga yoziladi.

Menejer tasdiqlanmagan havolasini o'chira oladi, tasdiqlanganini — yo'q.

## Menejer nimani ko'radi

```
Shu oy uchun kutilayotgan oylik
        $487.50
Tasdiq kutayotgani hisobga olinsa +$15.00

Oylik fiksa                       $200.00
Klinika tashriflari  187/250      $112.50   ▓▓▓▓▓▓▓░░ 75%
Yig'ilgan pul        $3 000       $75.00    ▓▓▓▓▓▓▓░░ 75%
Post / video         8/12         $40.00    ▓▓▓▓▓▓░░░ 67%
Shifokor otzivi      12/12        $60.00    ▓▓▓▓▓▓▓▓▓ 100%
```

Har qatorda maqsad, hozirgi natija va qoida yozilgan — menejer nima
qilishi kerakligini o'zi ko'radi.

## Direktor nimani ko'radi

**«Jamoa»** tabida barcha menejerlar oyligi va **bu oy jami to'lanadigan
summa** — oy oxirida hisob-kitob tayyor bo'ladi.

## Raqamlarni o'zgartirish

Barcha summalar bitta faylda: `app/services/kpi.py` — eng tepasida.
Fiksa, tashrif maqsadi, foizlar, post narxi va chegaralar. Aytsangiz
o'zgartirib beraman.
