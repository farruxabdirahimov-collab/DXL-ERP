"""Muhit o'zgaruvchilaridan olinadigan sozlamalar."""

from __future__ import annotations

from datetime import time
from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_hhmm(value: str) -> time:
    hh, _, mm = value.strip().partition(":")
    return time(hour=int(hh), minute=int(mm or 0))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot_token: str = ""
    #: @BotFather dagi bot username (masalan "dxl_erp_bot"). Bo'sh bo'lsa avtomatik aniqlanadi.
    bot_username: str = ""
    webhook_secret: str = "dxl-erp-secret"
    webapp_url: str = "http://localhost:5173"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/dxl_erp"

    superadmin_telegram_id: int = 0

    tz: str = "Asia/Tashkent"
    default_usd_uzs: float = 12500.0

    daily_report_time: str = "21:00"
    morning_reminder_time: str = "09:00"

    log_level: str = "INFO"
    auto_migrate: bool = True
    seed_demo: bool = False

    api_prefix: str = "/api"
    web_dist: str = Field(default="web/dist", description="Yig'ilgan Mini App papkasi")

    @field_validator("database_url")
    @classmethod
    def _normalize_db_url(cls, v: str) -> str:
        """Railway `postgresql://` beradi — asyncpg drayveriga o'tkazamiz."""
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql://", 1)
        if v.startswith("postgresql://"):
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @field_validator("webapp_url")
    @classmethod
    def _strip_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.tz)

    @property
    def report_time(self) -> time:
        return _parse_hhmm(self.daily_report_time)

    @property
    def reminder_time(self) -> time:
        return _parse_hhmm(self.morning_reminder_time)

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
