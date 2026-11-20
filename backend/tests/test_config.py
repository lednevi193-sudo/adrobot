"""Настройки: CAMPAIGN_PREFIX обязателен и не может остаться плейсхолдером (NFR-4)."""

import pytest
from pydantic import ValidationError

from app.config import Settings

BASE = {"keitaro_url": "https://keitaro.test", "keitaro_api_key": "k", "database_url": "postgresql+psycopg://x"}


@pytest.mark.parametrize("prefix", ["", "   ", "test_<фамилия>_"])
def test_prefix_must_be_real(prefix: str) -> None:
    with pytest.raises(ValidationError, match="CAMPAIGN_PREFIX"):
        Settings(_env_file=None, **BASE, campaign_prefix=prefix)


def test_prefix_is_trimmed() -> None:
    assert Settings(_env_file=None, **BASE, campaign_prefix=" test_ivanov_ ").campaign_prefix == "test_ivanov_"


def test_cache_and_lease_defaults_and_validation() -> None:
    settings = Settings(_env_file=None, **BASE, campaign_prefix='test_x_')
    assert settings.keitaro_offers_ttl == 60
    assert settings.push_lease_minutes == 5
    assert Settings(_env_file=None, **BASE, campaign_prefix='test_x_', keitaro_offers_ttl=0).keitaro_offers_ttl == 0
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **BASE, campaign_prefix='test_x_', keitaro_offers_ttl=-1)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **BASE, campaign_prefix='test_x_', push_lease_minutes=0)
    with pytest.raises(ValidationError, match='KEITARO_TIMEOUT'):
        Settings(_env_file=None, **BASE, campaign_prefix='test_x_', push_lease_minutes=0.01)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **BASE, campaign_prefix='test_x_', keitaro_timeout=0)
