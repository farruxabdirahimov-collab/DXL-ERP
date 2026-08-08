"""Rollar va ruxsatlar matritsasi.

Backend endpointlarni shu ro'yxat bilan himoyalaydi, frontend esa
menyuni shunga qarab chizadi — ikkalasi bitta manbadan oziqlanadi.
"""

from __future__ import annotations

from app.models import Role

# Ruxsat kalitlari
DASHBOARD = "dashboard"
PRODUCTS_VIEW = "products.view"
PRODUCTS_EDIT = "products.edit"
STOCK_VIEW = "stock.view"
STOCK_EDIT = "stock.edit"
DOCTORS_VIEW = "doctors.view"
DOCTORS_EDIT = "doctors.edit"
DOCTORS_ALL = "doctors.all"          # o'ziniki emas, hammasini ko'rish
ORDERS_VIEW = "orders.view"
ORDERS_CREATE = "orders.create"
ORDERS_APPROVE = "orders.approve"
ORDERS_DIRECTOR = "orders.director"  # limitdan ortiq chegirma/qarzni tasdiqlash
ORDERS_FULFILL = "orders.fulfill"    # yig'ish/jo'natish/yetkazish
PAYMENTS_VIEW = "payments.view"
PAYMENTS_CREATE = "payments.create"
FX_EDIT = "fx.edit"
RETURNS_CREATE = "returns.create"
REPORTS_VIEW = "reports.view"
REPORTS_FINANCE = "reports.finance"
PLANS_VIEW = "plans.view"
PLANS_EDIT = "plans.edit"
VISITS_OWN = "visits.own"
VISITS_ALL = "visits.all"
TASKS_OWN = "tasks.own"
USERS_MANAGE = "users.manage"
SETTINGS_MANAGE = "settings.manage"
AUDIT_VIEW = "audit.view"

_READ_ONLY_MANAGEMENT = {
    DASHBOARD,
    PRODUCTS_VIEW,
    STOCK_VIEW,
    DOCTORS_VIEW,
    DOCTORS_ALL,
    ORDERS_VIEW,
    PAYMENTS_VIEW,
    REPORTS_VIEW,
    REPORTS_FINANCE,
    PLANS_VIEW,
    VISITS_ALL,
}

PERMISSIONS: dict[Role, set[str]] = {
    Role.SUPERADMIN: {
        DASHBOARD, PRODUCTS_VIEW, PRODUCTS_EDIT, STOCK_VIEW, STOCK_EDIT,
        DOCTORS_VIEW, DOCTORS_EDIT, DOCTORS_ALL, ORDERS_VIEW, ORDERS_CREATE,
        ORDERS_APPROVE, ORDERS_DIRECTOR, ORDERS_FULFILL, PAYMENTS_VIEW,
        PAYMENTS_CREATE, FX_EDIT, RETURNS_CREATE, REPORTS_VIEW, REPORTS_FINANCE,
        PLANS_VIEW, PLANS_EDIT, VISITS_ALL, TASKS_OWN, USERS_MANAGE,
        SETTINGS_MANAGE, AUDIT_VIEW,
    },
    Role.DIRECTOR: {
        DASHBOARD, PRODUCTS_VIEW, PRODUCTS_EDIT, STOCK_VIEW, STOCK_EDIT,
        DOCTORS_VIEW, DOCTORS_EDIT, DOCTORS_ALL, ORDERS_VIEW, ORDERS_CREATE,
        ORDERS_APPROVE, ORDERS_DIRECTOR, ORDERS_FULFILL, PAYMENTS_VIEW,
        PAYMENTS_CREATE, FX_EDIT, RETURNS_CREATE, REPORTS_VIEW, REPORTS_FINANCE,
        PLANS_VIEW, PLANS_EDIT, VISITS_ALL, TASKS_OWN, USERS_MANAGE,
        SETTINGS_MANAGE, AUDIT_VIEW,
    },
    Role.FOUNDER: set(_READ_ONLY_MANAGEMENT),
    Role.ACCOUNTANT: {
        DASHBOARD, PRODUCTS_VIEW, STOCK_VIEW, DOCTORS_VIEW, DOCTORS_ALL,
        DOCTORS_EDIT, ORDERS_VIEW, PAYMENTS_VIEW, PAYMENTS_CREATE, FX_EDIT,
        RETURNS_CREATE, REPORTS_VIEW, REPORTS_FINANCE, TASKS_OWN,
    },
    Role.WAREHOUSE: {
        DASHBOARD, PRODUCTS_VIEW, PRODUCTS_EDIT, STOCK_VIEW, STOCK_EDIT,
        ORDERS_VIEW, ORDERS_FULFILL, RETURNS_CREATE, REPORTS_VIEW, TASKS_OWN,
    },
    Role.AGENT: {
        DASHBOARD, PRODUCTS_VIEW, STOCK_VIEW, DOCTORS_VIEW, DOCTORS_EDIT,
        ORDERS_VIEW, ORDERS_CREATE, ORDERS_APPROVE, PAYMENTS_VIEW,
        PAYMENTS_CREATE, REPORTS_VIEW, PLANS_VIEW, VISITS_OWN, TASKS_OWN,
    },
    Role.DOCTOR: {
        PRODUCTS_VIEW, STOCK_VIEW, ORDERS_VIEW, ORDERS_CREATE, PAYMENTS_VIEW,
    },
}


def permissions_for(role: Role) -> list[str]:
    return sorted(PERMISSIONS.get(role, set()))


def can(role: Role, permission: str) -> bool:
    return permission in PERMISSIONS.get(role, set())
