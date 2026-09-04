# Qarz nazorati — buyurtma endi to'xtamaydi

## Nima o'zgardi

Ilgari vrachning qarzi limitidan oshsa, buyurtma **direktor tasdig'iga**
tushardi va shu yerda kutib turardi.

Amalda esa direktor bu so'rovlarni deyarli hech qachon rad etmasdi — hamma
vrachga qarzga berilardi. Ya'ni tasdiq nazorat emas, faqat **kechikish**
edi: agent kutardi, vrach kutardi, tovar esa baribir ketardi.

Endi:

| Holat | Ilgari | Hozir |
|---|---|---|
| Qarz limitidan oshdi | Direktor tasdig'i kutiladi | **Buyurtma darhol o'tadi**, belgilanadi |
| Muddati o'tgan qarz bor | Direktor tasdig'i kutiladi | **Buyurtma darhol o'tadi**, belgilanadi |
| Chegirma limitdan oshdi | Direktor tasdig'i kutiladi | **O'zgarmadi** — tasdiq kerak |

Chegirma nega qoldi? Chunki u kamdan-kam bo'ladi va har bir foizi
to'g'ridan-to'g'ri foydadan ketadi. U yerda tasdiq haqiqiy qaror chiqaradi.

## Nazorat qayerda qoldi

Nazorat yo'qolgani yo'q — u **oldindan** emas, **keyin** bo'ladi.

1. **Darhol xabar.** Limitdan oshgan buyurtma o'tkazilganda direktor va
   super-admin Telegram'da xabar oladi:
   «⚠️ Limitdan oshgan buyurtma … Buyurtma o'tkazildi — bu ogohlantirish,
   so'rov emas.»

2. **«Nazorat» ro'yxati.** Buyurtmalar ekranida direktor uchun alohida
   **Nazorat** tabi bor. U yerda limitdan oshgan hamma buyurtma turadi.

3. **Buyurtma kartochkasi.** Buyurtma ichida sariq ogohlantirish
   ko'rinadi: «⚠️ Qarz limitidan oshgan» va aniq sabab
   (masalan: «Qarz limitidan oshadi: limit $1000, buyurtmadan keyin $1350»).

4. **21:00 kunlik hisobot.** Direktorning kunlik hisobotida yangi blok:
   «⚠️ Limitdan oshgan buyurtmalar: 3 ta ($2 150)» va eng kattalari
   ro'yxati.

## Agent nima ko'radi

Agent uchun hech narsa qiyinlashmadi — aksincha, kutish yo'qoldi. Buyurtma
yozadi, o'zi tasdiqlaydi, ombor yig'a boshlaydi. «Nazorat» tabi agentga
ko'rsatilmaydi.

## Sozlamalar

Sozlamalar bo'limida ikki tugma bor:

- **`block_on_debt_limit`** — qarz limiti oshganda belgilansinmi;
- **`block_on_overdue`** — muddati o'tgan qarzi borlar belgilansinmi.

Ikkalasi ham buyurtmani **to'xtatmaydi**, faqat belgi qo'yadi. O'chirilsa,
belgi ham qo'yilmaydi va Nazorat ro'yxati bo'sh bo'ladi.

Alohida vrachni butunlay chiqarib tashlash uchun uning kartochkasidagi
**`credit_block_override`** (nazoratdan ozod) belgisini yoqing — u holda
belgi hech qachon qo'yilmaydi.
