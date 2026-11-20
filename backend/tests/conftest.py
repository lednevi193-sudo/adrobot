"""Общая настройка тестов: изоляция от локального .env разработчика.

Settings читает .env из корня репозитория. Тесты не должны от него зависеть
(чистая машина, CI) и не должны видеть настоящий KEITARO_URL/ключ — поэтому
окружение для настроек задаётся здесь, а .env отключается.
"""

import os

import pytest

from app.config import Settings, get_settings

TEST_ENV = {
    "KEITARO_URL": "https://keitaro.test",
    "KEITARO_API_KEY": "test-key",
    "DATABASE_URL": "postgresql+psycopg://unused@127.0.0.1:1/unused",
    "CAMPAIGN_PREFIX": "test_x_",
}


@pytest.fixture(autouse=True, scope="session")
def _isolated_settings() -> None:
    Settings.model_config["env_file"] = None
    for key, value in TEST_ENV.items():
        os.environ[key] = value
    get_settings.cache_clear()
