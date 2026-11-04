"""FinScan 360 paketi: vrach arizasi hisobi va xabari.

Sahifa (`app/static/finscan/index.html`) xuddi shu hisobni JS'da qiladi.
Ariza xabaridagi raqamlarni serverda QAYTA hisoblaymiz: ochiq sahifadan
kelgan summa ishonchli emas, agent esa xabardagi raqam bilan vrachga boradi.
Qoidalar o'zgarsa — ikkala joyni ham o'zgartiring.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from html import escape

CBCT_PRICE = 40_000
DOWN_MIN = 10_000
N_MIN, N_MAX = 100, 2_000
TERM_MIN, TERM_MAX = 6, 14
PRICES = (45, 48, 49)


class PaketXato(ValueError):
    """Vrachga ko'rsatiladigan o'zbekcha sabab."""


def floor_price(n: int) -> int:
    """Soniga qarab eng past narx: 100–199 → $49, 200–300 → $48, 301+ → $45."""
    if n >= 301:
        return 45
    if n >= 200:
        return 48
    return 49


@dataclass(frozen=True)
class Paket:
    n: int
    price: int
    down: int
    term: int
    impl_sum: int
    total: int
    mon: int
    last: int


def paket(n: int, price: int, down: int, term: int) -> Paket:
    if not N_MIN <= n <= N_MAX:
        raise PaketXato(f"Implant soni {N_MIN} dan {N_MAX} gacha bo'lishi kerak.")
    if not TERM_MIN <= term <= TERM_MAX:
        raise PaketXato(f"Muddat {TERM_MIN} dan {TERM_MAX} oygacha.")
    if price not in PRICES or price < floor_price(n):
        raise PaketXato(f"{n} ta implant uchun narx kamida ${floor_price(n)}.")
    impl_sum = n * price
    total = CBCT_PRICE + impl_sum
    # Har oy kamida $1 qolsin — sahifadagi surgich chegarasi bilan bir xil
    if not DOWN_MIN <= down <= total - term:
        raise PaketXato(f"Boshlang'ich to'lov ${DOWN_MIN:,} dan paket narxigacha.".replace(",", " "))
    rest = total - down
    mon = math.ceil(rest / term)
    last = rest - mon * (term - 1)
    return Paket(n, price, down, term, impl_sum, total, mon, last)


def _usd(x: float) -> str:
    return "$" + f"{round(x):,}".replace(",", " ")


def ariza_text(
    p: Paket,
    *,
    name: str,
    head: str,
    phone: str,
    addr: str,
    agent_name: str | None,
    roi: str,
) -> str:
    """Agent va direktorga boradigan xabar. Vrach yozgan hamma narsa escape qilinadi."""
    lines = [
        "🩻 <b>Yangi FinScan arizasi</b>",
        "",
        f"<b>{escape(name, quote=False)}</b>",
    ]
    if head:
        lines.append(f"Rahbar: {escape(head, quote=False)}")
    lines.append(f"Telefon: {escape(phone, quote=False)}")
    if addr:
        lines.append(f"Manzil: {escape(addr, quote=False)}")
    lines += [
        "",
        f"Paket: <b>{_usd(p.total)}</b> — {p.n} ta implant × ${p.price} + tomograf",
        f"Boshlang'ich: {_usd(p.down)}",
        f"Oyiga: {_usd(p.mon)} × {p.term} oy (oxirgi oy {_usd(p.last)})",
    ]
    if roi:
        lines += ["", f"<i>Vrach hisobi: {escape(roi, quote=False)}</i>"]
    lines += [
        "",
        f"Agent: {escape(agent_name, quote=False)}" if agent_name else "Agent: havolada yo'q (to'g'ridan-to'g'ri)",
        "",
        "📞 Bugun qo'ng'iroq qiling.",
    ]
    return "\n".join(lines)
