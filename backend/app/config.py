"""Настройки приложения из переменных окружения и файла .env в корне репозитория."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# app/config.py -> app -> backend -> корень репозитория
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    keitaro_url: str
    keitaro_api_key: str = Field(repr=False)  # не попадёт в repr/логи
    keitaro_user_agent: str = "keitaro-wrapper/0.1"
    keitaro_timeout: float = Field(default=20.0, gt=0)
    keitaro_offers_ttl: float = Field(default=60.0, ge=0)
    push_lease_minutes: float = Field(default=5.0, gt=0)

    database_url: str = Field(repr=False)  # содержит пароль

    # Префикс «наших» кампаний на общем стенде (NFR-4, Q5). Обязателен: без него редактор
    # не видит ни одной своей кампании, а создаватор плодил бы кампании без признака «наша».
    campaign_prefix: str
    keitaro_domain_id: int = 1813
    keitaro_group_id: int = 10332
    keitaro_traffic_source_id: int = 836

    @model_validator(mode="after")
    def _push_window(self) -> "Settings":
        if self.push_lease_minutes * 60 <= 4 * self.keitaro_timeout:
            raise ValueError("PUSH_LEASE_MINUTES должен покрывать более четырёх KEITARO_TIMEOUT")
        return self

    @field_validator("campaign_prefix")
    @classmethod
    def _real_prefix(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("CAMPAIGN_PREFIX не задан: укажите префикс своих кампаний, например test_ivanov_")
        if any(ch in value for ch in "<> "):
            raise ValueError(f"CAMPAIGN_PREFIX={value!r} похож на плейсхолдер из .env.example: замените его своим")
        return value


@lru_cache
def get_settings() -> Settings:
    """Синглтон настроек: читается один раз за процесс."""
    return Settings()
