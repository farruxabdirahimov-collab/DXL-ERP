"""API routerlarini bitta joyda yig'amiz."""

from fastapi import APIRouter

from app.api import (
    admin,
    catalog,
    content,
    contracts,
    doctors,
    finance,
    me,
    orders,
    plans,
    reports,
    stock,
    tasks,
    visits,
)

api_router = APIRouter()
api_router.include_router(me.router)
api_router.include_router(catalog.router)
api_router.include_router(content.router)
api_router.include_router(contracts.router)
api_router.include_router(stock.router)
api_router.include_router(doctors.router)
api_router.include_router(orders.router)
api_router.include_router(finance.router)
api_router.include_router(reports.router)
api_router.include_router(plans.router)
api_router.include_router(visits.router)
api_router.include_router(tasks.router)
api_router.include_router(admin.router)

__all__ = ["api_router"]
