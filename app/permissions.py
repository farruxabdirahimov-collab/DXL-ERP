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
CONTENT_VIEW = "content.view"      # maqola/video ko'rish
CONTENT_MANAGE = "content.manage"  # material joylash va tahrirlash
BROADCAST_SEND = "broadcast.send"  # rassilka yuborish
TARIFFS_MANAGE = "tariffs.manage"      # tarif yaratish/tahrirlash — direktor
CONTRACTS_VIEW = "contracts.view"      # shartnomalarni ko'rish
CONTRACTS_CREATE = "contracts.create"  # vrach bilan shartnoma tuzish
GIFTS_ISSUE = "gifts.issue"            # qozonilgan sovg'ani berish

_READ_ONLY_MANAGEMENT = {
    DASHBOARD,
    CONTRACTS_VIEW,
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
    CONTENT_VIEW,
}

PERMISSIONS: dict[Role, set[str]] = {
    Role.SUPERADMIN: {
        DASHBOARD, PRODUCTS_VIEW, PRODUCTS_EDIT, STOCK_VIEW, STOCK_EDIT,
        DOCTORS_VIEW, DOCTORS_EDIT, DOCTORS_ALL, ORDERS_VIEW, ORDERS_CREATE,
        ORDERS_APPROVE, ORDERS_DIRECTOR, ORDERS_FULFILL, PAYMENTS_VIEW,
        PAYMENTS_CREATE, FX_EDIT, RETURNS_CREATE, REPORTS_VIEW, REPORTS_FINANCE,
        PLANS_VIEW, PLANS_EDIT, VISITS_ALL, TASKS_OWN, USERS_MANAGE,
        SETTINGS_MANAGE, AUDIT_VIEW, CONTENT_VIEW, CONTENT_MANAGE, BROADCAST_SEND,
        TARIFFS_MANAGE, CONTRACTS_VIEW, CONTRACTS_CREATE, GIFTS_ISSUE,
    },
    Role.DIRECTOR: {
        DASHBOARD, PRODUCTS_VIEW, PRODUCTS_EDIT, STOCK_VIEW, STOCK_EDIT,
        DOCTORS_VIEW, DOCTORS_EDIT, DOCTORS_ALL, ORDERS_VIEW, ORDERS_CREATE,
        ORDERS_APPROVE, ORDERS_DIRECTOR, ORDERS_FULFILL, PAYMENTS_VIEW,
        PAYMENTS_CREATE, FX_EDIT, RETURNS_CREATE, REPORTS_VIEW, REPORTS_FINANCE,
        PLANS_VIEW, PLANS_EDIT, VISITS_ALL, TASKS_OWN, USERS_MANAGE,
        SETTINGS_MANAGE, AUDIT_VIEW, CONTENT_VIEW, CONTENT_MANAGE, BROADCAST_SEND,
        TARIFFS_MANAGE, CONTRACTS_VIEW, CONTRACTS_CREATE, GIFTS_ISSUE,
    },
    Role.FOUNDER: set(_READ_ONLY_MANAGEMENT),
    Role.ACCOUNTANT: {
        DASHBOARD, PRODUCTS_VIEW, STOCK_VIEW, DOCTORS_VIEW, DOCTORS_ALL,
        DOCTORS_EDIT, ORDERS_VIEW, PAYMENTS_VIEW, PAYMENTS_CREATE, FX_EDIT,
        RETURNS_CREATE, REPORTS_VIEW, REPORTS_FINANCE, TASKS_OWN, CONTENT_VIEW,
        CONTRACTS_VIEW,
    },
    Role.WAREHOUSE: {
        DASHBOARD, PRODUCTS_VIEW, PRODUCTS_EDIT, STOCK_VIEW, STOCK_EDIT,
        ORDERS_VIEW, ORDERS_FULFILL, RETURNS_CREATE, REPORTS_VIEW, TASKS_OWN,
        CONTENT_VIEW, CONTRACTS_VIEW, GIFTS_ISSUE,
    },
    Role.AGENT: {
        DASHBOARD, PRODUCTS_VIEW, STOCK_VIEW, DOCTORS_VIEW, DOCTORS_EDIT,
        ORDERS_VIEW, ORDERS_CREATE, ORDERS_APPROVE, PAYMENTS_VIEW,
        PAYMENTS_CREATE, RETURNS_CREATE, REPORTS_VIEW, PLANS_VIEW, VISITS_OWN,
        TASKS_OWN, CONTENT_VIEW, CONTENT_MANAGE, BROADCAST_SEND,
        CONTRACTS_VIEW, CONTRACTS_CREATE,
    },
    Role.DOCTOR: {
        PRODUCTS_VIEW, STOCK_VIEW, ORDERS_VIEW, ORDERS_CREATE, PAYMENTS_VIEW,
        CONTENT_VIEW, CONTRACTS_VIEW,
    },
}


def permissions_for(role: Role) -> list[str]:
    return sorted(PERMISSIONS.get(role, set()))


def can(role: Role, permission: str) -> bool:
    return permission in PERMISSIONS.get(role, set())


def effective_permissions(user) -> set[str]:
    """Asosiy rol + qo'shimcha rollar ruxsatlarining birlashmasi."""
    result = set(PERMISSIONS.get(user.role, set()))
    for raw in user.extra_roles or []:
        try:
            result |= PERMISSIONS.get(Role(raw), set())
        except ValueError:  # noma'lum rol saqlanib qolgan bo'lsa
            continue
    return result


def user_can(user, permission: str) -> bool:
    return permission in effective_permissions(user)


def agent_scope(user) -> int | None:
    """Buyurtmalarni faqat o'ziniki bilan cheklash kerakmi? Kerak bo'lsa — ID.

    Agent bir vaqtda omborchi ham bo'lsa (ORDERS_FULFILL bor), u boshqalarning
    buyurtmalarini ham ko'rishi shart — aks holda yig'a olmaydi.
    """
    if user.role is not Role.AGENT:
        return None
    if user_can(user, ORDERS_FULFILL) or user_can(user, DOCTORS_ALL):
        return None
    return user.id


def doctor_scope(user) -> int | None:
    """Vrachlar ro'yxatini cheklash kerakmi? Qo'shimcha rol bunga ta'sir qilmaydi."""
    if user.role is Role.AGENT and not user_can(user, DOCTORS_ALL):
        return user.id
    return None
