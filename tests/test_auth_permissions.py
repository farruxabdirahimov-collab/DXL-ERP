"""Telegram imzosi va rol huquqlari."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest

from app.auth import TelegramAuthError, verify_init_data
from app.models import Role
from app.permissions import (
    AUDIT_VIEW,
    DOCTORS_ALL,
    FX_EDIT,
    ORDERS_CREATE,
    ORDERS_DIRECTOR,
    PAYMENTS_CREATE,
    PRODUCTS_EDIT,
    SETTINGS_MANAGE,
    STOCK_EDIT,
    USERS_MANAGE,
    can,
    permissions_for,
)

BOT_TOKEN = "123456:TEST-TOKEN"


def _sign(payload: dict, token: str = BOT_TOKEN) -> str:
    data_check = "\n".join(f"{k}={payload[k]}" for k in sorted(payload))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    signature = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    return urlencode({**payload, "hash": signature})


def _payload(**overrides) -> dict:
    base = {
        "auth_date": str(int(time.time())),
        "query_id": "AAA",
        "user": json.dumps({"id": 777, "first_name": "Aziz", "username": "aziz"}),
    }
    base.update(overrides)
    return base


def test_togri_imzo_qabul_qilinadi():
    user = verify_init_data(_sign(_payload()), BOT_TOKEN)
    assert user["id"] == 777
    assert user["username"] == "aziz"


def test_soxta_imzo_rad_etiladi():
    init_data = _sign(_payload())
    buzilgan = init_data.replace("hash=", "hash=0")
    with pytest.raises(TelegramAuthError, match="imzo"):
        verify_init_data(buzilgan, BOT_TOKEN)


def test_boshqa_token_bilan_imzolangan_data_rad_etiladi():
    init_data = _sign(_payload(), token="999:OTHER")
    with pytest.raises(TelegramAuthError, match="imzo"):
        verify_init_data(init_data, BOT_TOKEN)


def test_ozgartirilgan_foydalanuvchi_rad_etiladi():
    """Kimdir user maydonini almashtirsa imzo mos kelmaydi."""
    payload = _payload()
    init_data = _sign(payload)
    soxta = init_data.replace("777", "1")
    with pytest.raises(TelegramAuthError):
        verify_init_data(soxta, BOT_TOKEN)


def test_eskirgan_init_data_rad_etiladi():
    old = str(int(time.time()) - 60 * 60 * 48)  # 48 soat oldin
    with pytest.raises(TelegramAuthError, match="muddati"):
        verify_init_data(_sign(_payload(auth_date=old)), BOT_TOKEN)


def test_bosh_init_data_rad_etiladi():
    with pytest.raises(TelegramAuthError):
        verify_init_data("", BOT_TOKEN)


def test_hashsiz_data_rad_etiladi():
    with pytest.raises(TelegramAuthError, match="hash"):
        verify_init_data(urlencode(_payload()), BOT_TOKEN)


# --------------------------------------------------------------- huquqlar
def test_tasischi_hech_narsani_ozgartira_olmaydi():
    founder = permissions_for(Role.FOUNDER)
    yozuv_huquqlari = {
        PRODUCTS_EDIT,
        STOCK_EDIT,
        ORDERS_CREATE,
        ORDERS_DIRECTOR,
        PAYMENTS_CREATE,
        USERS_MANAGE,
        SETTINGS_MANAGE,
        FX_EDIT,
    }
    assert yozuv_huquqlari.isdisjoint(founder)
    # Lekin hamma hisobotni ko'ra oladi
    assert can(Role.FOUNDER, "reports.finance")
    assert can(Role.FOUNDER, DOCTORS_ALL)


def test_agent_boshqa_agentlarning_vrachlarini_kormaydi():
    assert not can(Role.AGENT, DOCTORS_ALL)
    assert can(Role.AGENT, "doctors.view")


def test_agent_direktor_tasdigini_bera_olmaydi():
    assert can(Role.AGENT, "orders.approve")
    assert not can(Role.AGENT, ORDERS_DIRECTOR)


def test_omborchi_moliyaga_kira_olmaydi():
    assert not can(Role.WAREHOUSE, PAYMENTS_CREATE)
    assert not can(Role.WAREHOUSE, "reports.finance")
    assert can(Role.WAREHOUSE, STOCK_EDIT)


def test_buxgalter_omborni_ozgartira_olmaydi():
    assert not can(Role.ACCOUNTANT, STOCK_EDIT)
    assert not can(Role.ACCOUNTANT, PRODUCTS_EDIT)
    assert can(Role.ACCOUNTANT, PAYMENTS_CREATE)
    assert can(Role.ACCOUNTANT, FX_EDIT)


def test_vrach_faqat_ozining_bolimlarini_koradi():
    doctor = set(permissions_for(Role.DOCTOR))
    assert doctor == {
        "products.view",
        "stock.view",
        "orders.view",
        "orders.create",
        "payments.view",
    }


def test_audit_faqat_rahbariyatga():
    assert can(Role.SUPERADMIN, AUDIT_VIEW)
    assert can(Role.DIRECTOR, AUDIT_VIEW)
    for role in (Role.FOUNDER, Role.ACCOUNTANT, Role.WAREHOUSE, Role.AGENT, Role.DOCTOR):
        assert not can(role, AUDIT_VIEW)


def test_foydalanuvchi_boshqaruvi_faqat_admin_rollarda():
    for role in Role:
        expected = role in (Role.SUPERADMIN, Role.DIRECTOR)
        assert can(role, USERS_MANAGE) is expected
