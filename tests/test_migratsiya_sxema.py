"""Migratsiya bilan model sxemasi mos kelishini tekshiradi.

Direktor tarif yaratganda 500 shundan chiqqan edi: `0006` da
`created_at` ustuni `server_default`siz yaratilgan, model esa qiymatni
bazadan kutadi. Toza bazada bu ko'rinmaydi, chunki `0001_initial`
jadvallarni `create_all` bilan yaratadi va default'ni o'zi qo'yadi.

Shuning uchun bu yerda migratsiya FAYLLARI matn sifatida tekshiriladi.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.models import Base

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations" / "versions"

#: Modelda `TimestampMixin` ishlatgan ustunlar — bazada default bo'lishi shart
DEFAULTLI_USTUNLAR = ("created_at", "updated_at")


def _migratsiya_fayllari() -> list[Path]:
    return sorted(p for p in MIGRATIONS.glob("*.py") if not p.name.startswith("_"))


def test_migratsiyalar_topildi():
    assert len(_migratsiya_fayllari()) >= 7


def _column_chaqiruvlari(fayl: Path):
    """Fayldagi barcha `sa.Column(...)` chaqiruvlarini AST orqali topadi.

    Regex ishlatmaymiz — ko'p qatorli e'lonlarni noto'g'ri kesadi.
    """
    daraxt = ast.parse(fayl.read_text())
    for tugun in ast.walk(daraxt):
        if not isinstance(tugun, ast.Call):
            continue
        fn = tugun.func
        if isinstance(fn, ast.Attribute) and fn.attr == "Column":
            yield tugun


@pytest.mark.parametrize("fayl", _migratsiya_fayllari(), ids=lambda p: p.stem)
def test_vaqt_ustunlarida_server_default_bor(fayl: Path):
    """Har bir created_at/updated_at ustuni default bilan yaratilsin."""
    for chaqiruv in _column_chaqiruvlari(fayl):
        if not chaqiruv.args:
            continue
        nom = chaqiruv.args[0]
        if not isinstance(nom, ast.Constant) or nom.value not in DEFAULTLI_USTUNLAR:
            continue

        kalitlar = {kw.arg for kw in chaqiruv.keywords}
        # nullable=True bo'lsa default shart emas
        majburiy = any(
            kw.arg == "nullable" and isinstance(kw.value, ast.Constant)
            and kw.value.value is False
            for kw in chaqiruv.keywords
        )
        if not majburiy:
            continue

        assert "server_default" in kalitlar, (
            f"{fayl.name}:{nom.lineno} — «{nom.value}» ustuni server_default'siz.\n"
            "Model TimestampMixin qiymatni bazadan kutadi, shuning uchun\n"
            "INSERT paytida NULL tushib 500 chiqadi."
        )


def test_timestampli_modellar_default_kutadi():
    """Bu testning asosini tasdiqlaymiz: model chindan ham bazadan kutadi."""
    tariffs = Base.metadata.tables["tariffs"]
    for ustun in DEFAULTLI_USTUNLAR:
        assert tariffs.c[ustun].server_default is not None
        assert not tariffs.c[ustun].nullable
