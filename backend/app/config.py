"""Настройки приложения из переменных окружения и файла .env в корне репозитория."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# app/config.py -> app -> backend -> корень репозитория
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    keitaro_url: str
    keitaro_api_key: str = Field(repr=False)  # не попадёт в repr/логи
    keitaro_user_agent: str = "keitaro-wrapper/0.1"
    keitaro_timeout: float = 20.0

    database_url: str = Field(repr=False)  # содержит пароль

    campaign_prefix: str = ""
    keitaro_domain_id: int = 1813
    keitaro_group_id: int = 10332
    keitaro_traffic_source_id: int = 836


@lru_cache
def get_settings() -> Settings:
    """Синглтон настроек: читается один раз за процесс."""
    return Settings()
