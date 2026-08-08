"""Vaqt bo'yicha ishlaydigan vazifalar (Asia/Tashkent)."""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.jobs.daily_report import send_daily_reports
from app.jobs.reminders import (
    run_daily_fx_check,
    run_monthly_close,
    run_morning_reminders,
    run_nightly_recalc,
)

log = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def start_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    tz = settings.timezone
    scheduler = AsyncIOScheduler(timezone=tz)

    report_time = settings.report_time
    scheduler.add_job(
        send_daily_reports,
        CronTrigger(hour=report_time.hour, minute=report_time.minute, timezone=tz),
        id="daily_report",
        name="Kunlik statistika (21:00)",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    reminder_time = settings.reminder_time
    scheduler.add_job(
        run_morning_reminders,
        CronTrigger(hour=reminder_time.hour, minute=reminder_time.minute, timezone=tz),
        id="morning_reminders",
        name="Ertalabki eslatmalar (09:00)",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    fx_total = reminder_time.hour * 60 + reminder_time.minute + 5
    scheduler.add_job(
        run_daily_fx_check,
        CronTrigger(hour=(fx_total // 60) % 24, minute=fx_total % 60, timezone=tz),
        id="fx_check",
        name="Kurs kiritilganini tekshirish",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    scheduler.add_job(
        run_nightly_recalc,
        CronTrigger(hour=2, minute=0, timezone=tz),
        id="nightly_recalc",
        name="Sodiqlik va toifalarni qayta hisoblash (02:00)",
        replace_existing=True,
        misfire_grace_time=7200,
    )

    scheduler.add_job(
        run_monthly_close,
        CronTrigger(day=1, hour=9, minute=0, timezone=tz),
        id="monthly_close",
        name="Oylik yakun (har oy 1-sana)",
        replace_existing=True,
        misfire_grace_time=7200,
    )

    scheduler.start()
    _scheduler = scheduler
    for job in scheduler.get_jobs():
        log.info("Job: %s — keyingi ishga tushish: %s", job.name, job.next_run_time)
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
